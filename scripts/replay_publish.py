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

    python scripts/replay_publish.py --many N=P [N=P ...] \
            [--offsets N=SECONDS,...] [--loop] [--reencode]
        Second system, several feeds (task S3.4; F9/F19/F58): start
        mediamtx ONCE and publish each file on its own path. Each feed
        is published ONCE THROUGH by default (no -stream_loop), started
        at its --offsets delay so the gaps between the clips are the
        real gaps between the shots (F56: real gaps, real speeds).
        Looping every feed needs an explicit --loop and is for wall and
        soak tests on a TEST DB only. Copy mode (-c:v copy) is the
        --many default - the F58 feeds are pre-transcoded to a <= 2 s
        GOP - and --reencode opts back into libx264.

    python scripts/replay_publish.py --register [--port P] [--hls-port H]
        The wall's stock feeds (F58): every data/local_feeds.csv row whose
        SENTINEL_FOOTAGE_DIR/feeds/<camera_id>.mp4 exists is published at
        stream/<camera_id> on ONE mediamtx - copy mode, LOOPED (explicit
        loop is legal for wall/demo feeds, F56; these are looped stock
        clips, disclosed in each registry row), a dead publisher respawned
        with jittered backoff. Missing files are skipped with a line.
        Continuous publishing, not mediamtx runOnDemand: all 28 measured
        25 Sep at 507 MB working set (133 MB unique) + 51 MB mediamtx.

