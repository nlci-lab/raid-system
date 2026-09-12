import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from apps.access import access
from apps.ai_chat import ai_chat
from apps.ai_chat import is_bot_enabled as _ai_chat_is_bot_enabled
from apps.attendance import attendance
from apps.auth import auth
from apps.blog import blog
from apps.blog import get_conn as _blog_get_conn, get_name_map as _blog_get_name_map, read_post_body as _blog_read_post_body
from apps.chat import chat
from apps.config import SECRET_KEY
from apps.dashboard import dashboard
from apps.db import USERS_DB
from apps.guide import guide
from apps.ildb import ildb
from apps.levels import ANONYMOUS_LEVEL, SUB_LEVEL_LABELS, VIEWER_LEVEL, current_level, level_label, real_level, tier
from apps.library import get_conn as _library_get_conn, library

app = Flask(__name__)
app.secret_key = SECRET_KEY

APP_VERSION = (Path(__file__).parent / "VERSION").read_text().strip()


@app.context_processor
def inject_app_version():
    return {"app_version": APP_VERSION}


@app.context_processor
def inject_ai_bot_enabled():
    """Global RAID Bot on/off switch (set at /dashboard/raid-bot-dash) --
    checked here so base.html can hide the floating widget entirely when
    off, on top of send_message() itself refusing to respond either way."""
    return {"ai_bot_enabled": _ai_chat_is_bot_enabled()}

app.register_blueprint(auth)
app.register_blueprint(library)
app.register_blueprint(dashboard)
app.register_blueprint(chat)
app.register_blueprint(ai_chat)
app.register_blueprint(attendance)
app.register_blueprint(blog)
app.register_blueprint(ildb)
app.register_blueprint(access)
app.register_blueprint(guide)


@app.errorhandler(403)
def forbidden(e):
    flash("You are not allowed to access this section.", "error")
    return render_template("403.html"), 403


PUBLIC_ENDPOINTS = {None, "static", "hello"}

# A real dev "viewing as" anonymous (lvl-6) is still logged in underneath —
# exempt their own view-as control so they can always switch back, and
# otherwise route them through the same login wall a real anonymous visitor
# would hit on any non-public page.
VIEW_AS_ENDPOINT = "dashboard.set_view_as"


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint == VIEW_AS_ENDPOINT or request.endpoint.startswith("auth."):
        return
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))
    level = current_level()
    if level is not None and tier(level) == ANONYMOUS_LEVEL:
        return redirect(url_for("auth.login"))


# Every level a dev can pick in the view-as switcher: the whole tiers plus
# every defined sub-level, so simulating e.g. 1.1 (director) is possible too
# — not just its whole-number tier. Sorted numerically, which naturally
# groups each tier with its sub-levels right after it (0, 0.1, 0.2, ..., 1, 1.1, ...).
VIEW_AS_LEVELS = sorted({0.0, 1.0, 2.0, 3.0, 4.0, 5.0, ANONYMOUS_LEVEL, *SUB_LEVEL_LABELS})


@app.context_processor
def inject_level_nav():
    """Every page gets the current user's effective level in context — a
    badge for everyone (including anonymous visitors on public pages like
    the home page), plus (for a real, non-simulated dev) the data needed
    to render the view-as switcher. See templates/base.html. Always returns
    the full key set — base.html references nav_current_level
    unconditionally, so an anonymous/not-logged-in visit must still get a
    sensible default (ANONYMOUS_LEVEL) rather than an empty context, which
    previously crashed the public home page with a 500 (found live on
    raid-server 2026-09-11, hotfixed there, now ported back here)."""
    if not session.get("logged_in"):
        return {
            "nav_current_level": ANONYMOUS_LEVEL,
            "nav_real_level": ANONYMOUS_LEVEL,
            "nav_is_dev": False,
            "nav_viewing_as": False,
            "nav_level_label": level_label,
            "nav_view_as_levels": VIEW_AS_LEVELS,
        }
    r_level = real_level()
    if r_level is None:
        return {
            "nav_current_level": ANONYMOUS_LEVEL,
            "nav_real_level": ANONYMOUS_LEVEL,
            "nav_is_dev": False,
            "nav_viewing_as": False,
            "nav_level_label": level_label,
            "nav_view_as_levels": VIEW_AS_LEVELS,
        }
    return {
        "nav_current_level": current_level(),
        "nav_real_level": r_level,
        "nav_is_dev": tier(r_level) == 0.0,
        "nav_viewing_as": session.get("view_as_level") is not None,
        "nav_level_label": level_label,
        "nav_view_as_levels": VIEW_AS_LEVELS,
    }


