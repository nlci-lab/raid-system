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

This repository holds the application codebase only — `app.py`, `modules/`,
`templates/`, and `static/`. It is one part of a larger local project layout;
the pieces that are **not** in this repository (and must not be committed to
it) are:

- the actual SQLite databases (staff records, attendance, chat, blog, library
  loans, and the internal language database)
- an internal architecture/deployment guide
- runtime logs
- a plaintext secrets/config file (SMTP or API credentials, session secret
  key, etc.)
- `tools/` — standalone utility scripts (e.g. `brevo_status.py`) that live as
  a sibling directory, not part of this app's own codebase

Those live as sibling directories/files alongside this one in the full
project layout, kept out of version control, and are supplied locally (or on
the server) at the paths described below.

## Modules at a glance

| Module | Purpose |
|---|---|
| `modules/auth` | Email + password login, with an OTP-based flow for first-time password setup and "forgot password" |
| `modules/dashboard` | Home/admin dashboard, user management |
| `modules/attendance` | Staff attendance tracking |
| `modules/blog` | Internal team blog (posts stored as files, indexed in a small DB) |
| `modules/chat` | Team chat with file attachments |
| `modules/ai_chat` | Optional AI chat assistant backed by a local [Ollama](https://ollama.com) instance (`http://localhost:11434`) — inert if Ollama isn't running |
| `modules/library` | Book catalog and lending/loan tracking, synced from a published Google Sheet |
| `modules/access` | Lets a user request access to a section they were denied, and lets an admin approve/deny it |
| `modules/ildb` | Admin-only, read-only table browser over any `.db` file in the database directory |
| `modules/guide` | Admin-only viewer for an internal markdown guide (optional — see below) |
| `modules/levels`, `modules/audit`, `modules/db`, `modules/config` | Shared infrastructure: numeric access-level system, audit logging, database path resolution, secrets loading |

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

`modules/db.py` and `modules/config.py` resolve two things relative to
*this* app folder, not from anywhere inside it:

- **Databases** — `modules/db.py` looks for a `db/` folder that is a
  **sibling of this app folder** (i.e. `../db/` relative to `app.py`),
  containing `users.db`, `library.db`, `attendance.db`, `chat.db`,
  `blog.db`, and `ildb.db`. The app will not start correctly without at
  least `users.db` present there.
- **Secrets** — `modules/config.py` loads a `pass_raid_system.txt` file,
  parsed as JSON, with at minimum:

  ```json
  {
    "email_id": "...",
    "passcode": "...",
    "secret_key": "..."
  }
  ```

  Optional keys: `resend_api_key`, `resend_from_email`, `dev_bypass_code`
  (a standing login-field bypass for local dev/automated testing only — see
  the docstring in `modules/config.py`). **Verify the exact path
  `modules/config.py` reads before relying on this** — depending on which
  snapshot of this layout you're working from, that file may need to sit
  directly inside the app folder or one level up as a sibling of it; check
  `CONFIG_PATH` in `modules/config.py` against where the file actually is
  before you assume it will be picked up.

- **Guide viewer (optional)** — `modules/guide` will look for a `guide/`
  folder as a sibling of this app folder. If it isn't present, the guide
  page simply has nothing to show (it's admin-only and non-essential to the
  rest of the app).

None of `db/`, `guide/`, `logs/`, or the secrets file are part of this
repository — set them up locally (or point at existing ones) before running
the app.

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
