"""Per-frame ANPR cascade (task S2.4; ml/CLAUDE.md).

motion gate → detector → tracker → OCR budget → **consensus voting** per
track → committed reads for :func:`ml.anpr.sightings.record_sighting`.

OCR budget (measured §7: ~0.45 s/crop on CPU): skip tracks whose full
consensus is already committed; ≥ 1.5 s of stream time between reads per
track; ≤ 2 crops per frame, largest first.

Consensus: per-character majority weighted by confidence over the
track's reads (within the modal length group). A consensus is committed
when ≥ 2 reads agree on it, or when the track dies holding ≥ 1 full
read — never a first-read latch (review D10).

Object-event and zone-event hooks are the ``on_result`` callback wiring
S2.5 adds; this module stays storage-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.core import plates
from backend.core.logging_setup import setup
from ml.anpr.detect import Detection, Detector, parse_roi
from ml.anpr.motion import MotionGate, gate_for_camera
from ml.anpr.ocr import PlateOcr, PlateRead
from ml.anpr.track import Track, Tracker
from ml.ingest.base import FrameTick

log = setup("pipeline")

OCR_MIN_GAP_MS = 1500.0
OCR_MAX_CROPS_PER_FRAME = 2

# Evidence visuals (S7.2, decision F73). Colours mirror
# frontend/src/styles/tokens.css so drawn boxes read as the product's own:
# amber --warn #e0912f (plate box), red --sev-critical #ff3b5c (vehicle
# box on a hit's evidence frame — drawn by the worker).
PLATE_BOX_BGR = (47, 145, 224)
VEHICLE_BOX_BGR = (92, 59, 255)
VEHICLE_PX_MAX_WIDTH = 240
EVIDENCE_MAX_WIDTH = 1280
EVIDENCE_JPEG_QUALITY = 80


@dataclass
class EvidenceJpeg:
    """The whole frame a read came from — encoded at once (≤ 1280 px wide,
    JPEG q80, raw, nothing drawn) so a track never holds a raw frame; the
    worker decodes, annotates and stores it only when the read becomes a
    watchlist hit (F73). ``scale`` maps source pixels to JPEG pixels. The
    boxes are those of THIS frame, because the committed read may borrow
    the frame from a different read of the same track."""

    jpeg: bytes
    scale: float
    plate_bbox: tuple[int, int, int, int] | None = None     # [x, y, w, h], source px
    vehicle_xyxy: tuple[int, int, int, int] | None = None   # source px


def _vehicle_thumb(vehicle_crop: np.ndarray,
                   plate_bbox: tuple[int, int, int, int],
                   offset: tuple[int, int]) -> np.ndarray | None:
    """The read's vehicle crop, ≤ 240 px wide, with the plate box drawn in
    amber (2 px). *plate_bbox* is [x, y, w, h] in source pixels; *offset*
    is the crop's top-left in the source frame."""
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None
    scale = min(1.0, VEHICLE_PX_MAX_WIDTH / max(1, vehicle_crop.shape[1]))
    if scale < 1.0:
        thumb = cv2.resize(vehicle_crop, (VEHICLE_PX_MAX_WIDTH,
                           max(1, int(vehicle_crop.shape[0] * scale))))
    else:
        thumb = vehicle_crop.copy()
    px, py, pw, ph = plate_bbox
    x1 = int((px - offset[0]) * scale)
    y1 = int((py - offset[1]) * scale)
    x2, y2 = int(x1 + pw * scale), int(y1 + ph * scale)
    cv2.rectangle(thumb, (x1, y1), (x2, y2), PLATE_BOX_BGR, 2)
    return thumb


