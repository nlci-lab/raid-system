"""Retrieval-augmented context for RAID Bot -- a from-scratch, dependency-
free (no numpy, no vector DB) semantic search over RAIDsystem's own
content, so answers can be grounded in the real app instead of only the
static system prompt.

Sources indexed: the codebase itself (the main route files + README), the
internal Guide, blog posts, and the library catalog. Note the Guide is
normally admin-only (see apps/guide) -- indexing it here means any RAID
Bot user (the bot is open to all tiers, see logged_in_required) can
surface Guide content through a question, an explicit tradeoff Boss chose
(2026-09-12) over leaving Guide out of RAG entirely.

Embeddings come from Ollama's own /api/embeddings (nomic-embed-text,
already installed alongside the chat model) -- built once via the
"Rebuild Index" button on /dashboard/raid-bot-dash, stored in ai_chat.db,
then just a cosine-similarity scan at query time (small corpus, pure
Python is plenty -- no need for numpy or a real vector DB at this scale).
"""

import json
import math
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from apps.db import AI_CHAT_DB, BLOG_DB, LIBRARY_DB

DEFAULT_EMBED_MODEL = "nomic-embed-text:latest"

# Kept modest -- retrieved context is injected into every single message's
# prompt, directly fighting the token-count trim the system prompt already
# went through for CPU-only latency (see that commit's message).
CHUNK_SIZE = 900
TOP_K = 4
MIN_SCORE = 0.3

# apps/ai_chat/rag.py -> apps/ -> core/ (the app root, pure codebase).
APP_ROOT = Path(__file__).resolve().parent.parent.parent

# The main route files + README -- not every file (skips static/, .html
# templates, tests) since raw HTML/CSS is noisy for semantic search and
# the Python files already carry the real behavior + explanatory comments.
CODEBASE_FILES = [
    "app.py",
    "README.md",
    "apps/levels.py",
    "apps/db.py",
    "apps/config.py",
    "apps/audit.py",
    "apps/auth/__init__.py",
    "apps/library/__init__.py",
    "apps/dashboard/__init__.py",
    "apps/chat/__init__.py",
    "apps/ai_chat/__init__.py",
    "apps/ai_chat/rag.py",
    "apps/attendance/__init__.py",
    "apps/blog/__init__.py",
    "apps/ildb/__init__.py",
    "apps/access/__init__.py",
    "apps/guide/__init__.py",
]

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        label TEXT NOT NULL,
        content TEXT NOT NULL,
        embedding TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rag_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
