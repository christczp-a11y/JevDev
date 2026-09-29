"""A 版：Edge TTS 基准（用主环境 .venv 跑）。
  .venv/Scripts/python experiments/tts_compare/gen_edge.py
输出 video/out/tts_compare/A_edge_<序号>_<角色>.mp3（同时转成 wav 便于对比）。
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import edge_tts

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES, SECOND  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"
OUT.mkdir(parents=True, exist_ok=True)


async def save(text, voice, rate, pitch, mp3):
    # Edge 偶尔不回音频，重试几次
    for i in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(mp3))
            return
        except edge_tts.exceptions.NoAudioReceived:
            print("retry", mp3.name, i + 1)
            await asyncio.sleep(1.5)
    raise RuntimeError(f"Edge 没有返回音频：{mp3.name}")


async def main():
    jobs = [(ln["text"], ln["edge"], OUT / f"A_edge_{ln['id']}_{ln['who']}.mp3") for ln in LINES]
    jobs += [(SECOND[ln["who"]], ln["edge"], OUT / f"A2_edge_{ln['who']}_第二句.mp3") for ln in LINES]
    for text, (voice, rate, pitch), mp3 in jobs:
        wav = mp3.with_suffix(".wav")
        if wav.exists():
            continue
        await save(text, voice, rate, pitch, mp3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(wav)], check=True)
        mp3.unlink()
        print("ok", wav.name)


asyncio.run(main())
