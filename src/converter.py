"""Conversion pipeline: one DJI R-JPEG to one temperature TIFF."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from PIL import Image

from .metadata import read_exif
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
    exif: Optional[Image.Exif],
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
    if exif is not None:
        save_kwargs["exif"] = exif
    img.save(str(output_path), **save_kwargs)


def convert_rjpeg(
    input_path: Path,
    output_path: Path,
    params: MeasurementParams = MeasurementParams(),
    preserve_metadata: bool = True,
) -> ConversionResult:
    """Convert a single R-JPEG to a float32 temperature TIFF in Celsius."""
    try:
        raw, width, height = extract_temperature(input_path, params=params)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        exif = read_exif(input_path) if preserve_metadata else None
        _save_temperature_tiff(raw, width, height, output_path, exif)

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
    cancel: Optional[threading.Event] = None,
    input_root: Optional[Path] = None,
) -> list[ConversionResult]:
    """Convert many R-JPEGs in parallel. `progress(done, total, result)` is called after each.

    If `cancel` is set while converting, pending files are dropped; in-flight
    files finish and are reported. Returned results cover processed files only.

    When `input_root` is given, the folder structure below it is mirrored in
    `output_dir` so that recursive batches with repeated file names (DJI
    restarts numbering per folder) do not overwrite each other.
    """
    paths = list(input_paths)
    total = len(paths)
    results: list[ConversionResult] = []
    if total == 0:
        return results

    output_dir.mkdir(parents=True, exist_ok=True)

    def _out_path(path: Path) -> Path:
        if input_root is not None:
            try:
                rel = path.resolve().relative_to(Path(input_root).resolve())
                return output_dir / rel.with_suffix(".tif")
            except ValueError:
                pass  # path lies outside input_root; fall back to flat layout
        return output_dir / (path.stem + ".tif")

    def _task(path: Path) -> ConversionResult:
        return convert_rjpeg(path, _out_path(path), params, preserve_metadata)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_task, path): path for path in paths}
        done = 0
        for future in as_completed(futures):
            if cancel is not None and cancel.is_set():
                for pending in futures:
                    pending.cancel()
            if future.cancelled():
                continue
            result = future.result()
            results.append(result)
            done += 1
            if progress is not None:
                progress(done, total, result)

    return results
