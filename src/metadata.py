"""Pure-Python EXIF handling via Pillow.

Replaces the previous ExifTool subprocess wrapper. Pillow reads the EXIF
block from the source R-JPEG and we re-embed it in the output TIFF so GPS,
timestamps and DJI-specific tags survive the conversion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image


class MetadataError(RuntimeError):
    pass


# IFD0 tags that describe the *pixel layout* of the source JPEG. When EXIF is
# embedded in a TIFF they merge into the image IFD itself, so a leftover
# SamplesPerPixel=3 or BitsPerSample from the RGB source (M2EA writes these)
# contradicts our single-band float32 raster and corrupts the file. Strip them
# and let Pillow declare the real layout.
_STRUCTURAL_TIFF_TAGS = frozenset({
    0x0100,  # ImageWidth
    0x0101,  # ImageLength
    0x0102,  # BitsPerSample
    0x0103,  # Compression
    0x0106,  # PhotometricInterpretation
    0x0111,  # StripOffsets
    0x0115,  # SamplesPerPixel
    0x0116,  # RowsPerStrip
    0x0117,  # StripByteCounts
    0x011C,  # PlanarConfiguration
    0x0142,  # TileWidth
    0x0143,  # TileLength
    0x0144,  # TileOffsets
    0x0145,  # TileByteCounts
    0x0152,  # ExtraSamples
    0x0153,  # SampleFormat
    0x0201,  # JPEGInterchangeFormat (thumbnail pointer)
    0x0202,  # JPEGInterchangeFormatLength
})


def read_exif(image_path: Path) -> Optional[Image.Exif]:
    """Return the source EXIF (GPS, timestamps, camera tags), sanitized for
    re-embedding into a TIFF. Returns None if the image carries no EXIF."""
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
    except Exception as exc:
        raise MetadataError(f"Could not read metadata from {image_path}: {exc}") from exc

    if not exif:
        return None
    for tag in _STRUCTURAL_TIFF_TAGS:
        exif.pop(tag, None)
    return exif
