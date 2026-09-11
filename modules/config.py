import json
from pathlib import Path

# modules/config.py -> modules/ -> core/ (app root) -> raid_system/ (container,
# sibling of the app folder) / "pass_raid_system.txt". Same three-.parent
# pattern as modules/db.py, so both keep resolving correctly together if the
# app folder itself is ever renamed/moved again.
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "pass_raid_system.txt"

with open(CONFIG_PATH, encoding="utf-8") as f:
    _config = json.load(f)

SMTP_EMAIL = _config["email_id"]
SMTP_PASSCODE = _config["passcode"].replace(" ", "")
SECRET_KEY = _config["secret_key"]

RESEND_API_KEY = _config.get("resend_api_key")
RESEND_FROM_EMAIL = _config.get("resend_from_email", SMTP_EMAIL)

# Standing bypass code for AI agents / developers running automated tests
# against this local instance. Typed into the login email field in place of
# an address, it logs straight in as DEV_BYPASS_EMAIL with no OTP round trip.
# Lives in pass_raid_system.txt (untracked secrets file) rather than env vars
# so it works out of the box for any local dev/AI session without setup.
DEV_BYPASS_CODE = _config.get("dev_bypass_code")

# Emails to force to level 0.0 (dev) during the one-off role->level migration
# (modules/migrate_to_levels.py). Lives here, in the untracked secrets file,
# rather than hardcoded in the migration script, so no real staff email ever
# ends up in git history. Optional key "dev_emails": ["someone@nlife.in"].
DEV_EMAILS = set(_config.get("dev_emails", []))
