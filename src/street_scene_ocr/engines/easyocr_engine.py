"""EasyOCR: the engine the 2021 version used.

Two neural networks in a row:

* CRAFT finds text by predicting, for every pixel, "is this the middle of a character?" and
  "is this the gap between two characters of the same word?". Boxes come from those two maps.
* A CRNN (convolutional layers + a bidirectional LSTM, trained with CTC loss) reads each box.
"""

from __future__ import annotations

import numpy as np

from .base import EngineOutput, OcrEngine, Stopwatch, TextRegion

# Traditional Chinese plus English, exactly as in 2021.
LANGUAGES = ["ch_tra", "en"]


class EasyOcrEngine(OcrEngine):
    name = "easyocr"
    title = "EasyOCR"
    summary = "CRAFT detector + CRNN recogniser on PyTorch, Traditional Chinese and English (the 2021 engine)"
    homepage = "https://github.com/JaidedAI/EasyOCR"
    modules = ("easyocr",)

    def load(self) -> None:
        import easyocr
        import torch

        torch.set_num_threads(self.settings.threads)
        gpu = self._use_gpu()
        options = {"gpu": gpu, "verbose": False}
        folder = self.model_dir()
        if folder is not None:
            options["model_storage_directory"] = str(folder)
            options["user_network_directory"] = str(folder)
        self._reader = easyocr.Reader(LANGUAGES, **options)
        self.device = "cuda" if gpu else "cpu"

    def _use_gpu(self) -> bool:
        if self.settings.device == "cpu":
            return False
        import torch

        available = torch.cuda.is_available()
        if self.settings.device == "cuda" and not available:
            raise RuntimeError("OCR_DEVICE=cuda but PyTorch cannot see a CUDA GPU")
        return available

    def read(self, image: np.ndarray) -> EngineOutput:
        from easyocr.utils import reformat_input

        # Same steps as Reader.readtext(), split so each stage can be timed separately.
        watch = Stopwatch()
        colour, grey = reformat_input(image)
        with watch.stage("detection"):
            horizontal, free = self._reader.detect(colour, reformat=False)
        with watch.stage("recognition"):
            found = self._reader.recognize(grey, horizontal[0], free[0], reformat=False)
        regions = [TextRegion.from_points(text, confidence, box) for box, text, confidence in found]
        return EngineOutput(regions, watch.stages_ms)
