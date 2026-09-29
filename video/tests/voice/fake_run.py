"""跑 voice.py 的 main()，但把合成函数 synth() 换掉，测试才不依赖网络、也不会每次结果不一样。
用法：python fake_run.py <voice.py 的参数...>
环境变量：
  VOICE_TEST_SYNTH   fake（默认）用 ffmpeg 生成一段正弦 mp3，时长按字数和语速估：0.3 秒 + 0.25 秒 × 字数 ÷ (1 + 语速)，和真人读的速度差不多；
                     real 调用真的 Edge TTS（要网络）；none 一调用合成就报错（证明没有重新合成）
  VOICE_TEST_LOG     每次调用合成，往这个文件追加一行 JSON：{"text", "voice", "rate", "pitch", "file"}（证明真正发给 Edge TTS 的是什么）
  VOICE_TEST_SERIES  换一份系列配置（voice.SERIES），测「系列声音改了、录音没重录」这类情况
  VOICE_TEST_ASSETS  换一个 video/assets 目录（voice.ASSETS），测 --make-ceremony 不动真的系列录音
  VOICE_TEST_TAIL    假 mp3 的结尾补这么多秒静音（模仿 Edge TTS 补的 0.5–1.0 秒），测时间线裁静音
  VOICE_TEST_MUTE    =1：假 mp3 整段都是静音（音量 0），测「读不到声音就不裁」
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODE = os.environ.get("VOICE_TEST_SYNTH", "fake")
if MODE != "real":   # 假合成、禁止合成都用不到 edge_tts：放个空模块进去，省掉每次 2 秒多的导入时间
    import types
    sys.modules["edge_tts"] = types.ModuleType("edge_tts")
spec = importlib.util.spec_from_file_location("voice", ROOT / "video" / "voice.py")
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)

LOG = os.environ.get("VOICE_TEST_LOG")
if os.environ.get("VOICE_TEST_SERIES"):
    voice.SERIES = Path(os.environ["VOICE_TEST_SERIES"])
if os.environ.get("VOICE_TEST_ASSETS"):
    voice.ASSETS = Path(os.environ["VOICE_TEST_ASSETS"])
real_synth = voice.synth


async def synth(text, v, r, p, path):
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"text": text, "voice": v, "rate": r, "pitch": p, "file": Path(path).name}, ensure_ascii=False) + "\n")
    if MODE == "none":
        raise SystemExit(f"不该调用合成！文字={text!r} 声音={v} 语速={r} 音高={p}")
    if MODE == "real":
        return await real_synth(text, v, r, p, path)
    n = len(re.sub(r"[^\w]", "", text))
    speed = 1 + float(r.rstrip("%")) / 100
    freq = 300 + int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % 500
    tmp = Path(path).with_name(Path(path).name + ".part")
    af = []
    if os.environ.get("VOICE_TEST_MUTE") == "1":
        af.append("volume=0")
    if float(os.environ.get("VOICE_TEST_TAIL", "0")) > 0:
        af.append(f"apad=pad_dur={os.environ['VOICE_TEST_TAIL']}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={0.3 + 0.25 * n / speed:.3f}:sample_rate=24000",
                    *(["-af", ",".join(af)] if af else []), "-ac", "1", "-b:a", "48k", "-f", "mp3", str(tmp)], check=True)
    os.replace(tmp, path)


voice.synth = synth
sys.argv = ["voice.py"] + sys.argv[1:]
voice.main()
