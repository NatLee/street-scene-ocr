#!/bin/sh
# Install the OCR engines named in $1 (space or comma separated) into the image's Python.
#
#   sh docker/install-engines.sh "easyocr rapidocr paddleocr" https://download.pytorch.org/whl/cpu
#
# Kept in one script so the Dockerfile stays readable and the two engine-specific quirks below
# live in one place.
set -eu

engines=$(echo "${1:-easyocr rapidocr paddleocr}" | tr ',' ' ')
torch_index=${2:-https://download.pytorch.org/whl/cpu}
extras=$(echo $engines | tr ' ' ',')

for engine in $engines; do
  case $engine in
    easyocr|rapidocr|paddleocr) ;;
    *) echo "unknown engine: $engine (choose from easyocr, rapidocr, paddleocr)" >&2; exit 1 ;;
  esac
done

has() { case " $engines " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# Quirk 1 - EasyOCR needs PyTorch. PyPI's default Linux wheel bundles several GB of CUDA libraries,
# so install the CPU-only wheel unless the base image already ships PyTorch (the GPU variant does).
if has easyocr && ! python -c "import torch" 2>/dev/null; then
  pip install --index-url "$torch_index" torch torchvision
fi

pip install "/app[$extras]"

# Quirk 2 - PaddleOCR's runtime (PaddleX) pins the desktop build of OpenCV, which needs the OpenGL
# and GLib system libraries, while EasyOCR and RapidOCR pull in the headless build. Both builds
# install the same `cv2` module, so reinstall PaddleX's pinned build last to make sure every file
# of `cv2` comes from one build, and add the libraries it links against.
# Remove this block once PaddleX depends on opencv-*-headless.
if has paddleocr; then
  apt-get update
  apt-get install -y --no-install-recommends libgl1 libglib2.0-0
  rm -rf /var/lib/apt/lists/*
  opencv=$(python -c "import importlib.metadata as m; print(m.version('opencv-contrib-python'))")
  pip install --force-reinstall --no-deps "opencv-contrib-python==$opencv"
fi

python -c "import cv2; print('OpenCV', cv2.__version__)"

# Report dependency conflicts without failing: base images can ship tools with pins of their own (the
# PyTorch CUDA image has a developer tool that wants an older click than uvicorn does). The engine smoke
# tests in CI are what catch a real breakage.
pip check || echo "pip check reported the conflicts above; see the comment in install-engines.sh"
