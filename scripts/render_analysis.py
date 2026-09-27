"""The analysis render: the real pipeline on a recorded stock clip (task S7.1, decision F74).

Runs the worker's own detector (``ml.anpr.detect.Detector``), tracker
(``ml.anpr.track.Tracker``), OCR (``ml.anpr.ocr.PlateOcr``), consensus
(``ml.anpr.pipeline.consensus``) and plate grammar (``backend.core.plates``)
on every frame of a clip at its source resolution. It writes an annotated
1920x1080 MP4, a JSON of every committed read, and one PNG still:

    .venv/Scripts/python scripts/render_analysis.py \
        D:/projects/sentinel-footage/raw/13270133_3840_2160_30fps.mp4 --watch MH02EX1995

- **Detect** on every ``--detect-every``-th frame, on the full-resolution
  frame (the detector letterboxes to 640 itself). **Track** with one
  ``Tracker``. Boxes on the frames between two detections are linearly
  interpolated when the track was matched at both ends, else held; never
  extrapolated.
- **OCR** is the offline budget, not the live one: vehicles only, box
  width >= ``--min-vehicle-w`` source px, >= ``--ocr-gap-ms`` of video time
  between reads of a track, <= ``--ocr-max`` crops per detected frame
  (largest first), and a track stops being read once it holds a committed
  full plate. Crops are cut from the **full-resolution** frame; with
  ``--ocr-width`` below the source width they are then scaled by
  ``ocr_width / source_width`` before OCR, which is exactly what the S7.0
  read test measured at that width (``scripts/analyze_footage.py``).
- **Consensus and commit** are the worker's: :func:`commit_track` is a
  copy of ``AnprPipeline._commit`` (``tests/test_render_analysis.py``
  proves the two agree), because this script never edits ``ml/``.

**Timing** is ``frame_index / fps`` from the container. This is a file, not
a live feed: root rule 3 (timing from PTS, never ``CAP_PROP_FPS``) guards
live pulls, where the gateway replays a GOP on join and frames arrive
faster than real time. A local file's container rate and frame index are
exact, so there is no ``CAP_PROP_FPS`` trap here (``docs/feed-rules.md``
applies to live pulls).

**What it is not:** never a camera, never a database row, never called
live. Nothing is published and nothing is written to a platform database;
the burned-in label on every frame says the footage is recorded and was
processed offline. Renders live outside the repo
(``<SENTINEL_FOOTAGE_DIR>/renders``); only the JSON summary and one still
are committed (F74).

Output is the product, so this CLI prints its progress (the CLI-tool
exception to the logging rule).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.core import config, plates  # noqa: E402
from ml.anpr.pipeline import CommittedRead, consensus  # noqa: E402
from ml.anpr.track import Track, Tracker  # noqa: E402

OUT_W, OUT_H = 1920, 1080
HUD_LABEL_HEAD = "SENTINEL"
HUD_LABEL_TAIL = " · pipeline output · recorded stock clip · processed offline at full frame rate"
HUD_LABEL = HUD_LABEL_HEAD + HUD_LABEL_TAIL
# A track missed by a detection keeps its last box for one detection
# interval plus this long (no flicker); held, never extrapolated.
HOLD_MS = 200.0
STRIP_READS = 5
STRIP_CROP_H = 48
STATS_BAND_H = 128  # height of the top-right HUD band
DECK_STILL_MAX_BYTES = 1_500_000
DRAWN = {"vehicle", "person"}  # superclasses that get a box

TOKENS_CSS = REPO_ROOT / "frontend" / "src" / "styles" / "tokens.css"
MEASUREMENTS = REPO_ROOT / "data" / "measurements"
DECK_IMG = REPO_ROOT / "deliverables" / "deck" / "img"
FONTS_DIR = Path(r"C:\Windows\Fonts")

# Box colour per detector class, by token name (frontend/src/styles/tokens.css).
CLASS_TOKEN = {"car": "accent-strong", "truck": "dept-municipal", "bus": "dept-panchayat",
               "motorcycle": "activity", "person": "cluster-line"}


# --- colours (the product's own tokens) -----------------------------------

_TOKEN = re.compile(
    r"--([a-z0-9-]+)\s*:\s*(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|rgba\([^)]*\))")


def load_tokens(path: Path = TOKENS_CSS) -> dict[str, tuple]:
    """``--name: #rrggbb`` (or ``#rgb``) → ``(b, g, r)``; ``rgba(r, g, b, a)`` →
    ``(b, g, r, a)``.

    Raises FileNotFoundError when the token sheet is missing.
    """
    tokens: dict[str, tuple] = {}
    for name, value in _TOKEN.findall(path.read_text(encoding="utf-8")):
        if value.startswith("#") and len(value) == 4:  # #000 → #000000
            value = "#" + "".join(c * 2 for c in value[1:])
        if value.startswith("#"):
            r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
            tokens[name] = (b, g, r)
        else:
            parts = [p.strip() for p in value[5:-1].split(",")]
            r, g, b = (int(p) for p in parts[:3])
            tokens[name] = (b, g, r, float(parts[3]))
    return tokens


@dataclass
class Palette:
    """The render's colours, all taken from the token sheet (BGR)."""

    tokens: dict[str, tuple]

    def __getitem__(self, name: str) -> tuple:
        try:
            return self.tokens[name]
        except KeyError:
            raise KeyError(f"token --{name} missing from {TOKENS_CSS}") from None

    def cls(self, name: str) -> tuple:
        return self[CLASS_TOKEN.get(name, "text-muted")][:3]


