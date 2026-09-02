import json
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

# Standing bypass code for AI agents / developers running automated tests
# against this local instance. Typed into the login email field in place of
# an address, it logs straight in as DEV_BYPASS_EMAIL with no OTP round trip.
# Lives in pass_raid_system.txt (untracked secrets file) rather than env vars
# so it works out of the box for any local dev/AI session without setup.
DEV_BYPASS_CODE = _config.get("dev_bypass_code")
