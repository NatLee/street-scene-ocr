"""Draw the label outlines on the benchmark images, to check or edit labels.json by eye.

    python eval/draw_labels.py photos /tmp/labels     # one PNG per photo in /tmp/labels

Graded lines are outlined in cyan with their text; ``###`` (ignored) areas in grey.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from street_scene_ocr.config import DEFAULT_FONT
from street_scene_ocr.evaluation import LabelLine

HERE = Path(__file__).resolve().parent
GRADED = (0, 220, 255)
IGNORED = (160, 160, 160)


def draw(folder: Path, out: Path) -> None:
    labels = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(DEFAULT_FONT), 18)
    for name, lines in labels.items():
        image = Image.open(folder / name).convert("RGB")
        canvas = ImageDraw.Draw(image)
        for line in map(LabelLine.from_dict, lines):
            colour = IGNORED if line.ignored else GRADED
            points = list(line.polygon)
            canvas.line(points + points[:1], fill=colour, width=2)
            if not line.ignored:
                x, y = min(p[0] for p in points), max(p[1] for p in points)
                box = canvas.textbbox((x, y + 2), line.text, font=font)
                canvas.rectangle(box, fill=(0, 0, 0))
                canvas.text((x, y + 2), line.text, font=font, fill=colour)
        image.save(out / f"{Path(name).stem}.png")
        print(out / f"{Path(name).stem}.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("set", choices=["photos", "synthetic"])
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    draw(HERE / "data" / args.set, args.out)


if __name__ == "__main__":
    main()
