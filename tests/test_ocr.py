"""S2.4 acceptance: OCR cascade, consensus voting, OCR budget (docs/tasks.md)."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.core import plates
from ml.anpr.detect import Detection
from ml.anpr.ocr import PlateOcr, PlateRead
from ml.anpr.pipeline import AnprPipeline, consensus
from ml.ingest.base import FrameTick


@pytest.fixture(scope="module")
def ocr() -> PlateOcr:
    return PlateOcr()


def _plate_crop(text: str = "GJ01AB1234", crop_h: int = 90, text_h: int = 22) -> np.ndarray:
    """A plate string *text_h* px high inside a *crop_h* px tall crop (BGR)."""
    img = Image.new("RGB", (crop_h * 2, crop_h), "white")
    ImageDraw.Draw(img).text((10, (crop_h - text_h) // 2), text,
                             fill="black", font_size=text_h)
    return np.array(img)[:, :, ::-1].copy()


def test_22px_plate_reads_in_a_90px_crop(ocr: PlateOcr) -> None:
    t0 = time.perf_counter()
    reads = ocr.read(_plate_crop())
    latency = time.perf_counter() - t0
    assert reads, "no plate-like read from the rendered crop"
    best = max(reads, key=lambda r: r.conf)
    assert plates.canonical(best.text) == plates.canonical("GJ01AB1234")
    print(f"\nOCR read {best.text!r} conf={best.conf:.2f} in {latency * 1000:.0f} ms/crop")


def test_caption_band_read_is_rejected(ocr: PlateOcr) -> None:
    crop = _plate_crop()
    # Same crop mapped to the very top of a 1080 px frame: inside the 5 % band.
    assert ocr.read(crop, offset=(200.0, 0.0), frame_h=1080) == []
    # Mapped lower down, it reads fine.
    assert ocr.read(crop, offset=(200.0, 400.0), frame_h=1080) != []


def test_bbox_maps_back_to_source_pixels(ocr: PlateOcr) -> None:
    reads = ocr.read(_plate_crop(), offset=(300.0, 500.0))
    x, y, w, h = max(reads, key=lambda r: r.conf).bbox
    assert 300 <= x <= 480 and 500 <= y <= 590  # inside the mapped crop
    assert 0 < w <= 180 and 0 < h <= 90


# --- consensus -------------------------------------------------------------

def _read(text: str, conf: float = 0.9) -> PlateRead:
    return PlateRead(text=text, raw=text, conf=conf, bbox=(0, 0, 10, 10),
                     kind=plates.plate_like(text) or "partial")


def test_consensus_votes_out_the_minority_character() -> None:
    reads = [_read("GJ01AB1234"), _read("GJ01A81234"), _read("GJ01AB1234")]
    text, conf = consensus(reads)
    assert text == "GJ01AB1234"
    assert 0.0 < conf <= 1.0


def test_consensus_weights_by_confidence() -> None:
    # One high-confidence read outvotes two poor ones on the differing char.
    reads = [_read("GJ01AB1234", 0.95), _read("GJ01A81234", 0.3), _read("GJ01A81234", 0.3)]
    text, _ = consensus(reads)
    assert text == "GJ01AB1234"


def test_consensus_groups_by_length() -> None:
    reads = [_read("GJ05JB432", 0.4), _read("GJ05JB4321", 0.9), _read("GJ05JB4321", 0.8)]
    text, _ = consensus(reads)
    assert text == "GJ05JB4321"
    assert consensus([]) is None


# --- pipeline: OCR budget and commit rules (stubbed detector/OCR) ----------

class StubDetector:
    def __init__(self) -> None:
        self.boxes: list[Detection] = []

    def detect(self, frame, roi=None):
        return self.boxes


class StubOcr:
    def __init__(self) -> None:
        self.queue: list[list[PlateRead]] = []
        self.calls = 0

    def read(self, crop, *, offset=(0, 0), frame_h=None):
        self.calls += 1
        return self.queue.pop(0) if self.queue else []


class AlwaysMoving:
    def moving(self, frame) -> bool: return True
    def reset(self) -> None: pass


def _tick(pts_ms: float, restart: bool = False) -> FrameTick:
    now = datetime.now(timezone.utc)
    return FrameTick(frame=np.zeros((360, 640, 3), dtype=np.uint8), pts_ms=pts_ms,
                     stream_time=now, wall_time=now, clock_source="replay",
                     restart=restart)


def _vehicle(x: float = 100, size: float = 100) -> Detection:
    return Detection(cls="car", superclass="vehicle", conf=0.9,
                     xyxy=(x, 100, x + size, 100 + size * 0.6))


def _pipeline() -> tuple[AnprPipeline, StubDetector, StubOcr]:
    det, ocr = StubDetector(), StubOcr()
    return AnprPipeline(det, ocr, gate=AlwaysMoving()), det, ocr


def test_two_agreeing_reads_commit_once_then_ocr_stops() -> None:
    pipe, det, ocr = _pipeline()
    det.boxes = [_vehicle()]
    ocr.queue = [[_read("GJ01AB1234")], [_read("GJ01AB1234")]]
    assert pipe.process(_tick(0.0)).committed == []          # one read: no latch
    result = pipe.process(_tick(1600.0))                     # second agreeing read
    assert [c.plate for c in result.committed] == ["GJ01AB1234"]
    assert result.committed[0].kind == "full"
    assert pipe.process(_tick(3200.0)).ocr_attempts == 0     # full consensus: skip
    assert ocr.calls == 2


def test_ocr_budget_respects_min_gap_and_two_crops_per_frame() -> None:
    pipe, det, ocr = _pipeline()
    det.boxes = [_vehicle(0, 60), _vehicle(200, 120), _vehicle(400, 90)]
    ocr.queue = [[], [], [], []]
    assert pipe.process(_tick(0.0)).ocr_attempts == 2        # <= 2 crops a frame
    assert pipe.process(_tick(500.0)).ocr_attempts == 1      # only the skipped third
    assert pipe.process(_tick(600.0)).ocr_attempts == 0      # all inside the 1.5 s gap


def test_dying_track_with_one_full_read_commits() -> None:
    pipe, det, ocr = _pipeline()
    det.boxes = [_vehicle()]
    ocr.queue = [[_read("GJ01AB1234")]]
    assert pipe.process(_tick(0.0)).committed == []
    det.boxes = []                                           # vehicle gone
    result = pipe.process(_tick(4000.0))                     # > max_age: track dies
    assert [c.plate for c in result.committed] == ["GJ01AB1234"]


def test_dying_track_with_only_partial_reads_never_commits() -> None:
    pipe, det, ocr = _pipeline()
    det.boxes = [_vehicle()]
    ocr.queue = [[_read("GJ05JB432")]]                       # partial
    pipe.process(_tick(0.0))
    det.boxes = []
    assert pipe.process(_tick(4000.0)).committed == []


def test_restart_commits_pending_reads_then_resets() -> None:
    pipe, det, ocr = _pipeline()
    det.boxes = [_vehicle()]
    ocr.queue = [[_read("GJ01AB1234")]]
    pipe.process(_tick(0.0))
    result = pipe.process(_tick(1000.0, restart=True))
    assert [c.plate for c in result.committed] == ["GJ01AB1234"]
    assert pipe.tracker.tracks == {} or all(
        t.hits == 1 for t in pipe.tracker.tracks.values())   # fresh tracks only
