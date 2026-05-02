import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import logging
import pathlib
import datetime
import re
import json

from worker import run_task, count_vocab_tokens

VOCAB_DIR = pathlib.Path(__file__).parent / "vocabularies"
VOCAB_TOKEN_LIMIT = 200

# (locale_key, model_path)
MODEL_PATHS = [
    ("model_large_v3",       "mlx-community/whisper-large-v3-mlx"),
    ("model_large_v3_turbo", "mlx-community/whisper-large-v3-turbo"),
]


def _natural_sort_key(s: str) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def _load_locale() -> dict:
    base = pathlib.Path(__file__).parent
    lang = "en"
    config_path = base / "config.json"
    if config_path.exists():
        try:
            lang = json.loads(config_path.read_text(encoding="utf-8")).get("language", "en")
        except Exception:
            pass
    locale_path = base / "locale" / f"{lang}.json"
    if not locale_path.exists():
        locale_path = base / "locale" / "en.json"
    return json.loads(locale_path.read_text(encoding="utf-8"))


class PoTraApp:
    def __init__(self, root: tk.Tk, formatter=None):
        self.root = root
        self.t = _load_locale()
        self.root.title(self.t["window_title"])
        self.root.geometry("820x750")

        self.formatter = formatter
        self.ui_queue: queue.Queue = queue.Queue()
        self.stop_requested = False
        self.local_files: list[pathlib.Path] = []
        self.episode_vars: list[tuple[str, str, tk.BooleanVar]] = []

        self._setup_logging()
        self._check_dependencies()
        self._build_ui()
        self._poll_ui_queue()

    # ------------------------------------------------------------------ logging

    def _setup_logging(self):
        log_dir = pathlib.Path.home() / "potra_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"potra_{ts}.log"

        self.file_logger = logging.getLogger(f"potra.{ts}")
        self.file_logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        self.file_logger.addHandler(handler)
        self.file_logger.propagate = False

    def _check_dependencies(self):
        missing = []
        for lib in ("feedparser", "requests", "mlx_whisper"):
            try:
                __import__(lib)
            except ImportError:
                missing.append(lib)
        if missing:
            messagebox.showwarning(
                self.t["dlg_missing_libs_title"],
                self.t["dlg_missing_libs_msg"].format(libs="\n".join(missing)),
            )

    # ------------------------------------------------------------------ UI build

    def _build_ui(self):
        t = self.t
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        rss_frame = ttk.Frame(self.notebook)
        self.notebook.add(rss_frame, text=t["tab_rss"])
        self._build_rss_tab(rss_frame)

        local_frame = ttk.Frame(self.notebook)
        self.notebook.add(local_frame, text=t["tab_local"])
        self._build_local_tab(local_frame)

        self._build_common_controls()

    def _build_rss_tab(self, parent: ttk.Frame):
        t = self.t

        url_lf = ttk.LabelFrame(parent, text=t["lf_rss_url"])
        url_lf.pack(fill=tk.X, padx=8, pady=4)
        self.rss_url_var = tk.StringVar()
        ttk.Entry(url_lf, textvariable=self.rss_url_var).pack(
            fill=tk.X, padx=4, pady=4
        )

        kw_lf = ttk.LabelFrame(parent, text=t["lf_keyword"])
        kw_lf.pack(fill=tk.X, padx=8, pady=4)
        kw_inner = ttk.Frame(kw_lf)
        kw_inner.pack(fill=tk.X, padx=4, pady=4)
        self.keyword_var = tk.StringVar()
        ttk.Entry(kw_inner, textvariable=self.keyword_var, width=40).pack(side=tk.LEFT)
        ttk.Button(kw_inner, text=t["btn_search"], command=self._search_rss).pack(
            side=tk.LEFT, padx=4
        )
        self.rss_count_label = ttk.Label(kw_inner, text="")
        self.rss_count_label.pack(side=tk.RIGHT, padx=4)

        ep_lf = ttk.LabelFrame(parent, text=t["lf_episodes"])
        ep_lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_row = ttk.Frame(ep_lf)
        btn_row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_row, text=t["btn_select_all"], command=self._select_all_episodes).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_row, text=t["btn_deselect_all"], command=self._deselect_all_episodes).pack(
            side=tk.LEFT, padx=2
        )

        canvas_outer = ttk.Frame(ep_lf)
        canvas_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.ep_canvas = tk.Canvas(canvas_outer, highlightthickness=0)
        ep_scroll = ttk.Scrollbar(
            canvas_outer, orient=tk.VERTICAL, command=self.ep_canvas.yview
        )
        self.ep_canvas.configure(yscrollcommand=ep_scroll.set)
        ep_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ep_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.ep_inner = ttk.Frame(self.ep_canvas)
        self._ep_window = self.ep_canvas.create_window(
            (0, 0), window=self.ep_inner, anchor="nw"
        )
        self.ep_inner.bind("<Configure>", self._on_ep_inner_configure)
        self.ep_canvas.bind("<Configure>", self._on_ep_canvas_configure)

        out_row = ttk.Frame(parent)
        out_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(out_row, text=t["label_output"]).pack(side=tk.LEFT)
        self.rss_output_var = tk.StringVar(
            value=str(pathlib.Path.home() / "potra_transcripts")
        )
        ttk.Entry(out_row, textvariable=self.rss_output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(
            out_row,
            text=t["btn_browse"],
            command=lambda: self._browse_folder(self.rss_output_var),
        ).pack(side=tk.LEFT)

    def _on_ep_inner_configure(self, _event):
        self.ep_canvas.configure(scrollregion=self.ep_canvas.bbox("all"))

    def _on_ep_canvas_configure(self, event):
        self.ep_canvas.itemconfig(self._ep_window, width=event.width)

    def _build_local_tab(self, parent: ttk.Frame):
        t = self.t

        add_lf = ttk.LabelFrame(parent, text=t["lf_add_files"])
        add_lf.pack(fill=tk.X, padx=8, pady=4)
        add_row = ttk.Frame(add_lf)
        add_row.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(
            add_row, text=t["btn_add_files"], command=self._add_files
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            add_row, text=t["btn_add_folder"], command=self._add_folder
        ).pack(side=tk.LEFT, padx=4)

        list_lf = ttk.LabelFrame(parent, text=t["lf_file_list"])
        list_lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        lb_frame = ttk.Frame(list_lf)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        lb_scroll = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox = tk.Listbox(
            lb_frame, selectmode=tk.EXTENDED, yscrollcommand=lb_scroll.set
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scroll.config(command=self.file_listbox.yview)

        ctrl_row = ttk.Frame(list_lf)
        ctrl_row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(
            ctrl_row, text=t["btn_remove_selected"], command=self._remove_selected_files
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            ctrl_row, text=t["btn_clear_list"], command=self._clear_files
        ).pack(side=tk.LEFT, padx=2)
        self.local_count_label = ttk.Label(
            ctrl_row, text=t["count_items"].format(n=0)
        )
        self.local_count_label.pack(side=tk.RIGHT, padx=4)

        out_row = ttk.Frame(parent)
        out_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(out_row, text=t["label_output"]).pack(side=tk.LEFT)
        self.local_output_var = tk.StringVar(
            value=str(pathlib.Path.home() / "potra_transcripts")
        )
        ttk.Entry(out_row, textvariable=self.local_output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(
            out_row,
            text=t["btn_browse"],
            command=lambda: self._browse_folder(self.local_output_var),
        ).pack(side=tk.LEFT)

    def _build_common_controls(self):
        t = self.t
        model_names = [t[key] for key, _ in MODEL_PATHS]

        # 1行目: モデル選択・開始・中断
        ctrl_row = ttk.Frame(self.root)
        ctrl_row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(ctrl_row, text=t["label_model"]).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=model_names[0])
        self.model_combo = ttk.Combobox(
            ctrl_row,
            textvariable=self.model_var,
            values=model_names,
            state="readonly",
            width=28,
        )
        self.model_combo.pack(side=tk.LEFT, padx=4)
        self.start_btn = ttk.Button(ctrl_row, text=t["btn_start"], command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(
            ctrl_row, text=t["btn_stop"], command=self._stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        # 2行目: 語彙ファイル選択
        vocab_row = ttk.Frame(self.root)
        vocab_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Label(vocab_row, text=t["label_vocab"]).pack(side=tk.LEFT)
        self.vocab_var = tk.StringVar(value=t["vocab_none"])
        self.vocab_combo = ttk.Combobox(
            vocab_row, textvariable=self.vocab_var, state="readonly", width=24
        )
        self.vocab_combo.pack(side=tk.LEFT, padx=4)
        self.vocab_combo.bind("<<ComboboxSelected>>", self._on_vocab_changed)
        self.vocab_token_label = tk.Label(vocab_row, text="")
        self.vocab_token_label.pack(side=tk.LEFT, padx=4)
        self._load_vocab_files()

        self.status_var = tk.StringVar(value=t["status_idle"])
        ttk.Label(self.root, textvariable=self.status_var).pack(
            fill=tk.X, padx=8, pady=(2, 0)
        )

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            self.root, variable=self.progress_var, maximum=100
        ).pack(fill=tk.X, padx=8, pady=2)

        ttk.Label(self.root, text=t["label_log"]).pack(anchor=tk.W, padx=8)

        self.log_area = scrolledtext.ScrolledText(
            self.root,
            height=9,
            state=tk.DISABLED,
            font=("Courier New", 10),
        )
        self.log_area.pack(fill=tk.X, padx=8, pady=(0, 8))

    # ------------------------------------------------------------------ RSS tab

    def _search_rss(self):
        t = self.t
        url = self.rss_url_var.get().strip()
        if not url:
            messagebox.showwarning(t["dlg_error"], t["dlg_no_rss_url"])
            return
        try:
            import feedparser
        except ImportError:
            messagebox.showerror(t["dlg_error"], t["dlg_no_feedparser"])
            return

        self._log(t["log_rss_loading"].format(url=url))
        feed = feedparser.parse(url)
        keyword = self.keyword_var.get().strip()

        entries: list[tuple[str, str]] = []
        for entry in feed.entries:
            title = getattr(entry, "title", "")
            audio_url = ""
            for enc in getattr(entry, "enclosures", []):
                u = enc.get("url", "")
                tp = enc.get("type", "")
                if "audio" in tp or u.lower().endswith((".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg")):
                    audio_url = u
                    break
            if not audio_url:
                for link in getattr(entry, "links", []):
                    u = link.get("href", "")
                    tp = link.get("type", "")
                    if "audio" in tp or u.lower().endswith((".mp3", ".m4a")):
                        audio_url = u
                        break
            if not audio_url:
                continue
            if keyword and keyword.lower() not in title.lower():
                continue
            entries.append((title, audio_url))

        entries.sort(key=lambda x: _natural_sort_key(x[0]))

        count = len(entries)
        self._log(t["log_rss_found"].format(count=count))
        if keyword:
            self.rss_count_label.config(
                text=t["count_keyword"].format(n=count, keyword=keyword)
            )
        else:
            self.rss_count_label.config(text=t["count_all"].format(n=count))

        for widget in self.ep_inner.winfo_children():
            widget.destroy()
        self.episode_vars.clear()

        for title, audio_url in entries:
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(self.ep_inner, text=title, variable=var).pack(
                anchor=tk.W, fill=tk.X
            )
            self.episode_vars.append((title, audio_url, var))

    def _select_all_episodes(self):
        for _, _, var in self.episode_vars:
            var.set(True)

    def _deselect_all_episodes(self):
        for _, _, var in self.episode_vars:
            var.set(False)

    # ------------------------------------------------------------------ Local tab

    def _add_files(self):
        filetypes = [
            ("Audio files", "*.mp3 *.m4a *.wav *.flac *.aac *.ogg"),
            ("All files", "*"),
        ]
        paths = filedialog.askopenfilenames(filetypes=filetypes)
        for p in paths:
            path = pathlib.Path(p)
            if path not in self.local_files:
                self.local_files.append(path)
                self.file_listbox.insert(tk.END, path.name)
        self._update_local_count()

    def _add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        for p in pathlib.Path(folder).glob("*.mp3"):
            if p not in self.local_files:
                self.local_files.append(p)
                self.file_listbox.insert(tk.END, p.name)
        self._update_local_count()

    def _remove_selected_files(self):
        for i in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(i)
            del self.local_files[i]
        self._update_local_count()

    def _clear_files(self):
        self.file_listbox.delete(0, tk.END)
        self.local_files.clear()
        self._update_local_count()

    def _update_local_count(self):
        self.local_count_label.config(
            text=self.t["count_items"].format(n=len(self.local_files))
        )

    # ------------------------------------------------------------------ vocab

    def _load_vocab_files(self):
        t = self.t
        files = [t["vocab_none"]]
        if VOCAB_DIR.exists():
            files += sorted(f.name for f in VOCAB_DIR.glob("*.txt"))
        self.vocab_combo["values"] = files
        if self.vocab_var.get() not in files:
            self.vocab_var.set(t["vocab_none"])

    def _on_vocab_changed(self, _event=None):
        t = self.t
        name = self.vocab_var.get()
        if name == t["vocab_none"]:
            self.vocab_token_label.config(text="")
            return
        vocab_path = VOCAB_DIR / name
        count = count_vocab_tokens(vocab_path)
        if count is None:
            self.vocab_token_label.config(text=t["vocab_no_tiktoken"], fg="gray")
        elif count <= VOCAB_TOKEN_LIMIT:
            self.vocab_token_label.config(
                text=t["vocab_token_ok"].format(count=count, limit=VOCAB_TOKEN_LIMIT),
                fg="green",
            )
        else:
            self.vocab_token_label.config(
                text=t["vocab_token_over"].format(count=count, limit=VOCAB_TOKEN_LIMIT),
                fg="#CC8800",
            )

    # ------------------------------------------------------------------ common

    def _browse_folder(self, var: tk.StringVar):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)

    def _start(self):
        t = self.t
        tab_index = self.notebook.index(self.notebook.select())

        if tab_index == 0:
            items = [
                (title, url)
                for title, url, var in self.episode_vars
                if var.get()
            ]
            if not items:
                messagebox.showwarning(t["dlg_warning"], t["dlg_no_episodes"])
                return
            output_dir = pathlib.Path(self.rss_output_var.get())
            mode = "rss"
        else:
            if not self.local_files:
                messagebox.showwarning(t["dlg_warning"], t["dlg_no_files"])
                return
            items = [(p.stem, str(p)) for p in self.local_files]
            output_dir = pathlib.Path(self.local_output_var.get())
            mode = "local"

        try:
            import mlx_whisper  # noqa: F401
        except ImportError:
            messagebox.showerror(t["dlg_error"], t["dlg_no_mlx_whisper"])
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = MODEL_PATHS[self.model_combo.current()][1]

        vocab_name = self.vocab_var.get()
        vocab_path = (VOCAB_DIR / vocab_name) if vocab_name != t["vocab_none"] else None

        self.stop_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_var.set(t["status_idle"])

        threading.Thread(
            target=run_task,
            args=(
                items,
                mode,
                output_dir,
                model_path,
                self.ui_queue,
                lambda: self.stop_requested,
                self.file_logger,
            ),
            kwargs={
                "formatter": self.formatter,
                "vocab_path": vocab_path,
                "messages": t,
            },
            daemon=True,
        ).start()

    def _stop(self):
        self.stop_requested = True
        self.status_var.set(self.t["status_stopping"])
        self.stop_btn.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ queue polling

    def _poll_ui_queue(self):
        t = self.t
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                mtype = msg.get("type")
                if mtype == "log":
                    self._append_log(msg["text"])
                elif mtype == "status":
                    self.status_var.set(msg["text"])
                elif mtype == "progress":
                    self.progress_var.set(msg["value"])
                elif mtype == "done":
                    ok, skip, err = msg["ok"], msg["skip"], msg["error"]
                    self.status_var.set(
                        t["status_done"].format(ok=ok, skip=skip, error=err)
                    )
                    self.progress_var.set(100)
                    self.start_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui_queue)

    # ------------------------------------------------------------------ log helpers

    def _append_log(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n" if text else f"[{ts}]\n"
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, line)
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def _log(self, text: str):
        self._append_log(text)
        self.file_logger.info(text)
