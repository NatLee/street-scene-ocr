"""Render synthetic street signs with exact labels.

Real photos need someone to type in every sign by hand. Synthetic signs come with perfect labels
for free, so they make a good second half of the benchmark: same font for every image, but random
colours, sizes, perspective, blur, noise and JPEG compression. Everything is drawn here from
scratch (no photos), using the bundled Noto Serif CJK TC font (SIL OFL 1.1).

    python eval/make_synthetic.py            # writes eval/data/synthetic/*.jpg and labels.json

The output is deterministic for a given seed and Pillow version.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from street_scene_ocr.config import DEFAULT_FONT

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "data" / "synthetic"
CANVAS = (960, 640)

# Made-up shop signs. Many use characters whose Simplified form differs (麵 面, 雞 鸡, 豐 丰, 號 号 ...),
# which is where engines trained mostly on Simplified Chinese slip.
HORIZONTAL = [
    ["老街豆花"],
    ["阿明牛肉麵", "營業時間 10:00-21:00"],
    ["幸福早餐店"],
    ["巷口滷味", "外送專線 2345-6789"],
    ["鮮榨果汁"],
    ["豐年五金行"],
    ["請勿停車"],
    ["鹽酥雞", "宵夜場"],
    ["樂聲鐘錶眼鏡"],
    ["藝術體驗教室"],
    ["Coffee & Tea"],
    ["優質二手書"],
    ["臺灣小吃館"],
    ["第二停車場", "PARKING"],
    ["福氣便當"],
    ["冷氣維修", "安裝 保養 買賣"],
]
VERTICAL = ["中醫診所", "理髮廳", "當舖", "書法教室", "旅社", "鐵板燒"]

PALETTES = [  # (board, text)
    ((196, 30, 36), (255, 244, 214)),
    ((250, 250, 245), (22, 64, 140)),
    ((18, 92, 64), (255, 255, 255)),
    ((255, 214, 0), (30, 30, 30)),
    ((32, 32, 36), (255, 196, 0)),
    ((240, 240, 240), (200, 20, 30)),
    ((0, 90, 160), (255, 255, 255)),
    ((120, 40, 20), (250, 230, 190)),
]


@dataclass
class Sign:
    image: Image.Image  # RGBA
    lines: list[tuple[str, tuple[float, float, float, float]]]  # text, box in sign pixels


def render_sign(rng: random.Random, lines: list[str], vertical: bool) -> Sign:
    board, ink = rng.choice(PALETTES)
    size = rng.randint(54, 86)
    font = ImageFont.truetype(str(DEFAULT_FONT), size)
    small = ImageFont.truetype(str(DEFAULT_FONT), int(size * 0.5))
    pad = int(size * 0.45)

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    placed: list[tuple[str, ImageFont.FreeTypeFont, tuple[int, int]]] = []
    if vertical:
        text = lines[0]
        step = int(size * 1.08)
        width, height = size + 2 * pad, step * len(text) + 2 * pad
        for i, char in enumerate(text):
            placed.append((char, font, (pad, pad + i * step)))
        boxes = [(text, (pad, pad, pad + size, pad + step * len(text)))]
    else:
        fonts = [font] + [small] * (len(lines) - 1)
        sizes = [measure.textbbox((0, 0), t, font=f) for t, f in zip(lines, fonts, strict=True)]
        width = max(b[2] - b[0] for b in sizes) + 2 * pad
        y, boxes = pad, []
        for text, f, b in zip(lines, fonts, sizes, strict=True):
            x = (width - (b[2] - b[0])) // 2 - b[0]
            placed.append((text, f, (x, y - b[1])))
            boxes.append((text, (x + b[0], y, x + b[2], y + (b[3] - b[1]))))
            y += (b[3] - b[1]) + int(pad * 0.7)
        height = y - int(pad * 0.7) + pad

    sign = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sign)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=int(pad * 0.6), fill=board + (255,))
    border = tuple(int(c * 0.6) for c in board) + (255,)
    draw.rounded_rectangle((3, 3, width - 4, height - 4), radius=int(pad * 0.5), outline=border, width=3)
    for text, f, xy in placed:
        draw.text(xy, text, font=f, fill=ink + (255,))
    return Sign(sign, boxes)


def street_background(rng: random.Random) -> Image.Image:
    """Buildings, windows and a road in flat colours: busy enough to tempt a detector, no real text."""
    w, h = CANVAS
    top = np.array([rng.randint(150, 220), rng.randint(170, 230), rng.randint(200, 250)], dtype=float)
    bottom = top * rng.uniform(0.55, 0.8)
    t = np.linspace(0, 1, h)[:, None, None]
    sky = (top * (1 - t) + bottom * t).repeat(w, axis=1).astype(np.uint8)
    image = Image.fromarray(sky)
    draw = ImageDraw.Draw(image)
    x = -rng.randint(0, 60)
    while x < w:
        bw = rng.randint(110, 260)
        bh = rng.randint(int(h * 0.45), h)
        shade = rng.randint(70, 190)
        colour = (shade, int(shade * rng.uniform(0.85, 1.05)), int(shade * rng.uniform(0.8, 1.0)))
        draw.rectangle((x, h - bh, x + bw, h), fill=colour)
        for wy in range(h - bh + 20, h - 40, 46):
            for wx in range(x + 14, x + bw - 30, 38):
                if rng.random() < 0.8:
                    glass = rng.randint(30, 120)
                    draw.rectangle((wx, wy, wx + 22, wy + 28), fill=(glass, glass + 10, glass + 25))
        x += bw + rng.randint(-10, 20)
    draw.rectangle((0, int(h * 0.88), w, h), fill=(64, 66, 70))
    return image


def homography(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> np.ndarray:
    """The 3x3 matrix that maps the four ``src`` corners onto the four ``dst`` corners."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(src, dst, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    h = np.linalg.solve(np.array(rows, dtype=float), np.array(rhs, dtype=float))
    return np.append(h, 1).reshape(3, 3)


