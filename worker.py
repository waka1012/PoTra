import pathlib
import re
from collections import Counter


def _safe_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "", title)
    name = name[:80].strip()
    return name


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _detect_speakers(text: str) -> set[str]:
    """
    テキスト中で「漢字/カタカナ始まりの短い語 + スペース + 続く内容」パターンが
    3回以上現れる語を話者名として検出する。
    日本語名は漢字かカタカナで始まることを利用して前の発言末尾との混入を防ぐ。
    """
    # 漢字またはカタカナで始まり、1〜4文字後続（最大5文字の名前）
    candidates = re.findall(r'([一-龯ァ-ヶ][一-龯ぁ-んァ-ヶ]{0,4})\s(?=\S)', text)
    counter = Counter(candidates)
    return {name for name, count in counter.items() if count >= 3}


def _extract_items(
    ts: str, text: str, speakers: set[str], current_speaker: str | None
) -> tuple[list[tuple[str, str | None, str]], str | None]:
    """1セグメントを (timestamp, speaker, text) タプルのリストに変換する。
    話者切り替えが検出されない場合は current_speaker を引き継ぐ。"""
    text = text.strip()
    if not text:
        return [], current_speaker

    if not speakers:
        return [(ts, current_speaker, text)], current_speaker

    sp_pat = (
        "("
        + "|".join(re.escape(s) for s in sorted(speakers, key=len, reverse=True))
        + r")\s(?=\S)"
    )
    parts = re.split(sp_pat, text)

    if len(parts) == 1:
        return [(ts, current_speaker, text)], current_speaker

    items: list[tuple[str, str | None, str]] = []
    last_speaker = current_speaker

    intro = parts[0].strip()
    if intro:
        items.append((ts, last_speaker, intro))

    for i in range(1, len(parts) - 1, 2):
        speaker = parts[i]
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            items.append((ts, speaker, content))
            last_speaker = speaker

    return items, last_speaker


_JP_RE = re.compile(r'[ぁ-んァ-ヶ一-龯]')
_JP_END = frozenset("。！？…")
_EN_END = frozenset(".!?")


def _join_sep(text: str) -> str:
    """テキストの言語に応じたセグメント結合用の区切り文字を返す。
    既に句読点で終わっている場合は区切りを追加しない。"""
    t = text.rstrip()
    if _JP_RE.search(t):
        return "" if (t and t[-1] in _JP_END) else "。"
    else:
        return "" if (t and t[-1] in _EN_END) else ". "


def _merge_consecutive(
    items: list[tuple[str, str | None, str]],
) -> list[tuple[str, str | None, str]]:
    """同一話者の連続アイテムを結合して1行にまとめる。
    タイムスタンプは連続セグメントの先頭を使用する。
    日本語は「。」、英語は「. 」で文を区切る。"""
    if not items:
        return []
    merged = []
    cur_ts, cur_speaker, cur_text = items[0]
    for ts, speaker, text in items[1:]:
        if speaker == cur_speaker:
            cur_text = cur_text + _join_sep(cur_text) + text
        else:
            merged.append((cur_ts, cur_speaker, cur_text))
            cur_ts, cur_speaker, cur_text = ts, speaker, text
    merged.append((cur_ts, cur_speaker, cur_text))
    return merged


def _to_markdown(segments: list, full_text: str) -> str:
    """セグメントごとにタイムスタンプ＋話者名で出力する。
    同一話者の連続セグメントはマージして1行にまとめる。"""
    speakers = _detect_speakers(full_text)

    if not segments:
        return full_text.strip()

    all_items: list[tuple[str, str | None, str]] = []
    current_speaker: str | None = None
    for seg in segments:
        ts = _format_timestamp(seg["start"])
        seg_items, current_speaker = _extract_items(
            ts, seg["text"], speakers, current_speaker
        )
        all_items.extend(seg_items)

    lines = []
    for ts, speaker, text in _merge_consecutive(all_items):
        if speaker:
            lines.append(f"- [{ts}] **{speaker}**: {text}")
        else:
            lines.append(f"- [{ts}] {text}")

    return "\n".join(lines)


def parse_vocab_file(path: pathlib.Path) -> list[str]:
    """語彙ファイルを読み込み、コメント・空行を除いた単語リストを返す。"""
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def build_initial_prompt(vocab_path: pathlib.Path | None, token_limit: int = 200) -> str | None:
    """語彙ファイルから initial_prompt を生成する。token_limit 超の単語は末尾から切り捨て。"""
    if vocab_path is None or not vocab_path.exists():
        return None
    words = parse_vocab_file(vocab_path)
    if not words:
        return None

    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        while words and len(enc.encode(", ".join(words))) > token_limit:
            words.pop()
    except ImportError:
        pass  # tiktoken なしの場合は切り捨てなしで全単語を使用

    return ", ".join(words) if words else None


