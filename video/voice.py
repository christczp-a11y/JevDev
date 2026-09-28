"""配音：逐句合成台词（Edge TTS，和 MoneyPrinterTurbo 用的是同一个免费配音引擎），量出每句的真实时长，排出全片时间线。

先配音、后排画面（动画的常规做法）：画面、字幕、口型都按真实的配音时长来对齐，不再用「每秒 4.8 个字」估算。
「动作」行没有台词，沿用剧本里写的时长。

用法：python video/voice.py video/stories/ep01/N5_最终.json video/out/ep01_voice [动作行号=秒 ...]
  例：14=2.0 15=6.5（剧本估的动作时长放不下纸偶动作时，在这里改）
输出：<目录>/NN.mp3（每句一个）和 timeline.json（每句的开始、结束、说话人、文字、音频文件）
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import edge_tts

# 角色 → （声音, 语速, 音高）。同一个声音用在两个角色上时，靠语速和音高区分
CAST = {
    "旁白": ("zh-CN-XiaoxiaoNeural", "+0%", "+0Hz"),
    "商鞅": ("zh-CN-YunyangNeural", "-4%", "-6Hz"),
    "小豆子": ("zh-CN-YunxiaNeural", "+6%", "+0Hz"),
    "农夫": ("zh-CN-YunjianNeural", "-6%", "-10Hz"),
    "大婶": ("zh-CN-liaoning-XiaobeiNeural", "+4%", "+0Hz"),
    "小伙": ("zh-CN-YunxiNeural", "+4%", "+0Hz"),
    "小孩": ("zh-CN-YunxiaNeural", "+8%", "+14Hz"),
    "同桌": ("zh-CN-XiaoyiNeural", "+4%", "+16Hz"),
    "司马光": ("zh-CN-YunxiaNeural", "-8%", "-12Hz"),
}
GAP = 0.3   # 两句之间的停顿（秒）


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return float(out)


async def synth(text, who, path):
    voice, rate, pitch = CAST[who]
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(path))


def main():
    story, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    if os.environ.get("HTTPS_PROXY") and not os.environ.get("WSS_PROXY"):
        os.environ["WSS_PROXY"] = os.environ["HTTPS_PROXY"]   # 云端：Edge TTS 走 wss://，aiohttp 只从 WSS_PROXY 读代理
    lines = json.loads(story.read_text(encoding="utf-8"))["lines"]
    act = {int(k): float(v) for k, v in (a.split("=") for a in sys.argv[3:])}
    t, timeline = 0.3, []
    for i, (s0, s1, who, text, visual) in enumerate(lines):
        if who == "动作" or not text:
            d, f = act.get(i, s1 - s0), None
        else:
            f = out / f"{i:02d}.mp3"
            if not f.exists():
                asyncio.run(synth(text, who, f))
            d = duration(f)
        timeline.append({"i": i, "t0": round(t, 2), "t1": round(t + d, 2), "who": who, "text": text, "visual": visual,
                         "audio": f.name if f else None, "script_t0": s0})
        t += d + GAP
    (out / "timeline.json").write_text(json.dumps({"duration": round(t + 0.5, 2), "lines": timeline}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    for x in timeline:
        print(f"{x['t0']:6.2f}–{x['t1']:6.2f}  {x['who']:<4} {x['text'][:30]}")
    print(f"全片 {t + 0.5:.1f} 秒（剧本估算 {lines[-1][1]:.1f} 秒）")


if __name__ == "__main__":
    main()
