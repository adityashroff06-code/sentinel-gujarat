"""S2.3 acceptance: detector, motion gate, fetch_models (docs/tasks.md)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from ml.anpr.detect import Detector, parse_roi, superclass
from ml.anpr.motion import MotionGate, gate_for_camera
from ml.tools import fetch_models

REPO = Path(__file__).resolve().parent.parent
FEED_IMG = REPO / "deliverables" / "deck" / "img" / "feed_cam01.jpg"


@pytest.fixture(scope="module")
def detector() -> Detector:
    return Detector()


def test_feed_cam01_has_at_least_three_vehicles(detector: Detector) -> None:
    frame = cv2.imread(str(FEED_IMG))
    assert frame is not None, f"missing test image {FEED_IMG}"
    dets = detector.detect(frame)
    vehicles = [d for d in dets if d.superclass == "vehicle"]
    print(f"\nfeed_cam01.jpg: {len(vehicles)} vehicles of {len(dets)} detections "
          f"on provider {detector.provider}")
    assert len(vehicles) >= 3
    for d in vehicles:
        assert 0.0 < d.conf <= 1.0
        x1, y1, x2, y2 = d.xyxy
        assert x1 < x2 and y1 < y2


def test_black_frame_has_no_detections(detector: Detector) -> None:
    assert detector.detect(np.zeros((720, 1280, 3), dtype=np.uint8)) == []


def test_roi_mask_zeroes_detections_outside_polygon(detector: Detector) -> None:
    frame = cv2.imread(str(FEED_IMG))
    # A sliver in the bottom-left corner: every vehicle is outside -> zeroed.
    sliver = [[0.0, 0.95], [0.05, 0.95], [0.05, 1.0], [0.0, 1.0]]
    assert detector.detect(frame, roi=sliver) == []
    # The full frame as ROI changes nothing structurally.
    full = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    vehicles = [d for d in detector.detect(frame, roi=full) if d.superclass == "vehicle"]
    assert len(vehicles) >= 3


def test_superclass_mapping() -> None:
    assert [superclass(c) for c in ("car", "truck", "bus", "motorcycle")] == ["vehicle"] * 4
    assert superclass("person") == "person"


def test_parse_roi() -> None:
    assert parse_roi(None) is None
    assert parse_roi("not json") is None
    assert parse_roi("[[0,0],[1,0]]") is None  # fewer than 3 points
    assert parse_roi("[[0,0],[1,0],[1,1]]") == [[0, 0], [1, 0], [1, 1]]


# --- motion gate -----------------------------------------------------------

def test_motion_gate_skips_identical_frames() -> None:
    rng = np.random.default_rng(7)
    frame = rng.integers(0, 255, (360, 640, 3), dtype=np.uint8)
    gate = MotionGate(min_ratio=0.002)
    passed = sum(gate.moving(frame) for _ in range(100))
    assert passed <= 10  # >= 90 % skipped


def test_motion_gate_passes_a_moving_box() -> None:
    gate = MotionGate(min_ratio=0.002)
    moving = 0
    for i in range(60):
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        x = 10 + i * 5
        frame[140:220, x:x + 80] = 255
        moving += gate.moving(frame)
    assert moving >= 48  # >= 80 % of frames pass


def test_motion_gate_reset_forgets_the_background() -> None:
    frame = np.full((360, 640, 3), 128, dtype=np.uint8)
    gate = MotionGate(min_ratio=0.002)
    for _ in range(50):
        gate.moving(frame)
    assert gate.moving(frame) is False
    gate.reset()
    assert gate.moving(frame) is True  # warm-up passes again after reset


def test_gate_for_camera_reads_notes_json() -> None:
    assert gate_for_camera({"notes": '{"motion_min_ratio": 0.5}'}).min_ratio == 0.5
    assert gate_for_camera({"notes": "free text"}).min_ratio == pytest.approx(0.002)
    assert gate_for_camera({"notes": None}).min_ratio == pytest.approx(0.002)


# --- fetch_models ----------------------------------------------------------

def test_fetch_models_refuses_a_tampered_file(tmp_path: Path) -> None:
    checksums = tmp_path / "CHECKSUMS.txt"
    model = tmp_path / "models" / "yolox_s.onnx"
    model.parent.mkdir()
    model.write_bytes(b"genuine weights")
    sha = fetch_models.sha256_file(model)
    checksums.write_text(f"{sha}  test-url  models/yolox_s.onnx\n")
    # Verifies clean first…
    fetch_models.ensure(root=tmp_path, checksums=checksums)
    # …then refuses after tampering.
    model.write_bytes(b"tampered weights")
    with pytest.raises(fetch_models.ChecksumMismatch):
        fetch_models.ensure(root=tmp_path, checksums=checksums)


def test_fetch_models_pins_an_existing_file(tmp_path: Path) -> None:
    checksums = tmp_path / "CHECKSUMS.txt"
    model = tmp_path / "models" / "yolox_s.onnx"
    model.parent.mkdir()
    model.write_bytes(b"weights")
    fetch_models.ensure(root=tmp_path, checksums=checksums)
    line = checksums.read_text().strip()
    assert line.split() == [fetch_models.sha256_file(model),
                            fetch_models.YOLOX_URL, "models/yolox_s.onnx"]
