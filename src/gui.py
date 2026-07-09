"""Tkinter desktop GUI for the R-JPG to temperature TIFF converter.

Bilingual (Spanish / English), switchable at runtime. The initial language
follows the Windows display language.
"""

from __future__ import annotations

import locale
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .converter import ConversionResult, batch_convert, discover_rjpegs
from .paths import asset_path, ensure_plugins_present
from .sdk import MeasurementParams

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        "title": "R-JPG a TempMap",
        "subtitle": "Convierte fotos térmicas R-JPEG de DJI en TIFF de temperatura (°C por píxel)",
        "step1": "1. Carpetas",
        "input": "Carpeta con imágenes térmicas:",
        "output": "Carpeta de salida:",
        "browse": "Examinar…",
        "recursive": "Incluir subcarpetas",
        "metadata": "Copiar metadatos EXIF / GPS a los TIFF (necesario para fotogrametría)",
        "step2": "2. Parámetros radiométricos",
        "distance": "Distancia al objetivo (m):",
        "humidity": "Humedad relativa (%):",
        "emissivity": "Emisividad:",
        "reflection": "Temperatura reflejada (°C):",
        "workers": "Conversiones en paralelo:",
        "defaults": "Restaurar valores",
        "step3": "3. Convertir",
        "convert": "Convertir",
        "cancel": "Cancelar",
        "open_output": "Abrir carpeta de salida",
        "log": "Actividad",
        "found_n": "{n} imágenes térmicas detectadas",
        "found_none": "No se encontraron imágenes térmicas DJI (*_R.JPG / *_T.JPG)",
        "err_title": "Error",
        "err_plugin": "Falta un componente",
        "err_input": "Selecciona una carpeta válida con imágenes térmicas.",
        "err_output": "Selecciona una carpeta de salida.",
        "err_scan": "No se pudo leer la carpeta de entrada:\n{err}",
        "err_none_title": "Nada que convertir",
        "starting": "Convirtiendo {n} imágenes…",
        "cancelling": "Cancelando… se terminan las imágenes en curso.",
        "done_ok": "Listo: {ok} imágenes convertidas correctamente.",
        "done_fail": "Terminado: {ok} convertidas, {fail} con error.",
        "done_cancel": "Cancelado: se convirtieron {ok} imágenes antes de detener.",
        "fatal": "Error inesperado: {err}",
        "ready": "Listo para convertir.",
        "ok": "OK",
        "fail": "ERROR",
        "language": "Idioma / Language:",
    },
    "en": {
        "title": "R-JPG to TempMap",
        "subtitle": "Convert DJI thermal R-JPEG photos into temperature TIFFs (°C per pixel)",
        "step1": "1. Folders",
        "input": "Folder with thermal images:",
        "output": "Output folder:",
        "browse": "Browse…",
        "recursive": "Include subfolders",
        "metadata": "Copy EXIF / GPS metadata into the TIFFs (required for photogrammetry)",
        "step2": "2. Radiometric parameters",
        "distance": "Distance to target (m):",
        "humidity": "Relative humidity (%):",
        "emissivity": "Emissivity:",
        "reflection": "Reflected temperature (°C):",
        "workers": "Parallel conversions:",
        "defaults": "Restore defaults",
        "step3": "3. Convert",
        "convert": "Convert",
        "cancel": "Cancel",
        "open_output": "Open output folder",
        "log": "Activity",
        "found_n": "{n} thermal images detected",
        "found_none": "No DJI thermal images (*_R.JPG / *_T.JPG) found",
        "err_title": "Error",
        "err_plugin": "Missing component",
        "err_input": "Select a valid folder with thermal images.",
        "err_output": "Select an output folder.",
        "err_scan": "Could not read the input folder:\n{err}",
        "err_none_title": "Nothing to convert",
        "starting": "Converting {n} images…",
        "cancelling": "Cancelling… finishing the images in progress.",
        "done_ok": "Done: {ok} images converted successfully.",
        "done_fail": "Finished: {ok} converted, {fail} failed.",
        "done_cancel": "Cancelled: {ok} images were converted before stopping.",
        "fatal": "Unexpected error: {err}",
        "ready": "Ready to convert.",
        "ok": "OK",
        "fail": "FAILED",
        "language": "Idioma / Language:",
    },
}

_LANG_LABELS = {"es": "Español", "en": "English"}

DEFAULTS = MeasurementParams()


