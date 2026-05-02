# PoTra — Podcast Transcriber

> **PoTra** は **Po**dcast + **Tra**nscriber の略です。

ポッドキャストのRSSフィードからエピソードをダウンロードし、[MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) で文字起こしするデスクトップGUIツールです。  
ローカルの音声ファイルを直接指定して文字起こしすることもできます。

**Apple Silicon（M1/M2/M3/M4）専用です。**

---

## 出力サンプル

```markdown
- [00:00:05] **鈴木**: 今日のテーマについて教えてもらえますか？
- [00:00:12] **田中**: はい、今回は生成AIの最新動向についてお話しします。
- [00:00:30] **鈴木**: 特に注目しているポイントはありますか？
- [00:00:33] **田中**: やはりマルチモーダルの進化が面白いですね。
```

話者名はテキスト中に出現するパターンから自動検出します。  
タイムスタンプ付きMarkdownで出力するため、生成AIへの入力としても活用できます。

---

## 動作環境

- macOS（Apple Silicon: M1/M2/M3/M4）
- Python 3.10 以上

---

## インストール

```bash
git clone https://github.com/waka1012/PoTra.git
cd PoTra

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

> **Note**  
> Homebrew の Python を使う場合、tkinter のために `python-tk` が必要です。
> ```bash
> brew install python-tk@3.12
> ```

---

## 起動

```bash
source .venv/bin/activate
python main.py
```

---

## 使い方

### RSSポッドキャスト

1. **RSS フィード URL** にポッドキャストのRSS URLを入力
2. キーワードフィルタで絞り込み（空欄で全件）→ **🔍 検索**
3. 文字起こしするエピソードにチェックを入れる
4. 出力先フォルダを確認
5. モデルを選択して **▶ 開始**

### ローカルファイル

1. **📄 MP3ファイルを選択** または **📁 フォルダを選択** でファイルを追加
2. 出力先フォルダを確認
3. モデルを選択して **▶ 開始**

---

## モデル

| 表示名 | HuggingFace リポジトリ | 特徴 |
|---|---|---|
| large-v3（高精度） | `mlx-community/whisper-large-v3-mlx` | 高精度、低速 |
| large-v3-turbo（高速） | `mlx-community/whisper-large-v3-turbo` | やや低精度、高速 |

初回実行時にモデルが自動ダウンロードされます（large-v3 は約3GB）。  
ダウンロード先: `~/.cache/huggingface/hub/`

---

## 出力

| 種類 | 保存先 |
|---|---|
| 文字起こし（Markdown） | `~/potra_transcripts/<エピソード名>.md` |
| 処理ログ | `~/potra_logs/potra_YYYYMMDD_HHMMSS.log` |

- 既存の `.md` ファイルはスキップされます（途中中断・再実行が安全）
- RSSでダウンロード済みの `.mp3` は再ダウンロードされません

---

## 表示言語の切り替え

プロジェクトルートの `config.json` を編集して `language` の値を変更してください：

```json
{ "language": "ja" }
```

| 値 | 言語 |
|---|---|
| `"ja"` | 日本語（デフォルト） |
| `"en"` | English |

保存後にアプリを再起動すると、ラベル・ボタン・ステータス・ログなどすべての表示が切り替わります。

---

## 語彙ファイル（initial_prompt）

`vocabularies/` ディレクトリに `.txt` ファイルを置くことで、固有名詞や専門用語を Whisper に認識させやすくできます。

**ファイル形式**（`vocabularies/my_terms.txt`）:
```
# # で始まる行はコメントとして無視されます
田中
鈴木
ポッドキャスト
生成AI
```

GUIの **語彙** ドロップダウンでファイルを選択してください。隣にトークン数が表示されます：
- ✅ 緑：200トークン以内（制限内）
- ⚠️ 黄：200トークン超 — 末尾の単語から切り捨てられます

単語はカンマ区切りで結合され、Whisper の `initial_prompt` として渡されます。「なし」を選択した場合は `initial_prompt` は設定されません。

---

## 出力フォーマットのカスタマイズ

`formatter.py` を編集することで、出力形式を自由に変更できます。  
`custom_formatter` に関数を設定するだけです。

```python
# formatter.py

def custom_formatter(result):
    # result["text"]                 : 全文テキスト（str）
    # result["segments"][n]["start"] : 開始時刻（秒、float）
    # result["segments"][n]["end"]   : 終了時刻（秒、float）
    # result["segments"][n]["text"]  : セグメントのテキスト
    ...
    return "出力したい文字列"

custom_formatter = custom_formatter  # 有効化
```

`custom_formatter = None`（デフォルト）のままにすると、組み込みフォーマッタ（タイムスタンプ＋話者検出 Markdown）が使われます。

**例1: プレーンテキストで出力**
```python
def custom_formatter(result):
    return result["text"].strip()

custom_formatter = custom_formatter
```

**例2: SRT 字幕形式で出力**
```python
def custom_formatter(result):
    def fmt(s):
        h, m = int(s // 3600), int((s % 3600) // 60)
        return f"{h:02d}:{m:02d}:{int(s % 60):02d},{int(s * 1000 % 1000):03d}"
    lines = []
    for i, seg in enumerate(result["segments"], 1):
        lines += [str(i), f"{fmt(seg['start'])} --> {fmt(seg['end'])}", seg["text"].strip(), ""]
    return "\n".join(lines)

custom_formatter = custom_formatter
```

---

## 依存ライブラリ

```
mlx-whisper
feedparser
requests
```

---

## ライセンス

MIT
