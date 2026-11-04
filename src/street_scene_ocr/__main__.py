"""Command line: start the web service, read one image, or download the models ahead of time.

street-scene-ocr serve                      # same as `python -m street_scene_ocr`
street-scene-ocr read photo.jpg --engine rapidocr --annotated out.png
street-scene-ocr warmup                     # load every installed engine once
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .config import Settings, SettingsError
from .engines import EngineError
from .imaging import InvalidImage, decode_image
from .postprocess import is_confident
from .render import annotate
from .service import EngineManager, EngineNotInstalled, UnknownEngine


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="street-scene-ocr",
        description="Read Traditional Chinese street signs with EasyOCR, RapidOCR or PaddleOCR.",
        epilog="Settings such as OCR_DEVICE or OCR_MODEL_DIR come from environment variables; see the README.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    serve = commands.add_parser("serve", help="start the web page and the API (default command)")
    serve.add_argument("--host", default=settings.host, help=f"address to listen on (default {settings.host})")
    serve.add_argument("--port", type=int, default=settings.port, help=f"port (default {settings.port})")

    read = commands.add_parser("read", help="read one image and print the result as JSON")
    read.add_argument("image", type=Path, help="png, jpg or jpeg file")
    read.add_argument("--engine", help="engine name (default: the configured default engine)")
    read.add_argument(
        "--min-confidence",
        type=float,
        default=settings.min_confidence,
        help=f"regions above this count as confident (default {settings.min_confidence})",
    )
    read.add_argument(
        "--to-traditional",
        action=argparse.BooleanOptionalAction,
        default=settings.to_traditional,
        help="convert Simplified characters to Traditional with OpenCC (default: %(default)s)",
    )
    read.add_argument("--annotated", type=Path, metavar="OUT.png", help="also save the image with boxes drawn on it")

    warmup = commands.add_parser("warmup", help="load engines once so their models are downloaded")
    warmup.add_argument("engines", nargs="*", help="engine names (default: every installed engine)")
    return parser


def serve(settings: Settings, host: str, port: int) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(replace(settings, host=host, port=port)), host=host, port=port)
    return 0


def read(settings: Settings, args: argparse.Namespace) -> int:
    manager = EngineManager(settings)
    engine = args.engine or manager.default_engine()
    if engine is None:
        raise EngineNotInstalled("no OCR engine is installed; try: pip install 'street-scene-ocr[rapidocr]'")
    image = decode_image(args.image.read_bytes())
    result = manager.read(engine, image, args.to_traditional)
    report = {
        "engine": result.engine,
        "device": result.device,
        "stages_ms": result.stages_ms,
        "total_ms": result.total_ms,
        "to_traditional": result.traditional,
        "regions": [
            {
                "text": r.text,
                "confidence": round(r.confidence, 4),
                "confident": is_confident(r, args.min_confidence),
                "polygon": [[round(x, 1), round(y, 1)] for x, y in r.polygon],
            }
            for r in result.regions
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.annotated:
        annotate(image, result.regions, args.min_confidence, settings.font_path).save(args.annotated)
        print(f"annotated image written to {args.annotated}", file=sys.stderr)
    return 0


def warmup(settings: Settings, names: list[str]) -> int:
    manager = EngineManager(settings)
    names = names or manager.installed
    if not names:
        print("no OCR engine is installed, nothing to warm up", file=sys.stderr)
        return 1
    for name in names:
        print(f"loading {name} ...", file=sys.stderr, flush=True)
        engine = manager.get(name)
        print(f"  {name} ready on {engine.device}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        settings = Settings.from_env()
    except SettingsError as exc:
        print(f"street-scene-ocr: {exc}", file=sys.stderr)
        return 2
    parser = build_parser(settings)
    args = parser.parse_args(argv)
    try:
        if args.command == "read":
            return read(settings, args)
        if args.command == "warmup":
            return warmup(settings, args.engines)
        host = getattr(args, "host", settings.host)
        port = getattr(args, "port", settings.port)
        return serve(settings, host, port)
    except (FileNotFoundError, InvalidImage) as exc:
        print(f"street-scene-ocr: cannot read the image: {exc}", file=sys.stderr)
        return 1
    except (UnknownEngine, EngineNotInstalled, EngineError) as exc:
        print(f"street-scene-ocr: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
