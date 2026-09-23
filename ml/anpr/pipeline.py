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


@dataclass
class CommittedRead:
    """A consensus ready to become a sighting row."""

    track_id: int
    plate: str            # normalised consensus
    plate_raw: str        # a genuine OCR output backing the consensus
    confidence: float
    bbox: tuple[int, int, int, int]
    vehicle_class: str
    kind: str             # full | partial
    pts_ms: float
    crop: object = None   # the backing read's plate pixels (np.ndarray | None)


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
        if text in track.committed_plates:
            return
        agreeing = sum(1 for r in track.ocr_reads if r.text == text)
        kind = plates.plate_like(text) or "partial"
        if need_agreement:
            if agreeing < 2:
                return
        elif not any(r.kind == "full" for r in track.ocr_reads):
            return  # dying track: only with >= 1 full read
        backing = max((r for r in track.ocr_reads if r.text == text),
                      key=lambda r: r.conf, default=track.ocr_reads[-1])
        track.committed_plates.add(text)
        if kind == "full":
            track.committed_full = True
        out.append(CommittedRead(
            track_id=track.id, plate=text, plate_raw=backing.raw, confidence=conf,
            bbox=backing.bbox, vehicle_class=track.cls, kind=kind, pts_ms=pts_ms,
            crop=backing.crop))

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
            reads = self.ocr.read(crop, offset=(max(0, x1), max(0, y1)), frame_h=frame_h)
            if not reads:
                continue
            track.ocr_reads.append(max(reads, key=lambda r: r.conf))
            self._commit(track, committed, tick.pts_ms, need_agreement=True)

        return FrameResult(moving=True, detections=detections, matches=matches,
                           committed=committed, ocr_attempts=ocr_attempts,
                           restart=tick.restart)
