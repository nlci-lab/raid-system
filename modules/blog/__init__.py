import html
import re
import sqlite3
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from modules.audit import log_action
from modules.db import BLOG_DB, USERS_DB

blog = Blueprint("blog", __name__, template_folder="templates")

MANAGER_ROLES = ("admin", "data_manager")

SCHEMA = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_email TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        is_internal INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id),
        author_email TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS post_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id),
        filename TEXT NOT NULL,
        mimetype TEXT,
        size INTEGER NOT NULL,
        data BLOB NOT NULL
    );
"""

HEADER_RE = re.compile(r"^(#{1,3})\s+(.*)$")
LIST_ITEM_RE = re.compile(r"^[-*]\s+(.*)$")


def get_conn():
    """Connect to blog.db, creating the schema if the file is missing or empty."""
    conn = sqlite3.connect(BLOG_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def get_name_map():
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT name, email FROM users WHERE email IS NOT NULL").fetchall()
    conn.close()
    return {row["email"]: row["name"] for row in rows}


def _can_manage(email):
    if not email:
        return False
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT role FROM users WHERE lower(email) = ?", (email.lower(),)).fetchone()
    conn.close()
    return bool(row) and row["role"] in MANAGER_ROLES


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        email = session.get("user_email")
        if not email:
            flash("Please log in as an admin or data manager to create posts.", "error")
            return redirect(url_for("auth.login"))
        if not _can_manage(email):
            flash("You need admin or data manager access to create posts.", "error")
            return redirect(url_for("blog.index"))
        return view(*args, **kwargs)

    return wrapped


def now():
    return datetime.now().isoformat(timespec="seconds")


def _inline_format(text):
    """Apply inline markdown-lite formatting to already-escaped text."""
    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^\n]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^\n*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        text,
    )
    return text


def render_post_body(raw_text):
    """Render a small, safe markdown-lite subset (headings, bold/italic, code, links, lists) to HTML."""
    escaped = html.escape(raw_text).replace("\r\n", "\n")
    blocks = re.split(r"\n[ \t]*\n+", escaped.strip())
    rendered = []

    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip() != ""]
        if not lines:
            continue

        header_match = HEADER_RE.match(lines[0]) if len(lines) == 1 else None
        if header_match:
            level = len(header_match.group(1)) + 2
            rendered.append(f"<h{level}>{_inline_format(header_match.group(2))}</h{level}>")
            continue

        if all(LIST_ITEM_RE.match(line) for line in lines):
            items = "".join(f"<li>{_inline_format(LIST_ITEM_RE.match(line).group(1))}</li>" for line in lines)
            rendered.append(f"<ul>{items}</ul>")
            continue

        paragraph = "<br>".join(_inline_format(line) for line in lines)
        rendered.append(f"<p>{paragraph}</p>")

    return Markup("\n".join(rendered))


def _save_attachments(conn, post_id, files):
    for f in files:
        if not f or not f.filename:
            continue
        data = f.read()
        if not data:
            continue
        filename = secure_filename(f.filename) or f.filename
        conn.execute(
            "INSERT INTO post_attachments (post_id, filename, mimetype, size, data) VALUES (?, ?, ?, ?, ?)",
            (post_id, filename, f.mimetype, len(data), data),
        )


@blog.route("/blog")
def index():
    email = session.get("user_email")
    conn = get_conn()
    query = """
        SELECT p.id, p.author_email, p.title, p.body, p.is_internal, p.created_at,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count
        FROM posts p
    """
    if not email:
        query += " WHERE p.is_internal = 0"
    query += " ORDER BY p.created_at DESC"
    posts = conn.execute(query).fetchall()
    conn.close()
    return render_template("blog_index.html", posts=posts, name_map=get_name_map(), is_admin=_can_manage(email))


@blog.route("/blog/new", methods=["GET", "POST"])
@admin_required
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        is_internal = 1 if request.form.get("is_internal") else 0
        if not title or not body:
            flash("Title and body are required.", "error")
            return render_template("blog_new.html", title=title, body=body, is_internal=is_internal)

        ts = now()
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO posts (author_email, title, body, is_internal, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_email"], title, body, is_internal, ts, ts),
        )
        post_id = cur.lastrowid
        _save_attachments(conn, post_id, request.files.getlist("files"))
        conn.commit()
        conn.close()
        log_action("blog", "new_post", f"post #{post_id} \"{title}\"")
        flash("Post published.", "info")
        return redirect(url_for("blog.view_post", post_id=post_id))

    return render_template("blog_new.html", title="", body="", is_internal=0)


@blog.route("/blog/<int:post_id>")
def view_post(post_id):
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    email = session.get("user_email")
    if post["is_internal"] and not email:
        conn.close()
        flash("This is an internal post. Please log in to view it.", "error")
        return redirect(url_for("auth.login"))

    comments = conn.execute("SELECT * FROM comments WHERE post_id = ? ORDER BY id", (post_id,)).fetchall()
    attachments = conn.execute(
        "SELECT id, filename, size FROM post_attachments WHERE post_id = ? ORDER BY id", (post_id,)
    ).fetchall()
    conn.close()

    is_owner = bool(email) and post["author_email"] == email
    return render_template(
        "blog_post.html",
        post=post,
        post_body_html=render_post_body(post["body"]),
        comments=comments,
        attachments=attachments,
        name_map=get_name_map(),
        is_owner=is_owner,
        can_delete=is_owner or _can_manage(email),
        logged_in=bool(email),
    )


@blog.route("/blog/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    if post["author_email"] != session["user_email"]:
        conn.close()
        flash("You can only edit your own posts.", "error")
        return redirect(url_for("blog.view_post", post_id=post_id))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        is_internal = 1 if request.form.get("is_internal") else 0
        if not title or not body:
            attachments = conn.execute(
                "SELECT id, filename, size FROM post_attachments WHERE post_id = ? ORDER BY id", (post_id,)
            ).fetchall()
            conn.close()
            flash("Title and body are required.", "error")
            return render_template("blog_edit.html", post=post, attachments=attachments)

        conn.execute(
            "UPDATE posts SET title = ?, body = ?, is_internal = ?, updated_at = ? WHERE id = ?",
            (title, body, is_internal, now(), post_id),
        )
        for attachment_id in request.form.getlist("remove_attachment"):
            conn.execute(
                "DELETE FROM post_attachments WHERE id = ? AND post_id = ?", (attachment_id, post_id)
            )
        _save_attachments(conn, post_id, request.files.getlist("files"))
        conn.commit()
        conn.close()
        flash("Post updated.", "info")
        return redirect(url_for("blog.view_post", post_id=post_id))

    attachments = conn.execute(
        "SELECT id, filename, size FROM post_attachments WHERE post_id = ? ORDER BY id", (post_id,)
    ).fetchall()
    conn.close()
    return render_template("blog_edit.html", post=post, attachments=attachments)


@blog.route("/blog/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    conn = get_conn()
    post = conn.execute("SELECT author_email FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    email = session["user_email"]
    is_manager = _can_manage(email)
    if post["author_email"] != email and not is_manager:
        conn.close()
        flash("You don't have permission to delete this post.", "error")
        return redirect(url_for("blog.view_post", post_id=post_id))

    conn.execute("DELETE FROM post_attachments WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    if is_manager and post["author_email"] != email:
        log_action("blog", "delete_post", f"post #{post_id} by {post['author_email']}")
    flash("Post deleted.", "info")
    return redirect(url_for("blog.index"))


@blog.route("/blog/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    conn = get_conn()
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    body = request.form.get("body", "").strip()
    if not body:
        conn.close()
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("blog.view_post", post_id=post_id))

    conn.execute(
        "INSERT INTO comments (post_id, author_email, body, created_at) VALUES (?, ?, ?, ?)",
        (post_id, session["user_email"], body, now()),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("blog.view_post", post_id=post_id))


@blog.route("/blog/attachment/<int:attachment_id>")
def download_attachment(attachment_id):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT a.filename, a.mimetype, a.data, p.is_internal
        FROM post_attachments a
        JOIN posts p ON p.id = a.post_id
        WHERE a.id = ?
        """,
        (attachment_id,),
    ).fetchone()
    conn.close()

    if not row:
        abort(404)
    if row["is_internal"] and not session.get("user_email"):
        flash("This is an internal post. Please log in to view it.", "error")
        return redirect(url_for("auth.login"))

    return send_file(
        BytesIO(row["data"]),
        mimetype=row["mimetype"] or "application/octet-stream",
        as_attachment=True,
        download_name=row["filename"],
    )