def apply(matrix: np.ndarray, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    for x, y in points:
        u, v, w = matrix @ np.array([x, y, 1.0])
        out.append((u / w, v / w))
    return out


def place(rng: random.Random, canvas: Image.Image, sign: Sign, area: tuple[int, int, int, int]):
    """Warp ``sign`` into a random tilted quadrilateral inside ``area`` and return its label outlines."""
    left, top, right, bottom = area
    sw, sh = sign.image.size
    scale = min((right - left) / sw, (bottom - top) / sh) * rng.uniform(0.6, 0.92)
    w, h = sw * scale, sh * scale
    x0 = rng.uniform(left, right - w)
    y0 = rng.uniform(top, bottom - h)
    jitter = 0.07
    corners = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    dst = [(x + rng.uniform(-jitter, jitter) * w, y + rng.uniform(-jitter, jitter) * h) for x, y in corners]
    src = [(0, 0), (sw, 0), (sw, sh), (0, sh)]
    to_canvas = homography(src, dst)
    to_sign = np.linalg.inv(to_canvas)
    coefficients = tuple((to_sign / to_sign[2, 2]).flatten()[:8])
    warped = sign.image.transform(canvas.size, Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC)
    canvas.alpha_composite(warped)

    labels = []
    for text, (left, top, right, bottom) in sign.lines:
        quad = apply(to_canvas, [(left, top), (right, top), (right, bottom), (left, bottom)])
        labels.append({"text": text, "polygon": [[round(x), round(y)] for x, y in quad]})
    return labels


def degrade(rng: random.Random, image: Image.Image) -> Image.Image:
    image = image.filter(ImageFilter.GaussianBlur(rng.choice([0, 0.6, 1.0, 1.5])))
    pixels = np.asarray(image, dtype=float)
    pixels = pixels * rng.uniform(0.75, 1.1) + rng.uniform(-15, 15)
    pixels += np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(2, 9), pixels.shape)
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))


def make(count: int, seed: int, out_dir: Path) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels: dict[str, list[dict]] = {}
    w, h = CANVAS
    horizontal = rng.sample(HORIZONTAL, len(HORIZONTAL))
    vertical = rng.sample(VERTICAL, len(VERTICAL))
    for index in range(count):
        canvas = street_background(rng).convert("RGBA")
        boxes: list[dict] = []
        if index % 3 == 2:  # every third image: a vertical sign next to a horizontal one
            v = render_sign(rng, [vertical[index // 3 % len(vertical)]], vertical=True)
            boxes += place(rng, canvas, v, (20, 20, int(w * 0.32), h - 20))
            s = render_sign(rng, horizontal[index % len(horizontal)], vertical=False)
            boxes += place(rng, canvas, s, (int(w * 0.36), 40, w - 20, h - 40))
        else:
            s = render_sign(rng, horizontal[index % len(horizontal)], vertical=False)
            boxes += place(rng, canvas, s, (30, 30, w - 30, h - 30))
        name = f"sign-{index:02d}.jpg"
        degrade(rng, canvas.convert("RGB")).save(out_dir / name, quality=rng.randint(55, 85))
        labels[name] = boxes
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=24, help="number of images (default 24)")
    parser.add_argument("--seed", type=int, default=2021, help="random seed (default 2021)")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help=f"output folder (default {OUT_DIR})")
    args = parser.parse_args()
    labels = make(args.count, args.seed, args.out)
    (args.out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(labels)} images and labels.json to {args.out}")


if __name__ == "__main__":
    main()