def count_vocab_tokens(vocab_path: pathlib.Path) -> int | None:
    """語彙ファイルのトークン数を返す。tiktoken 未インストール時は None。"""
    try:
        import tiktoken
        words = parse_vocab_file(vocab_path)
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(", ".join(words)))
    except ImportError:
        return None


def default_formatter(result: dict) -> str:
    """デフォルトの出力フォーマッタ。

    カスタマイズする場合は、同じシグネチャを持つ関数を定義して
    main.py の PoTraApp(root, formatter=...) に渡してください。

    Args:
        result: mlx_whisper.transcribe() の戻り値。主なキー:
            result["text"]     : str   全文テキスト
            result["segments"] : list  セグメントのリスト
                segment["start"] : float  開始時刻（秒）
                segment["end"]   : float  終了時刻（秒）
                segment["text"]  : str    テキスト

    Returns:
        出力ファイルに書き込む文字列。
    """
    return _to_markdown(result.get("segments", []), result.get("text", ""))


def run_task(items, mode, output_dir, model_path, ui_queue, stop_check, file_logger,
             formatter=None, vocab_path=None):
    if formatter is None:
        formatter = default_formatter

    initial_prompt = build_initial_prompt(vocab_path)

    total = len(items)
    ok = skip = error = 0

    def log(text):
        ui_queue.put({"type": "log", "text": text})
        file_logger.info(text) if text else file_logger.debug("")

    def status(text):
        ui_queue.put({"type": "status", "text": text})

    def progress(value):
        ui_queue.put({"type": "progress", "value": value})

    log("=" * 50)
    log(f"処理開始  全 {total} 件 | モデル: {model_path}")
    log(f"出力先: {output_dir}")
    if initial_prompt:
        log(f"initial_prompt: {initial_prompt}")
    log("=" * 50)
    log("")

    for i, (title, source) in enumerate(items, 1):
        if stop_check():
            log("中断されました")
            break

        progress((i - 1) / total * 100)
        status(f"({i}/{total}) {title}")

        safe_name = _safe_filename(title)
        out_path = pathlib.Path(output_dir) / f"{safe_name}.md"

        log(f"[{i}/{total}] {title}")

        if out_path.exists():
            log(f"  スキップ（既存）: {out_path.name}")
            skip += 1
            log("")
            continue

        if mode == "rss":
            mp3_path = pathlib.Path(output_dir) / f"{safe_name}.mp3"
            if not mp3_path.exists():
                log("  ダウンロード中…")
                tmp_path = mp3_path.with_suffix(".mp3.tmp")
                interrupted = False
                try:
                    import requests
                    resp = requests.get(source, stream=True, timeout=120)
                    resp.raise_for_status()
                    with open(tmp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if stop_check():
                                interrupted = True
                                break
                            if chunk:
                                f.write(chunk)
                except Exception as e:
                    tmp_path.unlink(missing_ok=True)
                    log(f"  ダウンロードエラー: {e}")
                    file_logger.error(f"ダウンロードエラー [{title}]: {e}")
                    error += 1
                    log("")
                    continue

                if interrupted:
                    tmp_path.unlink(missing_ok=True)
                    log("  ダウンロード中断")
                    log("")
                    break

                tmp_path.rename(mp3_path)
                size_mb = mp3_path.stat().st_size / 1024 / 1024
                log(f"  ダウンロード完了: {mp3_path.name} ({size_mb:.1f} MB)")
            audio_file = str(mp3_path)
        else:
            audio_file = source

        log("  文字起こし中…")
        try:
            import mlx_whisper
            transcribe_kwargs = dict(
                path_or_hf_repo=model_path,
                language="ja",
                word_timestamps=False,
            )
            if initial_prompt:
                transcribe_kwargs["initial_prompt"] = initial_prompt
            result = mlx_whisper.transcribe(audio_file, **transcribe_kwargs)
            md_text = formatter(result)
            out_path.write_text(md_text, encoding="utf-8")
            log(f"  → 完了: {out_path.name}")
            ok += 1
        except Exception as e:
            log(f"  文字起こしエラー: {e}")
            file_logger.error(f"文字起こしエラー [{title}]: {e}")
            error += 1

        log("")

    ui_queue.put({"type": "done", "ok": ok, "skip": skip, "error": error})
