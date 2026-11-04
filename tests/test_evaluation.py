import pytest

from street_scene_ocr.engines.base import TextRegion
from street_scene_ocr.evaluation import LabelLine, edit_distance, normalize, score_image, summarize

from .conftest import box


def label(text, left, top, right, bottom):
    return LabelLine.from_dict({"text": text, "box": [left, top, right, bottom]})


@pytest.mark.parametrize(
    ("a", "b", "distance"),
    [("", "", 0), ("水果行", "水果行", 0), ("水果行", "水菓行", 1), ("水果行", "", 3), ("鍋貼", "水餃鍋貼", 2)],
)
def test_edit_distance(a, b, distance):
    assert edit_distance(a, b) == distance
    assert edit_distance(b, a) == distance


def test_normalize_ignores_width_case_spaces_and_punctuation():
    assert normalize("外送專線： 2705-3788") == normalize("外送專線2705 3788") == "外送專線27053788"
    assert normalize("ＣＲＹＳＴＡＬ Art") == "crystalart"
    assert normalize("【鹹米糕 20】") == "鹹米糕20"
    assert normalize("精品·服飾·造型") == "精品服飾造型"


def test_split_line_is_joined_back_in_reading_direction():
    labels = [label("巴哈音樂中心", 0, 0, 30, 200)]  # tall box: vertical line
    regions = [TextRegion("中心", 0.9, box(5, 120, 25, 190)), TextRegion("巴哈音樂", 0.9, box(5, 5, 25, 110))]
    (line,) = score_image(regions, labels).lines
    assert line.read == "巴哈音樂中心"
    assert line.errors == 0


def test_missed_lines_count_fully_and_extras_do_not():
    labels = [label("安和", 0, 0, 100, 40), label("水果行", 0, 50, 100, 90)]
    regions = [TextRegion("安禾", 0.9, box(5, 5, 95, 35)), TextRegion("CRYSTAL", 0.9, box(300, 300, 400, 330))]
    score = score_image(regions, labels)
    assert [(line.read, line.errors) for line in score.lines] == [("安禾", 1), ("", 3)]
    assert score.extra_regions == 1
    summary = summarize([score])
    assert (summary.errors, summary.characters) == (4, 5)
    assert summary.cer == pytest.approx(0.8)
    assert summary.line_accuracy == 0.0


def test_region_goes_to_the_smallest_label_that_contains_it():
    labels = [label("整塊招牌", 0, 0, 200, 200), label("小字", 10, 10, 60, 40)]
    score = score_image([TextRegion("小字", 0.9, box(15, 15, 55, 35))], labels)
    assert [line.read for line in score.lines] == ["", "小字"]


def test_tilted_polygon_labels_separate_slanted_lines():
    # Two lines rising to the right; their axis-aligned boxes would overlap, their outlines do not.
    upper = LabelLine.from_dict({"text": "上", "polygon": [[0, 60], [100, 0], [110, 20], [10, 80]]})
    lower = LabelLine.from_dict({"text": "下", "polygon": [[10, 90], [110, 30], [120, 50], [20, 110]]})
    assert upper.contains((55, 40)) and not lower.contains((55, 40))
    assert lower.contains((65, 70)) and not upper.contains((65, 70))
    assert upper.area == pytest.approx(2600)


def test_ignored_labels_swallow_regions_without_scoring_them():
    labels = [label("###", 0, 0, 100, 100), label("好", 200, 0, 300, 100)]
    score = score_image([TextRegion("??", 0.9, box(10, 10, 90, 90))], labels)
    assert [line.expected for line in score.lines] == ["好"]
    assert score.extra_regions == 0


def test_vertical_follows_the_outline_not_the_text():
    assert label("直", 0, 0, 30, 100).vertical
    assert not label("橫", 0, 0, 100, 30).vertical


def test_empty_summary_is_zero_not_an_error():
    assert summarize([]).cer == 0.0
