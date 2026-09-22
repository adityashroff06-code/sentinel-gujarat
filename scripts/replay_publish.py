"""Local RTSP publisher for tests and the second system (tasks S2.2, S3.4).

Two jobs, one file:

    python scripts/replay_publish.py --fetch
        Download the MIT-licensed mediamtx Windows release zip (latest
        v1.x) into tools/mediamtx/, record version URL and SHA-256 in the
        root CHECKSUMS.txt (decision F25), and unpack the executable.
        The zip stays on disk so every later run can re-verify it.

    python scripts/replay_publish.py [--file F] [--name N] [--port P]
        Verify the recorded checksum, start mediamtx bound to
        127.0.0.1:<port> only (root rule 11: mediamtx never leaves
        localhost), and loop-publish a local file over RTSP at
        rtsp://127.0.0.1:<port>/stream/<name> until Ctrl+C.

Importable by tests (by path, like scripts/doctor.py) for the S2.2
harness fixture: ``start_mediamtx()`` / ``publish()`` return the Popen
handles and the caller owns their lifetime. Reused by S3.4's launcher
for the second-system demo feeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.core import config  # noqa: E402  (path bootstrap above)

TOOLS_DIR = REPO_ROOT / "tools" / "mediamtx"
CHECKSUMS = REPO_ROOT / "CHECKSUMS.txt"
RELEASES_LATEST = "https://api.github.com/repos/bluenviron/mediamtx/releases/latest"
DEFAULT_PORT = 8554
DEFAULT_CLIP = REPO_ROOT / "tests" / "fixtures" / "synthetic_60s.mp4"

# ponytail: Windows-amd64 asset only - this laptop is the only build host;
# extend the asset filter if a Linux runner ever needs it.
ASSET_SUFFIX = "windows_amd64.zip"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mediamtx_exe() -> Path:
    return TOOLS_DIR / ("mediamtx.exe" if sys.platform == "win32" else "mediamtx")


def _zip_on_disk() -> Path | None:
    zips = sorted(TOOLS_DIR.glob("mediamtx_*.zip"))
    return zips[-1] if zips else None


def _recorded_sha(relpath: str, checksums: Path | None = None) -> str | None:
    """The sha256 recorded for *relpath* (last whitespace token per line)."""
    checksums = checksums or CHECKSUMS  # resolved at call time, not def time
    if not checksums.exists():
        return None
    for line in checksums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and not line.lstrip().startswith("#") and parts[-1] == relpath:
            return parts[0]
    return None


def verify_zip(zip_path: Path | None = None, checksums: Path | None = None) -> Path:
    """Verify the downloaded mediamtx zip against CHECKSUMS.txt.

    Returns the zip path; raises SystemExit with a clear message when the
    zip is missing, unrecorded, or tampered (F25: verified on every run).
    """
    zip_path = zip_path or _zip_on_disk()
    if zip_path is None or not zip_path.exists():
        raise SystemExit(
            "mediamtx is not fetched: run  python scripts/replay_publish.py --fetch"
        )
    relpath = zip_path.relative_to(REPO_ROOT).as_posix()
    recorded = _recorded_sha(relpath, checksums)
    if recorded is None:
        raise SystemExit(f"{relpath}: no CHECKSUMS.txt entry - refetch with --fetch")
    actual = sha256_file(zip_path)
    if actual != recorded:
        raise SystemExit(
            f"{relpath}: SHA-256 mismatch (recorded {recorded[:12]}..., "
            f"actual {actual[:12]}...) - the file was altered; refusing to run it"
        )
    return zip_path


def fetch() -> None:
    """Download the latest v1.x mediamtx Windows zip and record it."""
    req = urllib.request.Request(RELEASES_LATEST, headers={"User-Agent": "sentinel-build"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        release = json.load(resp)
    tag = release["tag_name"]
    if not tag.startswith("v1."):
        raise SystemExit(f"latest release is {tag}, not a v1.x - task S2.2 pins v1.x")
    asset = next(
        (a for a in release["assets"] if a["name"].endswith(ASSET_SUFFIX)), None
    )
    if asset is None:
        raise SystemExit(f"{tag}: no {ASSET_SUFFIX} asset found")

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TOOLS_DIR / asset["name"]
    url = asset["browser_download_url"]
    print(f"downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "sentinel-build"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(zip_path, "wb") as out:
        shutil.copyfileobj(resp, out)
    digest = sha256_file(zip_path)

    relpath = zip_path.relative_to(REPO_ROOT).as_posix()
    if _recorded_sha(relpath) is None:
        with open(CHECKSUMS, "a", encoding="utf-8") as fh:
            fh.write(f"{digest}  {url}  {relpath}\n")
        print(f"recorded in CHECKSUMS.txt: {digest}  {relpath}")
    else:
        verify_zip(zip_path)  # a re-download must match what was recorded
        print(f"already recorded; verified: {digest[:12]}...")

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(TOOLS_DIR)
    print(f"unpacked {tag} into {TOOLS_DIR}")


def _wait_port(port: int, timeout_s: float = 10.0,
               proc: subprocess.Popen | None = None) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        # A dead child means it lost the bind (e.g. the port is already held
        # by a leaked mediamtx). Without this check the connect below would
        # succeed against that STALE server and mask the failure - the source
        # then pulls 0 frames from a publisher-less server until it times out.
        if proc is not None and proc.poll() is not None:
            raise SystemExit(
                f"mediamtx exited rc={proc.returncode} before binding "
                f"127.0.0.1:{port} (port already in use?) - see data/logs/mediamtx.log"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise SystemExit(f"mediamtx did not open 127.0.0.1:{port} within {timeout_s:.0f}s")


def start_mediamtx(port: int = DEFAULT_PORT) -> subprocess.Popen:
    """Verify the checksum, then start mediamtx on 127.0.0.1:<port> only.

    Everything but RTSP is disabled through mediamtx's MTX_* environment
    overrides, so no config file of ours to drift; the bundled default
    mediamtx.yml supplies the rest. Caller owns the returned handle.
    """
    verify_zip()
    exe = mediamtx_exe()
    if not exe.exists():
        raise SystemExit(f"{exe} missing although the zip verified - refetch")
    log_dir = config.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "mediamtx.log", "ab")
    import os

    env = {
        **os.environ,
        "MTX_RTSPADDRESS": f"127.0.0.1:{port}",
        "MTX_RTSPTRANSPORTS": "tcp",  # env lists are comma-separated, no brackets
        # A `-re`-paced publisher can stall past the 10 s default under load
        # (full test suite), and mediamtx then drops it, 404-ing every reader.
        # 30 s tolerates the lag so the local stream stays up for the module.
        "MTX_READTIMEOUT": "30s", "MTX_WRITETIMEOUT": "30s",
        "MTX_RTMP": "no", "MTX_HLS": "no", "MTX_WEBRTC": "no", "MTX_SRT": "no",
        "MTX_API": "no", "MTX_METRICS": "no", "MTX_PPROF": "no",
        "MTX_PLAYBACK": "no",
        # MoQ (new in 1.21) binds 0.0.0.0:8892/:8893 by default - it is what
        # made Windows Firewall prompt; nothing leaves loopback (rule 11).
        "MTX_MOQ": "no",
    }
    proc = subprocess.Popen(
        [str(exe), str(TOOLS_DIR / "mediamtx.yml")],
        cwd=str(TOOLS_DIR), env=env, stdout=log, stderr=log,
    )
    try:
        _wait_port(port, proc=proc)
    except SystemExit:
        proc.kill()
        raise
    return proc


def publish(file: str | Path, name: str, port: int = DEFAULT_PORT) -> subprocess.Popen:
    """Loop-publish *file* at rtsp://127.0.0.1:<port>/stream/<name>.

    ``-g 50`` forces a keyframe every 2 s at 25 fps so the consumer's
    stream-copied HLS tee can actually cut 2 s segments (hls_time 2 splits
    on keyframes; libx264's default 250-frame GOP would give 10 s ones).
    Caller owns the returned handle.
    """
    log_dir = config.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "replay_publish.log", "ab")
    cmd = [
        config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
        "-re", "-stream_loop", "-1", "-i", str(file),
        "-c:v", "libx264", "-preset", "veryfast", "-g", "50", "-keyint_min", "50",
        "-an", "-f", "rtsp", "-rtsp_transport", "tcp",
        f"rtsp://127.0.0.1:{port}/stream/{name}",
    ]
    return subprocess.Popen(cmd, stdout=log, stderr=log)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true",
                        help="download mediamtx and record its checksum")
    parser.add_argument("--file", default=str(DEFAULT_CLIP))
    parser.add_argument("--name", default="test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if args.fetch:
        fetch()
        return 0

    if not Path(args.file).exists():
        raise SystemExit(f"{args.file}: no such file")
    server = start_mediamtx(args.port)
    publisher = None
    try:
        publisher = publish(args.file, args.name, args.port)
        print(
            f"publishing {args.file} at rtsp://127.0.0.1:{args.port}/stream/"
            f"{args.name} - Ctrl+C to stop", flush=True,
        )
        while True:
            time.sleep(1)
            for proc, what in ((server, "mediamtx"), (publisher, "publisher")):
                if proc.poll() is not None:
                    raise SystemExit(f"{what} exited rc={proc.returncode}"
                                     f" - see data/logs/")
    except KeyboardInterrupt:
        print("stopping", flush=True)
        return 0
    finally:
        for proc in (publisher, server):
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
