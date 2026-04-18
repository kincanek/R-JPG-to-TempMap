"""Conversion pipeline: one DJI R-JPEG to one temperature TIFF."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np
import tifffile

from .metadata import copy_metadata, get_thermal_dimensions
from .sdk import MeasurementParams, extract_temperature

LOGGER = logging.getLogger(__name__)

RJPEG_SUFFIXES = {".jpg", ".jpeg"}


@dataclass
class ConversionResult:
    source: Path
    output: Optional[Path]
    ok: bool
    error: Optional[str] = None


def convert_rjpeg(
    input_path: Path,
    output_path: Path,
    params: MeasurementParams = MeasurementParams(),
    preserve_metadata: bool = True,
) -> ConversionResult:
    """Convert a single R-JPEG to a float32 temperature TIFF in Celsius."""
    try:
        dims = get_thermal_dimensions(input_path)
        temperature = extract_temperature(
            input_path, dims.width, dims.height, params=params
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tifffile.imwrite(
            str(output_path),
            temperature.astype(np.float32, copy=False),
            photometric="minisblack",
            compression="zlib",
            metadata={
                "Unit": "Celsius",
                "Source": input_path.name,
                "Emissivity": params.emissivity,
                "Distance": params.distance,
                "Humidity": params.humidity,
                "Reflection": params.reflection,
            },
        )

        if preserve_metadata:
            try:
                copy_metadata(input_path, output_path)
            except Exception as exc:
                LOGGER.warning("Metadata copy failed for %s: %s", input_path.name, exc)

        return ConversionResult(source=input_path, output=output_path, ok=True)
    except Exception as exc:
        LOGGER.error("Failed to convert %s: %s", input_path, exc)
        return ConversionResult(
            source=input_path, output=None, ok=False, error=str(exc)
        )


def discover_rjpegs(input_dir: Path, recursive: bool = False) -> list[Path]:
    """Return DJI R-JPEG candidates (JPEGs whose stem ends in _R or _T)."""
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)
    pattern = "**/*" if recursive else "*"
    candidates: list[Path] = []
    for entry in sorted(input_dir.glob(pattern)):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in RJPEG_SUFFIXES:
            continue
        if entry.stem.upper().endswith(("_R", "_T")):
            candidates.append(entry)
    return candidates


def batch_convert(
    input_paths: Iterable[Path],
    output_dir: Path,
    params: MeasurementParams = MeasurementParams(),
    preserve_metadata: bool = True,
    workers: int = 4,
    progress: Optional[Callable[[int, int, ConversionResult], None]] = None,
) -> list[ConversionResult]:
    """Convert many R-JPEGs in parallel. `progress(done, total, result)` is called after each."""
    paths = list(input_paths)
    total = len(paths)
    results: list[ConversionResult] = []
    if total == 0:
        return results

    output_dir.mkdir(parents=True, exist_ok=True)

    def _task(path: Path) -> ConversionResult:
        return convert_rjpeg(
            path, output_dir / (path.stem + ".tif"), params, preserve_metadata
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_task, path): path for path in paths}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1
            if progress is not None:
                progress(done, total, result)

    return results
