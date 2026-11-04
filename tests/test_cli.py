import json

import pytest
from PIL import Image

from street_scene_ocr import __main__ as cli
from street_scene_ocr.service import EngineManager

from .conftest import FakeEngine


@pytest.fixture
def fake_engines(monkeypatch):
    monkeypatch.setattr(cli, "EngineManager", lambda settings: EngineManager(settings, engine_classes=(FakeEngine,)))
    monkeypatch.setenv("OCR_DEFAULT_ENGINE", "fake")


def test_read_prints_json_and_writes_annotated_image(fake_engines, tmp_path, capsys):
    image = tmp_path / "sign.png"
    Image.new("RGB", (200, 100), "white").save(image)
    out = tmp_path / "out.png"
    assert cli.main(["read", str(image), "--annotated", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["engine"] == "fake"
    assert [(r["text"], r["confident"]) for r in report["regions"]] == [("安和", False), ("水果行", True)]
    assert Image.open(out).size == (200, 100)


def test_warmup_loads_installed_engines(fake_engines, capsys):
    assert cli.main(["warmup"]) == 0
    assert "fake ready on cpu" in capsys.readouterr().err


def test_help_mentions_every_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    text = capsys.readouterr().out
    for command in ("serve", "read", "warmup"):
        assert command in text


def test_bad_setting_exits_with_code_2(monkeypatch, capsys):
    monkeypatch.setenv("OCR_DEVICE", "tpu")
    assert cli.main(["read", "x.png"]) == 2
    assert "device must be one of" in capsys.readouterr().err


def test_missing_image_is_a_clear_error(fake_engines, tmp_path, capsys):
    assert cli.main(["read", str(tmp_path / "nope.png")]) == 1
    assert "cannot read the image" in capsys.readouterr().err
