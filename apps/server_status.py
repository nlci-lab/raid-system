"""Server health status for the raid-system-admin dashboard: process
uptime, resource usage, database file sizes, and a tail of real
application errors.

This is deliberately separate from apps/audit (which logs *who changed
what* — admin actions) — this module is about *what broke*: unhandled
exceptions and warnings, written to logs/error.log by the file handler
app.py attaches to the Flask logger.

psutil is optional. This app runs on both a Windows dev laptop and a
2-vCPU DigitalOcean droplet (raid-server) — there's no guarantee psutil is
pip-installed on both (see [[no_venv_preference]] — system Python
everywhere, no per-machine venv to pin dependencies) — so every resource
metric degrades to "not available" instead of crashing the dashboard.
"""
import platform
import sys
from datetime import datetime

from apps.config import PROJECT_ROOT
from apps.db import all_databases

try:
    import psutil
except ImportError:
    psutil = None

# Recorded at import time. apps.server_status is imported early in app.py
# (alongside the logging setup), before the app starts actually serving
# requests, so this is a good-enough proxy for "process start" without
# needing app.py to thread a start time through explicitly.
START_TIME = datetime.now()

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_PATH = LOG_DIR / "error.log"

VERSION_PATH = PROJECT_ROOT / "core" / "VERSION"


def get_app_version():
    try:
        return VERSION_PATH.read_text().strip()
    except OSError:
        return "unknown"


def _format_uptime(delta):
    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if days or hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _resource_usage():
    if psutil is None:
        return {"available": False, "cpu_percent": None, "memory_percent": None, "disk_percent": None}
    try:
        return {
            "available": True,
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage(str(PROJECT_ROOT)).percent,
        }
    except Exception:
        return {"available": False, "cpu_percent": None, "memory_percent": None, "disk_percent": None}


def _db_sizes():
    sizes = []
    for name, path in all_databases().items():
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        sizes.append({"name": name, "size_mb": round(size_bytes / (1024 * 1024), 2)})
    return sizes


def get_status():
    """Everything the admin dashboard's Server Status section needs, in one
    call — never raises, so a broken metric never takes the whole dashboard
    page down with it."""
    return {
        "app_version": get_app_version(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "started_at": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": _format_uptime(datetime.now() - START_TIME),
        "resources": _resource_usage(),
        "databases": _db_sizes(),
    }


def read_error_log(limit=50):
    """Most recent `limit` log lines, newest first. An empty list means
    nothing has been logged since this feature shipped, not that something
    is broken — the file may not exist yet on a fresh deploy."""
    if not ERROR_LOG_PATH.exists():
        return []
    try:
        lines = ERROR_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return list(reversed(lines[-limit:]))
