import base64
import re
import sqlite3
import unicodedata
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from modules.audit import log_action
from modules.db import BLOG_DB, USERS_DB
from modules.levels import MANAGER_LEVEL, current_level, tier

blog = Blueprint("blog", __name__, template_folder="templates")

BLOGS_DIR = Path(__file__).resolve().parent / "blogs"
BLOGS_DIR.mkdir(exist_ok=True)

SCHEMA = """
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_email TEXT NOT NULL,
        title TEXT NOT NULL,
        filename TEXT NOT NULL,
        is_internal INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
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


def slugify(title):
    """ASCII slug for a post's .md filename — same idea as the guide
    module's chapter slugs, just derived from the title instead of authored
    by hand."""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "post"


INTERNAL_PREFIX_RE = re.compile(r"(?i)^int[-_]")


def post_filename(post_id, title, is_internal=False):
    prefix = "INT-" if is_internal else ""
    return f"{prefix}{post_id}-{slugify(title)}.md"


def filename_is_internal(filename):
    """Convention for files dropped straight into BLOGS_DIR: a name starting
    with INT- (or int_, case-insensitive) marks the post internal."""
    return bool(INTERNAL_PREFIX_RE.match(filename))


def read_post_body(filename):
    path = BLOGS_DIR / filename
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write_post_body(filename, body):
    (BLOGS_DIR / filename).write_text(body, encoding="utf-8")


def delete_post_file(filename):
    path = BLOGS_DIR / filename
    if path.is_file():
        path.unlink()


def _migrate_body_to_files(conn):
    """One-time upgrade for DBs created before posts were stored as .md
    files: move each row's inline `body` out to BLOGS_DIR and drop the
    column. No-op once every DB has already been migrated."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(posts)")}
    if "body" not in cols:
        return
    if "filename" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN filename TEXT")
    for row in conn.execute("SELECT id, title, body, is_internal FROM posts WHERE filename IS NULL"):
        filename = post_filename(row["id"], row["title"], row["is_internal"])
        write_post_body(filename, row["body"])
        conn.execute("UPDATE posts SET filename = ? WHERE id = ?", (filename, row["id"]))
    conn.execute("ALTER TABLE posts DROP COLUMN body")
    conn.commit()


def _sync_posts_with_folder(conn):
    """BLOGS_DIR is the source of truth for what posts exist. Any .md file
    dropped straight into the folder gets a post row auto-created for it
    (title from its first `# heading`, else the filename; internal if the
    filename starts with INT-/int_); any post row whose file has been
    deleted from the folder gets removed along with its attachments. Runs on
    every connection — cheap directory scan for a folder this size."""
    known = {row["filename"]: row["id"] for row in conn.execute("SELECT id, filename FROM posts")}
    on_disk = {p.name for p in BLOGS_DIR.glob("*.md")}

    for filename, post_id in known.items():
        if filename not in on_disk:
            conn.execute("DELETE FROM post_attachments WHERE post_id = ?", (post_id,))
            conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    for filename in sorted(on_disk - known.keys()):
        path = BLOGS_DIR / filename
        text = path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = heading.group(1).strip() if heading else path.stem
        ts = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        is_internal = 1 if filename_is_internal(filename) else 0
        conn.execute(
            "INSERT INTO posts (author_email, title, filename, is_internal, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("system", title, filename, is_internal, ts, ts),
        )
    conn.commit()


def _drop_comments_table(conn):
    """Commenting was removed — drop the leftover table from older DBs."""
    conn.execute("DROP TABLE IF EXISTS comments")
    conn.commit()


