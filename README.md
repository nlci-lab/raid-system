# raid-system

An internal staff portal for the Research and Information Department (RAID) of
NLCI (New Life Computer Institute) — a department that documents
under-resourced languages through field survey work and produces the reports
that inform Bible translation priorities.

This app is the department's day-to-day internal tool: staff login,
attendance, an internal blog, a book-lending library, team chat, an
access-request/admin layer, and a read-only viewer over the department's
internal SQLite databases. It is not a public-facing site.

Current version: **5.1.0** (see [`VERSION`](VERSION); shown in the footer of
every page).

## What's in this repository

This repository holds the application codebase only — `app.py`, `apps/`,
`templates/`, and `static/` (plus `pass_raid_system.txt.example`, a
committed placeholder template — see below). It is one part of a larger
local project layout; the pieces that are **not** in this repository (and
must not be committed to it) are:

- the actual SQLite databases (staff records, attendance, chat, blog, library
  loans, and the internal language database)
- an internal architecture/deployment guide
- runtime logs
- a plaintext secrets/config file (SMTP or API credentials, session secret
  key, etc.) — the one file in this list that genuinely can't be created for
  you (see below)
- `tools/` — standalone utility scripts (e.g. `brevo_status.py`) that live as
  a sibling directory, not part of this app's own codebase

Those live as sibling directories/files alongside this one in the full
project layout, kept out of version control. **As of the first-run
bootstrap work below, the app creates the sibling folders/schema it needs on
its own the first time it starts** — the only thing you still have to supply
yourself is the secrets file.

## Modules at a glance

