# RAID System

Internal Flask app for NLCI's RAID department (library, language database, chat, blog, loans, attendance, access requests).

## Demo data

The `db/` folder ships with synthetic, non-real data only (placeholder names like `user1`, `lang1`, `book1`) so the app runs out of the box without exposing any real member or organizational records.

## Setup

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt   # venv\Scripts\pip on Windows
cp pass_raid_system.txt.example pass_raid_system.txt
# edit pass_raid_system.txt with your own SMTP account and secret key
python app.py
```

Login is restricted to `@nlife.in` email addresses via a one-time email code. Set `DEV_SKIP_OTP=1` in the environment for local development to skip email OTP delivery (never enable this in a deployed environment).
