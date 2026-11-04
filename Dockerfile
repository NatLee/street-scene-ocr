# syntax=docker/dockerfile:1
#
# CPU image (default):  docker build -t street-scene-ocr .
# Fewer engines:        docker build --build-arg ENGINES="rapidocr" -t street-scene-ocr:rapid .
# GPU image:            see compose.gpu.yaml (uses the PyTorch CUDA image as the base)

ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ARG ENGINES="easyocr rapidocr paddleocr"
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# PIP_BREAK_SYSTEM_PACKAGES: the PyTorch CUDA base image keeps its packages in the system Python, which
# Ubuntu marks "externally managed"; installing next to them is how that image is meant to be extended.
# It changes nothing on python:3.12-slim.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OCR_MODEL_DIR=/models \
    OCR_PORT=8000

WORKDIR /app

# Third-party packages first, from pyproject.toml alone, so editing the code does not reinstall
# PyTorch and friends. The placeholder package and README are replaced by the real ones below.
COPY pyproject.toml LICENSE ./
COPY docker/install-engines.sh /tmp/install-engines.sh
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p src/street_scene_ocr && touch src/street_scene_ocr/__init__.py README.md \
    && sh /tmp/install-engines.sh "$ENGINES" "$TORCH_INDEX_URL" \
    && pip uninstall -y street-scene-ocr && rm -rf src README.md

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps /app

# Models are downloaded on first use into /models. Mount a volume there to keep them between
# containers (compose.yaml does), or run `street-scene-ocr warmup` once to fetch them up front.
RUN useradd --create-home --uid 10001 ocr && mkdir -p /models && chown ocr /models
USER ocr
VOLUME ["/models"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"OCR_PORT\", \"8000\")}/healthz', timeout=4)"

CMD ["street-scene-ocr", "serve"]
