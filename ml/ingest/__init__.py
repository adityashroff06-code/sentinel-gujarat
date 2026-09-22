"""Frame acquisition package: ``for_camera(row)`` builds the source a
registry row asks for (task S2.2; architecture: registry is the single
source of truth - nothing hard-codes a camera id or URL)."""

from __future__ import annotations

from typing import Any, Mapping

from backend.core import config
from ml.ingest.base import FrameSource


def for_camera(row: "Mapping[str, Any]", fps: float | None = None) -> FrameSource:
    """Build a frame source from a registry row, dispatching on ``transport``.

    ``rtsp`` -> :class:`~ml.ingest.rtsp.RtspFrameSource`, teeing a local HLS
    window under ``data/hls/<camera_id>/`` for the Live Wall (one pull per
    camera, root rule 2). ``replay`` -> :class:`~ml.ingest.replay.
    ReplayFrameSource` on the file named by ``rtsp_url_template``.
    ``hls`` -> ``NotImplementedError`` until S4.2. Anything else raises
    ``ValueError``.
    """
    row = dict(row)
    camera_id = row["camera_id"]
    transport = row.get("transport")
    if transport == "rtsp":
        from ml.ingest.rtsp import RtspFrameSource, resolve_url

        return RtspFrameSource(
            camera_id,
            resolve_url(camera_id, row.get("rtsp_url_template")),
            fps=fps,
            hls_dir=config.REPO_ROOT / "data" / "hls" / camera_id,
        )
    if transport == "replay":
        from ml.ingest.replay import ReplayFrameSource

        return ReplayFrameSource(row["rtsp_url_template"], fps=fps, name=camera_id)
    if transport == "hls":
        raise NotImplementedError(
            f"{camera_id}: hls transport is the CDN VOD reader - task S4.2"
        )
    raise ValueError(f"{camera_id}: no usable transport ({transport!r})")
