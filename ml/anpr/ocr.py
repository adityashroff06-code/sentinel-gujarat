"""OCR on vehicle crops — PaddleOCR PP-OCRv5 mobile (task S2.4).

Never a full frame: the input is a vehicle crop, super-resolved first
(cubic upscale to ~400 px wide, capped at 4×, then CLAHE on the L
channel) — measured to lift a 22 px plate into readable range
(sandbox-findings §5). The PaddleOCR object is not thread-safe: one lock
around init **and** predict (§7). ``enable_mkldnn=False`` (paddle 3.3.1
raises otherwise). Models land under ``models/paddle/`` via
``PADDLE_PDX_CACHE_HOME`` — a repo-controlled path, not the user profile.

Every text region is gated by :func:`backend.core.plates.plate_like` and
mapped back to **source-frame pixels** as ``[x, y, w, h]``; regions in
the top caption band are rejected (burned-in caption reads as a plate).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from backend.core import config, plates
from backend.core.config import REPO_ROOT
from backend.core.logging_setup import setup

# Repo-controlled model path; a real environment variable still wins.
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(REPO_ROOT / "models" / "paddle"))
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

log = setup("ocr")

_TARGET_WIDTH = 400
_MAX_UPSCALE = 4.0


@dataclass
class PlateRead:
    text: str          # normalised (plates.normalise)
    raw: str           # exactly what OCR returned
    conf: float
    bbox: tuple[int, int, int, int]  # [x, y, w, h] in SOURCE-frame pixels
    kind: str          # full | partial
    crop: np.ndarray | None = None   # the plate region, cut when it was read


def _enhance(crop: np.ndarray) -> tuple[np.ndarray, float]:
    """Cubic upscale to ~400 px wide (≤ 4×) + CLAHE; returns (image, scale)."""
    scale = min(_MAX_UPSCALE, _TARGET_WIDTH / max(1, crop.shape[1]))
    if scale > 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    else:
        scale = 1.0
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), scale


class PlateOcr:
    """Lazy-initialised PaddleOCR behind one lock (init + predict)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            t0 = time.perf_counter()
            from paddleocr import PaddleOCR  # heavy import, deferred

            self._model = PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="en_PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
            log.info("PaddleOCR ready in %.1f s (models under %s)",
                     time.perf_counter() - t0, os.environ["PADDLE_PDX_CACHE_HOME"])
        return self._model

    def read(self, crop: np.ndarray, *, offset: tuple[float, float] = (0.0, 0.0),
             frame_h: int | None = None) -> list[PlateRead]:
        """Plate-like reads on a vehicle *crop*.

        ``offset`` is the crop's top-left in the source frame; region boxes
        come back in source pixels. With ``frame_h`` given, regions whose
        mapped centre sits in the top caption band are rejected.
        """
        if crop.size == 0:
            return []
        enhanced, scale = _enhance(crop)
        with self._lock:
            model = self._ensure_model()
            results = model.predict(enhanced)
        band_px = frame_h * config.caption_band() if frame_h else None
        reads: list[PlateRead] = []
        for result in results:
            for raw, conf, poly in zip(result["rec_texts"], result["rec_scores"],
                                       result["rec_polys"]):
                norm = plates.normalise(raw)
                kind = plates.plate_like(norm)
                if kind is None:
                    continue
                pts = np.asarray(poly, dtype=float) / scale
                x = float(pts[:, 0].min()) + offset[0]
                y = float(pts[:, 1].min()) + offset[1]
                w = float(pts[:, 0].max() - pts[:, 0].min())
                h = float(pts[:, 1].max() - pts[:, 1].min())
                if band_px is not None and (y + h / 2) < band_px:
                    log.debug("caption-band read rejected: %s", norm)
                    continue
                # The plate region from the ORIGINAL crop, 25 % margin —
                # kept with the read so a consensus committed frames later
                # still stores the pixels that produced it.
                cx1 = int(max(0, pts[:, 0].min() - w * 0.25))
                cy1 = int(max(0, pts[:, 1].min() - h * 0.25))
                cx2 = int(min(crop.shape[1], pts[:, 0].max() + w * 0.25))
                cy2 = int(min(crop.shape[0], pts[:, 1].max() + h * 0.25))
                plate_px = crop[cy1:cy2, cx1:cx2].copy() if cy2 > cy1 and cx2 > cx1 else None
                reads.append(PlateRead(text=norm, raw=raw, conf=float(conf),
                                       bbox=(int(x), int(y), int(w), int(h)), kind=kind,
                                       crop=plate_px))
        return reads