def _encode_evidence(frame: np.ndarray,
                     plate_bbox: tuple[int, int, int, int] | None = None,
                     vehicle_xyxy: tuple[int, int, int, int] | None = None,
                     ) -> EvidenceJpeg | None:
    """The whole frame, raw, nothing drawn, ≤ 1280 px wide, JPEG q80, with
    the boxes that belong to it."""
    h, w = frame.shape[:2]
    scale = min(1.0, EVIDENCE_MAX_WIDTH / max(1, w))
    img = cv2.resize(frame, (int(w * scale), max(1, int(h * scale)))) if scale < 1.0 else frame
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, EVIDENCE_JPEG_QUALITY])
    if not ok:
        return None
    return EvidenceJpeg(jpeg=buf.tobytes(), scale=scale,
                        plate_bbox=plate_bbox, vehicle_xyxy=vehicle_xyxy)


@dataclass
class CommittedRead:
    """A consensus ready to become a sighting row."""

    track_id: int
    plate: str            # normalised consensus; coerced when kind == full (§6)
    plate_raw: str        # a genuine OCR output backing the consensus
    confidence: float
    bbox: tuple[int, int, int, int]
    vehicle_class: str
    kind: str             # full | partial
    pts_ms: float
    crop: object = None   # the backing read's plate pixels (np.ndarray | None)
    # Evidence visuals (S7.2, F73) — all from the backing read:
    vehicle_px: object = None                  # np.ndarray | None, ≤ 240 px, plate box drawn
    evidence: EvidenceJpeg | None = None       # the whole frame, only on the track's best read
    vehicle_xyxy: tuple[int, int, int, int] | None = None  # source pixels


@dataclass
class FrameResult:
    moving: bool
    detections: list[Detection] = field(default_factory=list)
    matches: list[tuple[Track, Detection]] = field(default_factory=list)
    committed: list[CommittedRead] = field(default_factory=list)
    ocr_attempts: int = 0
    restart: bool = False


def consensus(reads: list[PlateRead]) -> tuple[str, float] | None:
    """Confidence-weighted per-character majority over *reads*.

    Reads are grouped by text length; the group with the highest total
    confidence votes. Returns ``(text, confidence)`` or None.
    """
    if not reads:
        return None
    groups: dict[int, list[PlateRead]] = {}
    for read in reads:
        groups.setdefault(len(read.text), []).append(read)
    voters = max(groups.values(), key=lambda g: sum(r.conf for r in g))
    length = len(voters[0].text)
    text_chars: list[str] = []
    char_confs: list[float] = []
    for i in range(length):
        weights: dict[str, float] = {}
        for read in voters:
            weights[read.text[i]] = weights.get(read.text[i], 0.0) + read.conf
        winner = max(weights, key=lambda c: weights[c])
        text_chars.append(winner)
        char_confs.append(weights[winner] / sum(weights.values()))
    mean_read_conf = sum(r.conf for r in voters) / len(voters)
    return "".join(text_chars), mean_read_conf * (sum(char_confs) / length)


