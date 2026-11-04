from PIL import Image

from street_scene_ocr.config import DEFAULT_FONT
from street_scene_ocr.engines.base import TextRegion
from street_scene_ocr.render import CONFIDENT_COLOUR, UNSURE_COLOUR, annotate, label_for

from .conftest import box

GREY = (128, 128, 128)


def test_label_format_matches_2021():
    assert label_for(TextRegion("水果行", 0.98765, box(0, 0, 1, 1))) == "水果行 98.77%"


def test_confident_regions_green_unsure_red():
    image = Image.new("RGB", (300, 200), GREY)
    regions = [TextRegion("好", 0.9, box(10, 10, 100, 60)), TextRegion("壞", 0.1, box(150, 10, 250, 60))]
    drawn = annotate(image, regions, 0.3, DEFAULT_FONT)
    assert drawn.size == image.size and drawn.mode == "RGB"
    assert drawn.getpixel((55, 10)) == CONFIDENT_COLOUR  # top edge of the first box
    assert drawn.getpixel((200, 10)) == UNSURE_COLOUR
    assert image.getpixel((55, 10)) == GREY  # the input is not modified


def test_unsure_regions_can_be_hidden():
    image = Image.new("RGB", (300, 200), GREY)
    drawn = annotate(image, [TextRegion("壞", 0.1, box(150, 10, 250, 60))], 0.3, DEFAULT_FONT, show_unsure=False)
    assert drawn.getcolors() == [(300 * 200, GREY)]
