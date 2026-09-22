"""Pydantic request AND response models — every endpoint declares a
response_model so the exported OpenAPI is the real contract (docs/api.md §7)."""

from __future__ import annotations

import re
from typing import Literal

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
