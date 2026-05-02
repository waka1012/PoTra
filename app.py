import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import logging
import pathlib
import datetime
import re

from worker import run_task


def _natural_sort_key(s: str) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]

MODELS = [
    ("large-v3（高精度）", "mlx-community/whisper-large-v3-mlx"),
    ("large-v3-turbo（高速）", "mlx-community/whisper-large-v3-turbo"),
]


class PoTraApp:
    def __init__(self, root: tk.Tk, formatter=None):
        self.root = root
        self.root.title("PoTra")
        self.root.geometry("820x750")

        self.formatter = formatter  # None → worker.py の default_formatter が使われる
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
                "依存ライブラリが見つかりません",
                "以下のライブラリがインストールされていません:\n" + "\n".join(missing),
            )

    # ------------------------------------------------------------------ UI build

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        rss_frame = ttk.Frame(self.notebook)
        self.notebook.add(rss_frame, text="📡 RSSポッドキャスト")
        self._build_rss_tab(rss_frame)

        local_frame = ttk.Frame(self.notebook)
        self.notebook.add(local_frame, text="📁 ローカル")
        self._build_local_tab(local_frame)

        self._build_common_controls()

    def _build_rss_tab(self, parent: ttk.Frame):
        # RSS URL
        url_lf = ttk.LabelFrame(parent, text="RSS フィード URL")
        url_lf.pack(fill=tk.X, padx=8, pady=4)
        self.rss_url_var = tk.StringVar()
        ttk.Entry(url_lf, textvariable=self.rss_url_var).pack(
            fill=tk.X, padx=4, pady=4
        )

        # Keyword filter
        kw_lf = ttk.LabelFrame(parent, text="キーワードフィルタ（空欄で全件）")
        kw_lf.pack(fill=tk.X, padx=8, pady=4)
        kw_inner = ttk.Frame(kw_lf)
        kw_inner.pack(fill=tk.X, padx=4, pady=4)
        self.keyword_var = tk.StringVar()
        ttk.Entry(kw_inner, textvariable=self.keyword_var, width=40).pack(side=tk.LEFT)
        ttk.Button(kw_inner, text="🔍 検索", command=self._search_rss).pack(
            side=tk.LEFT, padx=4
        )
        self.rss_count_label = ttk.Label(kw_inner, text="")
        self.rss_count_label.pack(side=tk.RIGHT, padx=4)

        # Episode list
        ep_lf = ttk.LabelFrame(parent, text="エピソード一覧")
        ep_lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        btn_row = ttk.Frame(ep_lf)
        btn_row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(btn_row, text="全選択", command=self._select_all_episodes).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_row, text="全解除", command=self._deselect_all_episodes).pack(
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

        # Output folder
        out_row = ttk.Frame(parent)
        out_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(out_row, text="出力先フォルダ:").pack(side=tk.LEFT)
        self.rss_output_var = tk.StringVar(
            value=str(pathlib.Path.home() / "potra_transcripts")
        )
        ttk.Entry(out_row, textvariable=self.rss_output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(
            out_row,
            text="選択…",
            command=lambda: self._browse_folder(self.rss_output_var),
        ).pack(side=tk.LEFT)

    def _on_ep_inner_configure(self, _event):
        self.ep_canvas.configure(scrollregion=self.ep_canvas.bbox("all"))

    def _on_ep_canvas_configure(self, event):
        self.ep_canvas.itemconfig(self._ep_window, width=event.width)

    def _build_local_tab(self, parent: ttk.Frame):
        # File addition
        add_lf = ttk.LabelFrame(parent, text="ファイル・フォルダ追加")
        add_lf.pack(fill=tk.X, padx=8, pady=4)
        add_row = ttk.Frame(add_lf)
        add_row.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(
            add_row, text="📄 MP3ファイルを選択（複数可）", command=self._add_files
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            add_row, text="📁 フォルダを選択", command=self._add_folder
        ).pack(side=tk.LEFT, padx=4)

        # File list
        list_lf = ttk.LabelFrame(parent, text="ファイル一覧")
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
            ctrl_row, text="選択行を削除", command=self._remove_selected_files
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            ctrl_row, text="リストをクリア", command=self._clear_files
        ).pack(side=tk.LEFT, padx=2)
        self.local_count_label = ttk.Label(ctrl_row, text="0 件")
        self.local_count_label.pack(side=tk.RIGHT, padx=4)

        # Output folder
        out_row = ttk.Frame(parent)
        out_row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(out_row, text="出力先フォルダ:").pack(side=tk.LEFT)
        self.local_output_var = tk.StringVar(
            value=str(pathlib.Path.home() / "potra_transcripts")
        )
        ttk.Entry(out_row, textvariable=self.local_output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(
            out_row,
            text="選択…",
            command=lambda: self._browse_folder(self.local_output_var),
        ).pack(side=tk.LEFT)

    def _build_common_controls(self):
        ctrl_row = ttk.Frame(self.root)
        ctrl_row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(ctrl_row, text="モデル:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=MODELS[0][0])
        self.model_combo = ttk.Combobox(
            ctrl_row,
            textvariable=self.model_var,
            values=[m[0] for m in MODELS],
            state="readonly",
            width=28,
        )
        self.model_combo.pack(side=tk.LEFT, padx=4)
        self.start_btn = ttk.Button(
            ctrl_row, text="▶ 開始", command=self._start
        )
        self.start_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(
            ctrl_row, text="⏹ 中断", command=self._stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(self.root, textvariable=self.status_var).pack(
            fill=tk.X, padx=8, pady=(2, 0)
        )

        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            self.root, variable=self.progress_var, maximum=100
        ).pack(fill=tk.X, padx=8, pady=2)

        ttk.Label(
            self.root, text="ログ （ファイル保存先: ~/potra_logs/）"
        ).pack(anchor=tk.W, padx=8)

        self.log_area = scrolledtext.ScrolledText(
            self.root,
            height=9,
            state=tk.DISABLED,
            font=("Courier New", 10),
        )
        self.log_area.pack(fill=tk.X, padx=8, pady=(0, 8))

    # ------------------------------------------------------------------ RSS tab

    def _search_rss(self):
        url = self.rss_url_var.get().strip()
        if not url:
            messagebox.showwarning("エラー", "RSS URLを入力してください")
            return
        try:
            import feedparser
        except ImportError:
            messagebox.showerror("エラー", "feedparser がインストールされていません")
            return

        self._log(f"RSS 読み込み中: {url}")
        feed = feedparser.parse(url)
        keyword = self.keyword_var.get().strip()

        entries: list[tuple[str, str]] = []
        for entry in feed.entries:
            title = getattr(entry, "title", "")
            audio_url = ""
            for enc in getattr(entry, "enclosures", []):
                u = enc.get("url", "")
                t = enc.get("type", "")
                if "audio" in t or u.lower().endswith((".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg")):
                    audio_url = u
                    break
            if not audio_url:
                for link in getattr(entry, "links", []):
                    u = link.get("href", "")
                    t = link.get("type", "")
                    if "audio" in t or u.lower().endswith((".mp3", ".m4a")):
                        audio_url = u
                        break
            if not audio_url:
                continue
            if keyword and keyword.lower() not in title.lower():
                continue
            entries.append((title, audio_url))

        entries.sort(key=lambda x: _natural_sort_key(x[0]))

        count = len(entries)
        self._log(f"{count} 件見つかりました")
        if keyword:
            self.rss_count_label.config(text=f'{count} 件  キーワード: "{keyword}"')
        else:
            self.rss_count_label.config(text=f"{count} 件")

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
            ("音声ファイル", "*.mp3 *.m4a *.wav *.flac *.aac *.ogg"),
            ("すべて", "*"),
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
        self.local_count_label.config(text=f"{len(self.local_files)} 件")

    # ------------------------------------------------------------------ common

    def _browse_folder(self, var: tk.StringVar):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)

    def _start(self):
        tab_index = self.notebook.index(self.notebook.select())

        if tab_index == 0:
            items = [
                (title, url)
                for title, url, var in self.episode_vars
                if var.get()
            ]
            if not items:
                messagebox.showwarning("警告", "エピソードが選択されていません")
                return
            output_dir = pathlib.Path(self.rss_output_var.get())
            mode = "rss"
        else:
            if not self.local_files:
                messagebox.showwarning("警告", "ファイルが追加されていません")
                return
            items = [(p.stem, str(p)) for p in self.local_files]
            output_dir = pathlib.Path(self.local_output_var.get())
            mode = "local"

        try:
            import mlx_whisper  # noqa: F401
        except ImportError:
            messagebox.showerror("エラー", "mlx_whisper がインストールされていません")
            return

        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = next(p for n, p in MODELS if n == self.model_var.get())

        self.stop_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_var.set("待機中")

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
            kwargs={"formatter": self.formatter},
            daemon=True,
        ).start()

    def _stop(self):
        self.stop_requested = True
        self.status_var.set("中断中…（現在の処理が終わり次第停止）")
        self.stop_btn.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ queue polling

    def _poll_ui_queue(self):
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
                        f"完了: {ok} 件 / スキップ: {skip} 件 / エラー: {err} 件"
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