def _system_language() -> str:
    try:
        locale.setlocale(locale.LC_CTYPE, "")
        name = (locale.getlocale()[0] or "").lower()
    except Exception:
        name = ""
    return "es" if name.startswith(("es", "spanish")) else "en"


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._lang = _system_language()
        self.geometry("760x640")
        self.minsize(680, 560)
        try:
            self.iconbitmap(str(asset_path("icon.ico")))
        except Exception:
            pass

        self._input_dir = tk.StringVar()
        self._output_dir = tk.StringVar()
        self._recursive = tk.BooleanVar(value=False)
        self._preserve_meta = tk.BooleanVar(value=True)
        self._distance = tk.DoubleVar(value=DEFAULTS.distance)
        self._humidity = tk.DoubleVar(value=DEFAULTS.humidity)
        self._emissivity = tk.DoubleVar(value=DEFAULTS.emissivity)
        self._reflection = tk.DoubleVar(value=DEFAULTS.reflection)
        self._workers = tk.IntVar(value=min(8, max(2, (os.cpu_count() or 4) // 2)))
        self._lang_choice = tk.StringVar(value=_LANG_LABELS[self._lang])

        self._worker_thread: threading.Thread | None = None
        self._event_queue: "queue.Queue[tuple]" = queue.Queue()
        self._cancel_event = threading.Event()
        self._last_output_dir: Path | None = None
        # Widgets whose text is retranslated on language change: (widget, key)
        self._translatable: list[tuple[tk.Widget, str]] = []

        self._build_ui()
        self._retranslate()
        self._input_dir.trace_add("write", lambda *_: self._update_found_count())
        self._poll_events()

    # ------------------------------------------------------------------ i18n

    def _t(self, key: str, **kwargs: object) -> str:
        text = STRINGS[self._lang][key]
        return text.format(**kwargs) if kwargs else text

    def _reg(self, widget: tk.Widget, key: str) -> tk.Widget:
        self._translatable.append((widget, key))
        return widget

    def _retranslate(self) -> None:
        self.title(f"{self._t('title')}  v{__version__}")
        for widget, key in self._translatable:
            widget.configure(text=self._t(key))
        self._update_found_count()
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._status_var.set(self._t("ready"))

    def _on_language_change(self, _event: object = None) -> None:
        for code, label in _LANG_LABELS.items():
            if self._lang_choice.get() == label:
                self._lang = code
        self._retranslate()

    # -------------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground="#555555")
        style.configure("Status.TLabel", font=("Segoe UI", 9, "bold"))
        style.configure("Convert.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 6))

        outer = ttk.Frame(self, padding=(14, 10, 14, 10))
        outer.pack(fill="both", expand=True)

        # --- Header: title + language picker
        header = ttk.Frame(outer)
        header.pack(fill="x")
        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        self._reg(ttk.Label(title_box, style="Title.TLabel"), "title").pack(anchor="w")
        self._reg(ttk.Label(title_box, style="Subtitle.TLabel"), "subtitle").pack(anchor="w")

        lang_box = ttk.Frame(header)
        lang_box.pack(side="right", anchor="n")
        self._reg(ttk.Label(lang_box), "language").pack(side="left", padx=(0, 6))
        lang_combo = ttk.Combobox(
            lang_box,
            textvariable=self._lang_choice,
            values=list(_LANG_LABELS.values()),
            state="readonly",
            width=9,
        )
        lang_combo.pack(side="left")
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        # --- Step 1: folders
        folders = self._reg(ttk.LabelFrame(outer, padding=(10, 6)), "step1")
        folders.pack(fill="x", pady=(10, 4))
        folders.columnconfigure(1, weight=1)

        self._reg(ttk.Label(folders), "input").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(folders, textvariable=self._input_dir).grid(
            row=0, column=1, sticky="ew", padx=6, pady=3
        )
        self._reg(ttk.Button(folders, command=self._pick_input), "browse").grid(
            row=0, column=2, pady=3
        )

        self._reg(ttk.Label(folders), "output").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(folders, textvariable=self._output_dir).grid(
            row=1, column=1, sticky="ew", padx=6, pady=3
        )
        self._reg(ttk.Button(folders, command=self._pick_output), "browse").grid(
            row=1, column=2, pady=3
        )

        opts = ttk.Frame(folders)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._reg(
            ttk.Checkbutton(opts, variable=self._recursive, command=self._update_found_count),
            "recursive",
        ).pack(side="left")
        self._found_label = ttk.Label(folders, style="Subtitle.TLabel")
        self._found_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(2, 0))

        self._reg(
            ttk.Checkbutton(folders, variable=self._preserve_meta), "metadata"
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))

        # --- Step 2: radiometric parameters
        params = self._reg(ttk.LabelFrame(outer, padding=(10, 6)), "step2")
        params.pack(fill="x", pady=4)
        grid = ttk.Frame(params)
        grid.pack(fill="x")

        self._add_param(grid, 0, 0, "distance", self._distance, 1.0, 25.0, 0.5)
        self._add_param(grid, 0, 2, "humidity", self._humidity, 20.0, 100.0, 5.0)
        self._add_param(grid, 1, 0, "emissivity", self._emissivity, 0.10, 1.00, 0.01)
        self._add_param(grid, 1, 2, "reflection", self._reflection, -40.0, 500.0, 1.0)
        self._add_param(grid, 2, 0, "workers", self._workers, 1, 16, 1, integer=True)
        self._reg(ttk.Button(grid, command=self._restore_defaults), "defaults").grid(
            row=2, column=3, sticky="e", padx=6, pady=3
        )
        for col in (1, 3):
            grid.columnconfigure(col, weight=1)

        # --- Step 3: convert
        run_frame = self._reg(ttk.LabelFrame(outer, padding=(10, 6)), "step3")
        run_frame.pack(fill="x", pady=4)

        controls = ttk.Frame(run_frame)
        controls.pack(fill="x")
        self._start_btn = ttk.Button(controls, style="Convert.TButton", command=self._start)
        self._reg(self._start_btn, "convert")
        self._start_btn.pack(side="left")
        self._cancel_btn = ttk.Button(controls, command=self._cancel, state="disabled")
        self._reg(self._cancel_btn, "cancel")
        self._cancel_btn.pack(side="left", padx=8)
        self._open_btn = ttk.Button(controls, command=self._open_output, state="disabled")
        self._reg(self._open_btn, "open_output")
        self._open_btn.pack(side="right")

        prog_row = ttk.Frame(run_frame)
        prog_row.pack(fill="x", pady=(8, 0))
        self._progress = ttk.Progressbar(prog_row, mode="determinate")
        self._progress.pack(side="left", fill="x", expand=True)
        self._progress_label = ttk.Label(prog_row, width=10, anchor="e")
        self._progress_label.pack(side="left", padx=(8, 0))

        self._status_var = tk.StringVar()
        ttk.Label(run_frame, textvariable=self._status_var, style="Status.TLabel").pack(
            anchor="w", pady=(6, 0)
        )

        # --- Log
        log_frame = self._reg(ttk.LabelFrame(outer, padding=(6, 4)), "log")
        log_frame.pack(fill="both", expand=True, pady=(4, 0))
        self._log = tk.Text(
            log_frame, height=8, wrap="word", state="disabled",
            font=("Consolas", 9), relief="flat", background="#f7f7f7",
        )
        scroll = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        self._log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._log.tag_configure("ok", foreground="#1a7a2e")
        self._log.tag_configure("fail", foreground="#b00020")

    def _add_param(self, parent, row, col, key, var, lo, hi, step, integer=False):
        self._reg(ttk.Label(parent), key).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=3)
        spin = ttk.Spinbox(
            parent, from_=lo, to=hi, increment=step, textvariable=var,
            width=8, format="%.0f" if integer else "%.2f",
        )
        spin.grid(row=row, column=col + 1, sticky="w", padx=(0, 18), pady=3)

    # --------------------------------------------------------------- actions

    def _pick_input(self) -> None:
        path = filedialog.askdirectory(title=self._t("input"))
        if path:
            self._input_dir.set(path)
            if not self._output_dir.get():
                self._output_dir.set(str(Path(path) / "tempmap_tif"))

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title=self._t("output"))
        if path:
            self._output_dir.set(path)

    def _restore_defaults(self) -> None:
        self._distance.set(DEFAULTS.distance)
        self._humidity.set(DEFAULTS.humidity)
        self._emissivity.set(DEFAULTS.emissivity)
        self._reflection.set(DEFAULTS.reflection)

    def _open_output(self) -> None:
        if self._last_output_dir and self._last_output_dir.exists():
            os.startfile(str(self._last_output_dir))  # noqa: S606 - local folder open

    def _update_found_count(self) -> None:
        raw = self._input_dir.get().strip()
        path = Path(raw) if raw else None
        if not path or not path.is_dir():
            self._found_label.configure(text="")
            return
        try:
            count = len(discover_rjpegs(path, recursive=self._recursive.get()))
        except Exception:
            self._found_label.configure(text="")
            return
        if count:
            self._found_label.configure(text=self._t("found_n", n=count))
        else:
            self._found_label.configure(text=self._t("found_none"))

    def _log_line(self, text: str, tag: str | None = None) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n", tag or ())
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self._start_btn.configure(state="disabled" if running else "normal")
        self._cancel_btn.configure(state="normal" if running else "disabled")

    def _start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        try:
            ensure_plugins_present()
        except FileNotFoundError as exc:
            messagebox.showerror(self._t("err_plugin"), str(exc))
            return

        raw_in = self._input_dir.get().strip()
        raw_out = self._output_dir.get().strip()
        input_dir = Path(raw_in) if raw_in else None
        output_dir = Path(raw_out) if raw_out else None
        if not input_dir or not input_dir.is_dir():
            messagebox.showerror(self._t("err_title"), self._t("err_input"))
            return
        if not output_dir:
            messagebox.showerror(self._t("err_title"), self._t("err_output"))
            return

        try:
            inputs = discover_rjpegs(input_dir, recursive=self._recursive.get())
        except Exception as exc:
            messagebox.showerror(self._t("err_title"), self._t("err_scan", err=exc))
            return
        if not inputs:
            messagebox.showwarning(self._t("err_none_title"), self._t("found_none"))
            return

        try:
            params = MeasurementParams(
                distance=float(self._distance.get()),
                humidity=float(self._humidity.get()),
                emissivity=float(self._emissivity.get()),
                reflection=float(self._reflection.get()),
            )
            workers = int(self._workers.get())
        except (tk.TclError, ValueError):
            messagebox.showerror(self._t("err_title"), self._t("err_scan", err="?"))
            return

        self._cancel_event.clear()
        self._last_output_dir = output_dir
        self._open_btn.configure(state="disabled")
        self._progress.configure(maximum=len(inputs), value=0)
        self._progress_label.configure(text=f"0/{len(inputs)}")
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._status_var.set(self._t("starting", n=len(inputs)))
        self._log_line(self._t("starting", n=len(inputs)))
        self._set_running(True)

        self._worker_thread = threading.Thread(
            target=self._run_batch,
            args=(inputs, input_dir, output_dir, params, workers),
            daemon=True,
        )
        self._worker_thread.start()

    def _run_batch(
        self,
        inputs: list[Path],
        inputs_root: Path,
        output_dir: Path,
        params: MeasurementParams,
        workers: int,
    ) -> None:
        def progress(done: int, total: int, result: ConversionResult) -> None:
            self._event_queue.put(("progress", done, total, result))

        try:
            results = batch_convert(
                inputs,
                output_dir,
                params=params,
                preserve_metadata=self._preserve_meta.get(),
                workers=workers,
                progress=progress,
                cancel=self._cancel_event,
                input_root=inputs_root,
            )
            ok = sum(1 for r in results if r.ok)
            fail = sum(1 for r in results if not r.ok)
            self._event_queue.put(("done", ok, fail, self._cancel_event.is_set()))
        except Exception as exc:
            self._event_queue.put(("error", str(exc)))

    def _cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled")
        self._status_var.set(self._t("cancelling"))
        self._log_line(self._t("cancelling"))

    def _poll_events(self) -> None:
        try:
            while True:
                event = self._event_queue.get_nowait()
                kind = event[0]
                if kind == "progress":
                    _, done, total, result = event
                    self._progress.configure(value=done)
                    self._progress_label.configure(text=f"{done}/{total}")
                    if result.ok:
                        self._log_line(
                            f"[{done}/{total}] {result.source.name}  •  {self._t('ok')}", "ok"
                        )
                    else:
                        self._log_line(
                            f"[{done}/{total}] {result.source.name}  •  "
                            f"{self._t('fail')}: {result.error}",
                            "fail",
                        )
                elif kind == "done":
                    _, ok, fail, cancelled = event
                    if cancelled:
                        msg = self._t("done_cancel", ok=ok)
                    elif fail:
                        msg = self._t("done_fail", ok=ok, fail=fail)
                    else:
                        msg = self._t("done_ok", ok=ok)
                    self._status_var.set(msg)
                    self._log_line(msg)
                    self._set_running(False)
                    if ok:
                        self._open_btn.configure(state="normal")
                elif kind == "error":
                    msg = self._t("fatal", err=event[1])
                    self._status_var.set(msg)
                    self._log_line(msg, "fail")
                    self._set_running(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)


def run() -> int:
    app = ConverterApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
