"""Runtime settings.

Every knob lives here and is read from environment variables once, so the rest of the code never
reaches for ``os.environ`` itself. The defaults keep the 2021 behaviour unless noted.
"""

from __future__ import annotations

import contextlib
import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"
DEFAULT_FONT = PACKAGE_DIR / "fonts" / "NotoSerifCJKtc-Bold.otf"

# The 2021 upload form accepted these extensions and nothing else, up to 16 MB.
ALLOWED_EXTENSIONS = ("png", "jpg", "jpeg")
DEFAULT_MAX_UPLOAD_MB = 16

# The 2021 page painted a box green when the engine was more than 30 % sure about it.
DEFAULT_MIN_CONFIDENCE = 0.3

# The 2021 engine. Still the default so the upload page behaves like it used to.
DEFAULT_ENGINE = "easyocr"

# Big phone photos are scaled down before OCR and the boxes are scaled back up afterwards.
# 2560 is EasyOCR's own default canvas size, so the original engine sees the same pixels as in 2021.
DEFAULT_MAX_IMAGE_SIDE = 2560

DEVICES = ("cpu", "cuda", "auto")

ENV_PREFIX = "OCR_"
TRUE_WORDS = ("1", "true", "yes", "on")
FALSE_WORDS = ("0", "false", "no", "off")


def available_cpus() -> int:
    """CPUs this process may really use: the container's CPU limit and pinning, not the host's core count.

    Inference libraries start one thread per core they see. In a container limited to 4 of 32 cores,
    32 threads fight over 4 cores and every image takes several times longer, so the engines are told
    this number instead (see OCR_THREADS).
    """
    count = os.cpu_count() or 1
    with contextlib.suppress(AttributeError, OSError):  # pinning, e.g. docker run --cpuset-cpus
        count = min(count, len(os.sched_getaffinity(0)))
    quota = cgroup_cpu_quota()  # limit, e.g. docker run --cpus
    if quota is not None:
        count = min(count, max(1, math.ceil(quota)))
    return count


# Where Linux control groups publish a container's CPU limit: cgroup v2 keeps "<quota> <period>" in one
# file ("max" when unlimited), cgroup v1 (still used by some Docker Desktop set-ups) in two (-1 = unlimited).
CGROUP_CPU_LIMIT_FILES = (
    (Path("/sys/fs/cgroup/cpu.max"),),
    (Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"), Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")),
)


def cgroup_cpu_quota(sources=CGROUP_CPU_LIMIT_FILES) -> float | None:
    """How many CPUs the container may use, or ``None`` when there is no limit (or no cgroup at all)."""
    for files in sources:
        try:
            quota, period = " ".join(f.read_text() for f in files).split()
        except (OSError, ValueError):
            continue
        if quota in ("max", "-1"):
            return None
        return int(quota) / int(period)
    return None


class SettingsError(ValueError):
    """An environment variable has a value we cannot use."""


@dataclass(frozen=True)
class Settings:
    default_engine: str = DEFAULT_ENGINE
    # ``None`` means "every engine whose Python package is installed".
    enabled_engines: tuple[str, ...] | None = None
    device: str = "cpu"
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    max_image_side: int = DEFAULT_MAX_IMAGE_SIDE
    # ``None`` lets each library use its own cache folder (usually under the home directory).
    model_dir: Path | None = None
    font_path: Path = DEFAULT_FONT
    # Convert Simplified characters in the results to Traditional (OpenCC s2tw). Off, as in 2021.
    to_traditional: bool = False
    # Threads each engine may use for one image; defaults to the CPUs available to this process.
    threads: int = field(default_factory=available_cpus)
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_extensions: tuple[str, ...] = field(default=ALLOWED_EXTENSIONS)

    def __post_init__(self) -> None:
        if self.device not in DEVICES:
            raise SettingsError(f"device must be one of {', '.join(DEVICES)}, got {self.device!r}")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise SettingsError(f"min_confidence must be between 0 and 1, got {self.min_confidence}")
        if self.max_upload_mb <= 0 or self.max_image_side <= 0 or self.threads <= 0:
            raise SettingsError("max_upload_mb, max_image_side and threads must be positive")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def model_dir_for(self, engine: str) -> Path | None:
        """Folder for one engine's model files, or ``None`` to keep the library default."""
        return None if self.model_dir is None else self.model_dir / engine

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``OCR_*`` environment variables; unset ones keep their defaults."""
        env = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = env.get(ENV_PREFIX + name, "").strip()
            return value or None

        def number(name: str, kind: type, default):
            raw = get(name)
            if raw is None:
                return default
            try:
                return kind(raw)
            except ValueError as exc:
                raise SettingsError(f"{ENV_PREFIX}{name} must be a {kind.__name__}, got {raw!r}") from exc

        def flag(name: str) -> bool:
            raw = (get(name) or "false").lower()
            if raw not in TRUE_WORDS + FALSE_WORDS:
                raise SettingsError(f"{ENV_PREFIX}{name} must be true or false, got {raw!r}")
            return raw in TRUE_WORDS

        engines = get("ENGINES")
        model_dir = get("MODEL_DIR")
        font = get("FONT_PATH")
        return cls(
            default_engine=get("DEFAULT_ENGINE") or DEFAULT_ENGINE,
            enabled_engines=tuple(e.strip() for e in engines.split(",") if e.strip()) if engines else None,
            device=(get("DEVICE") or "cpu").lower(),
            min_confidence=number("MIN_CONFIDENCE", float, DEFAULT_MIN_CONFIDENCE),
            max_upload_mb=number("MAX_UPLOAD_MB", int, DEFAULT_MAX_UPLOAD_MB),
            max_image_side=number("MAX_IMAGE_SIDE", int, DEFAULT_MAX_IMAGE_SIDE),
            model_dir=Path(model_dir) if model_dir else None,
            font_path=Path(font) if font else DEFAULT_FONT,
            threads=number("THREADS", int, available_cpus()),
            to_traditional=flag("TO_TRADITIONAL"),
            host=get("HOST") or "0.0.0.0",
            port=number("PORT", int, 8000),
        )