def _font(names: tuple[str, ...], size: int) -> ImageFont.ImageFont:
    for name in names:
        path = FONTS_DIR / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


@dataclass
class Fonts:
    ui: ImageFont.ImageFont = field(default_factory=lambda: _font(("segoeui.ttf",), 20))
    ui_bold: ImageFont.ImageFont = field(default_factory=lambda: _font(("segoeuib.ttf",), 20))
    small: ImageFont.ImageFont = field(default_factory=lambda: _font(("seguisb.ttf", "segoeui.ttf"), 15))
    stat: ImageFont.ImageFont = field(default_factory=lambda: _font(("segoeui.ttf",), 19))
    mono: ImageFont.ImageFont = field(default_factory=lambda: _font(("consolab.ttf", "consola.ttf"), 24))
    mono_hud: ImageFont.ImageFont = field(default_factory=lambda: _font(("consolab.ttf", "consola.ttf"), 22))
    mono_small: ImageFont.ImageFont = field(default_factory=lambda: _font(("consola.ttf",), 16))


# --- the commit rule (copied, never edited in ml/) -------------------------

def commit_track(track: Track, pts_ms: float, need_agreement: bool) -> CommittedRead | None:
    """The worker's commit rule, copied from ``ml/anpr/pipeline.py``
    ``AnprPipeline._commit`` (S2.4) so this script never edits ``ml/``.

    A consensus commits when >= 2 reads agree on it, or when the track is
    dying (``need_agreement=False``) holding >= 1 full read; a full read is
    stored in its ``plates.coerce`` form. Mutates the track exactly as
    ``_commit`` does. Returns the commit, or None when the rule does not
    hold. ``tests/test_render_analysis.py`` proves it matches ``_commit``.
    """
    result = consensus(track.ocr_reads)
    if result is None:
        return None
    text, conf = result
    kind = plates.plate_like(text) or "partial"
    stored = plates.coerce(text) if kind == "full" else None
    stored = stored or text
    if stored in track.committed_plates:
        return None
    agreeing = sum(1 for r in track.ocr_reads if r.text == text)
    if need_agreement:
        if agreeing < 2:
            return None
    elif not any(r.kind == "full" for r in track.ocr_reads):
        return None  # dying track: only with >= 1 full read
    backing = max((r for r in track.ocr_reads if r.text == text),
                  key=lambda r: r.conf, default=track.ocr_reads[-1])
    track.committed_plates.add(stored)
    if kind == "full":
        track.committed_full = True
    return CommittedRead(
        track_id=track.id, plate=stored, plate_raw=backing.raw, confidence=conf,
        bbox=backing.bbox, vehicle_class=track.cls, kind=kind, pts_ms=pts_ms,
        crop=backing.crop)


# --- state -----------------------------------------------------------------

@dataclass
class RenderOptions:
    detect_every: int = 2
    ocr_gap_ms: float = 300.0
    ocr_max: int = 6
    min_vehicle_w: float = 140.0
    ocr_width: int | None = None       # None = OCR at the source resolution
    ocr_track_max: int = 0             # 0 = no cap on OCR attempts per track
    watch: tuple[str, ...] = ()
    progress_every: int = 150          # frames between progress lines


@dataclass
class TrackInfo:
    """Render-side facts about one tracker id (the tracker is not edited)."""

    cls: str
    superclass: str
    first_frame: int
    last_frame: int
    box: tuple[float, float, float, float]
    last_seen_ms: float
    plate_rel: tuple[float, float, float, float] | None = None  # plate box / vehicle box
    ocr_attempts: int = 0
    label: dict | None = None          # the committed read shown on the vehicle
    best_vehicle_px: np.ndarray | None = None  # spot-check context (best read)
    best_conf: float = -1.0


@dataclass
class Item:
    """One box to draw."""

    track_id: int
    cls: str
    superclass: str
    box: tuple[float, float, float, float]
    last_seen_ms: float
    plate_rel: tuple[float, float, float, float] | None
    label: dict | None
    reading: bool


@dataclass
class Hud:
    t_s: float
    vehicles: int
    tracks: int
    plates: int
    strip: list[dict]


def _rel(plate_xywh: tuple, box: tuple) -> tuple[float, float, float, float] | None:
    """A plate box relative to its vehicle box (0-1), so it moves with the vehicle."""
    x1, y1, x2, y2 = box
    w, h = max(1.0, x2 - x1), max(1.0, y2 - y1)
    px, py, pw, ph = plate_xywh
    return ((px - x1) / w, (py - y1) / h, pw / w, ph / h)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(av + (bv - av) * t for av, bv in zip(a, b))


def _canon(plate: str) -> str:
    return plates.canonical(plates.coerce(plate) or plates.normalise(plate))


