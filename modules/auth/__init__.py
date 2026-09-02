import hashlib
import logging
import re
import secrets
import smtplib
import sqlite3
import time
import traceback
from email.mime.text import MIMEText
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from modules.config import DEV_BYPASS_CODE, SMTP_EMAIL, SMTP_PASSCODE
from modules.db import USERS_DB

auth = Blueprint("auth", __name__, template_folder="templates")

ALLOWED_DOMAIN = "nlife.in"
DEV_BYPASS_EMAIL = f"ai-tester@{ALLOWED_DOMAIN}"
OTP_TTL_SECONDS = 5 * 60
OTP_RESEND_COOLDOWN = 30
MAX_ATTEMPTS = 5

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# email -> {"hash": str, "expires_at": float, "attempts": int, "sent_at": float}
_otp_store = {}


def _hash_otp(email, code):
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _name_from_email(email):
    local_part = email.split("@", 1)[0]
    return " ".join(part.capitalize() for part in local_part.replace(".", "_").split("_") if part)


_USER_DETAIL_COLUMNS = {
    "created_at": "TEXT",
    "last_login_at": "TEXT",
    "login_count": "INTEGER NOT NULL DEFAULT 0",
    "last_ip": "TEXT",
    "last_user_agent": "TEXT",
}


def _ensure_user_detail_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    for name, ddl_type in _USER_DETAIL_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl_type}")
    conn.commit()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _register_user(email):
    conn = sqlite3.connect(USERS_DB)
    try:
        _ensure_user_detail_columns(conn)
        row = conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone()
        if row is not None:
            return False
        name = _name_from_email(email)
        now = _now()
        ip = request.remote_addr
        level = 4.0 if email.endswith(f"@{ALLOWED_DOMAIN}") else 5.0
        user_agent = request.headers.get("User-Agent", "")
        params = (name, email, level, now, now, ip, user_agent)
        insert_sql = (
            "INSERT INTO users (name, email, level, created_at, last_login_at, login_count, last_ip, last_user_agent) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)"
        )
        try:
            conn.execute(insert_sql, params)
            conn.commit()
        except sqlite3.IntegrityError:
            conn.execute(insert_sql, (f"{name} ({email})", *params[1:]))
            conn.commit()
        return True
    finally:
        conn.close()


def _record_login(email):
    conn = sqlite3.connect(USERS_DB)
    try:
        _ensure_user_detail_columns(conn)
        conn.execute(
            "UPDATE users SET last_login_at = ?, login_count = COALESCE(login_count, 0) + 1, "
            "last_ip = ?, last_user_agent = ? WHERE lower(email) = ?",
            (_now(), request.remote_addr, request.headers.get("User-Agent", ""), email),
        )
        conn.commit()
    finally:
        conn.close()


def _is_allowed_email(email):
    return bool(EMAIL_RE.match(email))


def _send_via_smtp(to_email, subject, text):
    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(SMTP_EMAIL, SMTP_PASSCODE)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())


def _send_otp_email(to_email, code):
    _send_via_smtp(
        to_email,
        "Your RAIDsystem login code",
        f"Your RAIDsystem verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_SECONDS // 60} minutes. "
        "If you did not request this, you can ignore this email.",
    )


def _send_welcome_email(to_email):
    _send_via_smtp(
        to_email,
        "Welcome to RAIDsystem",
        f"Hi {_name_from_email(to_email)},\n\n"
        "Your RAIDsystem account has been created and you're now logged in. "
        "If you did not expect this, please contact an administrator.\n",
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("hello"))

    if request.method == "POST":
        raw_input = request.form.get("email", "").strip()
        email = raw_input.lower()

        if DEV_BYPASS_CODE and raw_input == DEV_BYPASS_CODE:
            logging.getLogger(__name__).warning(
                "DEV_BYPASS_CODE used — bypassing OTP login for AI/dev testing (%s)", DEV_BYPASS_EMAIL
            )
            email = DEV_BYPASS_EMAIL
            is_new_user = _register_user(email)
            if is_new_user:
                try:
                    _send_welcome_email(email)
                except Exception:
                    pass
            else:
                _record_login(email)
            session["logged_in"] = True
            session["user_email"] = email
            return render_template("dev_verify.html", email=email)

        if not _is_allowed_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("login.html", email=email)

        existing = _otp_store.get(email)
        if existing and time.time() - existing["sent_at"] < OTP_RESEND_COOLDOWN:
            flash("A code was already sent. Please wait a moment before requesting another.", "error")
            session["pending_email"] = email
            return redirect(url_for("auth.verify"))

        code = _generate_otp()
        _otp_store[email] = {
            "hash": _hash_otp(email, code),
            "expires_at": time.time() + OTP_TTL_SECONDS,
            "attempts": 0,
            "sent_at": time.time(),
        }

        try:
            _send_otp_email(email, code)
        except Exception:
            traceback.print_exc()
            logging.getLogger(__name__).exception("Failed to send OTP email to %s", email)
            _otp_store.pop(email, None)
            flash("Could not send the verification email. Please try again.", "error")
            return render_template("login.html", email=email)

        session["pending_email"] = email
        flash(f"A verification code was sent to {email}.", "info")
        return redirect(url_for("auth.verify"))

    return render_template("login.html")


@auth.route("/login/verify", methods=["GET", "POST"])
def verify():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        entry = _otp_store.get(email)

        if not entry or time.time() > entry["expires_at"]:
            _otp_store.pop(email, None)
            session.pop("pending_email", None)
            flash("That code has expired. Please request a new one.", "error")
            return redirect(url_for("auth.login"))

        if entry["attempts"] >= MAX_ATTEMPTS:
            _otp_store.pop(email, None)
            session.pop("pending_email", None)
            flash("Too many incorrect attempts. Please request a new code.", "error")
            return redirect(url_for("auth.login"))

        if _hash_otp(email, code) != entry["hash"]:
            entry["attempts"] += 1
            flash("Incorrect code. Please try again.", "error")
            return render_template("verify_otp.html", email=email)

        _otp_store.pop(email, None)
        session.pop("pending_email", None)
        is_new_user = _register_user(email)
        if is_new_user:
            try:
                _send_welcome_email(email)
            except Exception:
                pass
        else:
            _record_login(email)
        session["logged_in"] = True
        session["user_email"] = email
        flash("Logged in successfully.", "info")
        return redirect(url_for("hello"))

    return render_template("verify_otp.html", email=email)


@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
