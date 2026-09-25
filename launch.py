#!/usr/bin/env python3
"""Sentinel launcher (task S3.4). Standard library only.

Run as plain ``python launch.py <mode>`` (Anaconda) - this file exists
before and around the venv; everything it spawns runs as
``.venv/Scripts/python`` (decision C12).

    python launch.py check         # report present / missing, change nothing
    python launch.py start         # doctor -> venv -> ffmpeg -> models -> probe
                                   #   -> seeds -> frontend -> API + worker -> browser
    python launch.py stop          # graceful (data/stop), then recorded PID trees only
    python launch.py status        # worker stats, DB counts, whether :8000 answers
    python launch.py demo          # inject the labelled demo route (demo_seed inject)
    python launch.py demo-clear    # remove only the demo rows (demo_seed purge)
    python launch.py replay-start  # second system (F9/F19/F58): mediamtx + local feeds
    python launch.py replay-stop   # stop the replay publisher tree
    python launch.py measure       # S4.1/F18 window sampler (--minutes 10)
    python launch.py harvest       # stub - cut in v2.5 (F54)

Ported from ``D:\\projects\\Sentinel_Repo\\launch.py`` (decision F52): the
resumable ffmpeg download, the venv/deps/DirectML recipe, the detached
starts with log files, the PID file and the friendly step-by-step output.
Adapted to this repo's contracts: ffmpeg resolves through
``backend.core.config.ffmpeg()`` (F25) with the fetched zip SHA-256
recorded in ``CHECKSUMS.txt``; stop is graceful first (the supervisor
watches ``data/stop``) and then kills ONLY the recorded PID trees via
psutil in the venv - never a blanket ``taskkill /IM ffmpeg.exe`` like the
old ``_kill_stray_children`` (unrelated ffmpeg processes must survive).
Output is ASCII only: the laptop console is cp1252 (doctor.py's lesson).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
DATA = ROOT / "data"
LOGS = DATA / "logs"
TOOLS_FFMPEG = ROOT / "tools" / "ffmpeg"
CHECKSUMS = ROOT / "CHECKSUMS.txt"
PIDFILE = DATA / "launcher_pids.txt"
REPLAY_PIDFILE = DATA / "replay_pids.txt"
REQ_HASH_FILE = DATA / ".req_hash"
STOP_FILE = DATA / "stop"
IS_WIN = os.name == "nt"

# The launcher cannot import backend.core.config (stdlib only, pre-venv);
# a real environment variable wins over .env there too (override=False),
# so honouring the same variable here stays consistent.
API_PORT = int(os.environ.get("SENTINEL_API_PORT", "8000"))
RTSP_PORT = int(os.environ.get("SENTINEL_RTSP_PORT", "8554"))

# F58: the transcoded sample feeds live outside both repos, never committed.
FOOTAGE_FEEDS = Path(r"D:\projects\sentinel-footage\feeds")
DEFAULT_REPLAY_NAMES = ("local01", "local02", "local03", "local04")

# Portable ffmpeg (BtbN GPL build first, gyan.dev essentials as fallback),
# fetched ONLY if backend.core.config resolves nothing (F25).
FFMPEG_URLS = [
    "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
]
DL_ATTEMPTS = 8  # per URL; every attempt resumes from the bytes on disk

USAGE = """\
usage: python launch.py <mode>
       (plain python = Anaconda; everything spawned runs as .venv/Scripts/python)

modes:
  check         report what is present / missing; change nothing
  start         doctor -> venv+deps -> ffmpeg -> models -> probe -> seeds
                -> frontend -> API + worker (detached, logs in data/logs/) -> browser
  stop          graceful stop (data/stop), then kill only the recorded PID trees
  status        worker stats highlights, database counts, whether :8000 answers
  demo          inject the labelled demo route + alerts (backend.tools.demo_seed inject)
  demo-clear    remove only the demo rows (backend.tools.demo_seed purge)
  replay-start  second system (F9/F19/F58): scripts/replay_publish.py --many, detached
  replay-stop   stop the replay publisher tree (recorded PID only)
  measure       S4.1/F18 window sampler against the RUNNING platform
                (start first, warm up >= 10 min): --minutes 10 --sample-s 5;
                writes data/measurements/<timestamp>.{json,md} (committed)
  harvest       stub - cut in v2.5 (F54)
