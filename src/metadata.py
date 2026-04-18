"""Pure-Python EXIF / image-size handling via Pillow.

Replaces the previous ExifTool subprocess wrapper. Pillow reads the raw EXIF
blob from the source R-JPEG and we re-embed it unchanged in the output TIFF
so GPS, timestamps and DJI-specific tags survive the conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


class MetadataError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class SourceMetadata:
    """Everything we need from the R-JPEG: its pixel size and the raw EXIF block."""

    dimensions: ImageDimensions
    exif_bytes: bytes


def read_source_metadata(image_path: Path) -> SourceMetadata:
    """Open an R-JPEG and return its thermal dimensions plus raw EXIF bytes."""
    try:
        with Image.open(image_path) as img:
            img.load()
            width, height = img.size
            exif_bytes = img.info.get("exif", b"")
    except Exception as exc:
        raise MetadataError(f"Could not read metadata from {image_path}: {exc}") from exc

    if width <= 0 or height <= 0:
        raise MetadataError(f"Invalid image size {width}x{height} for {image_path}")

    return SourceMetadata(
        dimensions=ImageDimensions(width=width, height=height),
        exif_bytes=exif_bytes or b"",
    )
