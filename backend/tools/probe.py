"""Live probe — first contact with the sandbox (decisions C6, F35).

Fetches the catalogue to ``data/cameras_raw.json``, then per camera:
an RTSP ffprobe (TCP, 20 s timeout, **4 at a time** — respect the
suspected session cap) and an HLS playlist head through the CDN session.
Writes registry rows (transport/health/last_seen and stream facts) without
ever touching seed-owned fields, and a masked
``data/probe_results_<YYYYMMDD>.json`` — the committed 14 Sep evidence
file is never overwritten.

Laptop-only in practice: RTSP is blocked from cloud workspaces and the
credentials live in Adi's ``.env``.

    python -m backend.tools.probe
"""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from backend.core import config
from backend.core import db as dbmod
from backend.core.cdn_session import CdnError, CdnSession
from backend.core.logging_setup import setup

RTSP_TIMEOUT_S = 20
RTSP_CONCURRENCY = 4

log = setup("probe")


def rtsp_url(camera_id: str) -> str:
    """The credentialed RTSP URL, built in memory only — never stored or
    logged unmasked (docs/reference/sandbox-access-spec.md §1)."""
    email = urllib.parse.quote(config.email(), safe="")
    password = urllib.parse.quote(config.password(), safe="")
    return (
        f"rtsp://{email}:{password}@{config.stream_ip()}:{config.rtsp_port()}"
        f"/stream/{camera_id}"
    )


def probe_rtsp(camera_id: str) -> dict[str, Any]:
    """ffprobe one camera over RTSP/TCP; a dict of stream facts or an error."""
    try:
        ffprobe = config.ffprobe()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    cmd = [
        ffprobe, "-v", "error", "-rtsp_transport", "tcp",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,profile,width,height,avg_frame_rate,pix_fmt",
        "-of", "json", rtsp_url(camera_id),
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=RTSP_TIMEOUT_S, check=False
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    if out.returncode != 0:
        return {"ok": False, "error": config.masked(out.stderr.strip()[:200] or "ffprobe failed")}
    try:
        stream = json.loads(out.stdout)["streams"][0]
    except (json.JSONDecodeError, LookupError):
        return {"ok": False, "error": "no video stream"}
    num, _, den = (stream.get("avg_frame_rate") or "0/1").partition("/")
    declared_fps = round(int(num) / int(den or 1), 2) if den and int(den or 1) else None
    return {
        "ok": True,
        "codec": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "declared_fps": declared_fps,
        "pix_fmt": stream.get("pix_fmt"),
    }


def probe_hls(session: CdnSession, camera_id: str) -> dict[str, Any]:
    """Playlist head through the session — gentle, one request per camera."""
    try:
        response = session.get(f"/{camera_id}/index.m3u8", max_attempts=2)
    except CdnError as exc:
        return {"ok": False, "error": config.masked(str(exc))}
    ok = response.text.lstrip().startswith("#EXTM3U")
    return {"ok": ok} if ok else {"ok": False, "error": "not a playlist"}


def fetch_catalogue(session: CdnSession) -> list[dict[str, str]]:
    entries = session.get("/cameras.json").json()
    path = config.REPO_ROOT / "data" / "cameras_raw.json"
    path.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    log.info("catalogue: %d cameras -> %s", len(entries), path)
    return entries


def write_registry(results: list[dict[str, Any]]) -> None:
    """Upsert stream facts; never overwrite seed-owned fields (F35)."""
    con = dbmod.connect()
    try:
        dbmod.migrate(con)
        now = dbmod.utcnow()
        for r in results:
            transport = "rtsp" if r["rtsp"].get("ok") else ("hls" if r["hls"].get("ok") else "none")
            health = "online" if transport != "none" else "offline"
            con.execute(
                "INSERT INTO cameras (camera_id, transport, health, last_seen, source,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, 'catalogue', ?, ?)"
                " ON CONFLICT(camera_id) DO UPDATE SET transport = excluded.transport,"
                " health = excluded.health, last_seen = excluded.last_seen,"
                " codec = COALESCE(?, codec), width = COALESCE(?, width),"
                " height = COALESCE(?, height), declared_fps = COALESCE(?, declared_fps),"
                " updated_at = excluded.updated_at",
                (
                    r["camera_id"], transport, health,
                    now if health == "online" else None, now, now,
                    r["rtsp"].get("codec"), r["rtsp"].get("width"),
                    r["rtsp"].get("height"), r["rtsp"].get("declared_fps"),
                ),
            )
        con.commit()
    finally:
        con.close()


def main() -> int:
    with CdnSession() as session:
        entries = fetch_catalogue(session)
        camera_ids = [e["id"] for e in entries]

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(RTSP_CONCURRENCY) as pool:
            rtsp_futures = {cid: pool.submit(probe_rtsp, cid) for cid in camera_ids}
            rtsp_results = {cid: f.result() for cid, f in rtsp_futures.items()}
        for cid in camera_ids:  # HLS sequentially — spare the rate limiter
            results.append(
                {
                    "camera_id": cid,
                    "hls": probe_hls(session, cid),
                    "rtsp": rtsp_results[cid],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = config.REPO_ROOT / "data" / f"probe_results_{stamp}.json"
    out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")

    rtsp_live = sum(1 for r in results if r["rtsp"].get("ok"))
    hls_live = sum(1 for r in results if r["hls"].get("ok"))
    errors_403 = sum(
        1 for r in results
        if "403" in str(r["hls"].get("error", "")) or "403" in str(r["rtsp"].get("error", ""))
    )
    write_registry(results)
    print(
        f"probe: {len(results)} cameras — RTSP live {rtsp_live}, HLS live {hls_live},"
        f" 403s {errors_403} -> {out_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