class AnprPipeline:
    """One per camera worker; detector and OCR instances are shared."""

    def __init__(self, detector: Detector, ocr: PlateOcr,
                 camera_row=None, gate: MotionGate | None = None) -> None:
        self.detector = detector
        self.ocr = ocr
        self.gate = gate or (gate_for_camera(camera_row) if camera_row is not None
                             else MotionGate())
        self.tracker = Tracker()
        self.roi = (parse_roi(camera_row["roi_json"])
                    if camera_row is not None and "roi_json" in camera_row.keys() else None)

    def _commit(self, track: Track, out: list[CommittedRead], pts_ms: float,
                need_agreement: bool) -> None:
        """Append the track's consensus to *out* when the commit rule holds."""
        result = consensus(track.ocr_reads)
        if result is None:
            return
        text, conf = result
        kind = plates.plate_like(text) or "partial"
        # A full read is stored in its structurally coerced form
        # (docs/api.md §6), so 6J23H1548 and GJ23H1548 are one plate for
        # search, dedupe and the watchlist match; plate_raw keeps the OCR
        # text. Partial reads are stored as read — never coerced (F40).
        stored = plates.coerce(text) if kind == "full" else None
        stored = stored or text
        if stored in track.committed_plates:
            return
        agreeing = sum(1 for r in track.ocr_reads if r.text == text)
        if need_agreement:
            if agreeing < 2:
                return
        elif not any(r.kind == "full" for r in track.ocr_reads):
            return  # dying track: only with >= 1 full read
        backing = max((r for r in track.ocr_reads if r.text == text),
                      key=lambda r: r.conf, default=track.ocr_reads[-1])
        # The one frame JPEG sits on the track's highest-confidence read,
        # which may have spelt the plate differently from the consensus;
        # the committed read borrows it then (same vehicle, same track), so
        # a watchlist hit never goes without its evidence frame.
        evidence = backing.evidence or next(
            (r.evidence for r in track.ocr_reads if r.evidence is not None), None)
        track.committed_plates.add(stored)
        if kind == "full":
            track.committed_full = True
        out.append(CommittedRead(
            track_id=track.id, plate=stored, plate_raw=backing.raw, confidence=conf,
            bbox=backing.bbox, vehicle_class=track.cls, kind=kind, pts_ms=pts_ms,
            crop=backing.crop, vehicle_px=backing.vehicle_px,
            evidence=evidence, vehicle_xyxy=backing.vehicle_xyxy))

    def process(self, tick: FrameTick) -> FrameResult:
        committed: list[CommittedRead] = []
        if tick.restart:
            # Dying tracks may still hold a usable full read — commit first.
            for track in self.tracker.tracks.values():
                self._commit(track, committed, tick.pts_ms, need_agreement=False)
            self.gate.reset()
            self.tracker.reset()
        if not self.gate.moving(tick.frame):
            return FrameResult(moving=False, committed=committed, restart=tick.restart)

        detections = self.detector.detect(tick.frame, roi=self.roi)
        matches = self.tracker.update(detections, tick.pts_ms)
        for track in self.tracker.last_removed:
            self._commit(track, committed, tick.pts_ms, need_agreement=False)

        # OCR budget: largest vehicle boxes first, at most 2 crops a frame.
        due = [
            (track, det) for track, det in matches
            if det.superclass == "vehicle" and not track.committed_full
            and tick.pts_ms - track.last_ocr_pts >= OCR_MIN_GAP_MS
        ]
        due.sort(key=lambda pair: -(pair[1].xyxy[2] - pair[1].xyxy[0])
                 * (pair[1].xyxy[3] - pair[1].xyxy[1]))
        ocr_attempts = 0
        frame_h = tick.frame.shape[0]
        for track, det in due[:OCR_MAX_CROPS_PER_FRAME]:
            x1, y1, x2, y2 = (int(v) for v in det.xyxy)
            crop = tick.frame[max(0, y1):y2, max(0, x1):x2]
            track.last_ocr_pts = tick.pts_ms
            ocr_attempts += 1
            offset = (max(0, x1), max(0, y1))
            reads = self.ocr.read(crop, offset=offset, frame_h=frame_h)
            if not reads:
                continue
            best = max(reads, key=lambda r: r.conf)
            # Evidence visuals (S7.2, F73) are attached HERE — this method
            # holds both the vehicle box and tick.frame, so ocr.read stays
            # frame-free (ml/CLAUDE.md). The full frame is encoded only
            # when this read becomes the track's best, and the previous
            # best drops its copy: a track holds at most one frame JPEG.
            best.vehicle_xyxy = (offset[0], offset[1], int(x2), int(y2))
            best.vehicle_px = _vehicle_thumb(crop, best.bbox, offset)
            prev_best = (max(track.ocr_reads, key=lambda r: r.conf)
                         if track.ocr_reads else None)
            if prev_best is None or best.conf > prev_best.conf:
                best.evidence = _encode_evidence(tick.frame, best.bbox, best.vehicle_xyxy)
                if prev_best is not None:
                    prev_best.evidence = None
            track.ocr_reads.append(best)
            self._commit(track, committed, tick.pts_ms, need_agreement=True)

        return FrameResult(moving=True, detections=detections, matches=matches,
                           committed=committed, ocr_attempts=ocr_attempts,
                           restart=tick.restart)
