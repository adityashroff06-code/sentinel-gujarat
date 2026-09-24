"""Score sample CCTV clips for use as local demo feeds (S3.4/S3.6 prep).

For every ``*.mp4`` under ``--dir``, samples frames, downscales to the
1080p the live path will run at, and runs the real S2.3/S2.4 stack on
them (YOLOX-S detector, then PaddleOCR on the largest vehicle crops).
Prints a ranking — clips with structurally full Indian plate reads
first — and writes the full per-clip record to ``--out`` JSON so the
pick is reproducible.

    .venv/Scripts/python scripts/analyze_footage.py --dir D:/projects/sentinel-footage/raw

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

from ml.anpr.detect import Detector  # noqa: E402
from ml.anpr.ocr import PlateOcr  # noqa: E402

MAX_WIDTH = 1920          # analyse at the resolution the feeds will run at
FRAMES_PER_CLIP = 8
OCR_CROPS_PER_FRAME = 3   # largest vehicles first (pipeline budget is 2; +1 for survey)


def sample_positions(total: int, fps: float, n: int) -> list[int]:
    """*n* frame indices spread over the clip, skipping the first second."""
    start = int(min(fps, max(0, total - 1)))
    if total <= start + n:
        return list(range(start, total))
    return [int(p) for p in np.linspace(start, total - 1, n)]


def analyse_clip(path: Path, detector: Detector, ocr: PlateOcr) -> dict:
    """Detection/OCR survey of one clip; returns the per-clip record."""
    cap = cv2.VideoCapture(str(path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        record: dict = {
            "clip": path.name, "frames_total": total, "fps": round(fps, 2),
            "frames_sampled": 0, "vehicles": 0, "persons": 0,
            "reads": [], "detect_ms": [], "ocr_ms": [],
        }
        for pos in sample_positions(total, fps, FRAMES_PER_CLIP):
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue
            if frame.shape[1] > MAX_WIDTH:
                scale = MAX_WIDTH / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            record["frames_sampled"] += 1
            t0 = time.perf_counter()
            detections = detector.detect(frame)
            record["detect_ms"].append((time.perf_counter() - t0) * 1000)
            vehicles = [d for d in detections if d.superclass == "vehicle"]
            record["vehicles"] += len(vehicles)
            record["persons"] += sum(1 for d in detections if d.cls == "person")
            vehicles.sort(key=lambda d: (d.xyxy[2] - d.xyxy[0]) * (d.xyxy[3] - d.xyxy[1]),
                          reverse=True)
            for det in vehicles[:OCR_CROPS_PER_FRAME]:
                x1, y1, x2, y2 = (int(v) for v in det.xyxy)
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                t0 = time.perf_counter()
                reads = ocr.read(crop, offset=(x1, y1), frame_h=frame.shape[0])
                record["ocr_ms"].append((time.perf_counter() - t0) * 1000)
                for r in reads:
                    record["reads"].append({
                        "frame": pos, "text": r.text, "raw": r.raw,
                        "conf": round(r.conf, 3), "kind": r.kind,
                        "plate_w_px": r.bbox[2],
                    })
        return record
    finally:
        cap.release()


def summarise(record: dict) -> dict:
    """Fold a clip record into the ranking row."""
    n = max(1, record["frames_sampled"])
    full = [r for r in record["reads"] if r["kind"] == "full"]
    distinct_full = sorted({r["text"] for r in full})
    return {
        "clip": record["clip"],
        "vehicles_per_frame": round(record["vehicles"] / n, 1),
        "persons_per_frame": round(record["persons"] / n, 1),
        "reads": len(record["reads"]),
        "full_reads": len(full),
        "distinct_full_plates": distinct_full,
        "best_conf": max((r["conf"] for r in full), default=0.0),
        "max_plate_w_px": max((r["plate_w_px"] for r in record["reads"]), default=0),
        "detect_ms_mean": round(float(np.mean(record["detect_ms"])), 1)
        if record["detect_ms"] else None,
        "ocr_ms_mean": round(float(np.mean(record["ocr_ms"])), 1)
        if record["ocr_ms"] else None,
        "score": len(full) * 10 + len(distinct_full) * 5 + round(record["vehicles"] / n, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="folder holding the *.mp4 clips")
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "footage_analysis.json"))
    args = parser.parse_args()

    clips = sorted(Path(args.dir).glob("*.mp4"))
    if not clips:
        raise SystemExit(f"no *.mp4 under {args.dir}")

    detector = Detector()
    ocr = PlateOcr()
    print(f"analysing {len(clips)} clips at <= {MAX_WIDTH} px wide, "
          f"{FRAMES_PER_CLIP} frames each (provider: {detector.provider})", flush=True)

    records, rows = [], []
    for i, clip in enumerate(clips, 1):
        record = analyse_clip(clip, detector, ocr)
        records.append(record)
        row = summarise(record)
        rows.append(row)
        print(f"[{i:2}/{len(clips)}] {row['clip']}: "
              f"veh/frame={row['vehicles_per_frame']} reads={row['reads']} "
              f"full={row['full_reads']} plates={row['distinct_full_plates']}", flush=True)

    rows.sort(key=lambda r: r["score"], reverse=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"provider": detector.provider, "ranking": rows,
                               "clips": records}, indent=2), encoding="utf-8")

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
        print(f"ocr: mean {np.mean(ocr_ms):.0f} ms, p90 {np.percentile(ocr_ms, 90):.0f} ms "
              f"over {len(ocr_ms)} crops")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
