# PoTra — Podcast Transcriber

> **PoTra** stands for **Po**dcast + **Tra**nscriber.

PoTra is a desktop GUI tool that downloads podcast episodes from RSS feeds and transcribes them using [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
Local audio files can also be transcribed directly.

**Apple Silicon (M1/M2/M3/M4) only.**

[日本語版 README](README.ja.md)

---

## Output Sample

```markdown
- [00:00:05] **Fukui**: This is a history curation program...
- [00:00:12] **Higuchi**: Welcome to Coten Radio...
- [00:00:30] **Fukui**: Let's get started.
- [00:00:33] **Higuchi**: Yes, let's dive in.
```

Speaker names are automatically detected from patterns in the transcribed text.
The timestamped Markdown output is also well-suited as input for LLMs.

---

## Requirements

- macOS (Apple Silicon: M1/M2/M3/M4)
- Python 3.10+

---

## Installation

```bash
git clone https://github.com/waka1012/PoTra.git
cd PoTra

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

> **Note**
> If you are using Homebrew Python, you need `python-tk` for tkinter support:
> ```bash
> brew install python-tk@3.12
> ```

---

## Launch

```bash
source .venv/bin/activate
python main.py
```

---

## Usage

### RSS Podcast

1. Enter the podcast RSS feed URL
2. Filter by keyword (leave blank for all episodes) → click **🔍 Search**
3. Check the episodes you want to transcribe
4. Confirm the output folder
5. Select a model and click **▶ Start**

### Local Files

1. Add files via **📄 Select MP3 files** or **📁 Select folder**
2. Confirm the output folder
3. Select a model and click **▶ Start**

---

## Models

| Name | HuggingFace repo | Notes |
|---|---|---|
| large-v3 (accurate) | `mlx-community/whisper-large-v3-mlx` | High accuracy, slower |
| large-v3-turbo (fast) | `mlx-community/whisper-large-v3-turbo` | Slightly lower accuracy, faster |

Models are downloaded automatically on first use (large-v3 is ~3 GB).
Cache location: `~/.cache/huggingface/hub/`

---

## Output

| Type | Location |
|---|---|
| Transcript (Markdown) | `~/potra_transcripts/<episode-title>.md` |
| Processing log | `~/potra_logs/potra_YYYYMMDD_HHMMSS.log` |

- Existing `.md` files are skipped, making it safe to stop and resume at any time.
- Already-downloaded `.mp3` files are not re-downloaded.

---

## Dependencies

```
mlx-whisper
feedparser
requests
```

---

## License

MIT
