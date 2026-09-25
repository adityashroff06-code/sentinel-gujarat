"""Pydantic request AND response models — every endpoint declares a
response_model so the exported OpenAPI is the real contract (docs/api.md §7)."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CAMERA_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"

Department = Literal["Health", "Police", "GSRTC", "Panchayat", "Municipal", "Unknown"]
Transport = Literal["hls", "rtsp", "replay", "none"]
Ownership = Literal["government", "private"]
FpsTier = Literal["active", "registered"]

_USERINFO = re.compile(r"://[^/@\s]+@")


def _no_credentials(url: str | None) -> str | None:
    """No stored URL ever contains a credential — placeholders only (§1)."""
    if url and _USERINFO.search(url) and "<email>" not in url:
        raise ValueError("URL must not embed credentials; use <email>/<password> placeholders")
    return url


class CameraIn(BaseModel):
    camera_id: str = Field(pattern=CAMERA_ID_PATTERN)
    department: Department = "Unknown"
    location_name: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    bearing_deg: float | None = Field(default=None, ge=0, lt=360)
    fov_deg: float | None = Field(default=None, gt=0, le=360)
    range_m: float | None = Field(default=None, gt=0)
    codec: str | None = None
    hls_url: str | None = None
    rtsp_url_template: str | None = None
    whep_url_template: str | None = None
    transport: Transport = "none"
    ownership: Ownership = "government"
    fps_tier: FpsTier = "registered"
    roi_json: str | None = None
    zones_json: str | None = None
    source: Literal["catalogue", "manual", "csv", "api"] = "manual"
    notes: str | None = None

    _urls = field_validator("hls_url", "rtsp_url_template", "whep_url_template")(_no_credentials)


class CameraPatch(BaseModel):
    department: Department | None = None
    location_name: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    bearing_deg: float | None = Field(default=None, ge=0, lt=360)
    fov_deg: float | None = Field(default=None, gt=0, le=360)
    range_m: float | None = Field(default=None, gt=0)
    codec: str | None = None
    hls_url: str | None = None
    rtsp_url_template: str | None = None
    whep_url_template: str | None = None
    transport: Transport | None = None
    ownership: Ownership | None = None
    fps_tier: FpsTier | None = None
    health: Literal["online", "degraded", "offline"] | None = None
    roi_json: str | None = None
    zones_json: str | None = None
    notes: str | None = None

    _urls = field_validator("hls_url", "rtsp_url_template", "whep_url_template")(_no_credentials)


class CameraOut(BaseModel):
    camera_id: str
    department: str | None = None
    location_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    bearing_deg: float | None = None
    fov_deg: float | None = None
    range_m: float | None = None
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    declared_fps: float | None = None
    measured_fps: float | None = None
    bitrate_kbps: int | None = None
    hls_url: str | None = None
    rtsp_url_template: str | None = None
    whep_url_template: str | None = None
    transport: str | None = None
    ownership: str | None = None
    health: str | None = None
    last_seen: str | None = None
    fps_tier: str | None = None
    roi_json: str | None = None
    zones_json: str | None = None
    source: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class CameraListOut(BaseModel):
    total: int
    cameras: list[CameraOut]


class StreamOut(BaseModel):
    hls: str


class ImportRejected(BaseModel):
    row: int
    reason: str


class ImportOut(BaseModel):
    accepted: list[str]
    rejected: list[ImportRejected]


class OfflineCameraOut(BaseModel):
    camera_id: str
    health: str | None = None
    last_seen: str | None = None
    department: str | None = None


class IsolatedCoverageOut(BaseModel):
    camera_id: str
    nearest_neighbour_km: float
    radius_km: float


class DepartmentSummaryOut(BaseModel):
    total: int
    online: int


class GapAnalysisOut(BaseModel):
    generated_at: str
    cameras_total: int
    online: int
    active_tier: int
    cameras_offline_or_degraded: list[OfflineCameraOut]
    isolated_coverage: list[IsolatedCoverageOut]
    department_summary: dict[str, DepartmentSummaryOut]


class CameraActivityOut(BaseModel):
    """One camera's read activity over a trailing window (the GIS Activity
    layer). ``by_provenance`` splits ``sightings`` and
    ``alerts_by_provenance`` splits ``alerts`` so a demo read or a demo
    alert never passes as a live one (root rule 12)."""

    camera_id: str
    sightings: int
    plates: int
    alerts: int
    last_seen: str | None = None
    by_provenance: dict[str, int] = Field(default_factory=dict)
    alerts_by_provenance: dict[str, int] = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: str
    db: str
    time: str
    counts: dict[str, int]


class StatsOut(BaseModel):
    cameras_online: int
    cameras_total: int
    departments: int
    sightings_total: int
    plates_unique: int
    events_total: int
    zone_events: int
    alerts_active: int


class SessionIn(BaseModel):
    api_key: str


class SessionOut(BaseModel):
    role: str


class MessageOut(BaseModel):
    detail: str


# --- analytics (S3.1a; docs/api.md §2-§4, §7) ------------------------------

Provenance = Literal["live", "harvest", "demo", "test"]
WatchCategory = Literal[
    "stolen_vehicle", "wanted_person", "missing_person", "blacklisted", "suspect"
]
WatchSeverity = Literal["high", "medium", "low"]


class SightingOut(BaseModel):
    sighting_id: int
    plate: str
    plate_raw: str
    plate_canonical: str
    confidence: float
    camera_id: str
    seen_at: str
    wall_time: str
    clock_source: str
    provenance: str
    pts_ms: float | None = None
    bbox_json: str | None = None
    vehicle_class: str | None = None
    crop_path: str | None = None
    frame_path: str | None = None
    track_id: str | None = None
    created_at: str
    department: str | None = None
    location_name: str | None = None
    crop_url: str | None = None
    # how this row matched the plate query (null without one): exact |
    # ambiguity | fuzzy | contains; distance 0 for exact/ambiguity, the
    # confusion-weighted distance for fuzzy, null for contains (§6)
    match_type: Literal["exact", "ambiguity", "fuzzy", "contains"] | None = None
    match_distance: float | None = None


SightingMatch = Literal["contains", "exact", "anpr"]


class SightingQueryOut(BaseModel):
    """How the plate grammar read the query (docs/api.md §6)."""

    plate: str
    normalised: str
    canonical: str
    kind: Literal["full", "partial"] | None = None
    coerced: str | None = None


class SightingListOut(BaseModel):
    total: int
    count: int
    sightings: list[SightingOut]
    match: SightingMatch = "contains"
    query: SightingQueryOut | None = None


class PlateSuggestionOut(BaseModel):
    plate: str
    reads: int
    cameras: int
    last_seen: str | None = None
    provenance: str | None = None
    on_watchlist: bool
    #: which cameras read it — filled for ``top_live`` (so a caller can say
    #: where a live read came from: the organisers' feed or a stock clip);
    #: empty for ``demo`` and ``watchlist``
    camera_ids: list[str] = []


class PlateSuggestOut(BaseModel):
    demo: list[PlateSuggestionOut]
    watchlist: list[PlateSuggestionOut]
    top_live: list[PlateSuggestionOut]


class RouteStopOut(BaseModel):
    sequence: int
    camera_id: str
    department: str | None = None
    location_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    seen_at: str
    clock_source: str
    provenance: str
    plate_raw: str
    confidence: float
    match_type: Literal["exact", "ambiguity", "fuzzy"]
    match_distance: float
    suspect: bool
    crop_url: str | None = None
    elapsed_from_previous_s: int | None = None
    implied_speed_kmh: float | None = None


class RouteGapOut(BaseModel):
    after_sequence: int
    minutes: int
    note: str


class RouteOut(BaseModel):
    query_plate: str
    normalised: str
    match_mode: Literal["none", "exact", "ambiguity", "fuzzy"]
    total_sightings: int
    first_seen: str | None = None
    last_seen: str | None = None
    duration_seconds: int | None = None
    distance_km: float
    departments_crossed: list[str]
    stops: list[RouteStopOut]
    gaps: list[RouteGapOut]
    warnings: list[str]


class WatchlistIn(BaseModel):
    plate: str = Field(min_length=1)
    category: WatchCategory
    severity: WatchSeverity
    description: str | None = None
    source_ref: str | None = None


class WatchlistOut(BaseModel):
    watchlist_id: int
    plate: str
    plate_canonical: str
    category: str
    severity: str
    description: str | None = None
    reason: str | None = None
    authority: str | None = None
    source_ref: str | None = None
    expires_at: str | None = None
    active: int
    added_at: str


class WatchlistDeleteOut(BaseModel):
    deleted: int


class AlertOut(BaseModel):
    alert_seq: int
    alert_id: str
    kind: str
    sighting_id: int | None = None
    watchlist_id: int | None = None
    event_id: int | None = None
    zone_id: str | None = None
    plate: str | None = None
    plate_canonical: str | None = None
    camera_id: str
    category: str | None = None
    severity: str
    match_type: str
    match_distance: float
    clock_source: str
    fired_at: str
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    clip_path: str | None = None
    clip_sha256: str | None = None
    department: str | None = None
    location_name: str | None = None
    crop_url: str | None = None


class EventOut(BaseModel):
    event_id: int
    camera_id: str
    zone_id: str | None = None
    event_type: str
    object_class: str | None = None
    confidence: float | None = None
    occurred_at: str
    wall_time: str
    clock_source: str
    provenance: str
    bbox_json: str | None = None
    crop_path: str | None = None


class CameraEventSummaryOut(BaseModel):
    objects: dict[str, int] = Field(default_factory=dict)
    intrusion: int = 0
    line_cross: int = 0


class EventsSummaryOut(BaseModel):
    minutes: int
    total: int
    cameras: dict[str, CameraEventSummaryOut]


class WorkersOut(BaseModel):
    """The supervisor's stats snapshot (data/worker_stats.json), or
    ``available: false`` when no worker has written one yet."""

    available: bool
    written_at: str | None = None
    uptime_s: float | None = None
    restarts: int | None = None
    rss_mb: float | None = None
    frames: int | None = None
    fps_sustained: float | None = None
    inferred: int | None = None
    motion_skip_rate: float | None = None
    detections: int | None = None
    detections_per_min: float | None = None
    sightings: int | None = None
    alerts: int | None = None
    zone_events: int | None = None
    cameras: dict[str, dict[str, Any]] = Field(default_factory=dict)
