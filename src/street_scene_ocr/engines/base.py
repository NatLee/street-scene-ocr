"""The one interface every OCR engine implements.

An engine takes an RGB image and returns text regions: a polygon, the text inside it and how sure
the engine is. Everything after that (threshold, reading order, drawing, the API) is shared, so
adding an engine means writing one subclass of :class:`OcrEngine` and listing it in
``engines/__init__.py``.
"""

from __future__ import annotations

import importlib.util
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np

from ..config import Settings

Point = tuple[float, float]


@dataclass(frozen=True)
class TextRegion:
    """One piece of text found in the image.

    ``polygon`` holds the corners in image pixels, usually four points clockwise from the top-left
    corner of the text (engines return quadrilaterals so tilted signs keep a tight outline).
    """

    text: str
    confidence: float
    polygon: tuple[Point, ...]

    @classmethod
    def from_points(cls, text: str, confidence: float, points: Iterable[Sequence[float]]) -> TextRegion:
        polygon = tuple((float(x), float(y)) for x, y in points)
        if len(polygon) < 3:
            raise ValueError(f"a text region needs at least 3 corners, got {len(polygon)}")
        return cls(text=str(text), confidence=float(confidence), polygon=polygon)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Axis-aligned box ``(left, top, right, bottom)`` around the polygon."""
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def center(self) -> Point:
        left, top, right, bottom = self.bbox
        return (left + right) / 2, (top + bottom) / 2

    def scaled(self, factor: float) -> TextRegion:
        """The same region with every coordinate multiplied by ``factor``."""
        if factor == 1:
            return self
        return TextRegion(self.text, self.confidence, tuple((x * factor, y * factor) for x, y in self.polygon))


@dataclass(frozen=True)
class EngineOutput:
    regions: list[TextRegion]
    # Milliseconds per pipeline stage when the engine reports them, e.g. {"detection": 120.0}.
    stages_ms: dict[str, float] = field(default_factory=dict)


class EngineError(RuntimeError):
    """The engine could not be loaded or failed while reading an image."""


class OcrEngine(ABC):
    #: Short id used in the API and the ``OCR_ENGINES`` setting, also the name of the pip extra.
    name: ClassVar[str]
    #: Human-readable name for the web page.
    title: ClassVar[str]
    #: One line about the models behind the engine.
    summary: ClassVar[str]
    homepage: ClassVar[str]
    #: Python modules that must be importable for the engine to work.
    modules: ClassVar[tuple[str, ...]]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.device = "cpu"

    @classmethod
    def missing_modules(cls) -> list[str]:
        return [m for m in cls.modules if importlib.util.find_spec(m) is None]

    @classmethod
    def is_installed(cls) -> bool:
        return not cls.missing_modules()

    def model_dir(self) -> Path | None:
        """Where this engine keeps its model files (created on demand), or ``None`` for the default."""
        folder = self.settings.model_dir_for(self.name)
        if folder is not None:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    @abstractmethod
    def load(self) -> None:
        """Load the models. May download them on first use; called once, before the first ``read``."""

    @abstractmethod
    def read(self, image: np.ndarray) -> EngineOutput:
        """Find and read text in an RGB ``uint8`` image of shape ``(height, width, 3)``."""


def to_bgr(image: np.ndarray) -> np.ndarray:
    """OpenCV-based libraries expect blue-green-red channel order."""
    return np.ascontiguousarray(image[:, :, ::-1])


class Stopwatch:
    """Collects how long each pipeline stage took, in milliseconds."""

    def __init__(self) -> None:
        self.stages_ms: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stages_ms[name] = round((time.perf_counter() - start) * 1000, 1)
