# PoTra — Podcast Transcriber

> **PoTra** は **Po**dcast + **Tra**nscriber の略です。

ポッドキャストのRSSフィードからエピソードをダウンロードし、[MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) で文字起こしするデスクトップGUIツールです。  
ローカルの音声ファイルを直接指定して文字起こしすることもできます。

**Apple Silicon（M1/M2/M3/M4）専用です。**

---

## 出力サンプル

```markdown
- [00:00:05] **深井**: はい同じ株式会社コテンの陽英史です
- [00:00:12] **樋口**: このラジオは歴史を愛し歴史の面白さを知りすぎてしまった
- [00:00:30] **深井**: 3日間ありますね
- [00:00:33] **樋口**: 大体3日やってるんですけど
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

## 依存ライブラリ

```
mlx-whisper
feedparser
requests
```

---

## ライセンス

MIT
