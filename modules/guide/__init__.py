"""Internal developer guide: serves the markdown chapters in guide/ (repo
root) with a chapter list sidebar. Read-only — the guide is a static
reference doc, not a database-backed module. Markdown -> HTML conversion
happens client-side (see static/js/main.js, setupMarkdownRender) — this
module only rewrites cross-chapter links and base64-encodes the source."""

import base64
import re
from pathlib import Path

from flask import Blueprint, abort, render_template, url_for

from modules.levels import ADMIN_LEVEL, current_level, tier

guide = Blueprint("guide", __name__, template_folder="templates")

GUIDE_DIR = Path(__file__).resolve().parent.parent.parent / "guide"
CHAPTER_RE = re.compile(r"^(\d{2})-([A-Za-z0-9-]+)\.md$")
LINK_RE = re.compile(r"\]\((\d{2}-[A-Za-z0-9-]+)\.md\)")


def _chapters():
    chapters = []
    for path in sorted(GUIDE_DIR.glob("*.md")):
        if not CHAPTER_RE.match(path.name):
            continue
        text = path.read_text(encoding="utf-8")
        heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = heading.group(1).strip() if heading else path.stem
        chapters.append({"slug": path.stem, "title": title})
    return chapters


def _require_access():
    level = current_level()
    if level is None or tier(level) > ADMIN_LEVEL:
        abort(403)


@guide.route("/guide")
@guide.route("/guide/<slug>")
def view(slug=None):
    _require_access()
    chapters = _chapters()
    if not chapters:
        abort(404)
    if slug is None:
        slug = chapters[0]["slug"]

    path = GUIDE_DIR / f"{slug}.md"
    if not CHAPTER_RE.match(path.name) or not path.is_file():
        abort(404)

    raw = LINK_RE.sub(lambda m: f"]({url_for('guide.view', slug=m.group(1))})", path.read_text(encoding="utf-8"))
    content_b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")

    return render_template("guide.html", chapters=chapters, active_slug=slug, content_b64=content_b64)
