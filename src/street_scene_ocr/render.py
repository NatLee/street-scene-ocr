"""Draw the OCR result on the image: an outline per region and a label with text and confidence."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .engines.base import TextRegion
from .postprocess import is_confident

# Colours from 2021: green for confident regions. The 2021 code meant red for the rest but drew blue,
# because it passed blue-green-red numbers to an image that was already red-green-blue.
CONFIDENT_COLOUR = (50, 255, 50)
UNSURE_COLOUR = (255, 50, 50)
LABEL_BACKGROUND = (0, 0, 0, 170)

# 2021 used a fixed 20 px label and 2 px lines. Big photos get proportionally bigger ones so the
# labels stay readable: about 1/64 of the longer side, never smaller than the 2021 sizes.
MIN_FONT_PX = 20
FONT_RATIO = 1 / 64
MIN_LINE_PX = 2
LINE_RATIO = 1 / 600


@lru_cache(maxsize=8)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def label_for(region: TextRegion) -> str:
    """The label format used since 2021, e.g. ``水果行 99.87%``."""
    return f"{region.text} {region.confidence * 100:.02f}%"


def annotate(
    image: Image.Image,
    regions: Iterable[TextRegion],
    threshold: float,
    font_path: Path,
    show_unsure: bool = True,
) -> Image.Image:
    """Return a copy of ``image`` with every region outlined and labelled.

    Regions are drawn from the least to the most confident one, so confident labels end up on top
    (the 2021 order).
    """
    longest = max(image.size)
    font = _font(str(font_path), max(MIN_FONT_PX, round(longest * FONT_RATIO)))
    line = max(MIN_LINE_PX, round(longest * LINE_RATIO))

    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for region in sorted(regions, key=lambda r: r.confidence):
        confident = is_confident(region, threshold)
        if not confident and not show_unsure:
            continue
        colour = CONFIDENT_COLOUR if confident else UNSURE_COLOUR
        points = list(region.polygon)
        draw.line(points + points[:1], fill=colour + (255,), width=line, joint="curve")

        left, _, _, bottom = region.bbox
        text = label_for(region)
        box = draw.textbbox((left, bottom), text, font=font)
        pad = max(2, line)
        draw.rectangle((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), fill=LABEL_BACKGROUND)
        draw.text((left, bottom), text, font=font, fill=colour + (255,))
    return Image.alpha_composite(canvas, overlay).convert("RGB")
