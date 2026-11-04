"""PaddleOCR: the official PP-OCR pipeline from Baidu's PaddlePaddle team.

PaddleOCR 3.7 defaults to PP-OCRv6 *medium*, the largest and most accurate model of the family.
We ask for its ONNX Runtime backend, so the 700 MB PaddlePaddle framework is not needed.
The document-photo stages (page orientation, page unwarping) are switched off: street signs are
not scanned pages.
"""

from __future__ import annotations

import os

import numpy as np

from .base import EngineOutput, OcrEngine, Stopwatch, TextRegion, to_bgr


class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"
    title = "PaddleOCR"
    summary = "PP-OCRv6 medium detector + recogniser, official pipeline on ONNX Runtime (CPU)"
    homepage = "https://github.com/PaddlePaddle/PaddleOCR"
    modules = ("paddleocr", "onnxruntime")

    def load(self) -> None:
        folder = self.model_dir()
        if folder is not None:
            # PaddleX (PaddleOCR's runtime) only reads its cache folder from this variable, at import time.
            os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(folder))
        # Skip the network check of every model host on import; models download on first use anyway.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(
            engine="onnxruntime",
            engine_config={
                "intra_op_num_threads": self.settings.threads,
                "inter_op_num_threads": 1,
                "log_severity_level": 3,  # errors only; ONNX Runtime warns about every unused weight
            },
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
        self.device = "cpu"

    def read(self, image: np.ndarray) -> EngineOutput:
        watch = Stopwatch()
        with watch.stage("detection + recognition"):
            (page,) = self._ocr.predict(to_bgr(image))
        regions = [
            TextRegion.from_points(text, score, polygon)
            for polygon, text, score in zip(page["rec_polys"], page["rec_texts"], page["rec_scores"], strict=True)
        ]
        return EngineOutput(regions, watch.stages_ms)
