from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from street_scene_ocr.config import Settings
from street_scene_ocr.engines.base import EngineOutput, OcrEngine, TextRegion
from street_scene_ocr.service import EngineManager


def box(left, top, right, bottom):
    return ((left, top), (right, top), (right, bottom), (left, bottom))


class FakeEngine(OcrEngine):
    """Pretends to read two lines of a 200x100 sign; records the size of every image it was given."""

    name = "fake"
    title = "Fake engine"
    summary = "returns fixed regions for tests"
    homepage = "https://example.invalid/fake"
    modules = ()

    seen_shapes: list[tuple[int, ...]] = []

    def load(self) -> None:
        self.device = "cpu"

    def read(self, image: np.ndarray) -> EngineOutput:
        FakeEngine.seen_shapes.append(image.shape)
        h, w = image.shape[:2]
        sx, sy = w / 200, h / 100
        regions = [
            TextRegion("水果行", 0.98, box(20 * sx, 50 * sy, 120 * sx, 80 * sy)),
            TextRegion("安和", 0.25, box(20 * sx, 10 * sy, 90 * sx, 40 * sy)),
        ]
        return EngineOutput(regions, {"detection": 1.0, "recognition": 2.0})


class MissingEngine(OcrEngine):
    name = "missing"
    title = "Not installed"
    summary = "needs a module that does not exist"
    homepage = "https://example.invalid/missing"
    modules = ("street_scene_ocr_module_that_does_not_exist",)

    def load(self) -> None:  # pragma: no cover - never called
        raise AssertionError

    def read(self, image):  # pragma: no cover - never called
        raise AssertionError


class BrokenEngine(FakeEngine):
    name = "broken"

    def read(self, image):
        raise RuntimeError("model exploded")


@pytest.fixture
def settings() -> Settings:
    return Settings(default_engine="fake", enabled_engines=("fake", "missing", "broken"))


@pytest.fixture
def manager(settings) -> EngineManager:
    FakeEngine.seen_shapes = []
    return EngineManager(settings, engine_classes=(FakeEngine, MissingEngine, BrokenEngine))


def png_bytes(width=200, height=100, colour=(255, 255, 255), fmt="PNG", **save_args) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, fmt, **save_args)
    return buffer.getvalue()
