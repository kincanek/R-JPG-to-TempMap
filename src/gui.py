"""Tkinter desktop GUI for the R-JPG to temperature TIFF converter."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .converter import ConversionResult, batch_convert, discover_rjpegs
from .paths import ensure_plugins_present
from .sdk import MeasurementParams


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("R-JPG to TempMap")
        self.geometry("720x520")
        self.minsize(640, 480)

        self._input_dir = tk.StringVar()
        self._output_dir = tk.StringVar()
        self._recursive = tk.BooleanVar(value=False)
        self._preserve_meta = tk.BooleanVar(value=True)
        self._distance = tk.DoubleVar(value=5.0)
        self._humidity = tk.DoubleVar(value=70.0)
        self._emissivity = tk.DoubleVar(value=0.95)
        self._reflection = tk.DoubleVar(value=23.0)
        self._workers = tk.IntVar(value=4)

        self._worker_thread: threading.Thread | None = None
        self._event_queue: "queue.Queue[tuple]" = queue.Queue()
        self._cancel_event = threading.Event()

        self._build_ui()
        self._poll_events()

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        folders = ttk.LabelFrame(self, text="Folders")
        folders.pack(fill="x", **pad)

        self._add_folder_row(folders, "Input folder:", self._input_dir, self._pick_input)
        self._add_folder_row(folders, "Output folder:", self._output_dir, self._pick_output)

        ttk.Checkbutton(
            folders, text="Include subfolders", variable=self._recursive
        ).grid(row=2, column=1, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(
            folders, text="Copy EXIF / GPS metadata into TIFFs", variable=self._preserve_meta
        ).grid(row=3, column=1, sticky="w", padx=8, pady=2)

        params = ttk.LabelFrame(self, text="Radiometric parameters")
        params.pack(fill="x", **pad)
        self._add_param(params, 0, "Distance (m)", self._distance, 1.0, 25.0, 0.1)
        self._add_param(params, 1, "Humidity (%)", self._humidity, 20.0, 100.0, 1.0)
        self._add_param(params, 2, "Emissivity", self._emissivity, 0.10, 1.00, 0.01)
        self._add_param(params, 3, "Reflection (C)", self._reflection, -40.0, 500.0, 0.5)
        self._add_param(params, 4, "Parallel workers", self._workers, 1, 16, 1, integer=True)

        controls = ttk.Frame(self)
        controls.pack(fill="x", **pad)
        self._start_btn = ttk.Button(controls, text="Convert", command=self._start)
        self._start_btn.pack(side="left")
        self._cancel_btn = ttk.Button(
            controls, text="Cancel", command=self._cancel, state="disabled"
        )
        self._cancel_btn.pack(side="left", padx=6)

        self._progress = ttk.Progressbar(self, mode="determinate")
        self._progress.pack(fill="x", **pad)

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self._log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        self._log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _add_folder_row(self, parent, label, var, browse):
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=60).grid(
            row=row, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Button(parent, text="Browse...", command=browse).grid(
            row=row, column=2, padx=8, pady=4
        )
        parent.columnconfigure(1, weight=1)

    def _add_param(self, parent, row, label, var, lo, hi, step, integer=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        spin = ttk.Spinbox(
            parent,
            from_=lo,
            to=hi,
            increment=step,
            textvariable=var,
            width=10,
            format="%.0f" if integer else "%.2f",
        )
        spin.grid(row=row, column=1, sticky="w", padx=4, pady=4)

    def _pick_input(self) -> None:
        path = filedialog.askdirectory(title="Select folder with R-JPEG files")
        if path:
            self._input_dir.set(path)
            if not self._output_dir.get():
                self._output_dir.set(str(Path(path) / "tempmap_tif"))

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self._output_dir.set(path)

    def _log_line(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        try:
            ensure_plugins_present()
        except FileNotFoundError as exc:
            messagebox.showerror("Missing plugin", str(exc))
            return

        input_dir = Path(self._input_dir.get()) if self._input_dir.get() else None
        output_dir = Path(self._output_dir.get()) if self._output_dir.get() else None
        if not input_dir or not input_dir.exists():
            messagebox.showerror("Invalid input", "Select a valid input folder.")
            return
        if not output_dir:
            messagebox.showerror("Invalid output", "Select an output folder.")
            return

        try:
            inputs = discover_rjpegs(input_dir, recursive=self._recursive.get())
        except Exception as exc:
            messagebox.showerror("Error", f"Could not scan input folder:\n{exc}")
            return
        if not inputs:
            messagebox.showwarning(
                "Nothing to do", "No DJI R-JPEG files (_R.JPG / _T.JPG) found."
            )
            return

        params = MeasurementParams(
            distance=float(self._distance.get()),
            humidity=float(self._humidity.get()),
            emissivity=float(self._emissivity.get()),
            reflection=float(self._reflection.get()),
        )

        self._cancel_event.clear()
        self._progress.configure(maximum=len(inputs), value=0)
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._log_line(f"Found {len(inputs)} R-JPEG files. Starting conversion...")

        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self._worker_thread = threading.Thread(
            target=self._run_batch,
            args=(inputs, output_dir, params),
            daemon=True,
        )
        self._worker_thread.start()

    def _run_batch(self, inputs, output_dir: Path, params: MeasurementParams) -> None:
        def progress(done: int, total: int, result: ConversionResult) -> None:
            self._event_queue.put(("progress", done, total, result))
            if self._cancel_event.is_set():
                raise RuntimeError("cancelled")

        try:
            batch_convert(
                inputs,
                output_dir,
                params=params,
                preserve_metadata=self._preserve_meta.get(),
                workers=self._workers.get(),
                progress=progress,
            )
            self._event_queue.put(("done", None))
        except Exception as exc:
            self._event_queue.put(("error", str(exc)))

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._log_line("Cancel requested; finishing in-flight files...")

    def _poll_events(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, done, total, result = event
                    self._progress.configure(value=done)
                    status = "OK" if result.ok else f"FAIL: {result.error}"
                    self._log_line(f"[{done}/{total}] {result.source.name} -> {status}")
                elif kind == "done":
                    self._log_line("Conversion finished.")
                    self._start_btn.configure(state="normal")
                    self._cancel_btn.configure(state="disabled")
                elif kind == "error":
                    self._log_line(f"ERROR: {event[1]}")
                    self._start_btn.configure(state="normal")
                    self._cancel_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


def run() -> int:
    app = ConverterApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
