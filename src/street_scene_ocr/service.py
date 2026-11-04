"""Runs the whole pipeline: image -> engine -> post-processing.

:class:`EngineManager` knows which engines exist, loads each one the first time it is asked for
(models are big, so nothing loads at start-up) and makes sure one engine reads one image at a time.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image

from .config import Settings
from .engines import ENGINE_CLASSES, EngineError, OcrEngine, TextRegion
from .imaging import fit_within, to_array
from .postprocess import reading_order, to_traditional


class UnknownEngine(LookupError):
    """No engine with that name is enabled."""


class EngineNotInstalled(RuntimeError):
    """The engine exists but its Python package is not installed in this environment."""


@dataclass(frozen=True)
class EngineInfo:
    name: str
    title: str
    summary: str
    homepage: str
    installed: bool
    missing: tuple[str, ...]
    loaded: bool
    device: str | None


@dataclass(frozen=True)
class OcrResult:
    engine: str
    device: str
    width: int
    height: int
    # In reading order and in the coordinates of the image that was passed in.
    regions: list[TextRegion]
    stages_ms: dict[str, float]
    total_ms: float
    traditional: bool
    # How much the image was shrunk before the engine saw it (1.0 = not at all).
    scale: float


class EngineManager:
    def __init__(self, settings: Settings, engine_classes: Iterable[type[OcrEngine]] = ENGINE_CLASSES) -> None:
        self.settings = settings
        classes = {cls.name: cls for cls in engine_classes}
        wanted = settings.enabled_engines
        if wanted is not None:
            unknown = sorted(set(wanted) - set(classes))
            if unknown:
                raise UnknownEngine(f"unknown engine(s) in OCR_ENGINES: {', '.join(unknown)}")
            classes = {name: classes[name] for name in wanted}
        # Engines that are not installed stay listed (the page shows them greyed out with an install hint);
        # asking one to read raises EngineNotInstalled.
        self._classes = classes
        self._engines: dict[str, OcrEngine] = {}
        self._locks = {name: threading.Lock() for name in classes}

    @property
    def names(self) -> list[str]:
        return list(self._classes)

    @property
    def installed(self) -> list[str]:
        return [name for name, cls in self._classes.items() if cls.is_installed()]

    def default_engine(self) -> str | None:
        """The configured default when it is usable, else the first installed engine."""
        installed = self.installed
        if self.settings.default_engine in installed:
            return self.settings.default_engine
        return installed[0] if installed else None

    def describe(self) -> list[EngineInfo]:
        infos = []
        for name, cls in self._classes.items():
            engine = self._engines.get(name)
            missing = tuple(cls.missing_modules())
            infos.append(
                EngineInfo(
                    name=name,
                    title=cls.title,
                    summary=cls.summary,
                    homepage=cls.homepage,
                    installed=not missing,
                    missing=missing,
                    loaded=engine is not None,
                    device=engine.device if engine else None,
                )
            )
        return infos

    def get(self, name: str) -> OcrEngine:
        """The loaded engine called ``name``, loading it first if needed."""
        cls = self._classes.get(name)
        if cls is None:
            raise UnknownEngine(f"unknown engine {name!r}; enabled engines: {', '.join(self._classes) or 'none'}")
        if not cls.is_installed():
            raise EngineNotInstalled(
                f"engine {name!r} is not installed (missing {', '.join(cls.missing_modules())}); "
                f"install it with: pip install 'street-scene-ocr[{name}]'"
            )
        with self._locks[name]:
            engine = self._engines.get(name)
            if engine is None:
                engine = cls(self.settings)
                try:
                    engine.load()
                except Exception as exc:  # any library error while loading models
                    raise EngineError(f"could not load {name}: {exc}") from exc
                self._engines[name] = engine
        return engine

    def read(self, name: str, image: Image.Image, traditional: bool | None = None) -> OcrResult:
        """Read ``image`` with engine ``name`` and return the regions in reading order.

        ``traditional`` converts Simplified characters to Traditional; ``None`` uses the setting.
        """
        engine = self.get(name)
        resized, scale = fit_within(image, self.settings.max_image_side)
        pixels = to_array(resized)
        start = time.perf_counter()
        with self._locks[name]:
            try:
                output = engine.read(pixels)
            except Exception as exc:  # any library error while reading
                raise EngineError(f"{name} failed to read the image: {exc}") from exc
        total_ms = round((time.perf_counter() - start) * 1000, 1)
        regions = reading_order(region.scaled(scale) for region in output.regions)
        traditional = self.settings.to_traditional if traditional is None else traditional
        if traditional:
            regions = to_traditional(regions)
        return OcrResult(
            engine=name,
            device=engine.device,
            width=image.width,
            height=image.height,
            regions=regions,
            stages_ms=output.stages_ms,
            total_ms=total_ms,
            traditional=traditional,
            scale=scale,
        )
