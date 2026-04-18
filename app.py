"""Entry point: launch GUI by default, CLI if arguments are given.

Usage:
    python app.py                               # launch desktop GUI
    python app.py <input_folder> -o <out_dir>   # run batch CLI
"""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) > 1:
        from src.cli import main as cli_main
        return cli_main()
    from src.gui import run as gui_run
    return gui_run()


if __name__ == "__main__":
    raise SystemExit(main())
