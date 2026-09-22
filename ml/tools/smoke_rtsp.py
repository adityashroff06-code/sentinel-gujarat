"""Smoke-pull one registry camera and report what was observed (task S2.2).

    .venv/Scripts/python -m ml.tools.smoke_rtsp cam06 --seconds 60

Prints (stdout, flushed - the detached acceptance run redirects this plus
the logger's stderr into ``data/logs/smoke_rtsp.log``): a progress line
every ~5 s with the frame count, last ``stream_time`` and tee state, and a
final summary with frame count, first/last ``stream_time``, monotonicity
and tee state. Backoff/watchdog lines come from the source's logger on
stderr, so the one redirected log shows the whole story of a network pull.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from datetime import datetime

from backend.core import config
from backend.core import db as dbmod
from ml.ingest import for_camera

PROGRESS_EVERY_S = 5.0


def tee_state(camera_id: str) -> str:
    """One line describing the local HLS tee for *camera_id*."""
    tee_dir = config.REPO_ROOT / "data" / "hls" / camera_id
    playlist = tee_dir / "index.m3u8"
    if not playlist.exists():
        return "tee: no playlist yet"
    listed = sum(
        1 for line in playlist.read_text(encoding="utf-8").splitlines()
        if line.strip().endswith(".ts")
    )
    on_disk = len(list(tee_dir.glob("*.ts")))
    return f"tee: playlist lists {listed} segments, {on_disk} .ts files on disk"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("camera_id")
    parser.add_argument("--seconds", type=float, default=60.0,
                        help="wall-clock pull duration (default 60)")
    args = parser.parse_args(argv)

    con = dbmod.connect()
    try:
        row = con.execute(
            "SELECT * FROM cameras WHERE camera_id = ?", (args.camera_id,)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        print(f"{args.camera_id}: not in the registry", flush=True)
        return 2

    source = for_camera(row)
    print(
        f"smoke_rtsp {args.camera_id}: transport={dict(row).get('transport')}"
        f" fps={source.fps if hasattr(source, 'fps') else '?'}"
        f" seconds={args.seconds:.0f}", flush=True,
    )

    count = 0
    non_monotonic = 0
    restarts_seen = 0
    first_time: datetime | None = None
    last_time: datetime | None = None
    next_report = time.monotonic() + PROGRESS_EVERY_S

    # A wall-clock stop that fires even when NO frames arrive: on a dead or
    # stalled feed frames() yields nothing and loops in backoff forever, so a
    # deadline checked only inside the loop body would never trip and the
    # detached network-pull run would hang. close() sets _stop and kills the
    # child, which ends the generator cleanly.
    stopper = threading.Timer(args.seconds, source.close)
    stopper.daemon = True
    stopper.start()
    try:
        for tick in source.frames():
            count += 1
            if tick.restart:
                restarts_seen += 1
            if first_time is None:
                first_time = tick.stream_time
            elif last_time is not None and tick.stream_time <= last_time:
                non_monotonic += 1
            last_time = tick.stream_time
            now = time.monotonic()
            if now >= next_report:
                next_report = now + PROGRESS_EVERY_S
                print(
                    f"  frames={count} last_stream_time={last_time.isoformat()}"
                    f" restarts_seen={restarts_seen} | {tee_state(args.camera_id)}",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("interrupted", flush=True)
    finally:
        stopper.cancel()
        summary_tee = tee_state(args.camera_id)  # before close() cleans it
        source.close()

    print(
        f"SUMMARY {args.camera_id}: frames={count} restarts_seen={restarts_seen}"
        f" first_stream_time={first_time.isoformat() if first_time else 'none'}"
        f" last_stream_time={last_time.isoformat() if last_time else 'none'}"
        f" monotonic={'yes' if non_monotonic == 0 else f'NO ({non_monotonic} violations)'}"
        f" | {summary_tee}", flush=True,
    )
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
