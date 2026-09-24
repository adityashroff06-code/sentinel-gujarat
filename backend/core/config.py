"""Configuration — one place (root CLAUDE.md §7).

Reads the repo-root ``.env`` through python-dotenv with ``override=False``,
so a real environment variable always wins (tests set ``SENTINEL_DB`` and the
API keys in ``tests/conftest.py`` and never read ``.env``). Every variable
documented in ``.env.example`` is read here with the same default.

Secrets never leave this module unmasked: :func:`masked` scrubs any
``scheme://user:pass@`` userinfo and the configured email/password (raw and
percent-encoded) from any string that is logged, stored or displayed.
"""

from __future__ import annotations

import os
import re
import shutil
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# override=False: an existing environment variable beats the .env file.
load_dotenv(REPO_ROOT / ".env", override=False)

_DEFAULT_FFMPEG_DIR = r"D:\projects\Sentinel_Repo\tools\ffmpeg\ffmpeg-master-latest-win64-gpl\bin"

_DEFAULTS: dict[str, str] = {
    "SENTINEL_EMAIL": "",
    "SENTINEL_PASSWORD": "",
    "SENTINEL_API_KEY_ADMIN": "",
    "SENTINEL_API_KEY_VIEWER": "",
    "SENTINEL_CDN": "https://cctv.corp8.cloud",
    "SENTINEL_CATALOGUE_URL": "",
    "SENTINEL_STREAM_IP": "103.250.160.189",
    "SENTINEL_RTSP_PORT": "8554",
    "SENTINEL_WHEP_PORT": "8889",
    "SENTINEL_DB": "data/sentinel.db",
    "SENTINEL_ACTIVE_CAMERAS": "6",
    "SENTINEL_INFER_FPS": "3",
    "SENTINEL_API_PORT": "8000",
    "SENTINEL_LOG_LEVEL": "INFO",
    "SENTINEL_LOG_DIR": "data/logs",
    "SENTINEL_FFMPEG_DIR": _DEFAULT_FFMPEG_DIR,
    "SENTINEL_STALL_TIMEOUT_S": "20",
    "SENTINEL_CAPTION_BAND": "0.05",
    "SENTINEL_RECORDING_EPOCH": "2026-06-13T21:00:00+05:30",
    "SENTINEL_LOOP_SECONDS": "43200",
    "SENTINEL_PLAYBACK_OFFSET_S": "0",
    "SENTINEL_ALERT_ON_FUZZY": "false",
    "SENTINEL_HEALTH_INTERVAL_S": "300",
    "SENTINEL_MOTION_MIN_RATIO": "0.002",
    "SENTINEL_DETECT_CONF": "0.4",
    "SENTINEL_SESSION_TTL_H": "8",
    "SENTINEL_PUBLIC_HOST": "",
}


def get(name: str) -> str:
    """Return the configured value of *name* (environment first, then the
    documented default). Raises ``KeyError`` for an undocumented name."""
    return os.environ.get(name, _DEFAULTS[name])


def _path(name: str) -> Path:
    p = Path(get(name))
    return p if p.is_absolute() else REPO_ROOT / p


# --- typed accessors (read the environment at call time, so tests can
# --- repoint them without re-importing) -----------------------------------

def email() -> str: return get("SENTINEL_EMAIL")
def password() -> str: return get("SENTINEL_PASSWORD")
def api_key_admin() -> str: return get("SENTINEL_API_KEY_ADMIN")
def api_key_viewer() -> str: return get("SENTINEL_API_KEY_VIEWER")
def cdn() -> str: return get("SENTINEL_CDN").rstrip("/")
def catalogue_url() -> str: return get("SENTINEL_CATALOGUE_URL").strip()
def stream_ip() -> str: return get("SENTINEL_STREAM_IP")
def rtsp_port() -> int: return int(get("SENTINEL_RTSP_PORT"))
def whep_port() -> int: return int(get("SENTINEL_WHEP_PORT"))
def db_path() -> Path: return _path("SENTINEL_DB")
def active_cameras() -> int: return int(get("SENTINEL_ACTIVE_CAMERAS"))
def infer_fps() -> float: return float(get("SENTINEL_INFER_FPS"))
def api_port() -> int: return int(get("SENTINEL_API_PORT"))
def log_level() -> str: return get("SENTINEL_LOG_LEVEL").upper()
def log_dir() -> Path: return _path("SENTINEL_LOG_DIR")
def stall_timeout_s() -> float: return float(get("SENTINEL_STALL_TIMEOUT_S"))
def caption_band() -> float: return float(get("SENTINEL_CAPTION_BAND"))
def recording_epoch() -> str: return get("SENTINEL_RECORDING_EPOCH")
def loop_seconds() -> int: return int(get("SENTINEL_LOOP_SECONDS"))
def playback_offset_s() -> float: return float(get("SENTINEL_PLAYBACK_OFFSET_S"))
def health_interval_s() -> float: return float(get("SENTINEL_HEALTH_INTERVAL_S"))
def motion_min_ratio() -> float: return float(get("SENTINEL_MOTION_MIN_RATIO"))
def detect_conf() -> float: return float(get("SENTINEL_DETECT_CONF"))
def session_ttl_h() -> float: return float(get("SENTINEL_SESSION_TTL_H"))
def public_host() -> str: return get("SENTINEL_PUBLIC_HOST").strip()


def alert_on_fuzzy() -> bool:
    return get("SENTINEL_ALERT_ON_FUZZY").strip().lower() in ("1", "true", "yes", "on")


# --- external tools (decision F25) ----------------------------------------

def _tool(name: str) -> str:
    """Resolve *name* (ffmpeg/ffprobe): SENTINEL_FFMPEG_DIR → PATH → error."""
    exe = name + (".exe" if os.name == "nt" else "")
    candidate = Path(get("SENTINEL_FFMPEG_DIR")) / exe
    if candidate.is_file():
        return str(candidate)
    on_path = shutil.which(name)
    if on_path:
        return on_path
    raise RuntimeError(
        f"{name} not found: set SENTINEL_FFMPEG_DIR to the directory holding "
        f"{exe}, or put {name} on PATH (docs/decisions.md F25)"
    )


def ffmpeg() -> str:
    """Path to the ffmpeg executable (never call ffmpeg any other way)."""
    return _tool("ffmpeg")


def ffprobe() -> str:
    """Path to the ffprobe executable."""
    return _tool("ffprobe")


# --- masking (root CLAUDE.md rule 1) --------------------------------------

_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@")


def masked(s: str) -> str:
    """Scrub credentials from *s* for display, logs and storage.

    Any ``scheme://user:pass@`` userinfo becomes ``scheme://<email>:***@``;
    additionally the configured email and password are replaced wherever they
    appear, raw or percent-encoded.
    """
    out = _USERINFO.sub(r"\1<email>:***@", s)
    for secret, repl in ((password(), "***"), (email(), "<email>")):
        if not secret:
            continue
        for form in {secret, urllib.parse.quote(secret, safe=""), urllib.parse.quote_plus(secret)}:
            if form:
                out = out.replace(form, repl)
    return out
