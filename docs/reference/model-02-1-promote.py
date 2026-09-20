#!/usr/bin/env python3
"""
Model 2.1 -- PIPELINE 3 "promote" step.
On a watchlist hit, lift [t-PRE, t+POST] out of the rolling ring buffer
into the evidence store. No re-encode, keyframe-aligned, audit-logged.
"""
import sys, os, re, json, time, hashlib, subprocess, datetime as dt

BUF   = "buf"
PLIST = os.path.join(BUF, "cam12.m3u8")
EVID  = "evidence"
PRE, POST = 30, 30           # seconds either side of the event


def read_playlist():
    """Return [(filename, program_date_time, duration)] for segments still on disk."""
    txt = open(PLIST).read()
    segs, pdt, dur = [], None, None
    for line in txt.splitlines():
        if line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
            pdt = dt.datetime.fromisoformat(line.split(":", 1)[1].strip())
        elif line.startswith("#EXTINF:"):
            dur = float(line.split(":", 1)[1].rstrip(","))
        elif line and not line.startswith("#"):
            p = os.path.join(BUF, line.strip())
            if pdt and os.path.exists(p):
                segs.append((p, pdt, dur))
            pdt = dur = None
    return segs


def promote(event_ts, plate, camera, event_id):
    lo = event_ts - dt.timedelta(seconds=PRE)
    hi = event_ts + dt.timedelta(seconds=POST)

    # The post-event window has not happened yet -> wait for it to be written.
    while True:
        segs = read_playlist()
        if segs and segs[-1][1] + dt.timedelta(seconds=segs[-1][2]) >= hi:
            break
        if not segs:
            time.sleep(1); continue
        behind = (hi - (segs[-1][1] + dt.timedelta(seconds=segs[-1][2]))).total_seconds()
        print(f"    waiting {behind:.0f}s for post-event segments...")
        time.sleep(min(behind + 1, 10))

    # Select only segments overlapping the window.
    want = [s for s in segs if s[1] < hi and (s[1] + dt.timedelta(seconds=s[2])) > lo]
    if not want:
        raise RuntimeError("window not in buffer -- buffer too shallow or event too old")

    os.makedirs(EVID, exist_ok=True)
    lst = os.path.join(EVID, f"{event_id}.txt")
    with open(lst, "w") as f:
        for p, _, _ in want:
            f.write(f"file '{os.path.abspath(p)}'\n")

    out = os.path.join(EVID, f"{event_id}.mp4")
    # -c copy : COPY the compressed packets. No decode, no re-encode, no quality loss.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", "-movflags", "+faststart", out],
        check=True)
    os.remove(lst)

    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    rec = {
        "event_id":     event_id,
        "plate":        plate,
        "camera":       camera,
        "event_time":   event_ts.isoformat(),
        "window":       [lo.isoformat(), hi.isoformat()],
        "segments_used": [os.path.basename(p) for p, _, _ in want],
        "clip":         out,
        "bytes":        os.path.getsize(out),
        "sha256":       sha,
        "trigger":      "watchlist_match:stolen_vehicle",
        "promoted_at":  dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with open(os.path.join(EVID, "audit.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    # Simulate ANPR firing "now minus 20s" (detection latency + operator reaction).
    now = dt.datetime.now(dt.timezone.utc)
    ev  = now - dt.timedelta(seconds=20)
    print(f"[ALERT] plate=GJ01AB1234 camera=CAM-12 at {ev.isoformat()}")
    print(f"    requesting window  -{PRE}s .. +{POST}s")
    t0 = time.time()
    rec = promote(ev, "GJ01AB1234", "CAM-12", "EVT-0001")
    print(f"[PROMOTED] in {time.time()-t0:.1f}s wall (incl. post-event wait)")
    print(json.dumps(rec, indent=2))
