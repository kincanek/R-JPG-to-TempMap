"""Resolve bundled plugin paths (DJI Thermal SDK + ExifTool)."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
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


def exiftool_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return plugins_dir() / f"exiftool{suffix}"


def ensure_plugins_present() -> None:
    missing = []
    for name, path in (
        ("dji_irp", dji_irp_executable()),
        ("exiftool", exiftool_executable()),
    ):
        if not path.exists():
            missing.append(f"{name} -> {path}")
    if missing:
        raise FileNotFoundError(
            "Required plugin binaries not found:\n  " + "\n  ".join(missing)
        )
