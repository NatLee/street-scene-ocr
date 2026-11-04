"""Post-processing: what happens after the engine has read the image.

Engines return text regions in whatever order their detector found them, with every guess they
made. Small, engine-independent steps make that usable:

1. **Confidence threshold.** A region counts as "confident" when the engine's score is above the
   threshold. Nothing is thrown away here; the API and the drawing show both groups so you can see
   what a threshold would cost you.
2. **Reading order.** Regions are grouped into rows (top to bottom) and each row is read left to
   right, which is how a person scans a street.
3. **Script conversion (optional, off by default).** Models that read Simplified and Traditional
   Chinese with one network sometimes answer with the Simplified form of a character (贺 for 賀).
   OpenCC can turn those back; it also changes a few characters that were right (台 becomes 臺), so
   the benchmark measures both effects.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from functools import lru_cache

from .engines.base import TextRegion

# OpenCC conversion: Simplified to Traditional with the character forms standard in Taiwan. "s2tw" works
# character by character; "s2twp" would also swap whole words (软件 to 軟體), which OCR must never do.
OPENCC_CONFIG = "s2tw"


def is_confident(region: TextRegion, threshold: float) -> bool:
    """The 2021 rule: strictly above the threshold counts as confident."""
    return region.confidence > threshold


def reading_order(regions: Iterable[TextRegion], row_overlap: float = 0.5) -> list[TextRegion]:
    """Sort regions into rows from top to bottom, then left to right inside each row.

    A region joins the current row when at least ``row_overlap`` of the shorter of the two heights
    overlaps vertically with the row; otherwise it starts a new row. Tall vertical signs end up as
    their own row, which is what you want for a sign written top to bottom.
    """
    rows: list[list[TextRegion]] = []
    row_spans: list[tuple[float, float]] = []
    for region in sorted(regions, key=lambda r: (r.bbox[1], r.bbox[0])):
        _, top, _, bottom = region.bbox
        for index, (row_top, row_bottom) in enumerate(row_spans):
            overlap = min(bottom, row_bottom) - max(top, row_top)
            shorter = min(bottom - top, row_bottom - row_top)
            if shorter > 0 and overlap / shorter >= row_overlap:
                rows[index].append(region)
                row_spans[index] = (min(top, row_top), max(bottom, row_bottom))
                break
        else:
            rows.append([region])
            row_spans.append((top, bottom))
    ordered_rows = sorted(zip(row_spans, rows, strict=True), key=lambda item: item[0][0])
    return [region for _, row in ordered_rows for region in sorted(row, key=lambda r: r.bbox[0])]


@lru_cache(maxsize=1)
def _opencc():
    import opencc

    return opencc.OpenCC(OPENCC_CONFIG)


def to_traditional(regions: Iterable[TextRegion]) -> list[TextRegion]:
    """Convert Simplified Chinese characters in every region to Traditional (Taiwan standard)."""
    convert = _opencc().convert
    return [replace(region, text=convert(region.text)) for region in regions]
