"""Conversion pipeline: one DJI R-JPEG to one temperature TIFF."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from PIL import Image

from .metadata import read_source_metadata
from .sdk import MeasurementParams, extract_temperature

LOGGER = logging.getLogger(__name__)

RJPEG_SUFFIXES = {".jpg", ".jpeg"}


@dataclass
class ConversionResult:
    source: Path
    output: Optional[Path]
    ok: bool
    error: Optional[str] = None


def _save_temperature_tiff(
    raw_float32: bytes,
    width: int,
    height: int,
    output_path: Path,
    exif_bytes: bytes,
) -> None:
    """Write a single-band float32 TIFF carrying the source EXIF block.

    The DJI SDK returns raw little-endian float32 pixels in row-major order.
    Pillow's 'F' mode reads those directly via frombytes, so we avoid a numpy
    dependency (and the ~600 MB of MKL DLLs that come with Anaconda's numpy).

    Pillow writes uncompressed TIFFs reliably for mode='F'. Compressed TIFF
    output via libtiff has crashed on some Windows builds, so we stay
    uncompressed; a 640x512 frame is ~1.3 MB, which is fine.
    """
    img = Image.frombytes("F", (width, height), raw_float32)
    save_kwargs: dict = {"format": "TIFF"}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes
    img.save(str(output_path), **save_kwargs)


def convert_rjpeg(
    input_path: Path,
    output_path: Path,
    params: MeasurementParams = MeasurementParams(),
    preserve_metadata: bool = True,
) -> ConversionResult:
    """Convert a single R-JPEG to a float32 temperature TIFF in Celsius."""
    try:
        source_meta = read_source_metadata(input_path)
        dims = source_meta.dimensions

        raw = extract_temperature(input_path, dims.width, dims.height, params=params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        exif = source_meta.exif_bytes if preserve_metadata else b""
        _save_temperature_tiff(raw, dims.width, dims.height, output_path, exif)

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
