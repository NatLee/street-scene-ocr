import os
import re
from pathlib import Path

import pytest

from street_scene_ocr.config import DEFAULT_ENGINE, Settings, SettingsError
from street_scene_ocr.engines import ENGINE_CLASSES
from street_scene_ocr.service import EngineManager, EngineNotInstalled, UnknownEngine

from .conftest import FakeEngine, MissingEngine


def test_defaults_keep_2021_behaviour():
    s = Settings.from_env({})
    assert (s.default_engine, s.min_confidence, s.max_upload_mb, s.device) == ("easyocr", 0.3, 16, "cpu")
    assert s.allowed_extensions == ("png", "jpg", "jpeg")
    assert s.model_dir is None and s.model_dir_for("easyocr") is None


def test_env_overrides():
    s = Settings.from_env(
        {
            "OCR_ENGINES": "rapidocr, paddleocr",
            "OCR_DEFAULT_ENGINE": "rapidocr",
            "OCR_DEVICE": "CUDA",
            "OCR_MIN_CONFIDENCE": "0.5",
            "OCR_MODEL_DIR": "/models",
            "OCR_PORT": "9000",
        }
    )
    assert s.enabled_engines == ("rapidocr", "paddleocr")
    assert (s.default_engine, s.device, s.min_confidence, s.port) == ("rapidocr", "cuda", 0.5, 9000)
    assert s.model_dir_for("rapidocr") == Path("/models/rapidocr")


@pytest.mark.parametrize(
    "env",
    [{"OCR_DEVICE": "tpu"}, {"OCR_MIN_CONFIDENCE": "1.5"}, {"OCR_PORT": "eighty"}, {"OCR_MAX_UPLOAD_MB": "0"}],
)
def test_bad_env_values_are_reported(env):
    with pytest.raises(SettingsError):
        Settings.from_env(env)


def test_registry_names_are_unique_and_match_pip_extras():
    names = [cls.name for cls in ENGINE_CLASSES]
    assert names == ["easyocr", "rapidocr", "paddleocr"]
    assert DEFAULT_ENGINE in names
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    for name in names:
        assert f"\n{name} = [" in pyproject, f"pyproject.toml has no [{name}] extra"


def test_unknown_engine_in_settings_fails_early():
    with pytest.raises(UnknownEngine):
        EngineManager(Settings(enabled_engines=("fake", "typo")), engine_classes=(FakeEngine,))


def test_without_explicit_list_every_engine_is_listed_but_only_installed_ones_read():
    manager = EngineManager(Settings(default_engine="fake"), engine_classes=(FakeEngine, MissingEngine))
    assert manager.names == ["fake", "missing"]
    assert manager.installed == ["fake"]
    with pytest.raises(EngineNotInstalled, match=re.escape("pip install 'street-scene-ocr[missing]'")):
        manager.get("missing")


def test_default_falls_back_to_first_installed_engine():
    manager = EngineManager(Settings(default_engine="easyocr"), engine_classes=(MissingEngine, FakeEngine))
    assert manager.default_engine() == "fake"


def test_engines_load_once(manager):
    first = manager.get("fake")
    assert manager.get("fake") is first
    assert manager.describe()[0].loaded


def test_threads_default_to_available_cpus_and_can_be_set():
    from street_scene_ocr.config import available_cpus

    assert 1 <= available_cpus() <= (os.cpu_count() or 1)
    assert Settings.from_env({}).threads == available_cpus()
    assert Settings.from_env({"OCR_THREADS": "3"}).threads == 3
    with pytest.raises(SettingsError):
        Settings.from_env({"OCR_THREADS": "0"})


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"cpu.max": "400000 100000\n"}, 4.0),
        ({"cpu.max": "max 100000\n"}, None),
        ({"quota": "150000\n", "period": "100000\n"}, 1.5),
        ({"quota": "-1\n", "period": "100000\n"}, None),
        ({}, None),
    ],
)
def test_cgroup_cpu_quota_reads_v2_and_v1_layouts(tmp_path, files, expected):
    from street_scene_ocr.config import cgroup_cpu_quota

    for name, text in files.items():
        (tmp_path / name).write_text(text)
    sources = ((tmp_path / "cpu.max",), (tmp_path / "quota", tmp_path / "period"))
    assert cgroup_cpu_quota(sources) == expected


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("1", True), ("off", False), ("", False)])
def test_to_traditional_setting(raw, expected):
    assert Settings.from_env({"OCR_TO_TRADITIONAL": raw}).to_traditional is expected


def test_to_traditional_setting_rejects_garbage():
    with pytest.raises(SettingsError):
        Settings.from_env({"OCR_TO_TRADITIONAL": "maybe"})
