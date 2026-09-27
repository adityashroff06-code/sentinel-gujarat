"""scripts/render_analysis.py — the analysis render (task S7.1, decision F74).

No GPU and no Paddle: the detector and OCR are fakes. Loaded by path,
like the other scripts' tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from backend.core import plates
from ml.anpr.detect import Detection
from ml.anpr.ocr import PlateRead
from ml.anpr.pipeline import AnprPipeline
from ml.anpr.track import Track

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "render_analysis", REPO_ROOT / "scripts" / "render_analysis.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through it
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ra():
    return _load()


def _read(text: str, conf: float = 0.9) -> PlateRead:
    return PlateRead(text=text, raw=text, conf=conf, bbox=(10, 20, 60, 15),
                     kind=plates.plate_like(text) or "partial",
                     crop=np.full((15, 60, 3), 200, dtype=np.uint8))


# --- the commit rule is the worker's -------------------------------------

class _Stub:
    def detect(self, frame, roi=None): return []
    def read(self, crop, *, offset=(0, 0), frame_h=None): return []
    def moving(self, frame): return True
    def reset(self): pass


# Each sequence is [(text, conf), ...] in arrival order. Every read gets a
# distinct raw, bbox and crop, so a wrong backing-read choice shows up.
SEQUENCES = [
    [("GJ01AB1234", .80), ("GJ01AB1234", .81)],                    # two agree -> commit
    [("GJ01AB1234", .95), ("GJ01AB1234", .80)],                    # backing = best, not newest
    [("GJ01AB1234", .80)],                                         # one read: no latch
    [("6J23H1548", .80), ("6J23H1548", .81)],                      # coerced on commit
    [("GJ01AB1234", .80), ("GJ01A81234", .81), ("GJ01AB1234", .82)],  # minority char out
    [("GJ05JB432", .80), ("GJ05JB432", .81)],                      # partial, stored as read
    [("MH02", .80), ("MH02EX1995", .81), ("MH02EX1995", .82)],     # length groups
    [("GJ05JB432", .80)],                                          # dying, no full read
    [("MH02EX1995", .80), ("MH02EX1996", .81)],                    # disagreement
    [("MH02EX1995", .80), ("MH02EX1995", .81), ("MH02EX1995", .82)],  # no double commit
    # consensus MH02EX1995 matches no read: dying commit backed by the last read
    [("MH02EX1996", .80), ("MH02EX1985", .81), ("MH02EX1895", .82)],
    # partial consensus wins the length vote, but a full read exists: dying commits it
    [("GJ01AB1234", .40), ("GJ05JB432", .81)],
]


def _read_n(text: str, conf: float, i: int) -> PlateRead:
    return PlateRead(text=text, raw=f"{text}/{i}", conf=conf, bbox=(10 + i, 20, 60, 15),
                     kind=plates.plate_like(text) or "partial",
                     crop=np.full((15, 60, 3), 10 * i, dtype=np.uint8))


def _commits_both_ways(ra, seq, dying: bool):
    pipe = AnprPipeline(_Stub(), _Stub(), gate=_Stub())
    ours, theirs = [], []
    t_ours = Track(id=7, boxes=[(0, 0, 100, 60)], last_seen_pts=0.0,
                   superclass="vehicle", cls="car")
    t_theirs = copy.deepcopy(t_ours)
    for i, item in enumerate(seq):
        text, conf = item if isinstance(item, tuple) else (item, 0.8 + 0.01 * i)
        r = _read_n(text, conf, i)
        t_ours.ocr_reads.append(r)
        t_theirs.ocr_reads.append(r)
        c = ra.commit_track(t_ours, 100.0 * i, need_agreement=True)
        if c is not None:
            ours.append(c)
        pipe._commit(t_theirs, theirs, 100.0 * i, need_agreement=True)
    if dying:
        c = ra.commit_track(t_ours, 999.0, need_agreement=False)
        if c is not None:
            ours.append(c)
        pipe._commit(t_theirs, theirs, 999.0, need_agreement=False)
    return ours, theirs, t_ours, t_theirs


FIELDS = ("track_id", "plate", "plate_raw", "confidence", "bbox", "vehicle_class",
          "kind", "pts_ms", "crop")


@pytest.mark.parametrize("seq", SEQUENCES)
@pytest.mark.parametrize("dying", [False, True])
def test_commit_rule_matches_the_workers_commit(ra, seq, dying) -> None:
    ours, theirs, t_ours, t_theirs = _commits_both_ways(ra, seq, dying)
    # `crop` compares by identity: the same backing PlateRead's pixels
    assert [tuple(id(getattr(c, f)) if f == "crop" else getattr(c, f) for f in FIELDS)
            for c in ours] ==            [tuple(id(getattr(c, f)) if f == "crop" else getattr(c, f) for f in FIELDS)
            for c in theirs]
    assert t_ours.committed_plates == t_theirs.committed_plates
    assert t_ours.committed_full == t_theirs.committed_full


def test_commit_rule_backs_a_commit_with_the_most_confident_agreeing_read(ra) -> None:
    ours, _, _, _ = _commits_both_ways(ra, [("GJ01AB1234", .95), ("GJ01AB1234", .80)],
                                       dying=False)
    (c,) = ours
    assert c.plate_raw == "GJ01AB1234/0" and c.bbox[0] == 10


def test_dying_track_with_a_partial_consensus_and_a_full_read_commits(ra) -> None:
    seq = [("GJ01AB1234", .40), ("GJ05JB432", .81)]
    ours, theirs, t_ours, _ = _commits_both_ways(ra, seq, dying=True)
    assert [c.kind for c in ours] == [c.kind for c in theirs] == ["partial"]
    assert t_ours.committed_full is False


def test_commit_rule_stores_the_coerced_plate(ra) -> None:
    ours, _, _, _ = _commits_both_ways(ra, [("6J23H1548", .8), ("6J23H1548", .81)],
                                       dying=False)
    assert [c.plate for c in ours] == ["GJ23H1548"]


# --- the render loop with fakes ------------------------------------------

class FakeDetector:
    """One car sliding right; the box is wide enough to be read."""

    provider = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def detect(self, frame, roi=None):
        self.calls += 1
        x = 100 + 20 * self.calls
        return [Detection(cls="car", superclass="vehicle", conf=0.9,
                          xyxy=(float(x), 300.0, float(x + 400), 540.0)),
                Detection(cls="person", superclass="person", conf=0.8,
                          xyxy=(900.0, 200.0, 960.0, 400.0))]


class FakeOcr:
    """Reads the same plate every call, in source pixels via the offset."""

    def __init__(self, text: str = "MH02EX1995") -> None:
        self.text = text
        self.calls = 0

    def read(self, crop, *, offset=(0.0, 0.0), frame_h=None):
        self.calls += 1
        return [PlateRead(text=self.text, raw=self.text, conf=0.9,
                          bbox=(int(offset[0] + 100), int(offset[1] + 150), 90, 22),
                          kind="full", crop=np.full((22, 90, 3), 230, dtype=np.uint8))]


GREEN = (0, 255, 0)


def _frames(n: int, w: int = 1920, h: int = 1080):
    for i in range(n):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = GREEN
        yield i, frame


def _run(ra, n: int = 10, **opt):
    out: list[np.ndarray] = []
    painter = ra.Painter(1920, 1080, clip_id="synthetic")
    opts = ra.RenderOptions(**{"detect_every": 2, "ocr_gap_ms": 0.0, "progress_every": 0,
                               "min_vehicle_w": 140.0, **opt})
    result = ra.render(_frames(n), fps=30.0, src_w=1920, src_h=1080,
                       detector=FakeDetector(), ocr=FakeOcr(), sink=out.append,
                       opts=opts, painter=painter, say=lambda s: None)
    return out, result, painter


def test_hud_label_is_drawn_on_every_frame(ra) -> None:
    out, _, painter = _run(ra, n=10)
    assert len(out) == 10  # one output frame per input frame, in order
    x1, y1, x2, y2 = painter.label_box
    assert x2 - x1 > 600 and y2 - y1 >= 40
    for i, frame in enumerate(out):
        assert frame.shape == (1080, 1920, 3)
        box = frame[y1:y2, x1:x2]
        pure_green = np.all(box == np.array(GREEN, dtype=np.uint8), axis=2)
        assert not pure_green.any(), f"frame {i}: label scrim missing"
        text_px = np.all(box > 180, axis=2).sum()  # the label's light text
        assert text_px > 300, f"frame {i}: label text missing ({text_px} px)"
        # the rest of the top row outside the HUD is still the source pixels
        assert np.all(frame[5, x2 + 50] == np.array(GREEN, dtype=np.uint8))


def test_render_commits_through_the_workers_rule_and_watches(ra) -> None:
    out, result, _ = _run(ra, n=10, watch=("MH02EX1995",))
    assert result["frames_processed"] == 10
    assert result["frames_detected"] == 5
    assert result["plates_read"] == 1
    (read,) = result["reads"]
    assert read["plate"] == "MH02EX1995" and read["kind"] == "full"
    assert read["watch"] is True
    # two agreeing reads commit (frames 0 and 2), then the track is not read again
    assert read["commit_frame"] == 2
    assert result["ocr_ms"]["crops"] == 2


def test_narrow_vehicles_are_never_read(ra) -> None:
    _, result, _ = _run(ra, n=6, min_vehicle_w=500.0)
    assert result["ocr_ms"]["crops"] == 0 and result["reads"] == []


def test_ocr_width_scales_the_crop_and_maps_the_box_back(ra) -> None:
    seen = []

    class SizeOcr(FakeOcr):
        def read(self, crop, *, offset=(0.0, 0.0), frame_h=None):
            seen.append((crop.shape[1], offset, frame_h))
            return super().read(crop, offset=offset, frame_h=frame_h)

    out: list[np.ndarray] = []
    opts = ra.RenderOptions(detect_every=2, ocr_gap_ms=0.0, progress_every=0,
                            ocr_width=960)
    result = ra.render(_frames(4), fps=30.0, src_w=1920, src_h=1080,
                       detector=FakeDetector(), ocr=SizeOcr(), sink=out.append, opts=opts,
                       painter=ra.Painter(1920, 1080, "s"), say=lambda s: None)
    width, offset, frame_h = seen[0]
    assert width == 200 and frame_h == 540          # a 400 px box read at half size
    assert offset == (120 * 0.5, 300 * 0.5)
    (read,) = result["reads"]
    assert read["plate_w_px"] == 180 and read["plate_w_px_ocr"] == 90


# --- the encoder ---------------------------------------------------------

def test_ffmpeg_argv_uses_config_ffmpeg_and_no_shell(ra, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ra.config, "ffmpeg", lambda: "C:/tools/ffmpeg.exe")
    argv = ra.ffmpeg_argv(tmp_path / "o.mp4", 30.0)
    assert argv[0] == "C:/tools/ffmpeg.exe"
    assert argv[argv.index("-f") + 1] == "rawvideo"
    assert argv[argv.index("-pix_fmt") + 1] == "bgr24"
    assert argv[argv.index("-s") + 1] == "1920x1080"
    assert argv[argv.index("-r") + 1] == "30/1"
    assert argv[argv.index("-i") + 1] == "-"
    for flag, value in (("-c:v", "libx264"), ("-preset", "medium"), ("-crf", "18"),
                        ("-movflags", "+faststart")):
        assert argv[argv.index(flag) + 1] == value
    assert argv[-1] == str(tmp_path / "o.mp4")
    assert ra.ffmpeg_argv(tmp_path / "o.mp4", 30000 / 1001)[argv.index("-r") + 1] == "30000/1001"

    calls = []

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            self.stdin = None

    monkeypatch.setattr(ra.subprocess, "Popen", FakePopen)
    ra.Encoder(tmp_path / "o.mp4", 30.0)
    (cmd, kwargs), = calls
    assert isinstance(cmd, list) and cmd[0] == "C:/tools/ffmpeg.exe"
    assert not kwargs.get("shell", False)
    assert kwargs["stdin"] is ra.subprocess.PIPE


# --- the JSON ------------------------------------------------------------

def test_summary_json_schema(ra, tmp_path) -> None:
    _, result, _ = _run(ra, n=10, watch=("MH02EX1995",))
    opts = ra.RenderOptions(watch=("MH02EX1995",))
    body = ra.summary_json(Path("13270133_3840_2160_30fps.mp4"),
                           {"width": 3840, "height": 2160, "fps": 30.0, "frames": 10,
                            "duration_s": 0.333},
                           tmp_path / "o.mp4", tmp_path / "o.png", opts, "fake", result,
                           10, (0.0, None))
    text = json.dumps(body)  # serialisable: no pixels left in it
    back = json.loads(text)
    for key in ("clip", "label", "source", "output", "still", "provider", "options",
                "frames_processed", "detect_ms", "ocr_ms", "runtime_s", "reads",
                "plates_read", "distinct_full_plates"):
        assert key in back, key
    assert back["label"] == ra.HUD_LABEL
    assert back["output"]["width"] == 1920 and back["output"]["height"] == 1080
    assert set(back["detect_ms"]) >= {"mean", "p90"}
    assert set(back["ocr_ms"]) >= {"mean", "p90", "crops"}
    assert back["options"]["watch"] == ["MH02EX1995"]
    read_keys = {"plate", "raw", "confidence", "kind", "track", "first_frame",
                 "first_t_s", "last_frame", "last_t_s", "plate_w_px"}
    assert back["reads"] and all(read_keys <= set(r) for r in back["reads"])
    assert all(isinstance(r["confidence"], float) for r in back["reads"])


# --- review-gate regressions (S7.1) ---------------------------------------

def test_letterbox_for_a_portrait_clip_uses_the_video_bg_token(ra) -> None:
    """Regression: the 3-digit `--video-bg: #000` token was not parsed, so a
    source that is not 16:9 raised KeyError on its first frame."""
    painter = ra.Painter(1080, 1920, "portrait")
    out = painter.to_output(np.full((1920, 1080, 3), 255, dtype=np.uint8))
    assert out.shape == (1080, 1920, 3)
    assert np.all(out[540, 10] == 0) and np.all(out[540, 960] == 255)


def test_label_stays_readable_under_a_labelled_vehicle_at_the_top(ra) -> None:
    """Regression: chips stacked above a box near the top overprinted the
    burned-in label; they now drop inside the box."""
    painter = ra.Painter(1920, 1080, "synthetic")
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[:] = GREEN
    label = {"plate": "MH02EX1995", "kind": "full", "confidence": 0.93, "watch": True}
    item = ra.Item(1, "car", "vehicle", (20.0, 40.0, 700.0, 400.0), 0.0,
                   (0.4, 0.7, 0.2, 0.1), label, False)
    hud = ra.Hud(t_s=1.0, vehicles=1, tracks=1, plates=1, strip=[])
    painter.draw(img, [item], hud)
    x1, y1, x2, y2 = painter.label_box
    box = img[y1:y2, x1:x2]
    # no opaque chip inside the label band: every pixel is scrim or label text
    plate_bg = np.array(painter.pal["plate-bg"][:3], dtype=np.uint8)
    hit_red = np.array(painter.pal["sev-critical"][:3], dtype=np.uint8)
    assert not np.all(box == plate_bg, axis=2).any()
    assert not np.all(box == hit_red, axis=2).any()
    assert np.all(box > 180, axis=2).sum() > 300


def test_hud_clock_never_shows_sixty_seconds(ra) -> None:
    painter = ra.Painter(1920, 1080, "c")
    line = painter.stats_lines(ra.Hud(t_s=1799 / 30.0, vehicles=0, tracks=0, plates=0,
                                      strip=[]))[0]
    assert line.endswith("01:00.0")
    line = painter.stats_lines(ra.Hud(t_s=41.26, vehicles=0, tracks=0, plates=0, strip=[]))[0]
    assert line.endswith("00:41.3")


def test_boxes_interpolate_between_distant_detections_without_blinking(ra) -> None:
    """Regression: the hold cut-off ran before interpolation, so with
    --detect-every 8 a tracked box vanished on the last frames of each gap."""
    drawn: list[int] = []

    class CountingPainter(ra.Painter):
        def draw(self, img, items, hud):
            drawn.append(sum(1 for i in items if i.superclass == "vehicle"))
            return img

    opts = ra.RenderOptions(detect_every=8, ocr_gap_ms=0.0, progress_every=0,
                            min_vehicle_w=10_000.0)
    ra.render(_frames(17), fps=30.0, src_w=1920, src_h=1080, detector=FakeDetector(),
              ocr=FakeOcr(), sink=lambda img: None, opts=opts,
              painter=CountingPainter(1920, 1080, "s"), say=lambda s: None)
    assert drawn == [1] * 17
