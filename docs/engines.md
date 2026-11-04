# Which OCR engine for Traditional Chinese street signs?

Short answer, as of November 2026: start with **RapidOCR**. It runs PaddleOCR's PP-OCRv6 models on ONNX
Runtime, reads Traditional Chinese well, needs no deep-learning framework and is the fastest of the three on
a CPU. Use **PaddleOCR** when you want the larger PP-OCRv6 *medium* models and every last bit of accuracy.
**EasyOCR**, the engine from 2021, is kept as the baseline: it shows how far the field has moved.

The numbers behind that advice are in [the benchmark](../eval/README.md); this page explains the engines.

## The three engines

| | EasyOCR | RapidOCR | PaddleOCR |
|---|---|---|---|
| Version used | 1.7.2 (September 2024, latest) | 3.10 (October 2026) | 3.7 (June 2026) |
| Detector | CRAFT (character + link maps) | PP-OCRv6 small (DB) | PP-OCRv6 medium (DB) |
| Recogniser | CRNN: CNN + BiLSTM + CTC, separate Traditional Chinese model (5,285 characters) | PP-OCRv6 small, CTC, one model for Chinese (both scripts), English, Japanese … (18,708 characters) | PP-OCRv6 medium, same family, larger |
| Runtime | PyTorch | ONNX Runtime | ONNX Runtime here (Paddle Inference also possible) |
| Model download | ~295 MB on first use | none, models ship in the wheel (31 MB) | ~140 MB on first use |
| GPU in this project | yes (CUDA image) | no (CPU build of ONNX Runtime) | no |
| Licence | Apache-2.0 | Apache-2.0 | Apache-2.0 |

What the authors report for Traditional Chinese, on PaddleOCR's own multi-scenario benchmark
([PP-OCRv6 docs](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html)):

| Model | Detection Hmean, Traditional Chinese | Recognition accuracy, Traditional Chinese |
|---|---:|---:|
| PP-OCRv6 medium (PaddleOCR here) | 86.3 % | 78.6 % |
| PP-OCRv6 small (RapidOCR here) | 85.7 % | 77.0 % |
| PP-OCRv6 tiny | 83.7 % | 65.0 % |
| PP-OCRv5 server | 81.5 % | 74.7 % |
| PP-OCRv5 mobile | 82.3 % | 72.0 % |

Those are the vendor's numbers on the vendor's data, so read them as a ranking inside one family, not as a
promise for your photos. The benchmark in this repository is small but independent.

### EasyOCR

The 2021 choice, and still the friendliest API (`easyocr.Reader(["ch_tra", "en"]).readtext(image)`). CRAFT
finds characters and the links between them, which helps with widely spaced or curved lettering; the CRNN
recogniser is small and old. Traditional Chinese is a separate model that cannot be combined with Simplified
Chinese or Japanese in one reader, so signs that mix in の (very common in Taiwan) lose that character. The
project's last release was in September 2024.

### RapidOCR

A community project that converts PaddleOCR's models to ONNX and wraps them in a small Python package with
almost no dependencies. Since version 3.9 its default models are PP-OCRv6 *small*, one model for Simplified and
Traditional Chinese, English and Japanese (and, for the small and medium sizes, 46 more Latin-script
languages). The models ship inside the wheel, so the first request is as fast as the hundredth.

### PaddleOCR

The reference implementation from Baidu's PaddlePaddle team. Version 3.7 defaults to PP-OCRv6 *medium*, the
most accurate model of the family. It can run on Paddle Inference (the default), ONNX Runtime, OpenVINO or
Hugging Face Transformers; this project asks for ONNX Runtime so the 700 MB PaddlePaddle framework is not
needed. The price is a heavier dependency tree (PaddleX, pandas, ModelScope and Hugging Face clients) and a
pinned desktop build of OpenCV.

### Not included, and why

- **Vision-language models** (PaddleOCR-VL, general multimodal LLMs) read difficult documents very well, but
  need a GPU and seconds per image. This project is about a CPU service that answers in about a second.
- **Tesseract** is built for scanned documents: clean, straight lines of text on a plain background. Street
  photos are the opposite.
- **Cloud OCR APIs** are accurate and convenient, but they are not something you can study, run offline or
  benchmark reproducibly.

Each of these would still be one class away; see below.

## Adding an engine

An engine is a subclass of `OcrEngine` ([`engines/base.py`](../src/street_scene_ocr/engines/base.py)) with
two methods: `load()` builds the model once, `read(image)` takes an RGB `numpy` array and returns
`TextRegion`s (text, confidence, polygon). Everything else — threshold, reading order, drawing, the API, the
web page, the benchmark — is shared.

```python
# src/street_scene_ocr/engines/myocr_engine.py
import numpy as np

from .base import EngineOutput, OcrEngine, Stopwatch, TextRegion


class MyOcrEngine(OcrEngine):
    name = "myocr"  # also the pip extra and the API name
    title = "MyOCR"
    summary = "what models it uses, in one line"
    homepage = "https://example.com/myocr"
    modules = ("myocr",)  # the engine is offered only when these import

    def load(self) -> None:
        import myocr  # import inside load(): the package is optional

        self._model = myocr.load(cache_dir=self.model_dir())

    def read(self, image: np.ndarray) -> EngineOutput:
        watch = Stopwatch()
        with watch.stage("detection + recognition"):
            found = self._model.read(image)
        regions = [TextRegion.from_points(f.text, f.score, f.corners) for f in found]
        return EngineOutput(regions, watch.stages_ms)
```

Then:

1. Add the class to `ENGINE_CLASSES` in [`engines/__init__.py`](../src/street_scene_ocr/engines/__init__.py).
2. Add an extra with the same name to `pyproject.toml`, e.g. `myocr = ["myocr>=1.0"]`
   (a test checks that the two stay in sync).
3. Install it (`pip install -e ".[myocr]"`, or add it to `ENGINES` when building the Docker image) and run
   `python eval/run.py --engines myocr` to see where it lands.

## Sources

- EasyOCR: <https://github.com/JaidedAI/EasyOCR>, release history on PyPI.
- CRAFT: Baek et al., *Character Region Awareness for Text Detection*, CVPR 2019,
  <https://arxiv.org/abs/1904.01941>.
- CRNN: Shi et al., *An End-to-End Trainable Neural Network for Image-based Sequence Recognition*, 2015,
  <https://arxiv.org/abs/1507.05717>.
- DB: Liao et al., *Real-time Scene Text Detection with Differentiable Binarization*, AAAI 2020,
  <https://arxiv.org/abs/1911.08947>.
- PP-OCRv6 model card and benchmarks: <https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html>
  and <https://huggingface.co/blog/PaddlePaddle/pp-ocrv6>.
- RapidOCR usage and default models: <https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/>.
- Character counts: `easyocr/character/ch_tra_char.txt` and the `character` metadata of RapidOCR's
  `PP-OCRv6_rec_small.onnx`, checked in the Docker image on 2026-11-04.
