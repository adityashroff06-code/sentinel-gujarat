"""Environment doctor (task S0.4). Prints facts, changes nothing.

Standard library only, so it runs with any Python before the venv exists:

    python scripts/doctor.py

It reports: Python, Node/npm, ffmpeg/ffprobe (and which path answered),
GPU via nvidia-smi, whether .env exists and which variable NAMES it sets
(never values), and whether the old build is reachable. Secrets are never
read into the report: only names of variables are printed.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OLD_REPO = Path(r"D:\projects\Sentinel_Repo")
DEFAULT_FFMPEG_DIR = OLD_REPO / "tools" / "ffmpeg" / "ffmpeg-master-latest-win64-gpl" / "bin"
NODE_MIN = (20, 19)


def run_first_line(cmd: list[str]) -> str | None:
    """Return the first stdout line of *cmd*, or None if it cannot run.

    The program is resolved through :func:`shutil.which` first. On Windows
    CreateProcess does no PATHEXT lookup, so a bare ``npm`` (which ships as
    ``npm.cmd`` beside an extensionless shell script) fails to launch and the
    doctor would report an installed npm as "not found".
    """
    resolved = shutil.which(cmd[0]) or cmd[0]
    try:
        out = subprocess.run(
            [resolved, *cmd[1:]], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).strip()
    return text.splitlines()[0] if text else None


def which_ffmpeg(name: str) -> tuple[str | None, str]:
    """Resolve *name* the way backend.core.config will: env dir, then PATH,
    then the old build's portable directory. Returns (path, source)."""
    exe = name + (".exe" if os.name == "nt" else "")
    env_dir = os.environ.get("SENTINEL_FFMPEG_DIR")
    if env_dir and (Path(env_dir) / exe).exists():
        return str(Path(env_dir) / exe), "SENTINEL_FFMPEG_DIR"
    on_path = shutil.which(name)
    if on_path:
        return on_path, "PATH"
    if (DEFAULT_FFMPEG_DIR / exe).exists():
        return str(DEFAULT_FFMPEG_DIR / exe), "default (old build tools/)"
    return None, "not found"


def env_var_names(path: Path) -> list[str]:
    """Variable NAMES set in a dotenv file. Values are never returned."""
    names: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if name:
            names.append(name)
    return names


def main() -> int:
    print(f"doctor.py - {platform.system()} {platform.release()} - repo {REPO_ROOT}")
    print(f"python   : {platform.python_version()} at {sys.executable}")

    node = run_first_line(["node", "--version"])
    if node:
        digits = node.lstrip("v").split(".")
        try:
            ok = tuple(int(d) for d in digits[:2]) >= NODE_MIN
        except ValueError:
            ok = False
        print(f"node     : {node} ({'>= 20.19 ok' if ok else 'TOO OLD - need >= 20.19'})")
    else:
        print("node     : not found")
    print(f"npm      : {run_first_line(['npm', '--version']) or 'not found'}")

    for tool in ("ffmpeg", "ffprobe"):
        path, source = which_ffmpeg(tool)
        line = run_first_line([path, "-version"]) if path else None
        print(f"{tool:9}: {line or 'not found'}  [{source}]")

    gpu = run_first_line(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]
    )
    print(f"gpu      : {gpu or 'nvidia-smi not available'}")

    dotenv = REPO_ROOT / ".env"
    if dotenv.exists():
        print(f".env     : present - variable names: {', '.join(env_var_names(dotenv))}")
    else:
        print(".env     : MISSING - Adi creates it (see docs/tasks.md S0.4) before the live tasks")

    print(f"old build: {'reachable' if OLD_REPO.exists() else 'not reachable'} at {OLD_REPO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