# --- drawing ---------------------------------------------------------------

class Painter:
    """Draws boxes, labels and the HUD on a 1920x1080 frame."""

    def __init__(self, src_w: int, src_h: int, clip_id: str,
                 palette: Palette | None = None, fonts: Fonts | None = None) -> None:
        self.pal = palette or Palette(load_tokens())
        self.fonts = fonts or Fonts()
        self.clip_id = clip_id
        self.scale = min(OUT_W / src_w, OUT_H / src_h)
        self.size = (int(round(src_w * self.scale)), int(round(src_h * self.scale)))
        self.pad = ((OUT_W - self.size[0]) // 2, (OUT_H - self.size[1]) // 2)
        head_w = self.fonts.ui_bold.getbbox(HUD_LABEL_HEAD)[2]
        tail_w = self.fonts.ui.getbbox(HUD_LABEL_TAIL)[2]
        #: the label's scrim rectangle (x1, y1, x2, y2) on every output frame
        self.label_box = (0, 0, 16 + head_w + tail_w + 16, 44)
        self._head_w = head_w

    def to_output(self, frame: np.ndarray) -> np.ndarray:
        """The source frame fitted into 1920x1080 (letterboxed if not 16:9)."""
        if frame.shape[1] == OUT_W and frame.shape[0] == OUT_H:
            return frame.copy()
        small = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA)
        if self.size == (OUT_W, OUT_H):
            return small
        out = np.zeros((OUT_H, OUT_W, 3), dtype=np.uint8)
        out[:] = self.pal["video-bg"]
        out[self.pad[1]:self.pad[1] + self.size[1], self.pad[0]:self.pad[0] + self.size[0]] = small
        return out

    def _pt(self, x: float, y: float) -> tuple[int, int]:
        return (int(round(x * self.scale + self.pad[0])), int(round(y * self.scale + self.pad[1])))

    def _scrim(self, img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        b, g, r, a = self.pal["overlay"]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
        if x2 <= x1 or y2 <= y1:
            return
        region = img[y1:y2, x1:x2].astype(np.float32)
        region = region * (1.0 - a) + np.array((b, g, r), dtype=np.float32) * a
        img[y1:y2, x1:x2] = region.astype(np.uint8)

    def stats_lines(self, hud: Hud) -> list[str]:
        """The top-right HUD block: clip time ``mm:ss.f`` and the three counts."""
        tenths = int(round(hud.t_s * 10))  # round first: never "00:60.0"
        return [f"{self.clip_id}  {tenths // 600:02d}:{(tenths % 600) / 10:04.1f}",
                f"vehicles in view {hud.vehicles}", f"tracks {hud.tracks}",
                f"plates read {hud.plates}"]

    def stats_x(self, hud: Hud) -> int:
        """Left edge of the top-right HUD band."""
        lines = self.stats_lines(hud)
        width = max(self.fonts.mono_hud.getbbox(lines[0])[2],
                    *(self.fonts.stat.getbbox(s)[2] for s in lines[1:]))
        return OUT_W - width - 32

    def _chip_top(self, p1: tuple[int, int], x_right: int, stack_h: int, stat_x: int) -> int:
        """Top of a chip stack above a box, never over the HUD bands.

        Chips go above the box; when that would cross the top edge or the
        label / stats band they drop inside the box instead, so the label
        stays readable on every frame (F74).
        """
        floor = 0
        if p1[0] < self.label_box[2]:
            floor = max(floor, self.label_box[3] + 2)
        if x_right > stat_x:
            floor = max(floor, STATS_BAND_H + 2)
        if p1[1] - stack_h >= floor:
            return p1[1] - stack_h
        return max(p1[1], floor) + 2

    def draw(self, img: np.ndarray, items: list[Item], hud: Hud) -> np.ndarray:
        """Annotate *img* (1920x1080 BGR) in place and return it."""
        pal, fonts = self.pal, self.fonts
        texts: list[tuple] = []  # (xy, text, font, fill) drawn in one PIL pass
        chips: list[tuple] = []  # (x1, y1, x2, y2, fill)

        stat_x = self.stats_x(hud)
        for item in items:
            p1, p2 = self._pt(*item.box[:2]), self._pt(*item.box[2:])
            hit = bool(item.label and item.label.get("watch"))
            colour = pal["sev-critical"][:3] if hit else pal.cls(item.cls)
            cv2.rectangle(img, p1, p2, colour, 3 if hit else 2)
            tag = f"#{item.track_id} {item.cls}"
            tw = fonts.small.getbbox(tag)[2]
            if item.superclass != "vehicle":
                ty = self._chip_top(p1, p1[0] + tw + 8, 20, stat_x)
                chips.append((p1[0], ty, p1[0] + tw + 8, ty + 20, colour))
                texts.append(((p1[0] + 4, ty + 1), tag, fonts.small, pal["text-on-color"]))
                continue
            if item.plate_rel is not None and (item.reading or item.label):
                x1, y1, x2, y2 = item.box
                w, h = x2 - x1, y2 - y1
                rx, ry, rw, rh = item.plate_rel
                q1 = self._pt(x1 + rx * w, y1 + ry * h)
                q2 = self._pt(x1 + (rx + rw) * w, y1 + (ry + rh) * h)
                if item.reading:
                    cv2.rectangle(img, q1, q2, pal["warn"][:3], 2)
                else:
                    cv2.rectangle(img, q1, q2, pal["plate-bg"][:3], 1)
            # the stack above the box, top to bottom:
            # [WATCHLIST HIT] [plate conf] [#id class] -- (height, [chip rows])
            rows: list[tuple[int, int, list, list]] = []  # (h, w, chips, texts) at y=0
            if item.label:
                lab = item.label
                full = lab["kind"] == "full"
                plate_txt = lab["plate"].upper() if full else f"{lab['plate'].upper()} partial"
                conf_txt = f"{lab['confidence']:.2f}"
                pw = fonts.mono.getbbox(plate_txt)[2]
                cw = fonts.mono_small.getbbox(conf_txt)[2]
                if hit:
                    bg, ink, ink2 = pal["sev-critical"][:3], pal["text-on-color"], pal["text-on-color"]
                    hw = fonts.ui_bold.getbbox("WATCHLIST HIT")[2]
                    rows.append((26, hw + 12,
                                 [(0, 0, hw + 12, 24, pal["sev-critical"][:3])],
                                 [((6, -1), "WATCHLIST HIT", fonts.ui_bold,
                                   pal["text-on-color"])]))
                elif full:
                    bg, ink, ink2 = pal["plate-bg"][:3], pal["plate-ink"], pal["plate-ink-muted"]
                else:
                    bg, ink, ink2 = pal["surface-3"][:3], pal["text-muted"], pal["text-faint"]
                rows.append((32, pw + cw + 26, [(0, 0, pw + cw + 26, 30, bg)],
                             [((8, 2), plate_txt, fonts.mono, ink),
                              ((pw + 18, 8), conf_txt, fonts.mono_small, ink2)]))
            rows.append((20, tw + 8, [(0, 0, tw + 8, 20, colour)],
                         [((4, 1), tag, fonts.small, pal["text-on-color"])]))
            y = self._chip_top(p1, p1[0] + max(r[1] for r in rows),
                               sum(r[0] for r in rows), stat_x)
            for h, _, row_chips, row_texts in rows:
                for cx1, cy1, cx2, cy2, fill in row_chips:
                    chips.append((p1[0] + cx1, y + cy1, p1[0] + cx2, y + cy2, fill))
                for (tx, ty), text, font, fill in row_texts:
                    texts.append(((p1[0] + tx, y + ty), text, font, fill))
                y += h

        # HUD scrims (translucent), then the chips (opaque, kept off the bands)
        lx1, ly1, lx2, ly2 = self.label_box
        self._scrim(img, lx1, ly1, lx2, ly2)
        stats = self.stats_lines(hud)
        self._scrim(img, stat_x, 0, OUT_W, STATS_BAND_H)
        strip_y = OUT_H - 76
        self._scrim(img, 0, strip_y, OUT_W, OUT_H)

        for x1, y1, x2, y2, fill in chips:
            if y2 > 0 and y1 < OUT_H:
                cv2.rectangle(img, (x1, max(0, y1)), (x2, min(OUT_H - 1, y2)), fill, -1)

        # bottom strip: the last five committed reads with their crops
        texts.append(((16, strip_y + 6), "LAST READS", fonts.small, pal["text-muted"]))
        cx = 16
        for read in hud.strip[-STRIP_READS:][::-1]:
            crop = read.get("crop_img")
            cy = strip_y + 22
            if crop is not None and crop.size:
                ch = STRIP_CROP_H
                cw = max(1, min(180, int(round(crop.shape[1] * ch / crop.shape[0]))))
                thumb = cv2.resize(crop, (cw, ch), interpolation=cv2.INTER_CUBIC)
                if cy + ch <= OUT_H and cx + cw <= OUT_W:
                    img[cy:cy + ch, cx:cx + cw] = thumb
                cx += cw + 8
            full = read["kind"] == "full"
            plate_txt = read["plate"].upper() if full else f"{read['plate'].upper()} partial"
            colour = (pal["sev-critical"] if read.get("watch")
                      else pal["text"] if full else pal["text-muted"])
            texts.append(((cx, cy + 2), plate_txt, fonts.mono_hud, colour[:3]))
            texts.append(((cx, cy + 28), f"conf {read['confidence']:.2f} · #{read['track']}",
                          fonts.mono_small, pal["text-muted"]))
            cx += max(fonts.mono_hud.getbbox(plate_txt)[2], 130) + 24
            if cx > OUT_W - 200:
                break

        pil = Image.fromarray(img)
        draw = ImageDraw.Draw(pil)
        for xy, text, font, fill in texts:
            draw.text(xy, text, font=font, fill=tuple(fill[:3]))
        # the label, burned into every frame (drawn last: nothing covers it)
        draw.text((16, 9), HUD_LABEL_HEAD, font=fonts.ui_bold, fill=pal["accent-strong"][:3])
        draw.text((16 + self._head_w, 9), HUD_LABEL_TAIL, font=fonts.ui, fill=pal["text"][:3])
        draw.text((stat_x + 16, 8), stats[0], font=fonts.mono_hud, fill=pal["text"][:3])
        for i, line in enumerate(stats[1:]):
            draw.text((stat_x + 16, 38 + i * 28), line, font=fonts.stat,
                      fill=(pal["text"] if i == 2 else pal["text-muted"])[:3])
        img[:] = np.asarray(pil)
        return img


# --- the render loop -------------------------------------------------------

def render(frames: Iterable[tuple[int, np.ndarray]], *, fps: float, src_w: int, src_h: int,
           detector, ocr, sink: Callable[[np.ndarray], None], opts: RenderOptions,
           painter: Painter, total_frames: int | None = None,
           reads_dir: Path | None = None, say: Callable[[str], None] = print) -> dict:
    """Run the pipeline over *frames* (``(frame_index, BGR)``) and feed the
    annotated 1920x1080 frames to *sink* in order, one per input frame.

    Returns the summary: timings, committed reads and the still. Raises
    whatever the detector, OCR or sink raise.
    """
    tracker = Tracker()
    info: dict[int, TrackInfo] = {}
    reads: list[dict] = []
    detect_ms: list[float] = []
    ocr_ms: list[float] = []
    seen_ids: set[int] = set()
    watch = {_canon(p) for p in opts.watch}
    ocr_scale = min(1.0, (opts.ocr_width or src_w) / src_w)
    pending: list[tuple[int, np.ndarray]] = []
    prev_items: list[Item] = []
    prev_hud: Hud | None = None
    prev_idx: int | None = None
    frames_in = frames_detected = 0
    best: dict = {"n": -1, "frame": None, "img": None}
    # a track missed by one detection keeps its box one cadence + HOLD_MS
    hold_ms = HOLD_MS + opts.detect_every * 1000.0 / fps + 1e-6
    t0 = time.perf_counter()

    def full_reads() -> list[dict]:
        return [r for r in reads if r["kind"] == "full"]

    def commit(track: Track, pts_ms: float, idx: int, need_agreement: bool) -> None:
        c = commit_track(track, pts_ms, need_agreement)
        if c is None:
            return
        ti = info.get(track.id)
        rec = {
            "plate": c.plate, "raw": c.plate_raw, "confidence": round(float(c.confidence), 3),
            "kind": c.kind, "track": c.track_id, "class": c.vehicle_class,
            "watch": c.kind == "full" and _canon(c.plate) in watch,
            "commit_frame": idx, "commit_t_s": round(idx / fps, 2),
            "first_frame": ti.first_frame if ti else idx,
            "first_t_s": round((ti.first_frame if ti else idx) / fps, 2),
            "last_frame": ti.last_frame if ti else idx,
            "last_t_s": round((ti.last_frame if ti else idx) / fps, 2),
            "plate_w_px": int(c.bbox[2]),
            "plate_w_px_ocr": int(round(c.bbox[2] * ocr_scale)),
            "crop_img": c.crop if isinstance(c.crop, np.ndarray) else None,
        }
        reads.append(rec)
        if ti is not None and (ti.label is None or ti.label["kind"] != "full"):
            ti.label = rec
        if reads_dir is not None:
            _save_spot_check(reads_dir, len(reads), rec, ti)
        say(f"  commit #{c.track_id} {c.plate} ({c.kind}, conf {c.confidence:.2f}) "
            f"at {idx / fps:.1f} s{'  WATCHLIST HIT' if rec['watch'] else ''}")

    def snapshot(idx: int, pts_ms: float) -> tuple[list[Item], Hud]:
        items = []
        for tid, ti in info.items():
            if tid not in tracker.tracks or pts_ms - ti.last_seen_ms > hold_ms:
                continue
            if ti.superclass not in DRAWN:
                continue
            track = tracker.tracks[tid]
            reading = bool(track.ocr_reads) and not track.committed_full
            items.append(Item(tid, ti.cls, ti.superclass, ti.box, ti.last_seen_ms,
                              ti.plate_rel, ti.label, reading))
        hud = Hud(t_s=idx / fps,
                  vehicles=sum(1 for it in items if it.superclass == "vehicle"),
                  tracks=len(seen_ids), plates=len({r["plate"] for r in full_reads()}),
                  strip=reads[-STRIP_READS:])
        return items, hud

    def emit(idx: int, img: np.ndarray, items: list[Item], hud: Hud) -> None:
        painter.draw(img, items, hud)
        labelled = sum(1 for it in items if it.label and it.label["kind"] == "full")
        if labelled > best["n"]:
            best.update(n=labelled, frame=idx, img=img.copy())
        sink(img)

    def flush(next_idx: int | None, next_items: dict[int, Item]) -> None:
        """Draw the frames held since the last detection (interpolate or hold)."""
        for pidx, pimg in pending:
            pts = pidx * 1000.0 / fps
            items = []
            for it in prev_items:
                nxt = next_items.get(it.track_id)
                matched_both = (
                    next_idx is not None and nxt is not None and prev_idx is not None
                    and abs(it.last_seen_ms - prev_idx * 1000.0 / fps) < 1e-6
                    and abs(nxt.last_seen_ms - next_idx * 1000.0 / fps) < 1e-6)
                if matched_both:  # seen at both ends: interpolate, never extrapolate
                    box = _lerp(it.box, nxt.box, (pidx - prev_idx) / (next_idx - prev_idx))
                elif pts - it.last_seen_ms > hold_ms:
                    continue
                else:
                    box = it.box  # held
                items.append(dataclasses.replace(it, box=box))
            hud = dataclasses.replace(prev_hud, t_s=pidx / fps,
                                      vehicles=sum(1 for i in items if i.superclass == "vehicle"))
            emit(pidx, pimg, items, hud)
        pending.clear()

    for idx, frame in frames:
        frames_in += 1
        pts_ms = idx * 1000.0 / fps
        img = painter.to_output(frame)
        if prev_idx is not None and (idx - prev_idx) % opts.detect_every != 0:
            pending.append((idx, img))
            continue

        frames_detected += 1
        td = time.perf_counter()
        detections = detector.detect(frame)
        detect_ms.append((time.perf_counter() - td) * 1000.0)
        matches = tracker.update(detections, pts_ms)
        for track in tracker.last_removed:
            commit(track, pts_ms, idx, need_agreement=False)
            if track.id in info:  # keep its frame span; free its pixels
                info[track.id].best_vehicle_px = None
        for track, det in matches:
            ti = info.get(track.id)
            if ti is None:
                ti = info[track.id] = TrackInfo(det.cls, det.superclass, idx, idx, det.xyxy, pts_ms)
            ti.cls, ti.box, ti.last_seen_ms, ti.last_frame = det.cls, det.xyxy, pts_ms, idx
            if det.superclass in DRAWN:
                seen_ids.add(track.id)

        # OCR, the offline budget: largest vehicle boxes first
        due = [(t, d) for t, d in matches
               if d.superclass == "vehicle" and not t.committed_full
               and d.xyxy[2] - d.xyxy[0] >= opts.min_vehicle_w
               and pts_ms - t.last_ocr_pts >= opts.ocr_gap_ms
               and (opts.ocr_track_max <= 0 or info[t.id].ocr_attempts < opts.ocr_track_max)]
        due.sort(key=lambda p: -(p[1].xyxy[2] - p[1].xyxy[0]) * (p[1].xyxy[3] - p[1].xyxy[1]))
        for track, det in due[:opts.ocr_max]:
            x1, y1, x2, y2 = (int(v) for v in det.xyxy)
            x1, y1 = max(0, x1), max(0, y1)
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            if ocr_scale < 1.0:
                crop = cv2.resize(crop, None, fx=ocr_scale, fy=ocr_scale,
                                  interpolation=cv2.INTER_AREA)
            track.last_ocr_pts = pts_ms
            info[track.id].ocr_attempts += 1
            to = time.perf_counter()
            got = ocr.read(crop, offset=(x1 * ocr_scale, y1 * ocr_scale),
                           frame_h=int(src_h * ocr_scale))
            ocr_ms.append((time.perf_counter() - to) * 1000.0)
            if not got:
                continue
            best_read = max(got, key=lambda r: r.conf)
            if ocr_scale < 1.0:  # back to source pixels
                bx, by, bw, bh = best_read.bbox
                best_read = dataclasses.replace(best_read, bbox=(
                    int(bx / ocr_scale), int(by / ocr_scale),
                    int(bw / ocr_scale), int(bh / ocr_scale)))
            track.ocr_reads.append(best_read)
            ti = info[track.id]
            ti.plate_rel = _rel(best_read.bbox, det.xyxy)
            if reads_dir is not None and best_read.conf > ti.best_conf:
                ti.best_conf = best_read.conf
                ti.best_vehicle_px = _context(frame, det.xyxy)
            commit(track, pts_ms, idx, need_agreement=True)

        items, hud = snapshot(idx, pts_ms)
        flush(idx, {it.track_id: it for it in items})
        emit(idx, img, items, hud)
        prev_items, prev_hud, prev_idx = items, hud, idx

        if opts.progress_every and frames_in % opts.progress_every < opts.detect_every:
            el = time.perf_counter() - t0
            say(f"[{idx}{'/' + str(total_frames) if total_frames else ''}] "
                f"{el:.0f} s, {frames_in / max(el, 1e-6):.1f} fps, "
                f"OCR crops {len(ocr_ms)}, plates {len({r['plate'] for r in full_reads()})}")

    # end of clip: every surviving track dies — the dying-track rule applies
    last_idx = pending[-1][0] if pending else (prev_idx if prev_idx is not None else 0)
    if prev_hud is not None:
        flush(None, {})
    plates_on_screen = len({r["plate"] for r in full_reads()})
    for track in list(tracker.tracks.values()):
        commit(track, last_idx * 1000.0 / fps, last_idx, need_agreement=False)

    for r in reads:  # the last frame each track was seen, now known
        ti = info.get(r["track"])
        if ti is not None:
            r["last_frame"], r["last_t_s"] = ti.last_frame, round(ti.last_frame / fps, 2)

    def stats(values: list[float]) -> dict:
        if not values:
            return {"mean": None, "p90": None, "n": 0}
        return {"mean": round(float(np.mean(values)), 1),
                "p90": round(float(np.percentile(values, 90)), 1), "n": len(values)}

    fulls = full_reads()
    return {
        "frames_processed": frames_in, "frames_detected": frames_detected,
        "detect_ms": stats(detect_ms),
        "ocr_ms": {**stats(ocr_ms), "crops": len(ocr_ms)},
        "runtime_s": round(time.perf_counter() - t0, 1),
        "tracks": len(seen_ids),
        "plates_read": len({r["plate"] for r in fulls}),
        "plates_read_on_screen": plates_on_screen,
        "distinct_full_plates": sorted({r["plate"] for r in fulls}),
        "reads": [{k: v for k, v in r.items() if k != "crop_img"} for r in reads],
        "still": {"frame": best["frame"], "labelled_plates": max(0, best["n"]),
                  "img": best["img"]},
    }


def _context(frame: np.ndarray, xyxy: tuple) -> np.ndarray:
    """The vehicle crop from the full-resolution frame, <= 640 px wide."""
    x1, y1, x2, y2 = (int(v) for v in xyxy)
    crop = frame[max(0, y1):y2, max(0, x1):x2]
    if crop.shape[1] > 640:
        crop = cv2.resize(crop, None, fx=640 / crop.shape[1], fy=640 / crop.shape[1],
                          interpolation=cv2.INTER_AREA)
    return crop.copy()


def _save_spot_check(reads_dir: Path, n: int, rec: dict, ti: TrackInfo | None) -> None:
    """The plate crop (x3) and the vehicle context behind a commit, for the
    precision spot check (S7.1 acceptance). Outside the repo."""
    reads_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{n:03d}_{rec['plate']}_t{rec['track']}"
    crop = rec.get("crop_img")
    if crop is not None and crop.size:
        big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(str(reads_dir / f"{stem}_plate.png"), big)
    if ti is not None and ti.best_vehicle_px is not None and ti.best_vehicle_px.size:
        cv2.imwrite(str(reads_dir / f"{stem}_vehicle.jpg"), ti.best_vehicle_px,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])


