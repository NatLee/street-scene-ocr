"""RapidOCR: PaddleOCR's PP-OCR models exported to ONNX and run with ONNX Runtime.

Small wheels, no deep-learning framework, and fast on a plain CPU. Since 3.9 its default models are
PP-OCRv6 *small*, one model for Simplified and Traditional Chinese, English and Japanese.
The pipeline is detection (DB) -> 180-degree direction check -> recognition (CTC).
"""

from __future__ import annotations

import numpy as np

from .base import EngineOutput, OcrEngine, TextRegion, to_bgr

# RapidOCR reports [detection, direction check, recognition] seconds in this order.
STAGES = ("detection", "direction", "recognition")


class RapidOcrEngine(OcrEngine):
    name = "rapidocr"
    title = "RapidOCR"
    summary = "PP-OCRv6 small detector + recogniser as ONNX models on ONNX Runtime (CPU)"
    homepage = "https://github.com/RapidAI/RapidOCR"
    modules = ("rapidocr", "onnxruntime")

    def load(self) -> None:
        from rapidocr import RapidOCR

        # The rapidocr wheel ships its default models, so nothing is downloaded and OCR_MODEL_DIR is not needed.
        params = {
            # Keep every result: the confidence threshold is applied later, the same way for all engines.
            "Global.text_score": 0.0,
            "Global.log_level": "warning",
            "EngineConfig.onnxruntime.intra_op_num_threads": self.settings.threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
        self._engine = RapidOCR(params=params)
        # The CPU build of ONNX Runtime is installed, so this engine runs on the CPU even with OCR_DEVICE=cuda.
        self.device = "cpu"

    def read(self, image: np.ndarray) -> EngineOutput:
        out = self._engine(to_bgr(image))
        stages = {
            stage: round(seconds * 1000, 1) for stage, seconds in zip(STAGES, out.elapse_list or [], strict=False)
        }
        if out.boxes is None:
            return EngineOutput([], stages)
        regions = [
            TextRegion.from_points(text, score, box)
            for box, text, score in zip(out.boxes, out.txts, out.scores, strict=True)
        ]
        return EngineOutput(regions, stages)
