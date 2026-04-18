"""ExifTool wrapper: read dimensions and copy EXIF/XMP/GPS metadata between files."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .paths import exiftool_executable


class ExifToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


def _run_exiftool(args: list[str]) -> subprocess.CompletedProcess:
    exe = exiftool_executable()
    if not exe.exists():
        raise ExifToolError(f"exiftool not found at {exe}")
    return subprocess.run(
        [str(exe), *args],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def read_tags(image_path: Path, tags: Optional[list[str]] = None) -> dict:
    """Return a dict of tag->value for the requested tags (all tags if None)."""
    args = ["-j", "-n"]
    if tags:
        args.extend(f"-{tag}" for tag in tags)
    args.append(str(image_path))
    result = _run_exiftool(args)
    if result.returncode != 0 or not result.stdout.strip():
        raise ExifToolError(
            f"exiftool failed for {image_path}: {result.stderr.strip() or result.stdout.strip()}"
        )
    payload = json.loads(result.stdout)
    if not payload:
        raise ExifToolError(f"exiftool returned no data for {image_path}")
    return payload[0]


def get_thermal_dimensions(image_path: Path) -> ImageDimensions:
    """Get the thermal raster dimensions embedded in an R-JPEG.

    DJI R-JPEGs encode the thermal frame as the main JPEG payload, so ImageWidth /
    ImageHeight match the thermal resolution (e.g. 640x512 on M3T, M2EA, H20T).
    """
    data = read_tags(image_path, ["ImageWidth", "ImageHeight"])
    try:
        return ImageDimensions(int(data["ImageWidth"]), int(data["ImageHeight"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ExifToolError(f"Could not read dimensions from {image_path}") from exc


def copy_metadata(source: Path, destination: Path) -> None:
    """Copy all EXIF/XMP/GPS metadata from source into destination, overwriting in place."""
    result = _run_exiftool([
        "-overwrite_original",
        "-TagsFromFile", str(source),
        "-all:all",
        "-XMP:all",
        "-GPS:all",
        "--ExifIFD:Orientation",
        str(destination),
    ])
    if result.returncode != 0:
        raise ExifToolError(
            f"exiftool metadata copy failed: {result.stderr.strip() or result.stdout.strip()}"
        )
