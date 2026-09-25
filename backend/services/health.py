"""Camera health checker (decisions C14, F31; FR-1.5).

Ported from ``D:\\projects\\Sentinel_Repo\\src\\ingest\\health.py`` (F52)
with the fresh build's rules:

- **Active RTSP cameras are judged by their worker's local tee freshness
  and are never probed**: the worker already holds the camera's single
  pull (root rule 2 — a probe would be a second connection), and never via
  the CDN (C14: a CDN probe once flipped 29/30 cameras offline and emptied
  the active set). Fresh tee → online; stale tee → degraded (the worker is
  reconnecting); absent tee → unchanged (no worker proves nothing about
  the camera). *The old build probed non-RTSP cameras through the CDN —
  that is the defect this module removes (F31).*
- **Other sandbox cameras are probed over RTSP with ffprobe**, paced two
  at a time with a 20 s timeout, `-rtsp_transport tcp` and `-timeout`
  (never ``-rw_timeout``, decision F44). Stream answers → online,
  otherwise offline.
- **Probes first, then one short write transaction** — a write is never
  held across a network call (backend/CLAUDE.md SQLite rules).

Runs as a background thread in the API process (``SENTINEL_HEALTH_INTERVAL_S``,
0 = off). The first pass runs ``FIRST_PASS_DELAY_S`` after start (startup
stays quiet), then every interval — waiting a whole interval first left the
map and header showing the previous run's health ("1/58 online") for five
minutes after every ``launch.py start`` (found 25 Sep on the live platform).
The credentialed RTSP URL exists only in memory and is never logged
unmasked, and the credentials are filled in only for a template on the
sandbox gateway — any other host is probed without them (root rule 1).
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.core import config
from backend.core import db as dbmod
from backend.core.logging_setup import setup

log = setup("health")

#: A local tee younger than this is live (task S3.1b: fresh < 20 s). Shared
#: with the HLS relay, which prefers a fresh tee over the CDN.
TEE_FRESH_S = 20.0
#: ffprobe budget per camera; the pass tolerates slow gateways, not hangs.
PROBE_TIMEOUT_S = 20.0
#: Paced probing — two concurrent RTSP probes, never a burst.
PROBE_WORKERS = 2
#: RTSP socket timeout in microseconds; the flag is ``-timeout`` (F44).
_RTSP_SOCKET_TIMEOUT_US = "15000000"


#: Seconds after start before the first pass (then every interval).
FIRST_PASS_DELAY_S = 30.0


def tee_playlist(camera_id: str) -> Path:
    """The worker's local HLS tee playlist for *camera_id*."""
    return config.hls_dir() / camera_id / "index.m3u8"


def tee_age_s(camera_id: str) -> float | None:
    """Seconds since the worker's tee playlist was last written, or None
    when no tee exists (no worker on this camera)."""
    try:
        return time.time() - tee_playlist(camera_id).stat().st_mtime
    except OSError:
        return None


def _is_sandbox_gateway(template: str) -> bool:
    """True when *template* is an ``rtsp://`` URL on the configured sandbox
    gateway (``config.stream_ip()`` : ``config.rtsp_port()``, 554 when the
    template names no port) — the only host the organisers' credentials may
    ever be sent to (root rule 1). A template with whitespace, control
    characters or a backslash is refused outright, so no parser disagreement
    between this check and ffprobe can move the credentials elsewhere."""
    if "\\" in template or any(ord(c) <= 0x20 or ord(c) == 0x7F for c in template):
        return False
    try:
        parts = urllib.parse.urlsplit(template)
        port = parts.port if parts.port is not None else 554
    except ValueError:
        return False
    gateway = config.stream_ip().strip().strip("[]").lower()
    return (
        parts.scheme.lower() == "rtsp"
        and (parts.hostname or "") == gateway
        and port == config.rtsp_port()
    )


def _resolve_rtsp_url(camera_id: str, template: str | None) -> str:
    """The camera's RTSP URL, built in memory only (mirrors
    ``ml.ingest.rtsp.resolve_url`` — duplicated because the API process
    never imports the worker package). Never log or store the result.

    ``<email>``/``<password>`` placeholders are filled **only** when the
    template points at the sandbox gateway (:func:`_is_sandbox_gateway`);
    a template on any other host is returned as-is, placeholders and all,
    so a registered camera can never make the probe hand the organisers'
    credentials to a host of its choosing (root rule 1)."""
    email = urllib.parse.quote(config.email(), safe="")
    password = urllib.parse.quote(config.password(), safe="")
    if template:
        if "<email>" not in template and "<password>" not in template:
            return template  # a plain local URL, used as-is
        if not _is_sandbox_gateway(template):
            log.warning(
                "camera %s: credential placeholders on a host that is not the"
                " sandbox gateway - probed as-is, without credentials (root rule 1)",
                camera_id,
            )
            return template
        return template.replace("<email>", email).replace("<password>", password)
    return (
        f"rtsp://{email}:{password}@{config.stream_ip()}:{config.rtsp_port()}"
        f"/stream/{camera_id}"
    )


