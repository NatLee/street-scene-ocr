from street_scene_ocr.engines.base import TextRegion
from street_scene_ocr.postprocess import is_confident, reading_order

from .conftest import box


def region(text, left, top, right, bottom, confidence=0.9):
    return TextRegion(text, confidence, box(left, top, right, bottom))


def test_threshold_is_strictly_above_like_2021():
    assert is_confident(region("a", 0, 0, 1, 1, 0.31), 0.3)
    assert not is_confident(region("a", 0, 0, 1, 1, 0.30), 0.3)


def test_reading_order_rows_then_left_to_right():
    shuffled = [
        region("C", 10, 60, 50, 90),
        region("B", 120, 12, 160, 38),  # slightly lower than A but on the same row
        region("A", 10, 10, 50, 40),
        region("D", 100, 58, 150, 92),
    ]
    assert [r.text for r in reading_order(shuffled)] == ["A", "B", "C", "D"]


def test_lines_beside_a_tall_vertical_sign_are_read_left_to_right():
    # The vertical sign overlaps both lines next to it, so all three share one row.
    regions = [region("right", 140, 170, 220, 200), region("V", 0, 0, 20, 200), region("left", 40, 0, 120, 30)]
    assert [r.text for r in reading_order(regions)] == ["V", "left", "right"]


def test_bbox_center_and_scaling():
    r = TextRegion.from_points("x", 0.5, [(10, 20), (30, 22), (31, 40), (9, 38)])
    assert r.bbox == (9, 20, 31, 40)
    assert r.center == (20, 30)
    assert r.scaled(2).bbox == (18, 40, 62, 80)
    assert r.scaled(1) is r


def test_from_points_rejects_degenerate_polygons():
    import pytest

    with pytest.raises(ValueError):
        TextRegion.from_points("x", 0.5, [(0, 0), (1, 1)])


def test_to_traditional_fixes_simplified_forms_and_keeps_the_rest():
    from street_scene_ocr.postprocess import to_traditional

    regions = [
        region("贺茶堂", 0, 0, 1, 1),
        region("天然手工凉麵", 0, 0, 1, 1),
        region("水果行 OPEN 2705-3788", 0, 0, 1, 1),
    ]
    assert [r.text for r in to_traditional(regions)] == ["賀茶堂", "天然手工涼麵", "水果行 OPEN 2705-3788"]
    assert to_traditional(regions)[0].polygon == regions[0].polygon


def test_to_traditional_also_changes_some_correct_characters():
    # The trade-off the benchmark measures: 台 is standard Traditional too, but s2tw prefers 臺.
    from street_scene_ocr.postprocess import to_traditional

    assert to_traditional([region("台灣代駕", 0, 0, 1, 1)])[0].text == "臺灣代駕"