"""


# ------------------------------------------------------------ small helpers

def say(msg: str) -> None:
    """Print one friendly line, flushed (the console is the product here)."""
    print(msg, flush=True)


def die(msg: str) -> NoReturn:
    """Stop on the first failure with the reason (old launcher's contract)."""
    say(f"[X] {msg}")
    say("fix the item above and run again")
    sys.exit(1)


def run(cmd: list[str], cwd: str | None = None) -> int:
    """Run *cmd* in the foreground, echoing it first. Returns the exit code."""
    say("    $ " + " ".join(str(c) for c in cmd))
    return subprocess.call([str(c) for c in cmd], cwd=cwd or str(ROOT))


def venv_python() -> Path | None:
    """Python inside .venv, or None (ported: venv and conda-env layouts)."""
    for rel in ("Scripts/python.exe", "python.exe", "bin/python"):
        p = VENV / rel
        if p.exists():
            return p
    return None


def _port_busy(port: int) -> bool:
    """True if something answers on 127.0.0.1:<port> (client connect only)."""
    with socket.socket() as sk:
        sk.settimeout(0.5)
        return sk.connect_ex(("127.0.0.1", port)) == 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _recorded_sha(relpath: str) -> str | None:
    """The SHA-256 CHECKSUMS.txt records for *relpath* (same three-column
    format scripts/replay_publish.py and ml.tools.fetch_models write)."""
    if not CHECKSUMS.exists():
        return None
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and not line.lstrip().startswith("#") and parts[-1] == relpath:
            return parts[0]
    return None


def _req_hash() -> str:
    """One hash over requirements.txt + requirements-dev.txt: editing either
    re-runs pip on the next start (the old bare 'ok' stamp once left a newly
    required package uninstalled forever - ported lesson)."""
    digest = hashlib.sha256()
    for name in ("requirements.txt", "requirements-dev.txt"):
        p = ROOT / name
        digest.update(name.encode("ascii"))
        digest.update(p.read_bytes() if p.exists() else b"missing")
    return digest.hexdigest()


def _read_pidfile(path: Path) -> dict[str, int]:
    """Parse '<name> <pid>' lines (bare pids tolerated). {} when absent."""
    pids: dict[str, int] = {}
    if not path.exists():
        return pids
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        parts = line.split()
        if not parts:
            continue
        if len(parts) >= 2 and parts[1].isdigit():
            pids[parts[0]] = int(parts[1])
        elif parts[0].isdigit():
            pids[f"proc{i}"] = int(parts[0])
    return pids


def _spawn_detached(args: list[str], log_path: Path) -> subprocess.Popen:
    """Start a child detached from this console, stdout+stderr APPENDED to
    *log_path* (sandbox-findings section 7: a console window swallows the
    crash trace; a log file keeps it diagnosable after the fact)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "ab")
    try:
        kwargs: dict = {}
        if IS_WIN:
            kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                       | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(  # noqa: S603 - argv list, no shell
            [str(a) for a in args], cwd=str(ROOT), stdout=log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kwargs)
    finally:
        log.close()  # the child inherited its own handle
    say(f"    started (pid {proc.pid}, log data/logs/{log_path.name}):"
        f" {' '.join(str(a) for a in args)}")
    return proc


# --- venv one-liners: psutil lives in the venv, launch.py stays stdlib ----

_WAIT_PIDS_PY = """\
import sys, time
import psutil
timeout = float(sys.argv[1])
pids = [int(a) for a in sys.argv[2:]]
deadline = time.monotonic() + timeout
while time.monotonic() < deadline and any(psutil.pid_exists(p) for p in pids):
    time.sleep(0.5)
print(' '.join(str(p) for p in pids if psutil.pid_exists(p)))
"""

# Kills each recorded pid's WHOLE TREE (worker -> its ffmpeg pulls), but only
# after checking the command line mentions this repo: a reused pid, or any
# unrelated ffmpeg, is never touched (deliberate departure from the old
# launcher's blanket `taskkill /IM ffmpeg.exe`).
_KILL_TREE_PY = """\
import sys
import psutil
repo = sys.argv[1].lower()
for arg in sys.argv[2:]:
    try:
        p = psutil.Process(int(arg))
    except (ValueError, psutil.NoSuchProcess):
        print('pid %s: already gone' % arg)
        continue
    try:
        cmdline = ' '.join(p.cmdline()).lower()
    except psutil.Error:
        cmdline = ''
    if repo not in cmdline:
        print('pid %s: not a sentinel process (pid reused?) - skipping' % arg)
        continue
    procs = p.children(recursive=True) + [p]
    for c in procs:
        try:
            c.terminate()
        except psutil.Error:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=5)
    for c in alive:
        try:
            c.kill()
        except psutil.Error:
            pass
    print('stopped pid %s (+%d children)' % (arg, len(procs) - 1))
"""

_DB_STATUS_PY = """\
from backend.core import config, db
p = config.db_path()
if not p.exists():
    print('database : not built yet (%s)' % p)
