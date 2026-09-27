"""Score sample CCTV clips for use as local demo feeds (S3.4/S3.6 prep; S7.0).

For every ``*.mp4`` under ``--dir`` (or the ``--clips`` subset), samples
frames, downscales to ``--max-width`` (default the 1080p the live path
runs at), and runs the real S2.3/S2.4 stack on them (YOLOX-S detector,
then PaddleOCR on the largest vehicle crops). Prints a ranking — clips
with structurally full Indian plate reads first — and writes the full
per-clip record to ``--out`` JSON so the pick is reproducible.

    .venv/Scripts/python scripts/analyze_footage.py --dir D:/projects/sentinel-footage/raw

The defaults reproduce the 25 Sep survey exactly (≤ 1920 px, 8 frames,
3 crops a frame, every clip, ``data/footage_analysis.json``). S7.0's
4K read test (decision F75) runs the same frames at several widths:

    ... --clips a.mp4,b.mp4 --frames 30 --ocr-per-frame 8 \
        --max-width 3840 --label w3840 --out data/measurements/read-test-w3840.json

and folds the runs into one Markdown table with ``--table``:

    ... --table data/measurements/read-test-w1920.json,...w2560.json,...w3840.json \
        --out data/measurements/read-test-20260927.md

Read-only: no database writes, no registry changes. Output is the
product, so this prints (CLI-tool exception to the logging rule).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.core import plates  # noqa: E402

MAX_WIDTH = 1920          # analyse at the resolution the feeds will run at
FRAMES_PER_CLIP = 8
OCR_CROPS_PER_FRAME = 3   # largest vehicles first (pipeline budget is 2; +1 for survey)
DEFAULT_LABEL = "survey"
SURVEY_OUT = REPO_ROOT / "data" / "footage_analysis.json"


def sample_positions(total: int, fps: float, n: int) -> list[int]:
    """*n* frame indices spread over the clip, skipping the first second."""
    start = int(min(fps, max(0, total - 1)))
    if total <= start + n:
        return list(range(start, total))
    return [int(p) for p in np.linspace(start, total - 1, n)]


def analyse_clip(path: Path, detector, ocr, *, max_width: int = MAX_WIDTH,
                 frames: int = FRAMES_PER_CLIP,
                 ocr_per_frame: int = OCR_CROPS_PER_FRAME) -> dict:
    """Detection/OCR survey of one clip; returns the per-clip record.

    Every width samples the same frame indices (they depend only on the
    clip's length), so runs at different ``max_width`` are an A/B on
    identical pixels. ``plate_w_px`` and ``vehicle_w_px`` are in the
    analysed frame's pixels.
    """
    cap = cv2.VideoCapture(str(path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        record: dict = {
            "clip": path.name, "frames_total": total, "fps": round(fps, 2),
            "source_w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "source_h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "analysed_w": None, "max_width": max_width,
            "frames_sampled": 0, "vehicles": 0, "persons": 0,
            "reads": [], "detect_ms": [], "ocr_ms": [],
        }
        for pos in sample_positions(total, fps, frames):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue
            if frame.shape[1] > max_width:
                scale = max_width / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            record["analysed_w"] = frame.shape[1]
            record["frames_sampled"] += 1
            t0 = time.perf_counter()
            detections = detector.detect(frame)
            record["detect_ms"].append((time.perf_counter() - t0) * 1000)
            vehicles = [d for d in detections if d.superclass == "vehicle"]
            record["vehicles"] += len(vehicles)
            record["persons"] += sum(1 for d in detections if d.cls == "person")
            vehicles.sort(key=lambda d: (d.xyxy[2] - d.xyxy[0]) * (d.xyxy[3] - d.xyxy[1]),
                          reverse=True)
            for det in vehicles[:ocr_per_frame]:
                x1, y1, x2, y2 = (int(v) for v in det.xyxy)
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                t0 = time.perf_counter()
                reads = ocr.read(crop, offset=(x1, y1), frame_h=frame.shape[0])
                record["ocr_ms"].append((time.perf_counter() - t0) * 1000)
                for r in reads:
                    record["reads"].append({
                        "frame": pos, "t_s": round(pos / fps, 2), "text": r.text,
                        "coerced": plates.coerce(r.text) if r.kind == "full" else None,
                        "raw": r.raw, "conf": round(r.conf, 3), "kind": r.kind,
                        "plate_w_px": r.bbox[2], "vehicle_w_px": x2 - x1,
                    })
        return record
    finally:
        cap.release()


def summarise(record: dict) -> dict:
    """Fold a clip record into the ranking row.

    ``distinct_full_plates`` is the OCR text as read (the 25 Sep field);
    ``distinct_full_coerced`` counts registrations the way the pipeline
    stores them (``plates.coerce``), so ``MHO2FG7423`` and ``MH02FG7423``
    are one plate — the count S7.1's render is held against.
    """
    n = max(1, record["frames_sampled"])
    full = [r for r in record["reads"] if r["kind"] == "full"]
    distinct_full = sorted({r["text"] for r in full})
    coerced = sorted({r.get("coerced") or plates.coerce(r["text"]) or r["text"] for r in full})
    plate_ws = [r["plate_w_px"] for r in record["reads"]]
    return {
        "clip": record["clip"],
        "analysed_w": record.get("analysed_w"),
        "vehicles_per_frame": round(record["vehicles"] / n, 1),
        "persons_per_frame": round(record["persons"] / n, 1),
        "reads": len(record["reads"]),
        "full_reads": len(full),
        "distinct_full_plates": distinct_full,
        "distinct_full_coerced": coerced,
        "best_conf": max((r["conf"] for r in full), default=0.0),
        "max_plate_w_px": max(plate_ws, default=0),
        "median_plate_w_px": float(np.median(plate_ws)) if plate_ws else None,
        "detect_ms_mean": round(float(np.mean(record["detect_ms"])), 1)
        if record["detect_ms"] else None,
        "ocr_ms_mean": round(float(np.mean(record["ocr_ms"])), 1)
        if record["ocr_ms"] else None,
        "ocr_crops": len(record["ocr_ms"]),
        "score": len(full) * 10 + len(distinct_full) * 5 + round(record["vehicles"] / n, 1),
    }


def _fmt(v, nd: int = 0) -> str:
    return "-" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def write_table(json_paths: list[Path], out: Path) -> str:
    """One Markdown row per clip × width from several read-test JSONs.

    Returns the Markdown written to *out*.
    """
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in json_paths]
    rows = []
    for run, path in zip(runs, json_paths):
        for rec in run["clips"]:
            row = summarise(rec)
            row["label"] = run.get("label", path.stem)
            rows.append(row)
    rows.sort(key=lambda r: (r["clip"], r["analysed_w"] or 0))
    lines = [
        "| clip | width px | full reads | distinct full plates (coerced) | median plate w px "
        "| max plate w px | detect ms | OCR ms / crop | crops | plates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['clip'].split('_')[0]}` | {_fmt(r['analysed_w'])} | {r['full_reads']} "
            f"| {len(r['distinct_full_coerced'])} | {_fmt(r['median_plate_w_px'], 1)} "
            f"| {r['max_plate_w_px']} | {_fmt(r['detect_ms_mean'], 1)} "
            f"| {_fmt(r['ocr_ms_mean'], 1)} | {r['ocr_crops']} "
            f"| {', '.join(r['distinct_full_coerced']) or '-'} |")
    lines.append("")
    lines.append("| run | provider | frames/clip | OCR crops/frame | OCR ms / crop (all clips) "
                 "| detect ms (all clips) | wall-clock s |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for run, path in zip(runs, json_paths):
        ocr_ms = [m for rec in run["clips"] for m in rec["ocr_ms"]]
        det_ms = [m for rec in run["clips"] for m in rec["detect_ms"]]
        lines.append(
            f"| {run.get('label', path.stem)} | {run.get('provider')} | {run.get('frames', '-')} "
            f"| {run.get('ocr_per_frame', '-')} "
            f"| {_fmt(float(np.mean(ocr_ms)) if ocr_ms else None, 1)} "
            f"| {_fmt(float(np.mean(det_ms)) if det_ms else None, 1)} "
            f"| {_fmt(run.get('wall_s'), 0)} |")
    text = "\n".join(lines) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", help="folder holding the *.mp4 clips")
    parser.add_argument("--out", default=None,
                        help="output JSON (default data/footage_analysis.json for the "
                             "'survey' label, else data/measurements/read-test-<label>.json); "
                             "with --table, the Markdown file")
    parser.add_argument("--max-width", type=int, default=MAX_WIDTH,
                        help=f"downscale frames wider than this (default {MAX_WIDTH})")
    parser.add_argument("--frames", type=int, default=FRAMES_PER_CLIP,
                        help=f"frames sampled per clip (default {FRAMES_PER_CLIP})")
    parser.add_argument("--ocr-per-frame", type=int, default=OCR_CROPS_PER_FRAME,
                        help=f"largest vehicles read per frame (default {OCR_CROPS_PER_FRAME})")
    parser.add_argument("--clips", default=None,
                        help="comma-separated file names under --dir (default: all *.mp4)")
    parser.add_argument("--label", default=DEFAULT_LABEL,
                        help=f"run label, stored in the JSON and in the default file name "
                             f"(default {DEFAULT_LABEL})")
    parser.add_argument("--table", default=None,
                        help="comma-separated read-test JSONs to fold into a Markdown table "
                             "(written to --out); no analysis runs")
    args = parser.parse_args()

    if args.table:
        if not args.out:
            raise SystemExit("--table needs --out <file.md>")
        print(write_table([Path(p) for p in args.table.split(",")], Path(args.out)), end="")
        return 0
    if not args.dir:
        raise SystemExit("--dir is required")

    if args.clips:
        names = [n.strip() for n in args.clips.split(",") if n.strip()]
        clips = [Path(args.dir) / n for n in names]
        missing = [str(c) for c in clips if not c.is_file()]
        if missing:
            raise SystemExit(f"not found: {', '.join(missing)}")
    else:
        clips = sorted(Path(args.dir).glob("*.mp4"))
    if not clips:
        raise SystemExit(f"no *.mp4 under {args.dir}")
    if args.out:
        out = Path(args.out)
    elif args.label == DEFAULT_LABEL:
        out = SURVEY_OUT
    else:
        out = REPO_ROOT / "data" / "measurements" / f"read-test-{args.label}.json"

    from ml.anpr.detect import Detector  # heavy imports: not needed for --table
    from ml.anpr.ocr import PlateOcr

    detector = Detector()
    ocr = PlateOcr()
    print(f"[{args.label}] analysing {len(clips)} clips at <= {args.max_width} px wide, "
          f"{args.frames} frames each, {args.ocr_per_frame} OCR crops a frame "
          f"(provider: {detector.provider})", flush=True)

    def write(complete: bool) -> float:
        """(Re)write *out* with every clip analysed so far; returns wall s."""
        wall = time.perf_counter() - t_start
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"provider": detector.provider, "label": args.label,
                                   "max_width": args.max_width, "frames": args.frames,
                                   "ocr_per_frame": args.ocr_per_frame,
                                   "complete": complete, "wall_s": round(wall, 1),
                                   "ranking": sorted(rows, key=lambda r: r["score"],
                                                     reverse=True),
                                   "clips": records}, indent=2), encoding="utf-8")
        return wall

    t_start = time.perf_counter()
    records, rows = [], []
    for i, clip in enumerate(clips, 1):
        t_clip = time.perf_counter()
        record = analyse_clip(clip, detector, ocr, max_width=args.max_width,
                              frames=args.frames, ocr_per_frame=args.ocr_per_frame)
        record["wall_s"] = round(time.perf_counter() - t_clip, 1)
        records.append(record)
        row = summarise(record)
        rows.append(row)
        write(complete=False)  # a checkpoint per clip: a killed run keeps its clips
        print(f"[{i:2}/{len(clips)}] {row['clip']} @ {row['analysed_w']} px: "
              f"veh/frame={row['vehicles_per_frame']} reads={row['reads']} "
              f"full={row['full_reads']} plates={row['distinct_full_coerced']} "
              f"ocr_ms/crop={row['ocr_ms_mean']} ({record['wall_s']:.0f} s)", flush=True)

    rows.sort(key=lambda r: r["score"], reverse=True)
    wall_s = write(complete=True)

    print("\n=== ranking (best first) ===")
    for row in rows:
        print(f"{row['score']:7.1f}  {row['clip']:34}  veh/frame={row['vehicles_per_frame']:5}  "
              f"full={row['full_reads']:3}  plates={','.join(row['distinct_full_plates']) or '-'}")
    detect_ms = [m for r in records for m in r["detect_ms"]]
    ocr_ms = [m for r in records for m in r["ocr_ms"]]
    if detect_ms:
        print(f"\ndetector ({detector.provider}): mean {np.mean(detect_ms):.0f} ms, "
              f"p90 {np.percentile(detect_ms, 90):.0f} ms over {len(detect_ms)} frames")
    if ocr_ms:
        print(f"ocr at <= {args.max_width} px: mean {np.mean(ocr_ms):.0f} ms per crop, "
              f"p90 {np.percentile(ocr_ms, 90):.0f} ms over {len(ocr_ms)} crops")
    print(f"wall-clock {wall_s:.0f} s; written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
