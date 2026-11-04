"""Re-create the figures in docs/images/ from the real models.

Run it inside the Docker image, which has all three engines and their models:

    docker run --rm -v street-scene-ocr_models:/models -v "$PWD:/src" -w /src street-scene-ocr:local \
        python docs/figures.py

Every picture in docs/pipeline.md comes from here, drawn from one of the CC0 benchmark photos.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from street_scene_ocr.config import DEFAULT_FONT, DEFAULT_MIN_CONFIDENCE, Settings
from street_scene_ocr.evaluation import LabelLine, score_image
from street_scene_ocr.postprocess import is_confident
from street_scene_ocr.render import annotate
from street_scene_ocr.service import EngineManager

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
PHOTO = ROOT / "eval" / "data" / "photos" / "noodle-shop-21.jpg"
ENGINES = ("easyocr", "rapidocr", "paddleocr")
JPEG = {"quality": 82, "optimize": True}
# Labelled lines of PHOTO shown in the recognition table: big and small, vertical, mixed scripts.
RECOGNITION_EXAMPLES = {"21工房", "天然手工涼麵", "敦美苑", "自家製の天然好麵", "HAND-MADE CHILLED NOODLES", "鐵道模型"}


def heat(values: np.ndarray) -> np.ndarray:
    """Map 0..1 to a dark-blue -> teal -> yellow ramp (readable for colour-blind readers)."""
    stops = np.array([[13, 8, 135], [20, 120, 140], [70, 190, 110], [250, 230, 40]], dtype=float)
    position = np.clip(values, 0, 1) * (len(stops) - 1)
    low = np.floor(position).astype(int).clip(0, len(stops) - 2)
    t = (position - low)[..., None]
    return (stops[low] * (1 - t) + stops[low + 1] * t).astype(np.uint8)


def blend(photo: Image.Image, values: np.ndarray, alpha: float = 0.65) -> Image.Image:
    overlay = Image.fromarray(heat(values)).resize(photo.size, Image.Resampling.BILINEAR)
    return Image.blend(photo.convert("RGB"), overlay, alpha)


def caption(image: Image.Image, text: str) -> Image.Image:
    font = ImageFont.truetype(str(DEFAULT_FONT), max(18, image.width // 34))
    bar = font.size + 16
    out = Image.new("RGB", (image.width, image.height + bar), (24, 28, 34))
    out.paste(image, (0, bar))
    ImageDraw.Draw(out).text((10, 7), text, font=font, fill=(240, 240, 240))
    return out


def craft_maps(manager: EngineManager, photo: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    """CRAFT's two outputs for the photo: character centres and the links between characters."""
    import torch
    from easyocr.imgproc import normalizeMeanVariance, resize_aspect_ratio

    reader = manager.get("easyocr")._reader
    resized, _, _ = resize_aspect_ratio(np.asarray(photo), 2560, interpolation=1, mag_ratio=1.0)
    batch = torch.from_numpy(normalizeMeanVariance(resized)).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        maps, _ = reader.detector(batch.to(next(reader.detector.parameters()).device))
    maps = maps[0].cpu().numpy()
    return maps[:, :, 0], maps[:, :, 1]