def _time_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


@app.route("/")
def hello():
    level = current_level()
    if not session.get("logged_in") or level is None or tier(level) == ANONYMOUS_LEVEL:
        return render_template("index.html")

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name FROM users WHERE lower(email) = ?",
        (session.get("user_email", "").lower(),),
    ).fetchone()
    conn.close()

    blog_conn = _blog_get_conn()
    home_post_rows = blog_conn.execute(
        "SELECT id, author_email, title, filename, is_internal, created_at FROM posts ORDER BY created_at DESC LIMIT 3"
    ).fetchall()
    blog_conn.close()
    home_posts = []
    for post_row in home_post_rows:
        post = dict(post_row)
        post["body"] = _blog_read_post_body(post_row["filename"])
        home_posts.append(post)

    home_loans = []
    home_new_books = []
    home_new_people = []
    if row and tier(level) <= VIEWER_LEVEL:
        loans_conn = _library_get_conn()
        home_loans = loans_conn.execute(
            """
            SELECT books.title AS title, loans.taken_at AS issued_at
            FROM loans
            JOIN books ON books.id = loans.book_id
            WHERE loans.requested_by = ? AND loans.status = 'issued'
            ORDER BY loans.taken_at DESC
            """,
            (row["id"],),
        ).fetchall()
        home_new_books = loans_conn.execute(
            "SELECT id, title, author FROM books ORDER BY id DESC LIMIT 3"
        ).fetchall()
        people_rows = loans_conn.execute(
            "SELECT name, email, level FROM users.users WHERE email IS NOT NULL AND id != ? ORDER BY id DESC LIMIT 3",
            (row["id"],),
        ).fetchall()
        home_new_people = [
            {
                "name": p["name"] or p["email"],
                "email": p["email"],
                "role": level_label(p["level"]) if p["level"] is not None else "member",
            }
            for p in people_rows
        ]
        loans_conn.close()

    return render_template(
        "index.html",
        home_greeting=_time_greeting(),
        home_display_name=(row["name"] if row and row["name"] else session.get("user_email", "")),
        home_today=datetime.now().strftime("%A, %d %B %Y"),
        home_posts=home_posts,
        home_blog_names=_blog_get_name_map(),
        home_loans=home_loans,
        home_new_books=home_new_books,
        home_new_people=home_new_people,
    )


@app.route("/search")
def search():
    """Portal-wide quick search: blog posts (everyone logged in), library
    books and the user directory (viewer tier and above, same gate as the
    Library tile on the home page — external/lvl-5 doesn't get either)."""
    q = request.args.get("q", "").strip()
    level = current_level()
    if len(q) < 2 or level is None:
        return jsonify(posts=[], books=[], people=[])

    like = f"%{q}%"

    blog_conn = _blog_get_conn()
    post_rows = blog_conn.execute(
        "SELECT id, title FROM posts WHERE title LIKE ? ORDER BY created_at DESC LIMIT 5",
        (like,),
    ).fetchall()
    blog_conn.close()
    posts = [{"id": r["id"], "title": r["title"]} for r in post_rows]

    books = []
    people = []
    if tier(level) <= VIEWER_LEVEL:
        lib_conn = _library_get_conn()
        book_rows = lib_conn.execute(
            "SELECT id, title, author FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title LIMIT 5",
            (like, like),
        ).fetchall()
        books = [{"id": r["id"], "title": r["title"], "author": r["author"]} for r in book_rows]

        person_rows = lib_conn.execute(
            "SELECT name, email FROM users.users WHERE email IS NOT NULL AND (name LIKE ? OR email LIKE ?) ORDER BY name LIMIT 5",
            (like, like),
        ).fetchall()
        people = [{"name": r["name"], "email": r["email"]} for r in person_rows]
        lib_conn.close()

    return jsonify(posts=posts, books=books, people=people)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5057, debug=True)
