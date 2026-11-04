"""Scoring OCR output against hand-checked labels.

The score is the **character error rate (CER)**: how many characters you would have to insert,
delete or replace to turn what the engine read into the right text, divided by the number of
characters in the right text. 0 % is perfect, 100 % is as bad as reading nothing, and it can go
above 100 % when an engine adds characters that are not there.

How engine output is matched to the labels:

* Every label is an outline (a box or a polygon) around one line of text, plus the text in it.
* An engine region belongs to the label whose outline contains the centre of the region (the
  smallest one if several do). Engines often split a line into pieces; the pieces are joined back
  together in reading direction before comparing.
* A label with no region inside it counts as every character missed.
* Regions outside every label are counted as "extra" but do not change the CER: photos have small
  print nobody labelled, and reading it is not a mistake.
* A label whose text is ``###`` marks text too small or unclear to grade. Regions inside it are
  ignored entirely (the convention of the ICDAR scene-text benchmarks).
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .engines.base import Point, TextRegion

IGNORE = "###"
# A label at least this many times taller than wide is a vertical line, read top to bottom.
VERTICAL_ASPECT = 1.5


def normalize(text: str) -> str:
    """Compare text the way a reader would: ignore spaces, punctuation, letter case and full/half width."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in text if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance: the fewest single-character edits that turn ``a`` into ``b``."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class LabelLine:
    text: str
    polygon: tuple[Point, ...]

    @classmethod
    def from_dict(cls, data: Mapping) -> LabelLine:
        """Accept ``{"text", "box": [left, top, right, bottom]}`` or ``{"text", "polygon": [[x, y], ...]}``."""
        if "box" in data:
            left, top, right, bottom = data["box"]
            points = [(left, top), (right, top), (right, bottom), (left, bottom)]
        else:
            points = data["polygon"]
        return cls(str(data["text"]), tuple((float(x), float(y)) for x, y in points))

    @property
    def ignored(self) -> bool:
        return self.text == IGNORE

    @property
    def vertical(self) -> bool:
        p = self.polygon
        if len(p) == 4:  # corners clockwise from top-left: compare the side lengths
            width = (math.dist(p[0], p[1]) + math.dist(p[3], p[2])) / 2
            height = (math.dist(p[1], p[2]) + math.dist(p[0], p[3])) / 2
        else:
            xs, ys = [q[0] for q in p], [q[1] for q in p]
            width, height = max(xs) - min(xs), max(ys) - min(ys)
        return height > VERTICAL_ASPECT * width

    @property
    def area(self) -> float:
        p = self.polygon
        return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2

    def contains(self, point: Point) -> bool:
        """Ray casting: count how often a ray to the right crosses the outline."""
        x, y = point
        inside = False
        p = self.polygon
        for (x1, y1), (x2, y2) in zip(p, p[1:] + p[:1], strict=True):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        return inside


@dataclass(frozen=True)
class LineScore:
    expected: str
    read: str
    errors: int
    characters: int


@dataclass(frozen=True)
class ImageScore:
    lines: list[LineScore]
    extra_regions: int

    @property
    def errors(self) -> int:
        return sum(line.errors for line in self.lines)

    @property
    def characters(self) -> int:
        return sum(line.characters for line in self.lines)


def score_image(regions: Iterable[TextRegion], labels: Sequence[LabelLine]) -> ImageScore:
    assigned: list[list[TextRegion]] = [[] for _ in labels]
    extra = 0
    for region in regions:
        owners = [i for i, label in enumerate(labels) if label.contains(region.center)]
        if not owners:
            extra += 1
            continue
        assigned[min(owners, key=lambda i: labels[i].area)].append(region)

    lines = []
    for label, found in zip(labels, assigned, strict=True):
        if label.ignored:
            continue
        axis = 1 if label.vertical else 0
        read = "".join(r.text for r in sorted(found, key=lambda r: r.center[axis]))
        expected = normalize(label.text)
        lines.append(LineScore(label.text, read, edit_distance(expected, normalize(read)), len(expected)))
    return ImageScore(lines, extra)


@dataclass(frozen=True)
class Summary:
    images: int
    lines: int
    characters: int
    errors: int
    exact_lines: int
    extra_regions: int

    @property
    def cer(self) -> float:
        return self.errors / self.characters if self.characters else 0.0

    @property
    def line_accuracy(self) -> float:
        return self.exact_lines / self.lines if self.lines else 0.0


def summarize(scores: Iterable[ImageScore]) -> Summary:
    scores = list(scores)
    lines = [line for score in scores for line in score.lines]
    return Summary(
        images=len(scores),
        lines=len(lines),
        characters=sum(line.characters for line in lines),
        errors=sum(line.errors for line in lines),
        exact_lines=sum(1 for line in lines if line.errors == 0),
        extra_regions=sum(score.extra_regions for score in scores),
    )
