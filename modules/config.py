import json
import os
from pathlib import Path

# modules/config.py -> modules/ -> core/ (app root) -> raid_system/ (container,
# sibling of the app folder) / "pass_raid_system.txt". Same three-.parent
# pattern as modules/db.py, so both keep resolving correctly together if the
# app folder itself is ever renamed/moved again.
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "pass_raid_system.txt"

with open(CONFIG_PATH, encoding="utf-8") as f:
    _config = json.load(f)

SECRET_KEY = _config["secret_key"]

# Historically the Gmail SMTP account used for outbound mail in local dev.
# Outbound SMTP (port 465/587) is blocked at the network level on
# raid-server, so production never uses this — it sends via Brevo's HTTP
# API instead (BREVO_* below). Kept optional (not a required key) so this
# same file loads cleanly wherever "passcode" isn't set.
SMTP_EMAIL = _config.get("email_id")
SMTP_PASSCODE = (_config.get("passcode") or "").replace(" ", "") or None

# Default "from" address, used as a fallback for RESEND_FROM_EMAIL /
# BREVO_FROM_EMAIL below when a provider-specific from-address isn't set.
_DEFAULT_FROM_EMAIL = _config.get("email_id")

RESEND_API_KEY = _config.get("resend_api_key")
RESEND_FROM_EMAIL = _config.get("resend_from_email", _DEFAULT_FROM_EMAIL)

# Brevo (formerly Sendinblue) transactional email HTTP API — the mail
# transport actually used in production (see modules/auth._send_via_brevo).
# Runs over HTTPS (port 443), unlike SMTP which is blocked on raid-server.
# Unset locally (no brevo_* keys in the local pass_raid_system.txt), which
# is exactly what makes modules/auth fall back to local SMTP for local dev.
BREVO_API_KEY = _config.get("brevo_api_key")
BREVO_FROM_EMAIL = _config.get("brevo_from_email", _DEFAULT_FROM_EMAIL)
BREVO_FROM_NAME = _config.get("brevo_from_name", "RAIDsystem")

# Standing bypass code for AI agents / developers running automated tests
# against a *local* instance. Typed into the login email field in place of
# an address, it logs straight in as DEV_BYPASS_EMAIL with no OTP round trip.
# Lives in pass_raid_system.txt (untracked secrets file) rather than env vars
# so it works out of the box for any local dev/AI session without setup.
DEV_BYPASS_CODE = _config.get("dev_bypass_code")

# Production's equivalent dev convenience: skip sending/checking a real OTP
# for @nlife.in addresses and log straight in. Env-var gated (not config-file
# gated like DEV_BYPASS_CODE above) so it can never be silently "on" just
# because a shared secrets file has a key set — must stay OFF unless
# explicitly exported before starting the app. Never enable in a real
# deployed/production environment: it removes proof of email ownership for
# anyone who types a valid-looking @nlife.in address.
DEV_SKIP_OTP = os.environ.get("DEV_SKIP_OTP", "").strip().lower() in ("1", "true", "yes")

# Emails to force to level 0.0 (dev) during the one-off role->level migration
# (modules/migrate_to_levels.py). Lives here, in the untracked secrets file,
# rather than hardcoded in the migration script, so no real staff email ever
# ends up in git history. Optional key "dev_emails": ["someone@nlife.in"].
DEV_EMAILS = set(_config.get("dev_emails", []))
