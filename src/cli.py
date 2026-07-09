"""Command-line interface for batch R-JPG to temperature TIFF conversion."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .converter import ConversionResult, batch_convert, discover_rjpegs
from .paths import ensure_plugins_present
from .sdk import MeasurementParams


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rjpg2tempmap",
        description="Convert DJI R-JPEG thermal images into temperature GeoTIFFs.",
    )
    parser.add_argument("input", type=Path, help="Input folder or single R-JPEG file")
    parser.add_argument(
        "-o", "--output", type=Path, required=True, help="Output folder for .tif files"
    )
    parser.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    parser.add_argument("--distance", type=float, default=5.0, help="Distance to target (m)")
    parser.add_argument("--humidity", type=float, default=70.0, help="Relative humidity (%)")
    parser.add_argument("--emissivity", type=float, default=0.95, help="Surface emissivity [0.10-1.00]")
    parser.add_argument("--reflection", type=float, default=23.0, help="Reflected temperature (C)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads")
    parser.add_argument(
        "--no-metadata", action="store_true", help="Skip copying EXIF/GPS into the TIFF"
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _collect_inputs(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    return discover_rjpegs(path, recursive=recursive)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        ensure_plugins_present()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        inputs = _collect_inputs(args.input, args.recursive)
    except FileNotFoundError:
        print(f"ERROR: input path does not exist: {args.input}", file=sys.stderr)
        return 2
    if not inputs:
        print(f"No R-JPEG files found under {args.input}", file=sys.stderr)
        return 1

    params = MeasurementParams(
        distance=args.distance,
        humidity=args.humidity,
        emissivity=args.emissivity,
        reflection=args.reflection,
    )

    total = len(inputs)
    print(f"Found {total} R-JPEG files. Converting to {args.output}...")

    def _progress(done: int, total: int, result: ConversionResult) -> None:
        status = "OK" if result.ok else f"FAIL ({result.error})"
        print(f"[{done}/{total}] {result.source.name} -> {status}")

    results = batch_convert(
        inputs,
        args.output,
        params=params,
        preserve_metadata=not args.no_metadata,
        workers=args.workers,
        progress=_progress,
        input_root=args.input if args.input.is_dir() else None,
    )

    failed = [r for r in results if not r.ok]
    print(f"\nDone. {total - len(failed)} succeeded, {len(failed)} failed.")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
