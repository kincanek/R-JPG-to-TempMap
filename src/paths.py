"""Resolve bundled plugin paths (DJI Thermal SDK + ExifTool)."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def project_root() -> Path:
    """Return the directory where bundled data (plugins/) lives.

    - When running from source: the repo root.
    - When packaged with PyInstaller: `_MEIPASS` (onefile: a temp dir; onedir:
      the `_internal/` folder next to the exe).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def plugins_dir() -> Path:
    return project_root() / "plugins"


def dji_sdk_dir() -> Path:
    base = plugins_dir() / "dji_thermal_sdk_v1.4_20220929"
    arch = "release_x64" if platform.architecture()[0] == "64bit" else "release_x86"
    sub = "windows" if os.name == "nt" else "linux"
    return base / "utility" / "bin" / sub / arch


def dji_irp_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return dji_sdk_dir() / f"dji_irp{suffix}"


def dji_irp_omp_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return dji_sdk_dir() / f"dji_irp_omp{suffix}"


def ensure_plugins_present() -> None:
    dji = dji_irp_executable()
    if not dji.exists():
        raise FileNotFoundError(
            f"DJI Thermal SDK binary not found at {dji}. "
            f"Make sure the plugins/ directory ships next to the application."
        )
