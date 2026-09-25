"""Rendered plate crops for the labelled demo sightings (ANPR search lane).

A demo sighting has no camera frame behind it, so Search and Route showed
no image for the demo plates. ``render_plate_crop`` draws one with Pillow
(already pinned): an Indian number-plate look — white plate, black bold
registration, the blue ``IND`` strip at the left — plus an unmistakable
**DEMO** marking on the image itself, so root rule 12 (a demo row never
passes as a live one) holds even for a crop seen out of context: a
translucent diagonal ``DEMO`` watermark across the plate and an orange
band reading ``DEMO · SEEDED · NOT A LIVE READ``.

Colours mirror the frontend token sheet (``--prov-demo`` for the band).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.core import plates

#: Bold face on this laptop; ``ImageFont.load_default(size=...)`` elsewhere.
FONT_PATH = Path(r"C:\Windows\Fonts\arialbd.ttf")

WIDTH = 400
PLATE_H = 96
BAND_H = 28
IND_W = 46
JPEG_QUALITY = 85

_PLATE_BG = (246, 246, 240)
_INK = (17, 17, 17)
_IND_BLUE = (30, 76, 160)
_DEMO = (224, 145, 47)       # --prov-demo
_WHITE = (255, 255, 255)
_BAND_TEXT = "DEMO · SEEDED · NOT A LIVE READ"


@lru_cache(maxsize=16)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:  # no Arial Bold here: Pillow's bundled scalable face
        return ImageFont.load_default(size=size)


def display_text(plate: str) -> str:
    """The registration as printed on a plate: ``GJ 01 AB 1234`` /
    ``22 BH 1234 AA``; anything that is not a full plate is shown as is."""
    p = plates.coerce(plate) or plates.normalise(plate)
    if plates.plate_like(p) == "full":
        if p[2:4] == "BH" and p[:2].isdigit():
            return f"{p[:2]} BH {p[4:8]} {p[8:]}"
        return f"{p[:2]} {p[2:4]} {p[4:-4]} {p[-4:]}"
    return p


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_size: int):
    size = max_size
    while size > 12:
        font = _font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_w:
            return font, (left, top, right, bottom)
        size -= 2
    font = _font(size)
    return font, draw.textbbox((0, 0), text, font=font)


def render_plate_image(plate: str) -> Image.Image:
    """The demo crop for *plate* as an RGB image (WIDTH × PLATE_H + BAND_H)."""
    img = Image.new("RGB", (WIDTH, PLATE_H + BAND_H), _WHITE)
    draw = ImageDraw.Draw(img)

    # the plate: white, black rim, blue IND strip on the left
    draw.rounded_rectangle((1, 1, WIDTH - 2, PLATE_H - 2), radius=10,
                           fill=_PLATE_BG, outline=_INK, width=3)
    draw.rounded_rectangle((5, 5, 5 + IND_W, PLATE_H - 6), radius=6, fill=_IND_BLUE)
    ind_font, (l, t, r, b) = _fit(draw, "IND", IND_W - 8, 16)
    draw.text((5 + (IND_W - (r - l)) / 2 - l, PLATE_H - 16 - (b - t) - t), "IND",
              font=ind_font, fill=_WHITE)
    draw.ellipse((5 + IND_W / 2 - 9, 16, 5 + IND_W / 2 + 9, 34), outline=_WHITE, width=2)

    text = display_text(plate)
    x0 = 5 + IND_W + 10
    font, (l, t, r, b) = _fit(draw, text, WIDTH - x0 - 12, 54)
    draw.text((x0 + (WIDTH - x0 - 12 - (r - l)) / 2 - l, (PLATE_H - (b - t)) / 2 - t),
              text, font=font, fill=_INK)

    # translucent diagonal DEMO watermark across the plate
    mark = Image.new("RGBA", (WIDTH, PLATE_H), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mark)
    mfont = _font(64)
    ml, mt, mr, mb = mdraw.textbbox((0, 0), "DEMO", font=mfont)
    mdraw.text(((WIDTH - (mr - ml)) / 2 - ml, (PLATE_H - (mb - mt)) / 2 - mt), "DEMO",
               font=mfont, fill=(*_DEMO, 96))
    mark = mark.rotate(-10, resample=Image.Resampling.BICUBIC)
    img.paste(mark, (0, 0), mark)

    # the band: demo orange, spelled out
    draw.rectangle((0, PLATE_H, WIDTH, PLATE_H + BAND_H), fill=_DEMO)
    bfont, (l, t, r, b) = _fit(draw, _BAND_TEXT, WIDTH - 16, 16)
    draw.text(((WIDTH - (r - l)) / 2 - l, PLATE_H + (BAND_H - (b - t)) / 2 - t),
              _BAND_TEXT, font=bfont, fill=_WHITE)
    return img


def render_plate_crop(plate: str, path: Path) -> Path:
    """Write the demo crop for *plate* to *path* as a JPEG; returns *path*.
    Raises ``OSError`` when the file cannot be written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    render_plate_image(plate).save(path, "JPEG", quality=JPEG_QUALITY)
    return path
