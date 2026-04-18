# PyInstaller spec: builds a Windows onedir package of R-JPG-to-TempMap.
# Produces dist/RJPG-to-TempMap/RJPG-to-TempMap.exe plus its supporting files.
#
# Usage: from the repo root, run  python -m PyInstaller build/RJPG-to-TempMap.spec

from pathlib import Path

# Resolve repo root relative to this spec. PyInstaller sets SPECPATH to the
# directory containing the spec; the repo root is one level up.
REPO_ROOT = Path(SPECPATH).parent
ENTRY = REPO_ROOT / "app.py"
PLUGINS = REPO_ROOT / "plugins"

block_cipher = None

a = Analysis(
    [str(ENTRY)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=[
        # Ship the bundled DJI SDK + ExifTool next to the exe. At runtime
        # src/paths.py locates them under <exe dir>/plugins/.
        (str(PLUGINS), "plugins"),
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RJPG-to-TempMap",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed app (GUI). Use True for a console for CLI debugging.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RJPG-to-TempMap",
)
