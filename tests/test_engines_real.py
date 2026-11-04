"""Smoke test with the real engines and models. Runs in the Docker CI job: ``pytest -m engines``."""

import json
from pathlib import Path

import pytest
from PIL import Image

from street_scene_ocr.config import Settings
from street_scene_ocr.engines import ENGINE_CLASSES
from street_scene_ocr.evaluation import LabelLine, score_image, summarize
from street_scene_ocr.postprocess import is_confident
from street_scene_ocr.service import EngineManager

SYNTHETIC = Path(__file__).parents[1] / "eval" / "data" / "synthetic"
# Plain horizontal signs that every engine reads correctly in eval/results/results.md.
EASY_SIGNS = ["sign-00.jpg", "sign-04.jpg"]

pytestmark = pytest.mark.engines


@pytest.fixture(scope="module")
def manager():
    return EngineManager(Settings.from_env())


@pytest.mark.parametrize("engine", [cls.name for cls in ENGINE_CLASSES])
def test_engine_reads_easy_synthetic_signs(manager, engine):
    if engine not in manager.installed:
        pytest.skip(f"{engine} is not installed in this environment")
    labels = json.loads((SYNTHETIC / "labels.json").read_text(encoding="utf-8"))
    scores = []
    for name in EASY_SIGNS:
        result = manager.read(engine, Image.open(SYNTHETIC / name))
        kept = [r for r in result.regions if is_confident(r, manager.settings.min_confidence)]
        scores.append(score_image(kept, [LabelLine.from_dict(line) for line in labels[name]]))
        assert result.stages_ms or result.total_ms > 0
    assert summarize(scores).cer <= 0.2
