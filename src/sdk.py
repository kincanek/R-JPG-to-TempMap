"""Wrapper around the DJI Thermal SDK `dji_irp` executable.

The SDK ships a CLI binary that extracts per-pixel temperature values from an
R-JPEG. We shell out to it rather than linking libdirp.dll via ctypes: the
subprocess approach is arch-agnostic and isolates any native crash in the
child process.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .paths import dji_irp_executable, dji_sdk_dir


class DjiSdkError(RuntimeError):
    pass


@dataclass(frozen=True)
class MeasurementParams:
    """Radiometric parameters passed to the SDK for temperature computation.

    Ranges (enforced by the SDK):
        distance:   [1, 25] meters
        humidity:   [20, 100] percent
        emissivity: [0.10, 1.00]
        reflection: [-40.0, 500.0] Celsius
    """

    distance: float = 5.0
    humidity: float = 70.0
    emissivity: float = 0.95
    reflection: float = 23.0

    def as_cli_args(self) -> list[str]:
        return [
            "--distance", f"{self.distance:.2f}",
            "--humidity", f"{self.humidity:.2f}",
            "--emissivity", f"{self.emissivity:.2f}",
            "--reflection", f"{self.reflection:.2f}",
        ]


# dji_irp prints the thermal raster size parsed from the R-JPEG header, e.g.
#   "      image  width : 640"
#   "      image height : 512"
# This is the authoritative size: on some cameras (e.g. M30T) the visible JPEG
# is upscaled 2x relative to the thermal raster, so Image.size cannot be used.
_WIDTH_RE = re.compile(r"image\s+width\s*:\s*(\d+)")
_HEIGHT_RE = re.compile(r"image\s+height\s*:\s*(\d+)")


def extract_temperature(
    rjpeg_path: Path,
    params: MeasurementParams = MeasurementParams(),
) -> tuple[bytes, int, int]:
    """Run dji_irp 'measure' on an R-JPEG.

    Returns `(raw, width, height)` where `raw` holds little-endian float32
    Celsius values in row-major order (height x width).
    """
    exe = dji_irp_executable()
    if not exe.exists():
        raise DjiSdkError(f"dji_irp executable not found at {exe}")
    if not rjpeg_path.exists():
        raise DjiSdkError(f"R-JPEG not found: {rjpeg_path}")

    with tempfile.TemporaryDirectory(prefix="rjpg2temp_") as tmpdir:
        raw_out = Path(tmpdir) / "measure.raw"
        # Pass absolute paths: cwd is set to dji_sdk_dir so libdirp can find its
        # sibling DLLs, which would otherwise resolve our -s argument relative
        # to the SDK folder and break.
        cmd = [
            str(exe),
            "-s", str(rjpeg_path.resolve()),
            "-a", "measure",
            "-o", str(raw_out.resolve()),
            "--measurefmt", "float32",
            *params.as_cli_args(),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(dji_sdk_dir()),
            encoding="utf-8",
            errors="replace",
            # Keep dji_irp from flashing a console window when launched from
            # the windowed GUI exe.
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0 or not raw_out.exists():
            raise DjiSdkError(
                f"dji_irp failed for {rjpeg_path.name}: "
                f"{result.stderr.strip() or result.stdout.strip() or 'unknown error'}"
            )

        width_match = _WIDTH_RE.search(result.stdout)
        height_match = _HEIGHT_RE.search(result.stdout)
        if not width_match or not height_match:
            raise DjiSdkError(
                f"Could not parse thermal raster size from dji_irp output "
                f"for {rjpeg_path.name}"
            )
        width = int(width_match.group(1))
        height = int(height_match.group(1))

        expected_bytes = width * height * 4
        actual_bytes = raw_out.stat().st_size
        if actual_bytes != expected_bytes:
            raise DjiSdkError(
                f"Unexpected raw output size for {rjpeg_path.name}: "
                f"expected {expected_bytes} bytes ({width}x{height} float32), "
                f"got {actual_bytes}"
            )

        return raw_out.read_bytes(), width, height
