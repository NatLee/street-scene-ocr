"""Engine registry.

To add an engine: write a subclass of :class:`OcrEngine` in its own module and add it to
``ENGINE_CLASSES``. Nothing else in the service, the web page or the benchmark needs to change.
"""

from __future__ import annotations

from .base import EngineError, EngineOutput, OcrEngine, TextRegion
from .easyocr_engine import EasyOcrEngine
from .paddleocr_engine import PaddleOcrEngine
from .rapidocr_engine import RapidOcrEngine

ENGINE_CLASSES: tuple[type[OcrEngine], ...] = (EasyOcrEngine, RapidOcrEngine, PaddleOcrEngine)

__all__ = [
    "ENGINE_CLASSES",
    "EngineError",
    "EngineOutput",
    "OcrEngine",
    "TextRegion",
]