Every mode except --fetch also serves HLS from mediamtx on
127.0.0.1:<SENTINEL_MEDIAMTX_HLS_PORT> (default 8888; --hls-port, 0 = off)
- MPEG-TS, 2 s segments, muxed only while someone reads - the relay's
local source for the wall tiles (http://127.0.0.1:8888/stream/<id>/index.m3u8).

Importable by tests (by path, like scripts/doctor.py) for the S2.2
harness fixture: ``start_mediamtx()`` / ``publish()`` return the Popen
handles and the caller owns their lifetime. Reused by S3.4's launcher
for the second-system demo feeds (``launch.py replay-start`` runs the
--many mode detached, or --register with no clip arguments; ``launch.py
start`` runs --register when the register and a feed file exist).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable

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


def mediamtx_env(port: int, hls_port: int = 0) -> dict[str, str]:
    """The MTX_* overrides start_mediamtx() applies (split out so a test
    can assert them; every key checked against the bundled v1.21.1
    mediamtx.yml).

    RTSP on 127.0.0.1:<port>, TCP only. ``hls_port`` > 0 also enables the
    HLS server on 127.0.0.1:<hls_port> - MPEG-TS segments of >= 2 s (the
    feeds carry a keyframe every 2 s, so segments are 2 s), 7 kept, the
    muxer built only when a reader asks (no remux cost for a feed nobody
    watches). ``hls_port`` 0 leaves HLS off. Everything else is off.
    Nothing binds anything but loopback (root rule 11).
    """
    env = {
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
    if hls_port:
        env.update({
            "MTX_HLS": "yes",
            "MTX_HLSADDRESS": f"127.0.0.1:{hls_port}",
            "MTX_HLSVARIANT": "mpegts",
            "MTX_HLSSEGMENTDURATION": "2s",
            "MTX_HLSSEGMENTCOUNT": "7",
            "MTX_HLSALWAYSREMUX": "no",
        })
    return env


def start_mediamtx(port: int = DEFAULT_PORT,
                   hls_port: int | None = None) -> subprocess.Popen:
    """Verify the checksum, then start mediamtx on 127.0.0.1:<port> only.

    ``hls_port`` None = ``config.mediamtx_hls_port()`` (the relay's local
    HLS source for the wall tiles); 0 = HLS off (the S2.2 test harness).
    Everything else is disabled through mediamtx's MTX_* environment
    overrides (:func:`mediamtx_env`), so no config file of ours to drift;
    the bundled default mediamtx.yml supplies the rest. Returns the Popen
    handle, which the caller owns; raises SystemExit when a port does not
    open (held by another process, usually).
    """
    verify_zip()
    exe = mediamtx_exe()
    if not exe.exists():
        raise SystemExit(f"{exe} missing although the zip verified - refetch")
    if hls_port is None:
        hls_port = config.mediamtx_hls_port()
    log_dir = config.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "mediamtx.log", "ab")
    import os

    env = {**os.environ, **mediamtx_env(port, hls_port)}
    proc = subprocess.Popen(
        [str(exe), str(TOOLS_DIR / "mediamtx.yml")],
        cwd=str(TOOLS_DIR), env=env, stdout=log, stderr=log,
    )
    try:
        _wait_port(port, proc=proc)
        if hls_port:
            _wait_port(hls_port, proc=proc)
    except SystemExit:
        proc.kill()
        raise
    return proc


def _publish_cmd(file: str | Path, name: str, port: int,
                 copy: bool = False, loop: bool = True) -> list[str]:
    """The ffmpeg argv publish() runs (split out so a test can assert it).

    ``loop=True`` keeps the historical ``-stream_loop -1`` behaviour (the
    S2.2 harness and wall tests); ``--many`` publishes once through by
    default instead (F56: a looped clip would repeat the route).
    """
    if copy:
        codec = ["-c:v", "copy"]
    else:
        codec = ["-c:v", "libx264", "-preset", "veryfast", "-g", "50",
                 "-keyint_min", "50"]
    head = [config.ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-re"]
    if loop:
        head += ["-stream_loop", "-1"]
    return [
        *head, "-i", str(file),
        *codec,
        "-an", "-f", "rtsp", "-rtsp_transport", "tcp",
        f"rtsp://127.0.0.1:{port}/stream/{name}",
    ]


def _spawn_publisher(cmd: list[str]) -> subprocess.Popen:
    """Popen *cmd* with stdout/stderr appended to data/logs/replay_publish.log."""
    log_dir = config.log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "replay_publish.log", "ab")
    return subprocess.Popen(cmd, stdout=log, stderr=log)


def publish(file: str | Path, name: str, port: int = DEFAULT_PORT,
            copy: bool = False, loop: bool = True) -> subprocess.Popen:
    """Publish *file* at rtsp://127.0.0.1:<port>/stream/<name>.

    ``-g 50`` forces a keyframe every 2 s at 25 fps so the consumer's
    stream-copied HLS tee can actually cut 2 s segments (hls_time 2 splits
    on keyframes; libx264's default 250-frame GOP would give 10 s ones).
    ``copy=True`` skips the re-encode (near-zero CPU — what several
    concurrent demo feeds need on the 4-core laptop); the input file must
    then already carry a <= 2 s GOP, e.g. transcoded with ``-g 60`` at
    30 fps. ``loop=False`` publishes once through (F56). Caller owns the
    returned handle.
    """
    return _spawn_publisher(_publish_cmd(file, name, port, copy, loop))


# --- the --many mode (task S3.4; F9/F19/F56/F58) ---------------------------

_NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")  # docs/api.md B11 camera_id shape


def _parse_many(specs: list[str]) -> list[tuple[str, Path]]:
    """``NAME=PATH`` pairs for ``--many``. Refuses a missing ``=``, an empty
    side, a duplicate name, and a name the registry would refuse (B11)."""
    pairs: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for spec in specs:
        name, sep, path = spec.partition("=")
        if not sep or not name or not path:
            raise SystemExit(f"--many: '{spec}' is not NAME=PATH")
        if not _NAME_RE.fullmatch(name):
            raise SystemExit(
                f"--many: name '{name}' must match [A-Za-z0-9_-]{{1,64}}"
                " (docs/api.md B11)")
        if name in seen:
            raise SystemExit(f"--many: duplicate name '{name}'")
        seen.add(name)
        pairs.append((name, Path(path)))
    return pairs


def _parse_offsets(spec: str, names: Iterable[str]) -> dict[str, float]:
    """``--offsets NAME=SECONDS,NAME=SECONDS`` -> ``{name: seconds}``.

    Refuses an unknown name and a negative offset — the offsets are the
    REAL gaps between the shots (F56), never invented corrections.
    """
    offsets: dict[str, float] = {}
    if not spec:
        return offsets
    known = set(names)
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        name, sep, secs = item.partition("=")
        if not sep or not name or not secs:
            raise SystemExit(f"--offsets: '{item}' is not NAME=SECONDS")
        if name not in known:
            raise SystemExit(f"--offsets: '{name}' is not a --many feed")
        try:
            value = float(secs)
        except ValueError:
            raise SystemExit(f"--offsets: '{secs}' is not a number of seconds")
        if value < 0:
            raise SystemExit(f"--offsets: '{name}' has a negative offset")
        offsets[name] = value
    return offsets


def _many_plan(pairs: list[tuple[str, Path]],
               offsets: dict[str, float] | None = None,
               port: int = DEFAULT_PORT, copy: bool = True,
               loop: bool = False) -> list[tuple[str, float, list[str]]]:
    """``(name, start_offset_s, ffmpeg argv)`` per feed, offset-sorted
    (split out so tests assert the built argv, never a bound port).
    Copy mode and once-through are the --many defaults (F56/F58)."""
    offsets = offsets or {}
    unknown = set(offsets) - {name for name, _ in pairs}
    if unknown:
        raise SystemExit(f"--offsets: unknown feed(s) {sorted(unknown)}")
    plan = [(name, float(offsets.get(name, 0.0)),
             _publish_cmd(path, name, port, copy=copy, loop=loop))
            for name, path in pairs]
    plan.sort(key=lambda entry: (entry[1], entry[0]))
    return plan


def restart_delay_s(attempt: int, rand: float) -> float:
    """Root rule 7's backoff for a dead register publisher: base 2 s,
    doubling per consecutive failure, capped at 30 s, times *rand*
    (drawn from ``random.uniform(0.5, 1.5)`` by the caller)."""
    return min(2.0 * 2 ** max(0, attempt - 1), 30.0) * rand


def run_many(pairs: list[tuple[str, Path]], offsets: dict[str, float],
             port: int = DEFAULT_PORT, copy: bool = True,
             loop: bool = False, restart: bool = False,
             hls_port: int | None = None) -> int:
    """Start mediamtx once, then each publisher at its offset.

    Once-through (default): a publisher exiting 0 is a finished clip;
    when all have finished, mediamtx stays up for readers until Ctrl+C
    (or the launcher's replay-stop). With ``--loop`` any publisher exit
    is a failure, as in the single-file mode — unless ``restart`` (the
    ``--register`` wall feeds): then a dead publisher is respawned after
    :func:`restart_delay_s` and the other feeds keep playing. Returns 0
    on Ctrl+C; raises SystemExit when mediamtx dies.
    """
    for _, path in pairs:
        if not path.exists():
            raise SystemExit(f"{path}: no such file")
    if loop and not restart:
        print("WARNING: --loop repeats every clip - wall/soak tests on a"
              " TEST DB only (F56/F58); a route-feeding run publishes once"
              " with real offsets", flush=True)
    plan = _many_plan(pairs, offsets, port, copy=copy, loop=loop)
    cmds = {name: cmd for name, _, cmd in plan}
    server = start_mediamtx(port, hls_port)
    publishers: dict[str, subprocess.Popen] = {}
    born: dict[str, float] = {}
    failures: dict[str, int] = {}
    respawn_at: dict[str, float] = {}
    pending = list(plan)
    all_done_said = False
    t0 = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            elapsed = now - t0
            while pending and pending[0][1] <= elapsed:
                name, offset, cmd = pending.pop(0)
                publishers[name] = _spawn_publisher(cmd)
                born[name] = now
                suffix = f" (offset {offset:.0f}s)" if offset else ""
                print(f"publishing {name} at rtsp://127.0.0.1:{port}/stream/"
                      f"{name}{suffix}", flush=True)
            if server.poll() is not None:
                raise SystemExit(f"mediamtx exited rc={server.returncode}"
                                 " - see data/logs/mediamtx.log")
            for name, proc in publishers.items():
                rc = proc.poll()
                if rc is not None and restart:
                    if name not in respawn_at:
                        # a publisher that ran >= 60 s was healthy: reset
                        if now - born[name] >= 60:
                            failures[name] = 0
                        failures[name] = failures.get(name, 0) + 1
                        delay = restart_delay_s(failures[name],
                                                random.uniform(0.5, 1.5))
                        respawn_at[name] = now + delay
                        print(f"publisher {name} exited rc={rc}; restart"
                              f" {failures[name]} in {delay:.1f} s", flush=True)
                    elif now >= respawn_at[name]:
                        del respawn_at[name]
                        publishers[name] = _spawn_publisher(cmds[name])
                        born[name] = now
                        print(f"publisher {name} respawned", flush=True)
                    continue
                if rc is not None and (loop or rc != 0):
                    raise SystemExit(f"publisher {name} exited rc={rc}"
                                     " - see data/logs/replay_publish.log")
            if (not pending and not loop and publishers and not all_done_said
                    and all(p.poll() == 0 for p in publishers.values())):
                print("all feeds published once through; mediamtx stays up"
                      " for readers - Ctrl+C to stop", flush=True)
                all_done_said = True
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("stopping", flush=True)
        return 0
    finally:
        for proc in (*publishers.values(), server):
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass


# --- the --register mode: the committed stock-feed register on the wall ----

REGISTER = REPO_ROOT / "data" / "local_feeds.csv"


def load_register(path: Path | None = None) -> list[dict[str, str]]:
    """The rows of ``data/local_feeds.csv`` (decision F58) as dicts."""
    with open(path or REGISTER, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def register_pairs(rows: list[dict[str, str]], feeds_dir: Path
                   ) -> tuple[list[tuple[str, Path]], list[str]]:
    """``(camera_id, feeds/<camera_id>.mp4)`` for every register row whose
    transcoded feed exists, and the ids whose file is missing (printed and
    skipped by the caller: partial coverage beats none, root section 9).
    Ids are checked like ``--many`` names (docs/api.md B11)."""
    pairs: list[tuple[str, Path]] = []
    missing: list[str] = []
    for row in rows:
        name = row["camera_id"]
        if not _NAME_RE.fullmatch(name):
            raise SystemExit(f"register: camera_id '{name}' must match"
                             " [A-Za-z0-9_-]{1,64} (docs/api.md B11)")
        path = feeds_dir / f"{name}.mp4"
        if path.is_file():
            pairs.append((name, path))
        else:
            missing.append(name)
    return pairs, missing


def run_register(port: int = DEFAULT_PORT, hls_port: int | None = None,
                 register: Path | None = None,
                 feeds_dir: Path | None = None) -> int:
    """Publish every register feed that exists on one mediamtx: path
    ``stream/<camera_id>``, copy mode, LOOPED, a dead publisher respawned.

    These are looped stock clips (F56 permits an explicit loop for wall and
    demo feeds; F58): their location_name in the registry says "stock
    footage, seeded coordinates", and a looped clip is never a filmed
    route. Returns run_many's code; raises SystemExit when no feed exists.
    """
    rows = load_register(register)
    feeds_dir = feeds_dir or (config.footage_dir() / "feeds")
    pairs, missing = register_pairs(rows, feeds_dir)
    for name in missing:
        print(f"skip {name}: {feeds_dir / (name + '.mp4')} missing"
              " (scripts/prepare_feeds.py makes it)", flush=True)
    if not pairs:
        raise SystemExit(f"no register feed found under {feeds_dir}"
                         " - run scripts/prepare_feeds.py")
    print(f"register: {len(pairs)}/{len(rows)} feeds - LOOPED STOCK CLIPS"
          " (F56/F58: wall and demo feeds, stock footage with seeded"
          " coordinates; never a filmed route)", flush=True)
    return run_many(pairs, {}, port, copy=True, loop=True, restart=True,
                    hls_port=hls_port)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true",
                        help="download mediamtx and record its checksum")
    parser.add_argument("--file", default=str(DEFAULT_CLIP))
    parser.add_argument("--name", default="test")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--copy", action="store_true",
                        help="publish with -c:v copy (input needs a <= 2 s GOP)")
    parser.add_argument("--many", nargs="+", metavar="NAME=PATH",
                        help="publish several files, one path each; once"
                             " through and copy mode by default (F56/F58)")
    parser.add_argument("--offsets", default="", metavar="NAME=SECONDS,...",
                        help="--many only: per-feed start delays = the real"
                             " gaps between the shots (F56)")
    parser.add_argument("--loop", action="store_true",
                        help="--many only: loop every feed - wall/soak tests"
                             " on a test DB only (F56/F58)")
    parser.add_argument("--reencode", action="store_true",
                        help="--many only: libx264 re-encode instead of the"
                             " copy-mode default")
    parser.add_argument("--register", action="store_true",
                        help="publish every data/local_feeds.csv feed found"
                             " under SENTINEL_FOOTAGE_DIR/feeds, looped, copy"
                             " mode, one path each (the wall's stock feeds)")
    parser.add_argument("--hls-port", type=int, default=None,
                        help="mediamtx HLS port on 127.0.0.1 (default"
                             " SENTINEL_MEDIAMTX_HLS_PORT; 0 = HLS off)")
    args = parser.parse_args()

    if args.fetch:
        fetch()
        return 0

    if args.register:
        if args.many:
            parser.error("--register and --many conflict")
        for flag, given in (("--offsets", args.offsets), ("--loop", args.loop),
                            ("--reencode", args.reencode)):
            if given:
                parser.error(f"{flag} does not apply to --register (always"
                             " looped, copy mode)")
        return run_register(args.port, args.hls_port)

    if args.many:
        if args.copy and args.reencode:
            parser.error("--copy and --reencode conflict")
        pairs = _parse_many(args.many)
        offsets = _parse_offsets(args.offsets, [name for name, _ in pairs])
        return run_many(pairs, offsets, args.port,
                        copy=not args.reencode, loop=args.loop,
                        hls_port=args.hls_port)
    for flag, given in (("--offsets", args.offsets), ("--loop", args.loop),
                        ("--reencode", args.reencode)):
        if given:
            parser.error(f"{flag} needs --many (the single-file mode always"
                         " loops)")

    if not Path(args.file).exists():
        raise SystemExit(f"{args.file}: no such file")
    server = start_mediamtx(args.port, args.hls_port)
    publisher = None
    try:
        publisher = publish(args.file, args.name, args.port, copy=args.copy)
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
