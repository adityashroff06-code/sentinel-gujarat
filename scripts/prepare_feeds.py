"""Transcode the stock clips into relay-ready local feeds (one-time, idempotent).

Reads ``data/local_feeds.csv`` (the committed register of the local stock
feeds, decision F58) and, for every row whose ``feeds/<camera_id>.mp4`` does
not exist yet, transcodes ``raw/<clip>`` once to a feed mediamtx can publish
in copy mode and the relay can cut into clean 2 s HLS segments:

- H.264 High, 30 fps constant, a keyframe every exactly 2 s (so a stream-
  copied HLS tee or mediamtx's muxer cuts 2 s segments), no audio, faststart.
- ``active`` rows (analysed by the ANPR workers) keep 1920x1080 so plates
  stay readable; ``registered`` rows (view-only relay tiles) go to 1280x720,
  which is plenty for a wall tile and a third of the browser decode cost.
- libx264 ``veryfast`` by default (measured 25 Sep: a 20.5 s 4K clip in
  13 s on the Ryzen 5 3550H). ``--nvenc`` tries NVDEC + NVENC on the GTX
  1650 first; on this laptop's BtbN build that attempt failed with
  "Invalid argument" (25 Sep), so it is opt-in and falls back to libx264.

The clips live OUTSIDE the repo (``SENTINEL_FOOTAGE_DIR``, default
``D:\\projects\\sentinel-footage``; ``raw/`` in, ``feeds/`` out) — stock footage
is never committed. ffmpeg is resolved only through
``backend.core.config.ffmpeg()`` (CLAUDE.md §7).

Usage::

    .venv/Scripts/python scripts/prepare_feeds.py [--only local05,local06] [--nvenc]

Prints one line per feed; exits 1 if any transcode failed (the others are
kept — rerunning skips what is done).
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.core import config  # noqa: E402

REGISTER = REPO_ROOT / "data" / "local_feeds.csv"
KEYFRAME_S = 2
FPS = 30


def load_register(path: Path = REGISTER) -> list[dict[str, str]]:
    """The rows of ``data/local_feeds.csv`` as dicts (header order kept)."""
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def feed_height(fps_tier: str) -> int:
    """Output height for a register row's tier: 1080 for ``active`` (ANPR
    needs the plate pixels), 720 for view-only ``registered`` wall tiles."""
    return 1080 if fps_tier == "active" else 720


def _has_nvenc(ffmpeg: str) -> bool:
    out = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                         capture_output=True, text=True, timeout=30).stdout
    return "h264_nvenc" in out


def transcode_cmd(ffmpeg: str, src: Path, dst: Path, *, height: int,
                  nvenc: bool) -> list[str]:
    """The argv for one feed (split out so a test can assert it)."""
    # fit inside a landscape box of the given height; a portrait clip keeps
    # its orientation at the same pixel budget (-2 keeps the width even)
    scale = (f"scale='if(gte(iw,ih),-2,{height * 9 // 16 // 2 * 2})'"
             f":'if(gte(iw,ih),{height},-2)'")
    vf = f"fps={FPS},{scale}"
    gop = str(FPS * KEYFRAME_S)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if nvenc:
        cmd += ["-hwaccel", "cuda"]
    cmd += ["-i", str(src), "-map", "0:v:0", "-an", "-vf", vf]
    if nvenc:
        cmd += ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr",
                "-cq", "23", "-b:v", "0", "-profile:v", "high",
                "-g", gop, "-forced-idr", "1",
                "-force_key_frames", f"expr:gte(t,n_forced*{KEYFRAME_S})"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-profile:v", "high", "-g", gop, "-keyint_min", gop,
                "-sc_threshold", "0"]
    cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    return cmd


def main(argv: list[str] | None = None) -> int:
    """Transcode every missing feed; 0 when all exist afterwards, else 1."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="comma-separated camera ids")
    ap.add_argument("--nvenc", action="store_true",
                    help="try NVDEC+NVENC first (falls back to libx264)")
    args = ap.parse_args(argv)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    ffmpeg = config.ffmpeg()
    nvenc = args.nvenc and _has_nvenc(ffmpeg)
    footage = config.footage_dir()
    raw_dir, feeds_dir = footage / "raw", footage / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    print(f"[feeds] encoder {'h264_nvenc (NVDEC in)' if nvenc else 'libx264'};"
          f" raw {raw_dir} -> {feeds_dir}")
    failed = 0
    for row in load_register():
        cam = row["camera_id"]
        if only and cam not in only:
            continue
        dst = feeds_dir / f"{cam}.mp4"
        if dst.exists() and dst.stat().st_size > 0:
            print(f"[feeds] {cam}: present - skip")
            continue
        src = raw_dir / row["clip"]
        if not src.exists():
            print(f"[feeds] {cam}: MISSING source {src.name}")
            failed += 1
            continue
        height = feed_height(row["fps_tier"])
        tmp = dst.with_suffix(".part.mp4")
        t0 = time.monotonic()
        rc = subprocess.call(transcode_cmd(ffmpeg, src, tmp, height=height,
                                           nvenc=nvenc))
        if rc != 0 and nvenc:  # an NVENC session limit or driver hiccup
            print(f"[feeds] {cam}: nvenc rc={rc} - retrying on libx264")
            rc = subprocess.call(transcode_cmd(ffmpeg, src, tmp, height=height,
                                               nvenc=False))
        if rc != 0:
            tmp.unlink(missing_ok=True)
            print(f"[feeds] {cam}: FAILED rc={rc}")
            failed += 1
            continue
        tmp.replace(dst)
        print(f"[feeds] {cam}: {src.name} -> {dst.name} {height}p "
              f"in {time.monotonic() - t0:.0f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