# --- input and output ------------------------------------------------------

def open_clip(path: Path) -> tuple[cv2.VideoCapture, float, int, int, int]:
    """``(capture, fps, frame_count, width, height)`` from the container.

    Raises FileNotFoundError / RuntimeError when the clip cannot be read.
    """
    if not path.is_file():
        raise FileNotFoundError(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)  # a file's container rate — not a live pull
    if not fps or fps <= 0:
        cap.release()
        raise RuntimeError(f"{path} reports no frame rate")
    return (cap, fps, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))


def iter_frames(cap: cv2.VideoCapture, first: int, last: int | None) -> Iterator[tuple[int, np.ndarray]]:
    """``(frame_index, frame)`` from *first* to *last* (inclusive, None = end)."""
    if first > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    idx = first
    while last is None or idx <= last:
        ok, frame = cap.read()
        if not ok:
            return
        yield idx, frame
        idx += 1


def ffmpeg_argv(out: Path, fps: float, width: int = OUT_W, height: int = OUT_H) -> list[str]:
    """The encoder command: raw BGR frames on stdin → H.264 MP4 (no shell)."""
    rate = Fraction(fps).limit_denominator(1001)
    return [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{rate.numerator}/{rate.denominator}", "-i", "-", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]


class Encoder:
    """Pipes frames to ffmpeg; never writes frames to disk one by one."""

    def __init__(self, out: Path, fps: float) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        self.argv = ffmpeg_argv(out, fps)
        self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, frame: np.ndarray) -> None:
        if frame.shape != (OUT_H, OUT_W, 3) or frame.dtype != np.uint8:
            raise ValueError(f"encoder wants {OUT_W}x{OUT_H} BGR uint8, got {frame.shape}")
        self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        self.frames += 1

    def close(self) -> None:
        """Finish the file; raises RuntimeError when ffmpeg failed."""
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        rc = self.proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited {rc}")

    def kill(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()


def probe_duration(path: Path) -> float | None:
    """The container duration of *path* in seconds (ffprobe), or None."""
    try:
        out = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                              "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, timeout=60, check=True)
        return round(float(out.stdout.strip()), 3)
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        print(f"ffprobe failed on {path}: {exc}", file=sys.stderr)
        return None


def summary_json(clip: Path, src: dict, out: Path, still: Path | None, opts: RenderOptions,
                 provider: str, result: dict, frames_written: int,
                 range_s: tuple[float, float | None]) -> dict:
    """The committed JSON: everything but the still's pixels."""
    body = {k: v for k, v in result.items() if k != "still"}
    return {
        "clip": clip.name,
        "label": HUD_LABEL,
        "source": src,
        "range_s": {"start": range_s[0], "end": range_s[1]},
        "output": {"path": str(out), "width": OUT_W, "height": OUT_H,
                   "frames_written": frames_written},
        "still": {"path": str(still) if still else None, "frame": result["still"]["frame"],
                  "labelled_plates": result["still"]["labelled_plates"]},
        "provider": provider,
        "options": {k: (list(v) if isinstance(v, tuple) else v)
                    for k, v in dataclasses.asdict(opts).items()},
        **body,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clip", help="the stock clip (an MP4 file)")
    parser.add_argument("--out", help="output MP4 (default <SENTINEL_FOOTAGE_DIR>/renders/<stem>.mp4)")
    parser.add_argument("--json", help="summary JSON (default data/measurements/render-<stem>.json)")
    parser.add_argument("--start", type=float, default=0.0, help="start at S seconds")
    parser.add_argument("--end", type=float, default=None, help="stop at S seconds")
    parser.add_argument("--detect-every", type=int, default=2)
    parser.add_argument("--ocr-gap-ms", type=float, default=300.0)
    parser.add_argument("--ocr-max", type=int, default=6)
    parser.add_argument("--min-vehicle-w", type=float, default=140.0,
                        help="source px; narrower vehicles are drawn but never read")
    parser.add_argument("--ocr-width", type=int, default=None,
                        help="OCR crops as if the frame were this wide (default: source)")
    parser.add_argument("--ocr-track-max", type=int, default=0,
                        help="cap on OCR attempts per track (default 0: none)")
    parser.add_argument("--watch", default="", help="comma-separated watchlist plates")
    parser.add_argument("--deck-still", action="store_true",
                        help=f"copy the still to deliverables/deck/img/ when <= {DECK_STILL_MAX_BYTES} bytes")
    args = parser.parse_args()

    if args.detect_every < 1 or args.ocr_max < 0:
        raise SystemExit("--detect-every must be >= 1 and --ocr-max >= 0")
    clip = Path(args.clip)
    stem = clip.stem.split("_")[0]
    out = Path(args.out) if args.out else config.footage_dir() / "renders" / f"{stem}.mp4"
    json_path = Path(args.json) if args.json else MEASUREMENTS / f"render-{stem}.json"
    still_path = out.with_suffix(".png")
    reads_dir = out.with_name(f"{out.stem}-reads")
    if reads_dir.exists():
        shutil.rmtree(reads_dir)  # our own spot-check folder from a previous run

    opts = RenderOptions(detect_every=args.detect_every, ocr_gap_ms=args.ocr_gap_ms,
                         ocr_max=args.ocr_max, min_vehicle_w=args.min_vehicle_w,
                         ocr_width=args.ocr_width, ocr_track_max=args.ocr_track_max,
                         watch=tuple(p.strip() for p in args.watch.split(",") if p.strip()))

    cap, fps, total, src_w, src_h = open_clip(clip)
    first = int(round(args.start * fps))
    last = int(round(args.end * fps)) - 1 if args.end is not None else None
    frames_expected = (min(total - 1, last) if last is not None else total - 1) - first + 1

    from ml.anpr.detect import Detector  # heavy imports after the cheap checks
    from ml.anpr.ocr import PlateOcr

    detector = Detector()
    ocr = PlateOcr()
    painter = Painter(src_w, src_h, clip_id=stem)
    print(f"render {clip.name}: {src_w}x{src_h} @ {fps:g} fps, frames {first}..{first + frames_expected - 1} "
          f"({frames_expected}), detector {detector.provider}, OCR width "
          f"{opts.ocr_width or src_w}, watch {list(opts.watch) or '-'} -> {out}", flush=True)

    encoder = Encoder(out, fps)
    try:
        result = render(iter_frames(cap, first, last), fps=fps, src_w=src_w, src_h=src_h,
                        detector=detector, ocr=ocr, sink=encoder.write, opts=opts,
                        painter=painter, total_frames=first + frames_expected - 1,
                        reads_dir=reads_dir, say=lambda s: print(s, flush=True))
        encoder.close()
    except BaseException:
        encoder.kill()
        raise
    finally:
        cap.release()

    still = None
    if result["still"]["img"] is not None:
        cv2.imwrite(str(still_path), result["still"]["img"], [cv2.IMWRITE_PNG_COMPRESSION, 9])
        still = still_path
    src = {"width": src_w, "height": src_h, "fps": round(fps, 3), "frames": total,
           "duration_s": probe_duration(clip)}
    body = summary_json(clip, src, out, still, opts, detector.provider, result,
                        encoder.frames, (args.start, args.end))
    body["output"]["duration_s"] = probe_duration(out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(body, indent=2), encoding="utf-8")

    if still is not None and args.deck_still:
        size = still.stat().st_size
        if size <= DECK_STILL_MAX_BYTES:
            DECK_IMG.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(still, DECK_IMG / f"render-{stem}.png")
            print(f"deck still: {DECK_IMG / f'render-{stem}.png'} ({size} bytes)")
        else:
            print(f"deck still not copied: {size} bytes > {DECK_STILL_MAX_BYTES}")

    print(f"done: {encoder.frames} frames in {result['runtime_s']:.0f} s; "
          f"plates read {result['plates_read']} {result['distinct_full_plates']}; "
          f"detect {result['detect_ms']['mean']} ms, OCR {result['ocr_ms']['mean']} ms x "
          f"{result['ocr_ms']['crops']} crops\n  mp4 {out}\n  json {json_path}\n  still {still}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