else:
    con = db.connect()
    q = lambda s: con.execute(s).fetchone()[0]
    print('cameras  : %s rows, %s active tier across %s departments' % (
        q('SELECT COUNT(*) FROM cameras'),
        q("SELECT COUNT(*) FROM cameras WHERE fps_tier='active'"),
        q("SELECT COUNT(DISTINCT department) FROM cameras"
          " WHERE fps_tier='active' AND department IS NOT NULL")))
    print('sightings: %s (%s unique plates, %s demo rows)' % (
        q('SELECT COUNT(*) FROM sightings'),
        q('SELECT COUNT(DISTINCT plate) FROM sightings'),
        q("SELECT COUNT(*) FROM sightings WHERE provenance='demo'")))
    print('events   : %s   alerts: %s   watchlist: %s' % (
        q('SELECT COUNT(*) FROM events'),
        q('SELECT COUNT(*) FROM alerts'),
        q('SELECT COUNT(*) FROM watchlist')))
    con.close()
"""


def _kill_trees(pids: list[int]) -> None:
    """Kill the recorded pids' process trees. psutil (venv) first; taskkill
    on the recorded pids only as the no-venv fallback. Never anyone else's
    ffmpeg."""
    if not pids:
        return
    vp = venv_python()
    if vp is not None:
        rc = subprocess.call([str(vp), "-c", _KILL_TREE_PY, str(ROOT),
                              *[str(p) for p in pids]], cwd=str(ROOT))
        if rc == 0:
            return
        say("[!] psutil kill pass failed - falling back to taskkill on the recorded PIDs only")
    elif IS_WIN:
        say("[!] .venv missing - falling back to taskkill on the recorded PIDs only")
    if IS_WIN:
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, check=False)
    else:
        for pid in pids:
            try:
                os.kill(pid, 15)
            except OSError as exc:
                say(f"pid {pid}: {exc}")


# ------------------------------------------------------------------ ffmpeg

def _progress(name: str, done: int, total: int) -> None:
    mb = done / 1e6
    if total > 0:
        print(f"\r    downloading {name} ... {mb:6.1f} / {total / 1e6:.0f} MB",
              end="", flush=True)
    else:
        print(f"\r    downloading {name} ... {mb:6.1f} MB", end="", flush=True)


def _download_resumable(url: str, part: Path) -> Path | None:
    """Download *url* to *part* with HTTP Range resume (ported from the old
    launcher: the first ffmpeg fetch died at 181/195 MB and resumed). Bytes
    on disk survive between attempts AND between runs; returns the finished
    file, or None when every attempt failed."""
    name = url.rsplit("/", 1)[-1]
    for attempt in range(1, DL_ATTEMPTS + 1):
        have = part.stat().st_size if part.exists() else 0
        done = have
        total = 0
        try:
            headers = {"User-Agent": "sentinel-launcher"}
            if have:
                headers["Range"] = f"bytes={have}-"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                if have and resp.status != 206:   # server ignored Range: restart
                    have = 0
                    done = 0
                total = have + int(resp.headers.get("Content-Length") or 0)
                if have:
                    say(f"    resuming {name} at {have / 1e6:.1f} MB (attempt {attempt})")
                with open(part, "ab" if have else "wb") as out:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        _progress(name, done, total)
            print(flush=True)
            if total and done < total:
                raise ConnectionError(f"short read {done}/{total}")
            final = part.with_suffix("")          # strip .part
            final.unlink(missing_ok=True)
            part.rename(final)
            return final
        except Exception as exc:  # noqa: BLE001 - retried, then reported below
            print(flush=True)
            say(f"    download interrupted ({type(exc).__name__}: {exc})"
                " - retrying in 3 s ...")
            time.sleep(3)
    say(f"    giving up on {name}")
    return None


def _local_ffmpeg_bin() -> Path | None:
    """Directory holding ffmpeg(.exe) under tools/ffmpeg, if extracted."""
    exe = "ffmpeg.exe" if IS_WIN else "ffmpeg"
    if TOOLS_FFMPEG.exists():
        for found in TOOLS_FFMPEG.rglob(exe):
            return found.parent
    return None


def _resolve_ffmpeg(vp: Path) -> str | None:
    """Ask backend.core.config (the only sanctioned resolver, F25)."""
    r = subprocess.run(
        [str(vp), "-c", "from backend.core import config; print(config.ffmpeg())"],
        cwd=str(ROOT), capture_output=True, text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _fetch_ffmpeg() -> Path:
    """Fetch/extract the portable build into tools/ffmpeg; SHA-256 of the
    zip recorded in CHECKSUMS.txt (F25). The zip stays on disk, like the
    mediamtx one, so later runs can re-verify it. Returns the bin dir."""
    existing = _local_ffmpeg_bin()
    if existing:
        say(f"    portable ffmpeg already extracted at {existing}")
        return existing
    TOOLS_FFMPEG.mkdir(parents=True, exist_ok=True)
    zips = sorted(TOOLS_FFMPEG.glob("*.zip"))
    zpath = zips[-1] if zips else None
    url_used = None
    if zpath is None:
        for url in FFMPEG_URLS:
            part = TOOLS_FFMPEG / (url.rsplit("/", 1)[-1] + ".part")
            got = _download_resumable(url, part)
            if got:
                zpath, url_used = got, url
                break
        if zpath is None:
            die("could not fetch ffmpeg (connection kept dropping).\n"
                "    Just run `python launch.py start` again - the download"
                " RESUMES where it stopped.")
    sha = _sha256(zpath)
    relpath = f"tools/ffmpeg/{zpath.name}"
    recorded = _recorded_sha(relpath)
    if recorded is None:
        with open(CHECKSUMS, "a", encoding="utf-8") as fh:
            fh.write(f"{sha}  {url_used or 'pre-existing-zip'}  {relpath}\n")
        say(f"    recorded in CHECKSUMS.txt: {sha}  {relpath}")
    elif recorded != sha:
        die(f"{relpath}: SHA-256 mismatch against CHECKSUMS.txt"
            " - the file was altered; delete it and run start again")
    say("    extracting ...")
    try:
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(TOOLS_FFMPEG)
    except zipfile.BadZipFile:
        zpath.unlink(missing_ok=True)
        die("downloaded ffmpeg archive is corrupt - run start again to re-download")
    bindir = _local_ffmpeg_bin()
    if bindir is None:
        die("ffmpeg zip extracted but no ffmpeg executable found under tools/ffmpeg")
    return bindir


def ensure_ffmpeg(vp: Path) -> str:
    """Resolve ffmpeg via config; fetch the BtbN build only if nothing
    resolves. Returns the resolved path."""
    say("[3/9] resolving ffmpeg through backend.core.config (F25) ...")
    path = _resolve_ffmpeg(vp)
    if path:
        say(f"    ffmpeg: {path}")
        return path
    say("    nothing resolves (SENTINEL_FFMPEG_DIR -> PATH)"
        " - fetching the portable build into tools/ffmpeg ...")
    bindir = _fetch_ffmpeg()
    # config reads the environment at call time (override=False beats .env),
    # so every child of THIS run resolves the fetched copy. Permanence needs
    # SENTINEL_FFMPEG_DIR in .env - Adi owns that file.
    os.environ["SENTINEL_FFMPEG_DIR"] = str(bindir)
    say(f"    SENTINEL_FFMPEG_DIR={bindir} (this run only;"
        " put it in .env to make it permanent - Adi owns .env)")
    path = _resolve_ffmpeg(vp)
    if not path:
        die("ffmpeg fetched but still does not resolve - check tools/ffmpeg contents")
    say(f"    ffmpeg: {path}")
    return path


# ------------------------------------------------------------- start steps

def ensure_venv_and_deps() -> Path:
    """Create .venv if missing; (re)install the pinned deps when the hash of
    requirements.txt + requirements-dev.txt (data/.req_hash) changes."""
    vp = venv_python()
    if vp is None:
        say("[2/9] creating .venv (first run) ...")
        if run([sys.executable, "-m", "venv", str(VENV)]) != 0:
            die("could not create .venv")
        vp = venv_python()
        if vp is None:
            die(".venv was created but no python found inside it")
    else:
        say(f"[2/9] .venv present ({vp})")
    want = _req_hash()
    have = (REQ_HASH_FILE.read_text(encoding="utf-8").strip()
            if REQ_HASH_FILE.exists() else "")
    if want != have:
        say("    requirements changed (or first install)"
            " - installing the pinned set (F37; first run takes minutes) ...")
        run([str(vp), "-m", "pip", "install", "--upgrade", "pip"])
        if run([str(vp), "-m", "pip", "install", "-r", "requirements.txt",
                "-r", "requirements-dev.txt"]) != 0:
            die("pip install failed (network?) - run start again")
        DATA.mkdir(exist_ok=True)
        REQ_HASH_FILE.write_text(want + "\n", encoding="utf-8")
        say("    deps installed; hash recorded in data/.req_hash")
    else:
        say("    pinned deps up to date (data/.req_hash matches)")
    return vp


def _directml_pin() -> str:
    """The exact onnxruntime-directml pin from requirements.txt (F37)."""
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        spec = line.split(";")[0].split("#")[0].strip()
        if spec.lower().startswith("onnxruntime-directml=="):
            return spec
    return "onnxruntime-directml"


def ensure_directml(vp: Path) -> None:
    """Repair the GPU provider if a plain `onnxruntime` install clobbered
    onnxruntime-directml (sandbox-findings section 7: the two wheels unpack
    over the same folder and the last one silently wins)."""
    if not IS_WIN:
        return
    say("    onnxruntime-directml guard (F37) ...")
    r = subprocess.run([str(vp), "-m", "pip", "show", "onnxruntime"],
                       cwd=str(ROOT), capture_output=True, text=True, check=False)
    if r.returncode == 0:
        say("[!] plain onnxruntime found in .venv - it clobbers the DirectML"
            " build; repairing ...")
        run([str(vp), "-m", "pip", "uninstall", "-y", "onnxruntime"])
        # --force-reinstall --no-deps: the wheels share files, so pip may
        # think directml is already satisfied right after the uninstall
        # broke it (ported fix).
        if run([str(vp), "-m", "pip", "install", "--force-reinstall",
                "--no-deps", _directml_pin()]) != 0:
            die("could not reinstall onnxruntime-directml")
    probe = ("import onnxruntime as o, sys; "
             "sys.exit(0 if 'DmlExecutionProvider' in o.get_available_providers() else 1)")
    if subprocess.run([str(vp), "-c", probe], cwd=str(ROOT),
                      capture_output=True, check=False).returncode != 0:
        say("[!] DmlExecutionProvider not available - the detector will run"
            " on CPU (~10x slower, sandbox-findings section 7); continuing")
    else:
        say("    DirectML provider present")


def ensure_models(vp: Path) -> None:
    say("[4/9] model weights (fetch once + SHA-256 verify every run, F25) ...")
    code = "from ml.tools import fetch_models; print(fetch_models.ensure())"
    r = subprocess.run([str(vp), "-c", code], cwd=str(ROOT),
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        die("model fetch/verify failed (see above)")
    lines = r.stdout.strip().splitlines()
    say(f"    {lines[-1] if lines else 'ok'}")


def ensure_probe(vp: Path) -> None:
    """Probe on first run only. NEVER fails start: with the sandbox down the
    local feeds keep the platform demonstrable (task S3.4 / F58)."""
    say("[5/9] camera grid probe (first run only) ...")
    if sorted(DATA.glob("probe_results*.json")):
        say("    probe results present - skipping"
            " (delete data/probe_results_*.json to re-probe)")
        return
    say("    no probe results - probing every catalogue camera (2-4 min) ...")
    if run([str(vp), "-m", "backend.tools.probe"]) != 0:
        say("[!] probe failed (sandbox unreachable?) - continuing:"
            " the local feeds keep the platform demonstrable (F58)")


def ensure_seeds(vp: Path) -> None:
    say("[6/9] seeding the camera registry (every start, F35) ...")
    if run([str(vp), "-m", "backend.tools.seed_registry"]) != 0:
        die("registry seeding failed")
    say("[7/9] seeding the watchlist (every start, C11"
        " - it must exist before the workers load their cache) ...")
    if run([str(vp), "-m", "backend.tools.seed_watchlist"]) != 0:
        die("watchlist seeding failed")


def ensure_frontend() -> None:
    say("[8/9] frontend build ...")
    if (ROOT / "frontend" / "dist" / "index.html").exists():
        say("    frontend/dist present - skipping")
        return
    npm = shutil.which("npm")
    if not npm:
        die("frontend/dist missing and npm is not installed (need Node 20.19+)")
    prefix = str(ROOT / "frontend")
    if not (ROOT / "frontend" / "node_modules").exists():
        say("    node_modules missing - npm install (first run, minutes) ...")
        if run([npm, "--prefix", prefix, "install"]) != 0:
            die("npm install failed")
    say("    npm run build ...")
    if run([npm, "--prefix", prefix, "run", "build"]) != 0:
        die("frontend build failed")


def _fail_start(reason: str) -> NoReturn:
    say(f"[X] {reason}")
    say("    read the reason in data/logs/api.launcher.log, fix it, run again")
    stop()  # kills what this start recorded, removes the PID file
    sys.exit(1)


def start() -> int:
    say("[1/9] environment doctor (scripts/doctor.py) ...")
    if subprocess.call([sys.executable, str(ROOT / "scripts" / "doctor.py")],
                       cwd=str(ROOT)) != 0:
        die("scripts/doctor.py failed")
    vp = ensure_venv_and_deps()
    ensure_directml(vp)
    ensure_ffmpeg(vp)
    ensure_models(vp)
    ensure_probe(vp)
    ensure_seeds(vp)
    ensure_frontend()

    say("[9/9] starting the platform ...")
    if PIDFILE.exists():
        say("    a previous instance is recorded - stopping it first"
            " (one stream pull per camera, root rule 2) ...")
        stop()
        time.sleep(2)
    if _port_busy(API_PORT):
        die(f"port {API_PORT} is already in use - stop whatever holds it and run again")
    STOP_FILE.unlink(missing_ok=True)  # a stale stop file would kill the worker at birth
    LOGS.mkdir(parents=True, exist_ok=True)
    api = _spawn_detached([str(vp), "-m", "backend.app"], LOGS / "api.launcher.log")
    worker = _spawn_detached([str(vp), "-m", "ml"], LOGS / "worker.launcher.log")
    DATA.mkdir(exist_ok=True)
    PIDFILE.write_text(f"api {api.pid}\nworker {worker.pid}\n", encoding="utf-8")
    say(f"    PIDs recorded in data/launcher_pids.txt (api {api.pid}, worker {worker.pid})")
    say(f"    waiting up to 30 s for the API to bind 127.0.0.1:{API_PORT} ...")
    for _ in range(30):
        if _port_busy(API_PORT):
            break
        if api.poll() is not None:
            _fail_start(f"the API exited rc={api.returncode} before binding :{API_PORT}")
        time.sleep(1)
    else:
        _fail_start(f"the API did not open 127.0.0.1:{API_PORT} within 30 s")
    url = f"http://127.0.0.1:{API_PORT}/"
    say(f"    opening {url} in the default browser ...")
    webbrowser.open(url)
    say("")
    say("Sentinel is running.")
    say(f"  dashboard : {url}  (sign in; nothing is reachable without it, rule 11)")
    say("  status    : python launch.py status")
    say("  demo      : python launch.py demo      (labelled demo route + alerts)")
    say("  replay    : python launch.py replay-start   (second system, F9/F19)")
    say("  stop      : python launch.py stop")
    return 0


# ------------------------------------------------------------------- modes

def check() -> int:
    """Report present / missing. Changes nothing on disk."""
    say(f"launch.py check - repo {ROOT}")
    rc = subprocess.call([sys.executable, str(ROOT / "scripts" / "doctor.py")],
                         cwd=str(ROOT))
    if rc != 0:
        say(f"[X] scripts/doctor.py exited rc={rc}")
    vp = venv_python()
    say(f".venv    : {('present at ' + str(vp)) if vp else 'MISSING (created on start)'}")
    if vp:
        fresh = (REQ_HASH_FILE.exists()
                 and REQ_HASH_FILE.read_text(encoding="utf-8").strip() == _req_hash())
        say("deps     : " + ("pinned set installed (data/.req_hash matches)" if fresh
                             else "STALE or never installed (start reinstalls)"))
    else:
        say("deps     : unknown until .venv exists")
    mtx = ROOT / "tools" / "mediamtx" / ("mediamtx.exe" if IS_WIN else "mediamtx")
    say(f"mediamtx : {'fetched' if mtx.exists() else 'MISSING - python scripts/replay_publish.py --fetch'}")
    say(f"model    : {'present' if (ROOT / 'models' / 'yolox_s.onnx').exists() else 'MISSING (fetched on start)'}"
        " (models/yolox_s.onnx)")
    say(f"frontend : {'built (frontend/dist)' if (ROOT / 'frontend' / 'dist' / 'index.html').exists() else 'NOT BUILT (built on start)'}")
    say(f"database : {'present' if (DATA / 'sentinel.db').exists() else 'not built yet (created on start)'}"
        " (data/sentinel.db)")
    probes = sorted(DATA.glob("probe_results*.json"))
    say(f"probe    : {probes[-1].name if probes else 'never run (runs on first start)'}")
    feeds = (sorted(FOOTAGE_FEEDS.glob("local*.mp4"))
             if FOOTAGE_FEEDS.exists() else [])
    say(f"feeds    : {len(feeds)} default replay feeds under {FOOTAGE_FEEDS}")
    say(f"pids     : {'recorded (data/launcher_pids.txt)' if PIDFILE.exists() else 'none recorded'};"
        f" api port {API_PORT} {'ANSWERING' if _port_busy(API_PORT) else 'closed'}")
    return 0 if rc == 0 else 1


def stop() -> int:
    """Graceful first (data/stop; the supervisor watches it), then kill only
    the recorded PID trees. Unrelated ffmpeg processes are never touched."""
    if not PIDFILE.exists():
        say("nothing recorded as running (no data/launcher_pids.txt)")
        STOP_FILE.unlink(missing_ok=True)
        return 0
    pids = _read_pidfile(PIDFILE)
    DATA.mkdir(exist_ok=True)
    STOP_FILE.write_text("stop requested by launch.py\n", encoding="utf-8")
    say("data/stop written - waiting up to 10 s for the worker to exit gracefully ...")
    vp = venv_python()
    worker_pids = [pid for name, pid in pids.items() if name.startswith("worker")]
    if vp is not None and worker_pids:
        subprocess.run([str(vp), "-c", _WAIT_PIDS_PY, "10",
                        *[str(p) for p in worker_pids]],
                       cwd=str(ROOT), capture_output=True, check=False)
    elif worker_pids:
        time.sleep(10)  # no venv to poll liveness with; grant the full window
    _kill_trees(list(pids.values()))
    PIDFILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)
    say("stopped - only the recorded PID trees were touched"
        " (unrelated ffmpeg never killed)")
    return 0


def _stats_age_s(written_at: str) -> float | None:
    try:
        ts = datetime.fromisoformat(written_at)
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds()


def _stats_highlights() -> None:
    st = DATA / "worker_stats.json"
    if not st.exists():
        say("workers  : never started (no data/worker_stats.json)")
        return
    try:
        d = json.loads(st.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        say(f"workers  : stats file unreadable ({type(exc).__name__})")
        return
    age = _stats_age_s(d.get("written_at", ""))
    if age is not None and age < 30:
        head = "live"
    elif age is not None:
        head = f"NOT RUNNING (stats {age / 60:.0f} min old, {d.get('written_at')})"
    else:
        head = "age unknown"
    say(f"workers  : {head}")
    say(f"           uptime {d.get('uptime_s', '?')} s, restarts {d.get('restarts', '?')},"
        f" rss {d.get('rss_mb', '?')} MB, fps {d.get('fps_sustained', '?')}")
    say(f"           frames {d.get('frames', '?')}, inferred {d.get('inferred', '?')},"
        f" detections {d.get('detections', '?')}, sightings {d.get('sightings', '?')},"
        f" alerts {d.get('alerts', '?')}")
    cams = d.get("cameras") or {}
    for cid, w in sorted(cams.items()):
        say(f"           {cid}: alive={w.get('alive')} frames={w.get('frames')}"
            f" detections={w.get('detections')} sightings={w.get('sightings')}"
            f" alerts={w.get('alerts')}")
    if not cams:
        say("           (no per-camera rows)")


def _db_counts() -> None:
    vp = venv_python()
    if vp is None:
        say("database : counts need .venv (run `python launch.py start` once)")
        return
    r = subprocess.run([str(vp), "-c", _DB_STATUS_PY], cwd=str(ROOT),
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()
        say(f"database : query failed ({tail[-1] if tail else 'no output'})")
        return
    for line in r.stdout.strip().splitlines():
        say(line)


def _api_line() -> None:
    if not _port_busy(API_PORT):
        say(f"api      : not running (127.0.0.1:{API_PORT} closed)")
        return
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{API_PORT}/api/health", timeout=3) as resp:
            say(f"api      : answering on :{API_PORT} (/api/health {resp.status})")
    except Exception as exc:  # noqa: BLE001 - reported, status stays best-effort
        say(f"api      : port {API_PORT} open but /api/health failed"
            f" ({type(exc).__name__})")


def status() -> int:
    _stats_highlights()
    _db_counts()
    _api_line()
    say(f"pids     : launcher {'recorded' if PIDFILE.exists() else 'none'};"
        f" replay {'recorded' if REPLAY_PIDFILE.exists() else 'none'}"
        " (data/launcher_pids.txt, data/replay_pids.txt)")
    return 0


def demo(extra: list[str], clear: bool = False) -> int:
    """`.venv` python -m backend.tools.demo_seed inject|purge (S3.1a's
    seeder; provenance=demo, labelled everywhere - root rule 12)."""
    vp = venv_python()
    if vp is None:
        die("no .venv yet - run `python launch.py start` once first")
    if not clear and not _port_busy(API_PORT):
        say(f"note: the API is not answering on :{API_PORT} - rows will be"
            " seeded, but start the platform to see them live")
    action = "purge" if clear else "inject"
    if run([str(vp), "-m", "backend.tools.demo_seed", action, *extra]) != 0:
        die(f"demo_seed {action} failed")
    if not clear:
        say("")
        say("demo route injected (provenance=demo, labelled on every screen):")
        say(f"  open http://127.0.0.1:{API_PORT}/ -> Route, search GJ01AB1234")
        say("  remove with: python launch.py demo-clear (demo rows only)")
    return 0


def _measure_cmd(vp: Path, extra: list[str]) -> list[str]:
    """The argv measure spawns (split out so a test can assert it)."""
    return [str(vp), "-m", "ml.tools.measure_run", *extra]


def measure(extra: list[str]) -> int:
    """S4.1's F18 window sampler, in the foreground (its countdown and
    the final table are the product). Run it against a platform that
    `launch.py start` brought up >= 10 min ago (the warm-up); pass
    `--minutes N`, `--sample-s N` or `--allow-cold` through."""
    vp = venv_python()
    if vp is None:
        die("no .venv yet - run `python launch.py start` once first")
    if not PIDFILE.exists():
        die("no running platform recorded (data/launcher_pids.txt)"
            " - python launch.py start first, warm up >= 10 min, then measure")
    return run(_measure_cmd(vp, extra))


def harvest() -> int:
    say("harvest: cut in v2.5 (F54) - own footage supplies the real route")
    return 0


# ---------------------------------------------------- second system (F9/F19)

def _default_replay_specs() -> list[str]:
    """The F58 defaults: local01..local04 from the feeds folder, looped
    (they are loopable WALL feeds - test DB only). Missing files are skipped
    with a warning (partial coverage beats none, root section 9); none at
    all is an error. A filmed-route run instead passes explicit NAME=PATH
    pairs plus --offsets and NO --loop (F56: real gaps, real speeds)."""
    specs: list[str] = []
    for name in DEFAULT_REPLAY_NAMES:
        path = FOOTAGE_FEEDS / f"{name}.mp4"
        if path.exists():
            specs.append(f"{name}={path}")
        else:
            say(f"[!] {path} missing - skipping {name}")
    if not specs:
        die(f"no default feeds found under {FOOTAGE_FEEDS}"
            " - pass NAME=PATH pairs explicitly")
    specs.append("--loop")
    return specs


def _replay_cmd(vp: Path, specs: list[str]) -> list[str]:
    """The argv replay-start spawns (split out so a test can assert it)."""
    return [str(vp), str(ROOT / "scripts" / "replay_publish.py"), "--many", *specs]


def replay_start(extra: list[str]) -> int:
    vp = venv_python()
    if vp is None:
        die("no .venv yet - run `python launch.py start` once first")
    if REPLAY_PIDFILE.exists():
        die("a replay publisher is already recorded (data/replay_pids.txt)"
            " - python launch.py replay-stop first")
    mtx = ROOT / "tools" / "mediamtx" / ("mediamtx.exe" if IS_WIN else "mediamtx")
    if not mtx.exists():
        die("mediamtx is not fetched - run: python scripts/replay_publish.py --fetch")
    if extra:
        specs = extra
        say("replay-start (explicit feeds): " + " ".join(specs))
    else:
        specs = _default_replay_specs()
        say("replay-start (F58 defaults - loopable wall feeds):")
        for spec in specs:
            say(f"    {spec}")
        say("    a filmed-route run passes NAME=PATH pairs plus --offsets"
            " and NO --loop instead (F56)")
    if "--loop" in specs:
        say("[!] --loop repeats every clip: wall/soak tests on a TEST DB only"
            " (F56/F58) - never a run that feeds a route")
    LOGS.mkdir(parents=True, exist_ok=True)
    proc = _spawn_detached(_replay_cmd(vp, specs), LOGS / "replay.launcher.log")
    time.sleep(2)  # a checksum refusal or a held port dies immediately
    if proc.poll() is not None:
        die(f"replay publisher exited rc={proc.returncode} at once"
            " - see data/logs/replay.launcher.log")
    DATA.mkdir(exist_ok=True)
    REPLAY_PIDFILE.write_text(f"replay {proc.pid}\n", encoding="utf-8")
    names = [s.split("=", 1)[0] for s in specs if "=" in s and not s.startswith("-")]
    say(f"replay publisher running (pid {proc.pid} -> data/replay_pids.txt); streams:")
    for name in names:
        say(f"    rtsp://127.0.0.1:{RTSP_PORT}/stream/{name}")
    say("  onboard during the demo through the Cameras form; for tests:")
    say("    .venv/Scripts/python -m backend.tools.seed_registry --add"
        f" local01 <department> rtsp://127.0.0.1:{RTSP_PORT}/stream/local01 --tier active")
    say("  stop with: python launch.py replay-stop")
    return 0


def replay_stop() -> int:
    if not REPLAY_PIDFILE.exists():
        say("no replay publisher recorded (data/replay_pids.txt missing)")
        return 0
    pids = _read_pidfile(REPLAY_PIDFILE)
    _kill_trees(list(pids.values()))
    REPLAY_PIDFILE.unlink(missing_ok=True)
    say("replay publisher stopped (its mediamtx + ffmpeg children only)")
    return 0


# -------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    """Dispatch one mode; returns the exit code (2 = usage error)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        say(USAGE)
        return 2
    mode, extra = argv[0].lower(), argv[1:]
    plain = {"check": check, "start": start, "stop": stop, "status": status,
             "harvest": harvest, "replay-stop": replay_stop}
    if mode in plain:
        if extra:
            say(f"launch.py {mode} takes no arguments")
            say(USAGE)
            return 2
        return plain[mode]()
    if mode == "measure":
        return measure(extra)
    if mode == "demo":
        return demo(extra)
    if mode == "demo-clear":
        return demo(extra, clear=True)
    if mode == "replay-start":
        return replay_start(extra)
    say(f"unknown mode: {mode}")
    say(USAGE)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
