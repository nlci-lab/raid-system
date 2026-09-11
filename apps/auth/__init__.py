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

import requests
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from apps.audit import log_action
from apps.levels import ANONYMOUS_LEVEL, current_level, tier
from apps.config import (
    BREVO_API_KEY,
    BREVO_FROM_EMAIL,
    BREVO_FROM_NAME,
    DEV_BYPASS_CODE,
    DEV_SKIP_OTP,
    SMTP_EMAIL,
    SMTP_PASSCODE,
)
from apps.db import USERS_DB

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
    "password_hash": "TEXT",
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
    """Send an email via Gmail SMTP.

    Local-dev mail transport, used whenever BREVO_API_KEY isn't configured
    (i.e. the local pass_raid_system.txt has no brevo_* keys). Outbound SMTP
    (port 465/587) is blocked at the network level on raid-server, so
    production never falls through to this — it always has BREVO_API_KEY
    set and uses _send_via_brevo below instead. This function must stay
    correct for local dev, but should never be the active path in production.
    """
    msg = MIMEText(text)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
        server.login(SMTP_EMAIL, SMTP_PASSCODE)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())


BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _send_via_brevo(to_email, subject, text):
    """Send an email via Brevo's transactional HTTP API.

    This is production's mail transport. Outbound SMTP (port 465/587) is
    blocked at the network level on raid-server, so delivery goes over
    HTTPS (port 443) via Brevo's API instead. Do not add an smtplib/SMTP_SSL
    fallback *inside this function* — it will silently fail/timeout in
    production. (The module-level fallback to _send_via_smtp when
    BREVO_API_KEY isn't configured, in _send_otp_email/_send_welcome_email
    below, is what makes local dev work without Brevo — that's a separate,
    deliberate mechanism, not a change to this function.)
    """
    if not BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY is not configured")

    payload = {
        "sender": {"name": BREVO_FROM_NAME, "email": BREVO_FROM_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
    }
    resp = requests.post(
        BREVO_API_URL,
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=10,
    )
    if resp.status_code != 201:
        raise RuntimeError(f"Brevo API send failed ({resp.status_code}): {resp.text}")


def _send_mail(to_email, subject, text):
    """Single entry point every route below calls. Uses Brevo when
    BREVO_API_KEY is configured (production), otherwise falls back to local
    Gmail SMTP (local dev, where outbound SMTP isn't network-blocked)."""
    if BREVO_API_KEY:
        _send_via_brevo(to_email, subject, text)
    else:
        _send_via_smtp(to_email, subject, text)


def _send_otp_email(to_email, code):
    _send_mail(
        to_email,
        "Your RAIDsystem login code",
        f"Your RAIDsystem verification code is: {code}\n\n"
        f"This code expires in {OTP_TTL_SECONDS // 60} minutes. "
        "If you did not request this, you can ignore this email.",
    )


def _send_welcome_email(to_email):
    _send_mail(
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
    # Bounce a real logged-in user back home — but not someone sitting at
    # the anonymous tier (e.g. from the home page's "Sign in" button for
    # anonymous-tier sessions), and not someone whose level can't be
    # resolved at all (current_level() returning None — an edge case, but
    # tier() crashes on None, so it must be checked before calling it).
    # Without this exception, that button would send an anonymous-tier
    # visitor to /login only to be redirected straight back home, looking
    # like it does nothing (found 2026-09-11).
    level = current_level()
    if session.get("logged_in") and level is not None and tier(level) != ANONYMOUS_LEVEL:
        return redirect(url_for("hello"))

    if request.method == "POST":
        raw_input = request.form.get("email", "").strip()
        email = raw_input.lower()

        # DEV_BYPASS_CODE branch — typed into the email field in place of an
        # address, logs straight in as DEV_BYPASS_EMAIL for local/AI testing.
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

        # DEV_SKIP_OTP branch — env-var gated (must be explicitly exported
        # before starting the app, never just present in a config file), so
        # it can never turn on silently. Bypasses OTP entirely for any
        # @nlife.in address. Distinct from the DEV_BYPASS_CODE branch above
        # (which requires typing a specific magic code into the email
        # field); this one activates for real-looking @nlife.in addresses.
        if DEV_SKIP_OTP and email.endswith(f"@{ALLOWED_DOMAIN}"):
            logging.getLogger(__name__).warning(
                "DEV_SKIP_OTP active — bypassing OTP for %s", email
            )
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

        # Look up user and check password.
        conn = sqlite3.connect(USERS_DB)
        try:
            _ensure_user_detail_columns(conn)
            user_row = conn.execute(
                "SELECT id, password_hash FROM users WHERE lower(email) = ?", (email,)
            ).fetchone()
        finally:
            conn.close()

        password = request.form.get("password", "").strip()

        # Send an OTP to set/reset the password if: the user doesn't exist
        # yet, they have no password_hash yet (first-time setup), OR they
        # left the password field blank (even with an existing password —
        # this makes blank-password on the main form double as "forgot
        # password" for any account state, not just brand-new ones).
        if user_row is None or not user_row[1] or not password:
            existing = _otp_store.get(email)
            if existing and time.time() - existing["sent_at"] < OTP_RESEND_COOLDOWN:
                flash("A code was already sent. Please wait a moment before requesting another.", "error")
                session["pending_email"] = email
                session["otp_purpose"] = "set_password"
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
            session["otp_purpose"] = "set_password"
            flash("We don't have a password on file for you yet — enter the code we just emailed you to set one.", "info")
            return redirect(url_for("auth.verify"))

        # User exists and has a password — validate it.
        if not check_password_hash(user_row[1], password):
            flash("Incorrect email or password.", "error")
            return render_template("login.html", email=email)

        # Password is correct — log them in.
        _record_login(email)
        session["logged_in"] = True
        session["user_email"] = email
        flash("Logged in successfully.", "info")
        return redirect(url_for("hello"))

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
            session.pop("otp_purpose", None)
            flash("That code has expired. Please request a new one.", "error")
            return redirect(url_for("auth.login"))

        if _hash_otp(email, code) != entry["hash"]:
            entry["attempts"] += 1
            if entry["attempts"] >= MAX_ATTEMPTS:
                _otp_store.pop(email, None)
                session.pop("pending_email", None)
                session.pop("otp_purpose", None)
                flash("Too many incorrect attempts. Please request a new code.", "error")
                return redirect(url_for("auth.login"))
            flash("Incorrect code. Please try again.", "error")
            return render_template("verify_otp.html", email=email)

        # OTP verified — set otp_verified_email and redirect to set-password.
        _otp_store.pop(email, None)
        session.pop("pending_email", None)
        session["otp_verified_email"] = email
        return redirect(url_for("auth.set_password"))

    return render_template("verify_otp.html", email=email)


@auth.route("/login/set-password", methods=["GET", "POST"])
def set_password():
    email = session.get("otp_verified_email")
    if not email:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not password or not confirm:
            flash("Please enter and confirm your password.", "error")
            return render_template("set_password.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("set_password.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("set_password.html")

        # Hash and store the password.
        password_hash = generate_password_hash(password)
        conn = sqlite3.connect(USERS_DB)
        try:
            _ensure_user_detail_columns(conn)
            is_new_user = _register_user(email)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE lower(email) = ?",
                (password_hash, email),
            )
            conn.commit()
        finally:
            conn.close()

        # Log them in first so the audit entry below attributes correctly.
        session["logged_in"] = True
        session["user_email"] = email
        session.pop("otp_verified_email", None)
        session.pop("otp_purpose", None)

        # Log the action.
        log_action("auth", "password_set", f"Email: {email}")

        # If this wasn't a brand-new registration, record the login.
        if not is_new_user:
            _record_login(email)
        flash("Password set. You're now logged in.", "info")
        return redirect(url_for("hello"))

    return render_template("set_password.html")


@auth.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