"""


def _conn():
    conn = sqlite3.connect(AI_CHAT_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _embed_model():
    # Deferred import -- apps.ai_chat imports this module at load time, so
    # importing back at module level here would be circular. By the time
    # any of this file's functions actually run, apps.ai_chat has finished
    # initializing, so a call-time import is safe.
    from apps.ai_chat import _get_setting
    return _get_setting("embed_model_name", DEFAULT_EMBED_MODEL)


def _ollama_embed_url():
    from apps.ai_chat import _ollama_base_url
    return f"{_ollama_base_url()}/api/embeddings"


def _embed(text):
    payload = {"model": _embed_model(), "prompt": text}
    req = urllib.request.Request(
        _ollama_embed_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("embedding")


def _chunk_text(text, size=CHUNK_SIZE):
    """Paragraph-aware chunker -- packs whole paragraphs up to ~size chars
    per chunk instead of slicing mid-sentence."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if current and len(current) + len(p) + 2 > size:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def _gather_documents():
    """Yields (source, label, text) tuples for every document to index."""
    for rel_path in CODEBASE_FILES:
        path = APP_ROOT / rel_path
        if path.is_file():
            yield "codebase", rel_path, path.read_text(encoding="utf-8")

    # RAID Bot's own hand-written knowledge docs -- real-world department
    # facts (org structure, policies, survey process) that don't live
    # anywhere else in the codebase or the Guide. Drop any .md file here
    # to have it indexed automatically on the next rebuild.
    knowledge_dir = Path(__file__).parent / "knowledge"
    for md_path in sorted(knowledge_dir.glob("*.md")):
        yield "knowledge", md_path.name, md_path.read_text(encoding="utf-8")

    try:
        from apps.guide import GUIDE_DIR
        for md_path in sorted(GUIDE_DIR.glob("*.md")):
            yield "guide", md_path.name, md_path.read_text(encoding="utf-8")
    except Exception:
        pass

    try:
        conn = sqlite3.connect(BLOG_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT title, filename FROM posts").fetchall()
        conn.close()
        from apps.blog import read_post_body
        for row in rows:
            body = read_post_body(row["filename"])
            if body:
                yield "blog", row["title"], f"# {row['title']}\n\n{body}"
    except Exception:
        pass

    try:
        conn = sqlite3.connect(LIBRARY_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, author, genre, series, publish_year FROM books"
        ).fetchall()
        conn.close()
        for row in rows:
            bits = [row["title"]]
            if row["author"]:
                bits.append(f"by {row['author']}")
            if row["genre"]:
                bits.append(f"genre: {row['genre']}")
            if row["series"]:
                bits.append(f"series: {row['series']}")
            if row["publish_year"]:
                bits.append(f"year: {row['publish_year']}")
            yield "library", row["title"], " — ".join(bits)
    except Exception:
        pass


def build_index():
    """Full rebuild -- clears and re-embeds everything. Runs synchronously
    (admin-triggered, occasional -- not worth background-job machinery at
    this app's scale); can take anywhere from several seconds to a couple
    of minutes depending on corpus size. Returns a summary dict.

    Deliberately opens/closes a fresh short-lived connection for each
    individual write (the DELETE, then one INSERT per chunk) instead of
    holding a single connection across the whole loop. The slow part of
    this function is the network call to Ollama for each chunk's
    embedding, not the DB -- holding a write transaction open for that
    whole multi-minute stretch previously locked ai_chat.db for every
    other request site-wide (is_bot_enabled() runs on *every* page via
    app.py's inject_ai_bot_enabled context processor), turning a RAG
    rebuild into a site-wide outage for its whole duration. Found live
    2026-09-12: rebuilding while the widget's own is_bot_enabled() check
    ran on every page load raised "sqlite3.OperationalError: database is
    locked" on the plain home page.

    Prints progress to stdout (visible in the dev server's console / prod's
    systemd log) since this blocks the request for a while with no other
    feedback -- makes a genuinely slow build distinguishable from a hang."""
    conn = _conn()
    conn.execute("DELETE FROM rag_chunks")
    conn.commit()
    conn.close()

    total_chunks = sum(len(_chunk_text(text)) for _, _, text in _gather_documents())
    print(f"[rag] build_index: {total_chunks} chunks to embed", flush=True)

    counts = {}
    errors = []
    done = 0
    for source, label, text in _gather_documents():
        for chunk in _chunk_text(text):
            done += 1
            try:
                embedding = _embed(chunk)
            except Exception as e:
                errors.append(f"{source}/{label}: {e}")
                print(f"[rag] {done}/{total_chunks} FAILED {source}/{label}: {e}", flush=True)
                continue
            if not embedding:
                continue
            row_conn = _conn()
            row_conn.execute(
                "INSERT INTO rag_chunks (source, label, content, embedding) VALUES (?, ?, ?, ?)",
                (source, label, chunk, json.dumps(embedding)),
            )
            row_conn.commit()
            row_conn.close()
            counts[source] = counts.get(source, 0) + 1
            if done % 10 == 0 or done == total_chunks:
                print(f"[rag] {done}/{total_chunks} embedded ({source}/{label})", flush=True)

    conn = _conn()
    conn.execute(
        "INSERT INTO rag_meta (key, value) VALUES ('built_at', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (datetime.now().isoformat(timespec="seconds"),),
    )
    conn.commit()
    conn.close()
    return {"counts": counts, "errors": errors, "total": sum(counts.values())}


def index_status():
    conn = _conn()
    built_at_row = conn.execute("SELECT value FROM rag_meta WHERE key = 'built_at'").fetchone()
    counts = {}
    for row in conn.execute("SELECT source, COUNT(*) AS n FROM rag_chunks GROUP BY source"):
        counts[row["source"]] = row["n"]
    conn.close()
    return {
        "built_at": built_at_row["value"] if built_at_row else None,
        "counts": counts,
        "total": sum(counts.values()),
    }


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(query, top_k=TOP_K, min_score=MIN_SCORE):
    """Best-effort -- returns [] (never raises) if Ollama's embeddings
    endpoint is unreachable or the index is empty, so a RAG failure never
    breaks a normal chat reply."""
    try:
        query_embedding = _embed(query)
    except Exception:
        return []
    if not query_embedding:
        return []

    conn = _conn()
    rows = conn.execute("SELECT source, label, content, embedding FROM rag_chunks").fetchall()
    conn.close()

    scored = []
    for row in rows:
        try:
            chunk_embedding = json.loads(row["embedding"])
        except (json.JSONDecodeError, TypeError):
            continue
        score = _cosine(query_embedding, chunk_embedding)
        if score >= min_score:
            scored.append((score, row["source"], row["label"], row["content"]))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        {"score": s, "source": src, "label": label, "content": content}
        for s, src, label, content in scored[:top_k]
    ]
