"""YOLOX-S object detector on ONNX Runtime (task S2.3; F14, F25).

Providers: DirectML first, CPU fallback — the chosen one is logged once.
The session is **not thread-safe under DirectML** (measured crash,
sandbox-findings §7): one lock around ``session.run()``; everything
before and after runs in parallel.

Decode follows the official YOLOX ONNX demo (Apache-2.0, re-implemented):
letterbox to 640 with 114-grey padding, raw BGR float32 (no
normalisation), grid + stride decode, ``obj_conf × cls_conf`` scoring,
per-class NMS.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import onnxruntime as ort

from backend.core import config
from backend.core.logging_setup import setup
from ml.tools import fetch_models

log = setup("detect")

INPUT_SIZE = 640
_STRIDES = (8, 16, 32)
_NMS_THRESHOLD = 0.45

# COCO ids we keep (task S2.3). Everything else is discarded.
COCO_KEEP = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
             5: "bus", 7: "truck", 24: "backpack", 26: "handbag"}
_VEHICLES = {"car", "truck", "bus", "motorcycle"}


def superclass(cls: str) -> str:
    """car/truck/bus/motorcycle → ``vehicle``; anything else is itself."""
    return "vehicle" if cls in _VEHICLES else cls


@dataclass
class Detection:
    cls: str
    superclass: str
    conf: float
    xyxy: tuple[float, float, float, float]  # source-frame pixels


def _grids() -> tuple[np.ndarray, np.ndarray]:
    """(grids, expanded_strides) for the fixed 640 input, shape (1, N, 2)/(1, N, 1)."""
    grids, strides = [], []
    for stride in _STRIDES:
        n = INPUT_SIZE // stride
        xv, yv = np.meshgrid(np.arange(n), np.arange(n))
        grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
        grids.append(grid)
        strides.append(np.full((1, grid.shape[1], 1), stride))
    return np.concatenate(grids, 1).astype(np.float32), np.concatenate(strides, 1).astype(np.float32)


_GRIDS, _EXPANDED_STRIDES = _grids()


def roi_mask(frame_shape: tuple[int, ...], roi: Sequence[Sequence[float]]) -> np.ndarray:
    """A uint8 mask (1 inside the normalised 0–1 polygon, 0 outside)."""
    h, w = frame_shape[:2]
    pts = np.array([[int(x * w), int(y * h)] for x, y in roi], dtype=np.int32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 1)
    return mask


class Detector:
    """One ONNX session, shared by every camera thread through one lock."""

    def __init__(self, model_path: str | Path | None = None,
                 conf: float | None = None) -> None:
        path = Path(model_path) if model_path else fetch_models.ensure()
        self.conf = config.detect_conf() if conf is None else conf
        available = ort.get_available_providers()
        preferred = [p for p in ("DmlExecutionProvider", "CPUExecutionProvider") if p in available]
        self.session = ort.InferenceSession(str(path), providers=preferred)
        self.provider = self.session.get_providers()[0]
        self._input_name = self.session.get_inputs()[0].name
        self._lock = threading.Lock()
        log.info("detector ready: %s on %s (conf >= %.2f)", path.name, self.provider, self.conf)

    def _preproc(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        r = min(INPUT_SIZE / frame.shape[0], INPUT_SIZE / frame.shape[1])
        resized = cv2.resize(frame, (int(frame.shape[1] * r), int(frame.shape[0] * r)),
                             interpolation=cv2.INTER_LINEAR)
        padded = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized
        return np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)[None], r

    def detect(self, frame: np.ndarray,
               roi: Sequence[Sequence[float]] | None = None) -> list[Detection]:
        """Detections on *frame* (BGR), in source pixels.

        ``roi`` is the registry row's parsed ``roi_json`` (normalised 0–1
        polygon): pixels outside it are zeroed **before** inference.
        Boxes centred in the top caption band are dropped (burned-in
        caption, sandbox-findings §5).
        """
        if roi:
            frame = frame * roi_mask(frame.shape, roi)[:, :, None]
        blob, r = self._preproc(frame)
        with self._lock:
            out = self.session.run(None, {self._input_name: blob})[0][0]  # (N, 85)
        boxes = out[:, :4].copy()
        boxes[:, :2] = (boxes[:, :2] + _GRIDS[0]) * _EXPANDED_STRIDES[0]
        boxes[:, 2:4] = np.exp(boxes[:, 2:4]) * _EXPANDED_STRIDES[0]
        scores = out[:, 4:5] * out[:, 5:]  # obj_conf x cls_conf, (N, 80)

        h, w = frame.shape[:2]
        band_px = h * config.caption_band()
        detections: list[Detection] = []
        for class_id, name in COCO_KEEP.items():
            cls_scores = scores[:, class_id]
            keep = cls_scores >= self.conf
            if not keep.any():
                continue
            cxywh = boxes[keep]
            confs = cls_scores[keep]
            x1 = (cxywh[:, 0] - cxywh[:, 2] / 2) / r
            y1 = (cxywh[:, 1] - cxywh[:, 3] / 2) / r
            bw, bh = cxywh[:, 2] / r, cxywh[:, 3] / r
            rects = np.stack([x1, y1, bw, bh], axis=1)
            picked = cv2.dnn.NMSBoxes(rects.tolist(), confs.tolist(), self.conf, _NMS_THRESHOLD)
            for i in np.array(picked).reshape(-1):
                bx1, by1, bbw, bbh = rects[i]
                bx2, by2 = bx1 + bbw, by1 + bbh
                if (by1 + by2) / 2 < band_px:
                    continue  # burned-in caption band
                detections.append(Detection(
                    cls=name, superclass=superclass(name), conf=float(confs[i]),
                    xyxy=(float(max(0, bx1)), float(max(0, by1)),
                          float(min(w, bx2)), float(min(h, by2))),
                ))
        return detections


def parse_roi(roi_json: str | None) -> list[list[float]] | None:
    """The registry row's ``roi_json`` as a polygon, or None."""
    if not roi_json:
        return None
    try:
        roi = json.loads(roi_json)
        return roi if isinstance(roi, list) and len(roi) >= 3 else None
    except ValueError:
        log.warning("unparseable roi_json ignored: %.60s", roi_json)
        return None
