# PoTra 出力フォーマットのカスタマイズファイル
#
# このファイルの custom_formatter 関数を編集すると、文字起こし結果の
# 出力形式を自由に変更できます。
#
# 引数 result は mlx_whisper.transcribe() の戻り値です。
#   result["text"]       : str   全文テキスト
#   result["segments"]   : list  セグメントのリスト
#     segment["start"]   : float 開始時刻（秒）
#     segment["end"]     : float 終了時刻（秒）
#     segment["text"]    : str   テキスト
#
# 戻り値として出力ファイルに書き込む文字列を返してください。
#
# カスタマイズしない場合は custom_formatter = None のままにしてください。
# その場合、デフォルト（タイムスタンプ＋話者検出 Markdown）が使われます。

# from worker import default_formatter  # デフォルト実装を参照したい場合


# ------------------------------------------------------------------ 例
# 例1: プレーンテキストで出力
# def custom_formatter(result):
#     return result["text"].strip()
#
# 例2: セグメントを SRT 字幕形式で出力
# def custom_formatter(result):
#     def fmt(s):
#         h, m = int(s // 3600), int((s % 3600) // 60)
#         return f"{h:02d}:{m:02d}:{int(s % 60):02d},{int(s * 1000 % 1000):03d}"
#     lines = []
#     for i, seg in enumerate(result["segments"], 1):
#         lines += [str(i), f"{fmt(seg['start'])} --> {fmt(seg['end'])}", seg["text"].strip(), ""]
#     return "\n".join(lines)
# ------------------------------------------------------------------


custom_formatter = None  # ← None のままだとデフォルト形式で出力されます
