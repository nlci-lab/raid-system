"""Internal developer guide: serves the markdown chapters in guide/ (repo
root) with a chapter list sidebar. Read-only — the guide is a static
reference doc, not a database-backed module. Markdown -> HTML conversion
happens client-side (see static/js/main.js, setupMarkdownRender) — this
module only rewrites cross-chapter links and base64-encodes the source."""

import base64
import re
from pathlib import Path

from flask import Blueprint, abort, render_template, url_for

from apps.levels import ADMIN_LEVEL, current_level, tier

guide = Blueprint("guide", __name__, template_folder="templates")

# The guide now lives on Google Drive (RAID department shared drive), not
# as a folder committed to this repo. Same existence-based fallback on
# both environments, no env-specific code path needed:
#   - Windows dev machine with Google Drive for Desktop mounted: the G:\
#     path exists, read straight from the live Drive mount.
#   - raid-server (Linux — "G:/..." is just a literal, never-existing
#     path there, so .exists() safely returns False, no crash): falls
#     back to the local sibling "guide/" folder, which is the
#     rclone-synced copy kept current by /root/raid_system_guide_sync.sh.
#   - Any machine with neither (G:\ not mounted, rclone not synced yet):
#     falls back to the same local sibling path, which may just be
#     empty/missing — _chapters() below already handles that (404).
#
# Four .parents, not three: apps/guide/__init__.py -> apps/ -> core/ (the
# app folder itself, pure codebase only) -> raid_system/ (the container,
# sibling of core/) — matching where db/, blogs/, guide/ etc. actually
# live on both local dev and production (2026-09-12: moved production's
# guide/ out of core/'s equivalent app-root folder to be a proper sibling
# at /root/, same convention as local's layout, instead of nested inside
# the app folder where it happened to still work before this fix but
# wasn't actually "pure code only" in core/'s sense).
_GDRIVE_GUIDE_DIR = Path("G:/Shared drives/Research And Information Department(NLCI)/RAID-system-configs/guide")
_LOCAL_GUIDE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "guide"
GUIDE_DIR = _GDRIVE_GUIDE_DIR if _GDRIVE_GUIDE_DIR.exists() else _LOCAL_GUIDE_DIR
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
