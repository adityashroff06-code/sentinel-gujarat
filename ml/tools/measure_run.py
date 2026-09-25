"""S4.1 measurement sampler (decision F18, GATE B).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\tools\\measure_run.py``
(decision F52), which produced the previous build's measured 10-minute
run on 24 Sep. Two adaptations to this build's contracts, and two of the
old tool's defects fixed in the port:

- The old tool spawned the API and the workers itself; here ``launch.py
  start`` already owns spawning (S3.4), so this sampler measures the
  ALREADY RUNNING platform: it reads ``data/launcher_pids.txt``, attaches
  to both processes with psutil and refuses to run if either is gone.
- RSS came from Windows ``tasklist`` CSV; psutil process trees replace it
  (cross-platform, ffmpeg children included per tree, no locale parsing).
- Defect: the old aggregate divided whole-run counters by whole-run
  uptime, so warm-up dragged every sustained number down. F18 wants a
  post-warm-up WINDOW, so this port snapshots ``data/worker_stats.json``
  at the start and the end and reports deltas over the window only.
- Defect: worker restarts were inferred from per-camera uptime
  regressions sample to sample — a missed sample hid a restart. The
  supervisor's cumulative ``restarts`` counter is authoritative; the port
  uses its window delta, and flags any camera whose counters regressed
  (its worker was respawned and its rates marked unreliable).

Writes ``data/measurements/<timestamp>.json`` (committed — the evidence
behind every ``[measured]`` claim) and ``<timestamp>.md`` (the markdown
table pasted into ``docs/progress.md`` "Key measurements"), and prints
the table. Low read counts are findings, not failures: exit 0. Exit 2
only when the platform itself died mid-window.

CLI tool: output is the product, so it prints (root CLAUDE.md §7).

Usage:  .venv python -m ml.tools.measure_run [--minutes 10] [--sample-s 5]
        (normally via: python launch.py measure --minutes 10)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from backend.core import config

DATA = config.REPO_ROOT / "data"
PIDFILE = DATA / "launcher_pids.txt"
STATS = DATA / "worker_stats.json"
OUT_DIR = DATA / "measurements"

STATS_STALE_S = 60.0  # supervisor writes every 10 s; older means wedged

# Per-camera counters the window deltas are computed over (worker.stats).
_COUNTERS = ("frames", "inferred", "motion_skipped", "detections",
             "sightings", "alerts", "zone_events", "restart_ticks",
             "ocr_attempts", "full_reads", "vehicle_tracks")
# The plate-read-rate counters (S4.1); absent from a pre-S4.1 worker.
_READ_COUNTERS = ("full_reads", "vehicle_tracks")
_UNMEASURED_READS = "unmeasured (worker predates the read counters)"

# Indirection so tests can stub waiting without touching global sleep
# (the S2.1 lesson: patching time.sleep turns subprocess polls into spins).
_sleep = time.sleep


def _gpu_used_mib() -> int | None:
    """GPU memory in use (MiB) via nvidia-smi, or None if unavailable.

    None is reported as "unmeasured" (root rule 8) — never invented.
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL, timeout=10)
        return int(out.strip().splitlines()[0])
    except Exception:  # noqa: BLE001 - any failure means "unmeasured"
        return None


def _tree_rss_mb(proc: psutil.Process) -> float:
    """RSS of *proc* plus all its children (MB). Children that exit
    between listing and reading are skipped, not fatal."""
    total = 0
    for p in [proc, *proc.children(recursive=True)]:
        try:
            total += p.memory_info().rss
        except psutil.NoSuchProcess:
            continue
    return total / 1e6


