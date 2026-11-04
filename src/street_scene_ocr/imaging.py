"""Turning uploaded bytes into the pixels an engine reads."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImage(ValueError):
    """The bytes are not an image Pillow can open."""


def decode_image(data: bytes) -> Image.Image:
    """Open an uploaded image, apply the camera's rotation flag and return it as RGB.

    Phones store photos sideways and add an EXIF "orientation" flag; without applying it the
    engines would read every portrait photo lying on its side.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened)
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImage("the file is not a readable image") from exc
    return image.convert("RGB")


def fit_within(image: Image.Image, max_side: int) -> tuple[Image.Image, float]:
    """Shrink ``image`` so its longer side is at most ``max_side`` pixels.

    Returns the image the engine should read and the factor that maps its coordinates back to the
    original image (``1.0`` when nothing was resized).
    """
    longest = max(image.size)
    if longest <= max_side:
        return image, 1.0
    ratio = max_side / longest
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    return image.resize(size, Image.Resampling.LANCZOS), longest / max_side


def to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.uint8)
