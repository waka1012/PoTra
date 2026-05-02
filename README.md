# PoTra — Podcast Transcriber

> **PoTra** stands for **Po**dcast + **Tra**nscriber.

PoTra is a desktop GUI tool that downloads podcast episodes from RSS feeds and transcribes them using [MLX-Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
Local audio files can also be transcribed directly.

**Apple Silicon (M1/M2/M3/M4) only.**

[日本語版 README](README.ja.md)

---

## Output Sample

```markdown
- [00:00:05] **Suzuki**: Could you tell us about today's topic?
- [00:00:12] **Tanaka**: Sure, today we'll be discussing the latest trends in generative AI.
- [00:00:30] **Suzuki**: Is there a particular area you're most excited about?
- [00:00:33] **Tanaka**: Definitely the advances in multimodal models.
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

## Vocabulary File (initial_prompt)

Placing `.txt` files in the `vocabularies/` directory lets you specify domain-specific words (proper nouns, technical terms, etc.) that Whisper should prefer during transcription.

**File format** (`vocabularies/my_terms.txt`):
```
# Lines starting with # are comments
田中
鈴木
ポッドキャスト
生成AI
```

Select the file from the **語彙** dropdown in the GUI. The token count is shown next to the dropdown:
- ✅ green: within the 200-token limit
- ⚠️ yellow: over the limit — words will be trimmed from the end

The words are joined with commas and passed as `initial_prompt` to Whisper. If no file is selected, `initial_prompt` is not set.

---

## Customizing the Output Format

Edit `formatter.py` to change the output format. Set `custom_formatter` to any function that takes a Whisper result and returns a string.

```python
# formatter.py

def custom_formatter(result):
    # result["text"]              : full transcript as a single string
    # result["segments"][n]["start"] : start time in seconds (float)
    # result["segments"][n]["end"]   : end time in seconds (float)
    # result["segments"][n]["text"]  : segment text
    ...
    return "your formatted string"

custom_formatter = custom_formatter  # enable your formatter
```

Setting `custom_formatter = None` (the default) uses the built-in formatter:
timestamped Markdown with automatic speaker detection.

**Example: plain text output**
```python
def custom_formatter(result):
    return result["text"].strip()

custom_formatter = custom_formatter
```

**Example: SRT subtitle format**
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

## Dependencies

```
mlx-whisper
feedparser
requests
```

---

## License

MIT