def _read_stats(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _read_pidfile(path: Path) -> dict[str, int]:
    """``api <pid>`` / ``worker <pid>`` lines, as launch.py writes them."""
    pids: dict[str, int] = {}
    if not path.exists():
        return pids
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            pids[parts[0]] = int(parts[1])
    return pids


def window_rows(base: dict, final: dict, window_s: float) -> dict[str, dict]:
    """Per-camera window deltas and rates from two stats snapshots.

    Returns ``{camera_id: row}`` where each row carries the raw deltas,
    the derived rates (fps, vehicles/min, detection boxes/min, motion-skip
    rate, plate-read rate) and ``reliable`` — False when any counter
    regressed (the worker was respawned mid-window; deltas are clamped to
    zero and must not be quoted as measured).
    """
    window_s = max(window_s, 1e-9)
    rows: dict[str, dict] = {}
    base_cams = base.get("cameras", {})
    for cam, end in sorted(final.get("cameras", {}).items()):
        start = base_cams.get(cam, {})
        deltas = {k: end.get(k, 0) - start.get(k, 0) for k in _COUNTERS}
        reliable = all(v >= 0 for v in deltas.values())
        d = {k: max(v, 0) for k, v in deltas.items()}
        gated = d["inferred"] + d["motion_skipped"]
        # A worker started before the S4.1 counters existed writes no
        # full_reads / vehicle_tracks at all; defaulting them to 0 would
        # print a plate-read rate of 0.0 that no code measured (rule 8).
        has_reads = all(k in end and k in start for k in _READ_COUNTERS)
        rows[cam] = {
            **d,
            "alive": bool(end.get("alive", False)),
            "reliable": reliable,
            "read_counters": has_reads,
            "fps": round(d["frames"] / window_s, 2),
            "vehicles_per_min": (round(d["vehicle_tracks"] / (window_s / 60), 1)
                                 if has_reads else None),
            "boxes_per_min": round(d["detections"] / (window_s / 60), 1),
            "motion_skip_rate": round(d["motion_skipped"] / max(1, gated), 3),
            "plate_read_rate": (round(d["full_reads"] / max(1, d["vehicle_tracks"]), 3)
                                if has_reads else None),
        }
    return rows


def _fmt_per_cam(rows: dict[str, dict], key: str,
                 suffix: str = "") -> str:
    parts = []
    for cam, row in rows.items():
        flag = "" if row["reliable"] else " (restarted — unreliable)"
        value = "unmeasured" if row[key] is None else f"{row[key]}{suffix}"
        parts.append(f"{cam} {value}{flag}")
    return " · ".join(parts) if parts else "no cameras in stats"


def render_markdown(result: dict) -> str:
    """The table pasted into docs/progress.md "Key measurements"."""
    rows = result["cameras"]
    t = result["totals"]
    gpu = result["gpu"]
    ram = result["peak_rss_mb"]
    stamp = result["measured_at"]
    where = f"S4.1 measure {stamp} [measured]"
    n = len(rows)
    alive = sum(1 for r in rows.values() if r["alive"])
    reads = (f"{t['plate_read_rate']} ({t['full_reads']}/{t['vehicle_tracks']}) overall; "
             f"{_fmt_per_cam(rows, 'plate_read_rate')}"
             if t["plate_read_rate"] is not None else _UNMEASURED_READS)
    vram = (f"{gpu['peak_mib']} MiB (baseline before window: "
            f"{gpu['baseline_mib']} MiB)" if gpu["available"]
            else "unmeasured (nvidia-smi unavailable)")
    lines = [
        f"## Measured run — {stamp} "
        f"({result['window_s']:.0f} s window, sample every "
        f"{result['sample_s']:.0f} s)",
        "",
        "| Measurement | Value | Where measured |",
        "|---|---|---|",
        f"| Sustained inference fps per camera, N active | "
        f"{_fmt_per_cam(rows, 'fps')} (N={n}, {alive} alive at end) | {where} |",
        f"| Real detection rate (vehicles/camera/min) | "
        f"{_fmt_per_cam(rows, 'vehicles_per_min')} | {where} |",
        f"| Peak VRAM used | {vram} | {where} |",
        f"| Peak RAM used | {ram['combined']:.0f} MB "
        f"(api tree {ram['api']:.0f} + worker tree {ram['worker']:.0f}) | {where} |",
        f"| Motion-skip rate per camera | "
        f"{_fmt_per_cam(rows, 'motion_skip_rate')} | {where} |",
        f"| Plate-read rate (full reads / vehicle tracks) | {reads} | {where} |",
        "",
        f"- Detection boxes/min per camera (raw): {_fmt_per_cam(rows, 'boxes_per_min')}",
        f"- Sightings in window: {t['sightings']}; zone events: {t['zone_events']}; "
        f"alerts: {t['alerts']}",
        f"- Worker restarts in window: {result['restarts_in_window']}",
        f"- RAM trend: Q1 avg {result['ram_trend']['q1_mb']:.0f} MB -> Q4 avg "
        f"{result['ram_trend']['q4_mb']:.0f} MB ({result['ram_trend']['drift_pct']:+.1f}%); "
        f"steady-state Q3 -> Q4 {result['ram_trend']['steady_pct']:+.1f}%",
    ]
    if not result["warmup_ok"]:
        lines.append(
            f"- **WARM-UP NOT SATISFIED** (uptime {result['warmup_uptime_s']:.0f} s "
            f"at start; F18 wants >= {result['warmup_min']:.0f} min) — "
            "NOT valid for the [measured] rows")
    if result["crashed"]:
        lines.append("- **PLATFORM DIED MID-WINDOW** — partial evidence only")
    return "\n".join(lines) + "\n"


def _quartile_trend(series: list[float]) -> dict[str, float]:
    if not series:
        return {"q1_mb": 0.0, "q3_mb": 0.0, "q4_mb": 0.0,
                "drift_pct": 0.0, "steady_pct": 0.0}
    q = max(len(series) // 4, 1)
    q1 = sum(series[:q]) / q
    q3s = series[2 * q:3 * q] or series[:q]
    q3 = sum(q3s) / len(q3s)
    q4 = sum(series[-q:]) / q
    return {"q1_mb": round(q1, 1), "q3_mb": round(q3, 1),
            "q4_mb": round(q4, 1),
            "drift_pct": round((q4 - q1) / max(q1, 1e-9) * 100, 1),
            "steady_pct": round((q4 - q3) / max(q3, 1e-9) * 100, 1)}


def main(argv: list[str] | None = None) -> int:
    """Run the window measurement against the running platform.

    Returns 0 on a completed window (low counts are findings), 2 when
    the API or the worker process died mid-window. Raises SystemExit
    with a message for precondition failures (platform not running,
    stats stale, warm-up not met without --allow-cold).
    """
    ap = argparse.ArgumentParser(description="F18 window sampler (S4.1)")
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--sample-s", type=float, default=5.0)
    ap.add_argument("--warmup-min", type=float, default=10.0)
    ap.add_argument("--allow-cold", action="store_true",
                    help="measure before the F18 warm-up (marked in the "
                         "output; not valid for the [measured] rows)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--pidfile", type=Path, default=PIDFILE)
    ap.add_argument("--stats", type=Path, default=STATS)
    args = ap.parse_args(argv)
    if args.minutes <= 0 or args.sample_s <= 0:
        ap.error("--minutes and --sample-s must be positive")

    pids = _read_pidfile(args.pidfile)
    if "api" not in pids or "worker" not in pids:
        raise SystemExit(
            f"no running platform recorded ({args.pidfile}) - "
            "python launch.py start first, warm up, then measure")
    procs: dict[str, psutil.Process] = {}
    for name in ("api", "worker"):
        try:
            procs[name] = psutil.Process(pids[name])
        except psutil.NoSuchProcess:
            raise SystemExit(
                f"{name} process {pids[name]} is not running - "
                "python launch.py start first") from None

    if not args.stats.exists():
        raise SystemExit(f"{args.stats} missing - is the worker running?")
    stats_age = time.time() - args.stats.stat().st_mtime
    if stats_age > STATS_STALE_S:
        raise SystemExit(
            f"{args.stats} is {stats_age:.0f} s old (supervisor writes "
            "every 10 s) - the pipeline looks wedged; fix that first")

    base = _read_stats(args.stats)
    uptime = float(base.get("uptime_s", 0.0))
    warmup_ok = uptime >= args.warmup_min * 60
    if not warmup_ok and not args.allow_cold:
        raise SystemExit(
            f"warm-up not met: worker uptime {uptime:.0f} s < "
            f"{args.warmup_min:.0f} min (F18). Wait, or pass --allow-cold "
            "for a non-[measured] check run")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    baseline_gpu = _gpu_used_mib()
    gpu_available = baseline_gpu is not None
    print(f"[measure] window {args.minutes:g} min, sample every "
          f"{args.sample_s:g} s; stats uptime {uptime:.0f} s; "
          f"GPU {'baseline %d MiB' % baseline_gpu if gpu_available else 'unmeasured'}")

    t0 = time.monotonic()
    t_end = t0 + args.minutes * 60
    peak = {"api": 0.0, "worker": 0.0, "combined": 0.0}
    peak_gpu = baseline_gpu or 0
    ram_series: list[float] = []
    samples: list[dict[str, Any]] = []
    crashed = False
    while time.monotonic() < t_end:
        _sleep(min(args.sample_s, max(t_end - time.monotonic(), 0.01)))
        dead = [n for n, p in procs.items() if not p.is_running()]
        if dead:
            crashed = True
            print(f"[measure] {' and '.join(dead).upper()} PROCESS DIED - "
                  "aborting window")
            break
        rss = {n: _tree_rss_mb(p) for n, p in procs.items()}
        combined = sum(rss.values())
        gpu = _gpu_used_mib() if gpu_available else None
        snap = _read_stats(args.stats)
        cams = snap.get("cameras", {})
        n_alive = sum(1 for c in cams.values() if c.get("alive"))
        for name in ("api", "worker"):
            peak[name] = max(peak[name], rss[name])
        peak["combined"] = max(peak["combined"], combined)
        if gpu is not None:
            peak_gpu = max(peak_gpu, gpu)
        ram_series.append(combined)
        samples.append({"t_s": round(time.monotonic() - t0, 1),
                        "rss_api_mb": round(rss["api"], 1),
                        "rss_worker_mb": round(rss["worker"], 1),
                        "gpu_mib": gpu,
                        "workers_alive": n_alive,
                        "sightings": snap.get("sightings", 0)})
        left = max(t_end - time.monotonic(), 0)
        print(f"[measure] {left:5.0f}s left | RAM {combined:6.0f} MB"
              f" | GPU {gpu if gpu is not None else '?':>5} MiB"
              f" | workers {n_alive}/{len(cams)}"
              f" | sightings {snap.get('sightings', 0)}")

    final = _read_stats(args.stats)
    window_s = time.monotonic() - t0
    rows = window_rows(base, final, window_s)
    totals = {k: sum(r[k] for r in rows.values())
              for k in ("frames", "detections", "sightings", "alerts",
                        "zone_events", "full_reads", "vehicle_tracks",
                        "ocr_attempts")}
    totals["plate_read_rate"] = (
        round(totals["full_reads"] / max(1, totals["vehicle_tracks"]), 3)
        if rows and all(r["read_counters"] for r in rows.values()) else None)
    result: dict[str, Any] = {
        "measured_at": stamp,
        "planned_minutes": args.minutes,
        "window_s": round(window_s, 1),
        "sample_s": args.sample_s,
        "warmup_ok": warmup_ok,
        "warmup_uptime_s": round(uptime, 1),
        "warmup_min": args.warmup_min,
        "crashed": crashed,
        "n_active": len(rows),
        "cameras": rows,
        "totals": totals,
        "restarts_in_window": max(
            final.get("restarts", 0) - base.get("restarts", 0), 0),
        "peak_rss_mb": {k: round(v, 1) for k, v in peak.items()},
        "ram_trend": _quartile_trend(ram_series),
        "gpu": {"available": gpu_available, "baseline_mib": baseline_gpu,
                "peak_mib": peak_gpu if gpu_available else None},
        "samples": samples,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"{stamp}.json"
    json_path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    md = render_markdown(result)
    md_path = args.out_dir / f"{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    print()
    print(md)
    print(f"[measure] evidence: {json_path} and {md_path} "
          "(data/measurements/ is committed on purpose)")
    return 2 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