| Module | Purpose |
|---|---|
| `apps/auth` | Email + password login, with an OTP-based flow for first-time password setup and "forgot password" |
| `apps/dashboard` | Home/admin dashboard, user management |
| `apps/attendance` | Staff attendance tracking |
| `apps/blog` | Internal team blog (posts stored as files, indexed in a small DB) |
| `apps/chat` | Team chat with file attachments |
| `apps/ai_chat` | Optional AI chat assistant backed by a local [Ollama](https://ollama.com) instance (`http://localhost:11434`) — inert if Ollama isn't running |
| `apps/library` | Book catalog and lending/loan tracking, synced from a published Google Sheet |
| `apps/access` | Lets a user request access to a section they were denied, and lets an admin approve/deny it |
| `apps/ildb` | Admin-only, read-only table browser over any `.db` file in the database directory |
| `apps/guide` | Admin-only viewer for an internal markdown guide (optional — see below) |
| `apps/levels`, `apps/audit`, `apps/db`, `apps/config` | Shared infrastructure: numeric access-level system, audit logging, database path resolution, secrets loading |

**Access control**: a single numeric `users.level` field (lower = more
privileged) gates every route — dev, admin, data manager, staff, viewer,
external, anonymous — with optional decimal sub-levels for organizational
roles that share a tier's permissions.

## Running locally

### Requirements

- Python 3.x
- [Flask](https://flask.palletsprojects.com/) (`pip install flask`) — the
  only runtime dependency of the app itself. `werkzeug` comes with it.
- (Optional) [`requests`](https://pypi.org/project/requests/) — only needed
  if you use the standalone `tools/brevo_status.py` CLI script (lives outside
  this repo, as a sibling `tools/` directory alongside `core/`).
- (Optional) A local [Ollama](https://ollama.com) instance if you want the
  `ai_chat` module to actually respond.

There is currently no `requirements.txt` in this repo — the dependency list
above is everything actually imported by the code.

### Directory layout this code expects

`apps/db.py` and `apps/config.py` resolve two things relative to
*this* app folder, not from anywhere inside it:

- **Databases** — `apps/db.py` looks for a `db/` folder that is a
  **sibling of this app folder** (i.e. `../db/` relative to `app.py`),
  containing `users.db`, `library.db`, `attendance.db`, `chat.db`, and
  `blog.db`. **As of the first-run bootstrap work, none of this needs to
  exist beforehand** — on import, `apps/db.py` creates `db/` if missing
  and creates the base `users` table if it isn't there yet (nothing else in
  the codebase did, which used to make the very first request after a fresh
  checkout crash with "no such table: users"); `apps/library` similarly
  bootstraps an empty `books` table so `/library`/the dashboard/the home
  page work before anyone has run the catalog sync. Every other app-owned
  table (`posts`, `conversations`, `attendance`, `access_requests`,
  `loans`, `audit_log`, ...) already creates itself via its own
  `CREATE TABLE IF NOT EXISTS` the first time that module's `get_conn()`
  runs — this was already true before this bootstrap work, confirmed still
  correct starting from a totally empty `db/`.
  `ildb.db` is the one exception: it's real curated language-database
  content (see `apps/ildb`), not app-owned schema, so it is **not**
  auto-created — without it, `/internal-database` just has one less
  database to pick from, it doesn't crash.
- **Secrets** — `apps/config.py` loads `pass_raid_system.txt`, parsed as
  JSON. It checks the RAID department's shared Google Drive first
  (`G:\Shared drives\Research And Information Department(NLCI)\
  RAID-system-configs\pass_raid_system.txt` — used automatically if that
  path exists, e.g. Google Drive for Desktop mounted on a staff Windows
  machine), then falls back to a local sibling file at
  `../pass_raid_system.txt` (i.e. next to this app folder, not inside it —
  what raid-server and any machine without the Drive mounted uses). See
  `CONFIG_PATH` in `apps/config.py` if you need to check which one a given
  run actually picked up.

  **This file cannot be auto-generated** — it holds real secrets (Flask
  `secret_key`, mail credentials) and there's no safe placeholder to
  fabricate. Copy [`pass_raid_system.txt.example`](pass_raid_system.txt.example)
  (committed to this repo, safe placeholder values) to
  `../pass_raid_system.txt` and fill in your own values — at minimum
  `secret_key`, `email_id`, `passcode`. If it's missing, or present but not
  valid JSON, or missing `secret_key`, the app now exits at startup with a
  clear message telling you exactly what to do and which path it looked at
  — not a raw traceback.

  Optional keys (see the `.example` file and the docstrings in
  `apps/config.py` for what each does): `resend_api_key`,
  `resend_from_email`, `brevo_api_key`, `brevo_from_email`,
  `brevo_from_name`, `dev_bypass_code` (a standing login-field bypass for
  local dev/automated testing only), `dev_emails`.

- **Guide viewer (optional)** — `apps/guide` looks for the guide first on
  the same RAID department shared Google Drive as the secrets file above,
  falling back to a local sibling `guide/` folder. If neither is present,
  the guide page simply has nothing to show (it's admin-only and
  non-essential to the rest of the app) — already handled gracefully, no
  bootstrap needed.
- **Blog post files** — `apps/blog` looks for a `blogs/` folder as a
  sibling of this app folder, and already creates it if missing
  (`BLOGS_DIR.mkdir(exist_ok=True)`) — unchanged by this bootstrap work,
  it was already correct.
- **`logs/`** — nothing in this codebase (`app.py` or any `apps/*` module)
  writes to a `logs/` path; there's no in-code reference to one at all.
  Whatever ends up in a sibling `logs/` folder locally or on raid-server
  gets there purely via how the process is launched (e.g. gunicorn/a runner
  script redirecting stdout/stderr into it) — that's a deploy/ops concern,
  not something this app needs to create for itself.

None of `db/`, `guide/`, `blogs/`, `logs/`, or the secrets file are part of
this repository.

### Run it

```bash
python app.py
```

Runs a Flask dev server on `0.0.0.0:5055` with debug mode on. Production
deployment (gunicorn + nginx, systemd) is handled outside this repository.

## License / audience

Internal tool for NLCI's RAID department. Shared here as source-of-truth
code for deployment purposes; no warranty of fitness for use outside that
context.
