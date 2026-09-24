"""Live probe — first contact with the sandbox (decisions C6, F35, F45).

Fetches the catalogue (both published shapes — the sandbox's
``cameras.json`` and the Integrator's Guide's ``GET /api/ingest``;
``SENTINEL_CATALOGUE_URL`` overrides the source) to
``data/cameras_raw.json``, then per camera:
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
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

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


# --- catalogue adapter (task S3.7, decision F45) ---------------------------
# Accepts BOTH published catalogue shapes and normalises them to registry
# columns: the sandbox's cameras.json ({id, name}) and the Integrator's
# Guide's GET /api/ingest (id, location, codec, live status, stream
# properties, RTSP/WHEP/HLS URLs). Whatever the catalogue supplies is used
# verbatim; data/camera_seed.csv fills only what it does not carry
# (seed_registry.apply_seed).

CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # B11, at every boundary

# scheme://user:pass@ -> scheme://<email>:<password>@ (root rule 1: no stored
# URL ever carries a credential; quotes excluded so JSON text can be scrubbed)
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s\"']+@")

_CODECS = {"h264": "h264", "avc": "h264", "h265": "hevc", "hevc": "hevc"}
_STATUS_LIVE = {"live", "online", "up", "ok", "true", "1", "yes"}


def scrub_url(url: str) -> str:
    """Replace any ``scheme://user:pass@`` userinfo with the storage
    placeholders ``<email>:<password>@`` (docs/api.md §1 hygiene)."""
    return _URL_USERINFO.sub(r"\1<email>:<password>@", url)


def _entry_list(raw: Any) -> list[Any]:
    """The camera entries of a catalogue payload — a bare list, or a list
    wrapped in a one-key envelope. Raises ``ValueError`` on anything else."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("cameras", "streams", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
    raise ValueError("catalogue JSON is neither a list nor a wrapped list")


def catalogue_shape(raw: Any) -> str:
    """``'ingest'`` when any entry carries more than ``{id, name}``, else
    ``'cameras.json'`` (the write-off names which shape the grid served)."""
    for entry in _entry_list(raw):
        if isinstance(entry, dict) and set(entry) - {"id", "camera_id", "name"}:
            return "ingest"
    return "cameras.json"


def _first(entry: dict[str, Any], *names: str) -> Any:
    for name in names:
        if entry.get(name) is not None:
            return entry[name]
    return None


def normalise_catalogue(raw: Any) -> list[dict[str, Any]]:
    """Normalise a catalogue payload (either shape) to registry columns.

    Returns one dict per camera carrying ``camera_id`` plus ONLY the columns
    that entry actually supplied — the caller can therefore tell "catalogue
    said nothing" from "catalogue said null". Entries with an id that fails
    the B11 pattern are skipped with a warning, never invented or repaired.
    Raises ``ValueError`` when the payload is not a catalogue at all.
    """
    records: list[dict[str, Any]] = []
    for entry in _entry_list(raw):
        if not isinstance(entry, dict):
            log.warning("catalogue: skipping non-object entry %r", entry)
            continue
        raw_id = _first(entry, "id", "camera_id")
        camera_id = str(raw_id) if raw_id is not None else ""
        if not CAMERA_ID_RE.match(camera_id):
            log.warning("catalogue: skipping invalid camera id %r", raw_id)
            continue
        rec: dict[str, Any] = {"camera_id": camera_id}

        location = _first(entry, "location", "name")
        if isinstance(location, str) and location.strip():
            rec["location_name"] = location.strip()
        department = _first(entry, "department")
        if isinstance(department, str) and department.strip():
            rec["department"] = department.strip()
        lat = _first(entry, "lat", "latitude")
        lon = _first(entry, "lon", "lng", "longitude")
        if lat is not None and lon is not None:
            try:
                rec["lat"], rec["lon"] = float(lat), float(lon)
            except (TypeError, ValueError):
                log.warning("catalogue %s: unreadable coordinates %r/%r",
                            camera_id, lat, lon)

        codec = _first(entry, "codec")
        if isinstance(codec, str) and codec.strip():
            folded = codec.strip().lower().replace(".", "")
            rec["codec"] = _CODECS.get(folded, folded)
        for column, keys, cast in (
            ("width", ("width",), int),
            ("height", ("height",), int),
            ("declared_fps", ("fps", "frame_rate", "declared_fps"), float),
            ("bitrate_kbps", ("bitrate_kbps", "bitrate"), int),
        ):
            value = _first(entry, *keys)
            if value is not None:
                try:
                    rec[column] = cast(value)
                except (TypeError, ValueError):
                    log.warning("catalogue %s: unreadable %s %r",
                                camera_id, column, value)

        live = _first(entry, "live", "live_status", "status")
        if live is not None:
            if not isinstance(live, bool):
                live = str(live).strip().lower() in _STATUS_LIVE
            rec["health"] = "online" if live else "offline"

        for column, keys in (
            ("rtsp_url_template", ("rtsp", "rtsp_url")),
            ("whep_url_template", ("whep", "whep_url", "webrtc", "webrtc_url")),
            ("hls_url", ("hls", "hls_url")),
        ):
            url = _first(entry, *keys)
            if isinstance(url, str) and url.strip():
                rec[column] = scrub_url(url.strip())
        records.append(rec)
    return records


def load_catalogue_file(path: Path) -> list[dict[str, Any]]:
    """Read a catalogue JSON from disk (either shape) and normalise it."""
    return normalise_catalogue(json.loads(Path(path).read_text(encoding="utf-8")))


def fetch_catalogue(session: CdnSession | None = None) -> list[dict[str, Any]]:
    """Fetch the catalogue and return normalised registry-column records.

    ``SENTINEL_CATALOGUE_URL`` overrides the source — a local JSON file
    path, an absolute URL (a new grid's ``GET /api/ingest``, fetched
    plainly), or a CDN path/URL (fetched through the session). Unset, it is
    the sandbox's ``/cameras.json`` through the CDN session. A network
    fetch writes the raw payload, credential-scrubbed, to
    ``data/cameras_raw.json`` so the seeder stays offline-capable (F35); a
    local-file source never rewrites the committed catalogue.
    Raises ``CdnError``/``httpx.HTTPError``/``ValueError`` on failure.
    """
    src = config.catalogue_url()
    if src and not src.lower().startswith(("http://", "https://")):
        source_path = Path(src)
        if not source_path.is_absolute():
            source_path = config.REPO_ROOT / source_path
        records = load_catalogue_file(source_path)
        print(f"catalogue: {len(records)} cameras from {source_path.name}")
        return records

    if src and not src.startswith(config.cdn()):
        # A new grid's catalogue needs no CDN cookie — plain GET (consume only).
        response = httpx.get(src, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        raw = response.json()
    else:
        owned = session is None
        session = session or CdnSession()
        try:
            raw = session.get(src or "/cameras.json").json()
        finally:
            if owned:
                session.close()

    path = config.REPO_ROOT / "data" / "cameras_raw.json"
    path.write_text(scrub_url(json.dumps(raw, indent=1)), encoding="utf-8")
    shape = catalogue_shape(raw)
    records = normalise_catalogue(raw)
    print(f"catalogue: {len(records)} cameras ({shape} shape) -> {path.name}")
    log.info("catalogue: %d cameras (%s shape) -> %s", len(records), shape, path)
    return records


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
        camera_ids = [e["camera_id"] for e in entries]

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
