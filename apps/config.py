import json
import os
import sys
from pathlib import Path

# apps/config.py -> apps/ -> core/ (app root) -> raid_system/ (container,
# sibling of the app folder) / "pass_raid_system.txt". Same three-.parent
# pattern as apps/db.py, so both keep resolving correctly together if the
# app folder itself is ever renamed/moved again.
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Secrets base dir is moving to Google Drive (RAID department shared
# drive) — same existence-check pattern as apps/guide's GUIDE_DIR, so this
# works unmodified on both a Windows dev machine with Google Drive for
# Desktop mounted (G:\ exists -> used) and raid-server / any machine
# without it mounted (G:\ doesn't exist -> falls back to the local sibling
# file). This file is edited directly through Drive (web UI or the G:\
# mount's own apps), never by automated tooling here — a failed
# programmatic write against a Drive-synced file has previously truncated
# it (2026-09-11 incident), so nothing in this codebase writes to
# CONFIG_PATH, only reads it.
_GDRIVE_CONFIG_PATH = Path("G:/Shared drives/Research And Information Department(NLCI)/RAID-system-configs/pass_raid_system.txt")
_LOCAL_CONFIG_PATH = PROJECT_ROOT / "pass_raid_system.txt"
CONFIG_PATH = _GDRIVE_CONFIG_PATH if _GDRIVE_CONFIG_PATH.exists() else _LOCAL_CONFIG_PATH

# This file can't be auto-generated with real values (it's the actual
# secret_key/mail-credential store) — unlike db/, logs/, blogs/, there is no
# safe bootstrap here. Fail loudly but *cleanly* instead of the raw
# FileNotFoundError/JSONDecodeError traceback this used to surface (confirmed
# 2026-09-11 when the Drive copy got emptied by a failed programmatic write —
# see the CONFIG_PATH comment above). sys.exit() on a plain, non-traceback
# message is deliberate: this is a startup precondition check, not a bug to
# debug via stack trace.
if not CONFIG_PATH.exists():
    sys.exit(
        f"\npass_raid_system.txt not found at: {CONFIG_PATH}\n\n"
        "This file holds local secrets (Flask secret_key, mail credentials, "
        "etc.) and is intentionally untracked in git — it is never created "
        "automatically.\n\n"
        f"Fix: copy {PROJECT_ROOT / 'pass_raid_system.txt.example'} to\n"
        f"     {_LOCAL_CONFIG_PATH}\n"
        "and fill in your own values (at minimum: secret_key, email_id, "
        "passcode).\n\n"
        "(If you're expecting the RAID department's shared Google Drive copy "
        f"instead, check that G:\\ is mounted and this file exists there:\n"
        f"     {_GDRIVE_CONFIG_PATH})\n"
    )

with open(CONFIG_PATH, encoding="utf-8") as f:
    try:
        _config = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(
            f"\npass_raid_system.txt at {CONFIG_PATH} is not valid JSON ({e}).\n"
            "Check for a truncated/corrupted file (this has happened before via "
            "a failed Drive-synced write) and restore or rewrite it — see "
            f"{PROJECT_ROOT / 'pass_raid_system.txt.example'} for the expected shape.\n"
        )

try:
    SECRET_KEY = _config["secret_key"]
except KeyError:
    sys.exit(
        f"\npass_raid_system.txt at {CONFIG_PATH} is missing the required "
        '"secret_key" key.\n'
        f"See {PROJECT_ROOT / 'pass_raid_system.txt.example'} for the expected shape.\n"
    )

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
# transport actually used in production (see apps/auth._send_via_brevo).
# Runs over HTTPS (port 443), unlike SMTP which is blocked on raid-server.
# Unset locally (no brevo_* keys in the local pass_raid_system.txt), which
# is exactly what makes apps/auth fall back to local SMTP for local dev.
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
# (apps/migrate_to_levels.py). Lives here, in the untracked secrets file,
# rather than hardcoded in the migration script, so no real staff email ever
# ends up in git history. Optional key "dev_emails": ["someone@nlife.in"].
DEV_EMAILS = set(_config.get("dev_emails", []))