def get_conn():
    """Connect to blog.db, creating the schema if the file is missing or empty."""
    conn = sqlite3.connect(BLOG_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate_body_to_files(conn)
    _drop_comments_table(conn)
    _sync_posts_with_folder(conn)
    return conn


def get_name_map():
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT name, email FROM users WHERE email IS NOT NULL").fetchall()
    conn.close()
    return {row["email"]: row["name"] for row in rows}


def _can_manage(email):
    """email is always the current session user in practice — kept as a
    param for API clarity, but the check is against current_level()."""
    if not email:
        return False
    level = current_level()
    return level is not None and tier(level) <= MANAGER_LEVEL


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


def render_post_body(raw_text):
    """Base64-encode a post body for the client-side Markdown renderer (see
    static/js/main.js, setupMarkdownRender). Encoding it, rather than
    dropping the raw text into the template directly, means no character in
    a post — including a literal `</script>` typed by a user — can break out
    of whatever tag it's embedded in."""
    return base64.b64encode(raw_text.encode("utf-8")).decode("ascii")


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
        SELECT p.id, p.author_email, p.title, p.filename, p.is_internal, p.created_at
        FROM posts p
    """
    if not _can_manage(email):
        query += " WHERE p.is_internal = 0"
    query += " ORDER BY p.created_at DESC"
    rows = conn.execute(query).fetchall()
    conn.close()

    posts = []
    for row in rows:
        post = dict(row)
        body = read_post_body(row["filename"])
        post["excerpt"] = body[:180] + ("…" if len(body) > 180 else "")
        posts.append(post)

    return render_template("blog_index.html", posts=posts, name_map=get_name_map(), is_admin=_can_manage(email))


@blog.route("/blog/new", methods=["GET", "POST"])
@admin_required
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        is_internal = 1 if request.form.get("is_internal") else 0
        md_file = request.files.get("md_file")
        if not title or not md_file or not md_file.filename:
            flash("Title and a .md file are required.", "error")
            return render_template("blog_new.html", title=title, is_internal=is_internal)
        if not md_file.filename.lower().endswith(".md"):
            flash("Post content must be a .md file.", "error")
            return render_template("blog_new.html", title=title, is_internal=is_internal)

        body = md_file.read().decode("utf-8", errors="replace").strip()
        if not body:
            flash("The uploaded .md file is empty.", "error")
            return render_template("blog_new.html", title=title, is_internal=is_internal)

        ts = now()
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO posts (author_email, title, filename, is_internal, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_email"], title, "", is_internal, ts, ts),
        )
        post_id = cur.lastrowid
        filename = post_filename(post_id, title, is_internal)
        conn.execute("UPDATE posts SET filename = ? WHERE id = ?", (filename, post_id))
        write_post_body(filename, body)
        _save_attachments(conn, post_id, request.files.getlist("files"))
        conn.commit()
        conn.close()
        log_action("blog", "new_post", f"post #{post_id} \"{title}\"")
        flash("Post published.", "info")
        return redirect(url_for("blog.view_post", post_id=post_id))

    return render_template("blog_new.html", title="", is_internal=0)


@blog.route("/blog/<int:post_id>")
def view_post(post_id):
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    email = session.get("user_email")
    if post["is_internal"]:
        if not email:
            conn.close()
            flash("This is an internal post. Please log in to view it.", "error")
            return redirect(url_for("auth.login"))
        if not _can_manage(email):
            conn.close()
            flash("This is an internal post — visible to manager-level staff only.", "error")
            return redirect(url_for("blog.index"))

    attachments = conn.execute(
        "SELECT id, filename, size FROM post_attachments WHERE post_id = ? ORDER BY id", (post_id,)
    ).fetchall()
    conn.close()

    body = read_post_body(post["filename"])
    is_owner = bool(email) and post["author_email"] == email
    return render_template(
        "blog_post.html",
        post=post,
        post_body_b64=render_post_body(body),
        attachments=attachments,
        name_map=get_name_map(),
        is_owner=is_owner,
        can_delete=is_owner or _can_manage(email),
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
            post_dict = dict(post)
            post_dict["title"] = title
            post_dict["body"] = body
            post_dict["is_internal"] = is_internal
            return render_template("blog_edit.html", post=post_dict, attachments=attachments)

        new_filename = post_filename(post_id, title, is_internal)
        write_post_body(new_filename, body)
        if new_filename != post["filename"]:
            delete_post_file(post["filename"])

        conn.execute(
            "UPDATE posts SET title = ?, filename = ?, is_internal = ?, updated_at = ? WHERE id = ?",
            (title, new_filename, is_internal, now(), post_id),
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
    post_dict = dict(post)
    post_dict["body"] = read_post_body(post["filename"])
    return render_template("blog_edit.html", post=post_dict, attachments=attachments)


@blog.route("/blog/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    conn = get_conn()
    post = conn.execute("SELECT author_email, filename FROM posts WHERE id = ?", (post_id,)).fetchone()
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
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    delete_post_file(post["filename"])
    if is_manager and post["author_email"] != email:
        log_action("blog", "delete_post", f"post #{post_id} by {post['author_email']}")
    flash("Post deleted.", "info")
    return redirect(url_for("blog.index"))


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
    if row["is_internal"]:
        email = session.get("user_email")
        if not email:
            flash("This is an internal post. Please log in to view it.", "error")
            return redirect(url_for("auth.login"))
        if not _can_manage(email):
            flash("This is an internal post — visible to manager-level staff only.", "error")
            return redirect(url_for("blog.index"))

    return send_file(
        BytesIO(row["data"]),
        mimetype=row["mimetype"] or "application/octet-stream",
        as_attachment=True,
        download_name=row["filename"],
    )
