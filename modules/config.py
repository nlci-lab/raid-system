import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "pass_raid_system.txt"

with open(CONFIG_PATH, encoding="utf-8") as f:
    _config = json.load(f)

SMTP_EMAIL = _config["email_id"]
SMTP_PASSCODE = _config["passcode"].replace(" ", "")
SECRET_KEY = _config["secret_key"]

RESEND_API_KEY = _config.get("resend_api_key")
RESEND_FROM_EMAIL = _config.get("resend_from_email", SMTP_EMAIL)

# Dev-only convenience: skip sending/checking a real OTP code for @nlife.in
# addresses and log straight in. Must stay OFF unless explicitly set locally
# (e.g. `set DEV_SKIP_OTP=1` before `python app.py`) — never enable this in
# a deployed/production environment, since it removes proof of email
# ownership for anyone who types a valid-looking @nlife.in address.
DEV_SKIP_OTP = os.environ.get("DEV_SKIP_OTP", "").strip().lower() in ("1", "true", "yes")
