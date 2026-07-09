# PyInstaller spec: builds a Windows onedir package of R-JPG-to-TempMap.
# Produces dist/RJPG-to-TempMap/ containing:
#   RJPG-to-TempMap.exe       windowed GUI launcher
#   RJPG-to-TempMap-cli.exe   console launcher for command-line batch use
#
# Usage: from the repo root, run  python -m PyInstaller build/RJPG-to-TempMap.spec

from pathlib import Path

# Resolve repo root relative to this spec. PyInstaller sets SPECPATH to the
# directory containing the spec; the repo root is one level up.
REPO_ROOT = Path(SPECPATH).parent
ENTRY = REPO_ROOT / "app.py"

# Ship only the DJI SDK runtime binaries (dji_irp.exe + DLLs) and its license,
# not the full SDK tree (sample datasets and docs add ~45 MB of dead weight).
# The destination paths mirror the repo layout so src/paths.py resolves them
# the same way frozen and from source.
SDK_NAME = "dji_thermal_sdk_v1.4_20220929"
SDK_ROOT = REPO_ROOT / "plugins" / SDK_NAME
SDK_BIN_REL = Path("utility") / "bin" / "windows" / "release_x64"

a = Analysis(
    [str(ENTRY)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[
        (str(SDK_ROOT / SDK_BIN_REL), f"plugins/{SDK_NAME}/{SDK_BIN_REL.as_posix()}"),
        (str(SDK_ROOT / "License.txt"), f"plugins/{SDK_NAME}"),
        (str(REPO_ROOT / "assets" / "icon.ico"), "assets"),
    ],
    hiddenimports=[
        "src",
        "src.cli",
        "src.gui",
        "src.converter",
        "src.sdk",
        "src.metadata",
        "src.paths",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Our code does not use numpy; Pillow's optional numpy integration
        # drags in Intel MKL DLLs (~600 MB) when building from an Anaconda
        # Python. Excluding numpy shrinks the distribution dramatically.
        "numpy",
        # Test / docs / REPL tooling
        "pytest", "sphinx", "IPython", "notebook", "jupyter", "jupyterlab",
        "nbconvert", "nbformat", "ipykernel",
        # GUI toolkits we do not use (we ship Tkinter, which is stdlib)
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        # Scientific stack pulled in by Anaconda's numpy bundle
        "scipy", "pandas", "matplotlib", "sklearn", "skimage", "seaborn",
        "statsmodels", "sympy", "numba", "dask", "xarray", "h5py", "netCDF4",
        "tables", "pyarrow", "bokeh", "plotly", "altair",
        # Web / networking frameworks
        "tornado", "aiohttp", "fastapi", "flask", "django", "twisted",
        # Misc heavy optional deps
        "cryptography", "lxml", "docutils", "babel", "pygments", "zmq",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Windowed GUI launcher (no console window on double-click).
exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RJPG-to-TempMap",
    icon=str(REPO_ROOT / "assets" / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Console launcher: same entry point, but with stdout/stderr attached so the
# documented CLI usage (progress lines, error messages) actually prints.
exe_cli = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RJPG-to-TempMap-cli",
    icon=str(REPO_ROOT / "assets" / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_gui,
    exe_cli,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RJPG-to-TempMap",
)