def probe_rtsp(url: str, timeout_s: float = PROBE_TIMEOUT_S) -> bool:
    """True when the RTSP stream answers with a video stream.

    Runs ffprobe (through :func:`backend.core.config.ffprobe`) over TCP.
    Unreachable, refused, timed out or streamless all return False — an
    unreachable camera is a valid verdict, not an error. Never raises with
    the credentialed URL in the message (root rule 1).
    """
    cmd = [
        config.ffprobe(), "-v", "error", "-rtsp_transport", "tcp",
        "-timeout", _RTSP_SOCKET_TIMEOUT_US, "-select_streams", "v:0",
        "-show_entries", "stream=codec_name", "-of", "json", url,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        # TimeoutExpired.cmd carries the credentialed argv; swallow it whole.
        return False
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("ffprobe could not run: %s", config.masked(str(exc)))
        return False
    if out.returncode != 0:
        log.debug("probe refused: %s", config.masked((out.stderr or "").strip())[-200:])
        return False
    try:
        return bool(json.loads(out.stdout).get("streams"))
    except (json.JSONDecodeError, AttributeError):
        return False


def check_all() -> dict[str, int]:
    """One health pass over every camera; returns the verdict tally.

    Reads the registry (short read), gathers every verdict — tee freshness
    for active RTSP cameras, paced RTSP ffprobe for the rest — and only
    then opens one short write transaction. The CDN is never touched.
    """
    con = dbmod.connect()
    try:
        cams = [
            dict(r)
            for r in con.execute(
                "SELECT camera_id, transport, fps_tier, rtsp_url_template FROM cameras"
            )
        ]
    finally:
        con.close()

    verdicts: dict[str, str] = {}
    tally = {"online": 0, "degraded": 0, "offline": 0, "unchanged": 0}
    to_probe: list[dict] = []
    for cam in cams:
        cid = cam["camera_id"]
        if cam["transport"] == "rtsp" and cam["fps_tier"] == "active":
            age = tee_age_s(cid)
            if age is None:
                # No worker tee: nothing to conclude about the CAMERA, and
                # never probe it — the worker may hold its one pull (rule 2).
                tally["unchanged"] += 1
            elif age <= TEE_FRESH_S:
                verdicts[cid] = "online"
            else:
                verdicts[cid] = "degraded"  # worker reconnecting / tee stalled
        elif cam["transport"] in ("rtsp", "hls"):
            to_probe.append(cam)
        else:
            # replay/none: local demo sources, not health-checked here.
            tally["unchanged"] += 1

    if to_probe:
        def _one(cam: dict) -> tuple[str, bool]:
            url = _resolve_rtsp_url(cam["camera_id"], cam["rtsp_url_template"])
            return cam["camera_id"], probe_rtsp(url)

        with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
            for cid, ok in pool.map(_one, to_probe):
                verdicts[cid] = "online" if ok else "offline"

    now = dbmod.utcnow()
    con = dbmod.connect()
    try:
        for cid, status in verdicts.items():
            tally[status] += 1
            if status == "online":
                con.execute(
                    "UPDATE cameras SET health = 'online', last_seen = ?,"
                    " updated_at = ? WHERE camera_id = ?",
                    (now, now, cid),
                )
            else:
                con.execute(
                    "UPDATE cameras SET health = ?, updated_at = ? WHERE camera_id = ?",
                    (status, now, cid),
                )
        con.commit()
    finally:
        con.close()
    log.info("health pass: %s", tally)
    return tally


def run_loop(interval_s: float, stop: threading.Event,
             first_delay_s: float | None = None) -> None:
    """Run health passes every *interval_s* until *stop* is set.

    The first pass waits *first_delay_s* (default ``FIRST_PASS_DELAY_S``,
    never longer than the interval): startup stays quiet and a short-lived
    test app never fires one, yet the registry's health is current within
    seconds of a start instead of a whole interval later. A failed pass is
    logged and the loop continues — a health loop must not die (root §7:
    no silent failure, but a checker crash must not take the API down).
    """
    delay = min(FIRST_PASS_DELAY_S if first_delay_s is None else first_delay_s,
                interval_s)
    while not stop.wait(delay):
        delay = interval_s
        try:
            check_all()
        except Exception:
            log.exception("health pass failed; continuing")


def start_background() -> threading.Event | None:
    """Start the checker thread per ``SENTINEL_HEALTH_INTERVAL_S``.

    Returns the stop event (set it to end the loop), or None when the
    checker is configured off (interval <= 0).
    """
    interval = config.health_interval_s()
    if interval <= 0:
        log.info("health checker off (SENTINEL_HEALTH_INTERVAL_S=0)")
        return None
    stop = threading.Event()
    threading.Thread(
        target=run_loop, args=(interval, stop), name="health-checker", daemon=True
    ).start()
    log.info("health checker every %.0f s", interval)
    return stop
