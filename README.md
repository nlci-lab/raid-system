# RAID System

Public demo mirror of the internal Flask web application built for NLCI's RAID department (Research and Information Department). It brings several day-to-day departmental workflows — a library catalog, an internal language database, team chat, a blog, book loans, attendance tracking, and access-request handling — into a single portal with role-based permissions. The `db/` folder ships with synthetic, non-real data (placeholder names like `user1`, `lang1`, `book1`) so the app runs out of the box without exposing any real member or organizational records.

## Features

- **Auth** — email-based one-time-code login open to any valid email address; an `@nlife.in` address gets the `viewer` tier by default, anything else gets `external`, with a dev bypass switch for local testing.
- **Dashboard** — a role-aware landing page; dedicated dashboard views exist for a few specific sub-roles (e.g. director, senior manager) while everyone else shares the default one.
- **Library** — book catalog with checkouts/returns (loans), synced from an external sheet/CSV import.
- **Internal Language Database (ildb)** — a read-only table viewer over the app's own SQLite databases, admin-only, originally built around a language/dialect reference dataset.
- **Chat** — internal team messaging with file attachments.
- **Blog** — internal posts/announcements with image support.
- **Attendance** — daily attendance marking and history.
- **Access requests** — lets a user who hits a permission wall ask an admin to grant access to that section.
- **AI chat** — an assistant panel backed by a local LLM endpoint.
- **Audit log** — tracks key actions (level changes, approvals, etc.) for admin review.

### Access levels

Permissions are governed by a numeric level on each user (lower = more privileged), with optional decimal sub-levels for organizational sub-titles that share their whole-number tier's permissions:

| Level | Role |
|---|---|
| 0 | dev |
| 1 | admin |
| 2 | data_manager |
| 3 | raid_staff |
| 4 | viewer |
| 5 | external |
| 6 | anonymous |

## Setup

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt   # venv\Scripts\pip on Windows
cp pass_raid_system.txt.example pass_raid_system.txt
# edit pass_raid_system.txt with your own SMTP account and secret key
python app.py
```

Login normally goes through a one-time email code (SMTP credentials required in `pass_raid_system.txt`). For local testing without email delivery, set a `dev_bypass_code` in `pass_raid_system.txt` and type that value into the login form's email field instead of a real address — it logs straight in with no OTP round trip.

## Tech stack

Flask (Python) backend, server-rendered Jinja templates, SQLite for storage — one database file per module (users, books/loans, chat, blog, attendance, ildb).