def db_map(photo: Image.Image) -> np.ndarray:
    """The PP-OCRv6 detector's probability map, straight from its ONNX file (the "DB" approach)."""
    import onnxruntime
    import rapidocr

    # RapidOCR ships its default ONNX models inside the package.
    model = next((Path(rapidocr.__file__).parent / "models").glob("*det*.onnx"))
    session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    # Same preparation as the engine: shorter side 736 px, both sides a multiple of 32, scaled to -1..1.
    ratio = 736 / min(photo.size)
    size = tuple(max(32, round(side * ratio / 32) * 32) for side in photo.size)
    pixels = np.asarray(photo.resize(size, Image.Resampling.BILINEAR), dtype=np.float32)[:, :, ::-1]
    batch = ((pixels / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None]
    (probability,) = session.run(None, {session.get_inputs()[0].name: batch})
    return probability[0, 0]


EXPECTED, RIGHT, WRONG = (15, 118, 110), (29, 35, 43), (194, 65, 12)


def fit(draw: ImageDraw.ImageDraw, text: str, width: int, size: int) -> ImageFont.FreeTypeFont:
    """The largest font size, at most ``size``, at which ``text`` fits in ``width`` pixels."""
    while size > 10:
        font = ImageFont.truetype(str(DEFAULT_FONT), size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 1
    return ImageFont.truetype(str(DEFAULT_FONT), size)


def recognition_table(results: dict, photo: Image.Image, labels: list[LabelLine], picks: set[str]) -> Image.Image:
    """Crops of a few labelled text lines, the right answer, and what each engine read in them."""
    # Score against every label of the photo, so each region goes to the line it belongs to.
    graded = [label for label in labels if not label.ignored]
    read = {
        name: score_image([r for r in result.regions if is_confident(r, DEFAULT_MIN_CONFIDENCE)], labels).lines
        for name, result in results.items()
    }
    rows, seen = [], set()
    for i, label in enumerate(graded):
        if label.text in picks and label.text not in seen:
            rows.append((i, label))
            seen.add(label.text)
    font = ImageFont.truetype(str(DEFAULT_FONT), 24)
    small = ImageFont.truetype(str(DEFAULT_FONT), 19)
    columns = ["expected", *ENGINES]
    crop_w, row_h, col_w = 230, 92, 255
    width = crop_w + col_w * len(columns) + 30
    sheet = Image.new("RGB", (width, 46 + row_h * len(rows)), (250, 248, 243))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(columns):
        draw.text((crop_w + 20 + i * col_w, 12), name, font=small, fill=(90, 98, 110))
    for row, (index, label) in enumerate(rows):
        top = 46 + row * row_h
        xs, ys = [p[0] for p in label.polygon], [p[1] for p in label.polygon]
        crop = photo.crop((int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
        crop.thumbnail((crop_w - 10, row_h - 12))
        sheet.paste(crop, (10, top + (row_h - crop.height) // 2))
        cells = [(label.text, EXPECTED)]
        for name in ENGINES:
            line = read[name][index]
            mark = "✓" if line.errors == 0 else f"×{line.errors}"
            cells.append((f"{line.read or '—'} {mark}", RIGHT if line.errors == 0 else WRONG))
        for i, (text, colour) in enumerate(cells):
            fitted = fit(draw, text, col_w - 14, font.size)
            y = top + (row_h - fitted.size) // 2 - 2
            draw.text((crop_w + 20 + i * col_w, y), text, font=fitted, fill=colour)
        draw.line((10, top + row_h - 1, width - 10, top + row_h - 1), fill=(220, 213, 199))
    return sheet


def main() -> None:
    settings = Settings.from_env()
    manager = EngineManager(settings)
    photo = Image.open(PHOTO).convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)

    results = {name: manager.read(name, photo) for name in ENGINES}
    for name, result in results.items():
        drawn = annotate(photo, result.regions, settings.min_confidence, settings.font_path)
        kept = sum(is_confident(r, settings.min_confidence) for r in result.regions)
        label = f"{name}: {kept} confident regions, {result.total_ms / 1000:.1f} s on CPU"
        caption(drawn.resize((960, round(960 * photo.height / photo.width))), label).save(
            OUT / f"result-{name}.jpg", **JPEG
        )

    region, affinity = craft_maps(manager, photo)
    panels = [
        caption(photo.resize((640, 480)), "1. input photo"),
        caption(blend(photo, region).resize((640, 480)), "2. CRAFT: character centres"),
        caption(blend(photo, affinity).resize((640, 480)), "3. CRAFT: links between characters"),
        caption(blend(photo, db_map(photo)).resize((640, 480)), "4. PP-OCRv6 (DB): text-line map"),
    ]
    grid = Image.new("RGB", (1280, panels[0].height * 2), (24, 28, 34))
    for i, panel in enumerate(panels):
        grid.paste(panel, ((i % 2) * 640, (i // 2) * panel.height))
    grid.save(OUT / "detection-maps.jpg", **JPEG)

    labels = json.loads((PHOTO.parent / "labels.json").read_text(encoding="utf-8"))[PHOTO.name]
    lines = [LabelLine.from_dict(line) for line in labels]
    recognition_table(results, photo, lines, RECOGNITION_EXAMPLES).save(OUT / "recognition.png", optimize=True)
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
