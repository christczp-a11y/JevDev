"""跑 voice.py 的 main()，但把调 Qwen3-TTS 的 run_worker() 换掉，测试才不需要显卡、不依赖模型、也不会每次结果不一样。
用法：python fake_run.py <voice.py 的参数...>
环境变量：
  VOICE_TEST_SYNTH   fake（默认）用 ffmpeg 生成正弦波 wav：念一句的时长 0.3 秒 + 0.25 秒 × 字数 ÷ 语速倍数；设计参考音出一段 3 秒的正弦波；
                     real 调用真的 worker（要 .venv-tts、显卡、模型）；none 一调用 worker 就报错（证明没有重新合成）
  VOICE_TEST_LOG     每次调用，往这个文件追加 JSON 行：{"kind": "speak", "text", "voice", "job"} 和 {"kind": "design", "id", "instruct", "n", "anchor"}
                     （证明真正发给 Qwen 的是什么）
  VOICE_TEST_SERIES  换一份系列配置（voice.SERIES），测「系列声音改了、录音没重录」这类情况
  VOICE_TEST_ASSETS  换一个 video/assets 目录（voice.ASSETS），测 --make-ceremony 不动真的系列录音
  VOICE_TEST_VOICES  换一个参考音目录（voice.VOICES）；不设就是 ASSETS/audio/voices
  VOICE_TEST_SPEED   语速倍数（默认 1.0），测语速报警；写成 快嘴=1.8 只让这个声音快，别的声音仍是 1.0
  VOICE_TEST_HEAD    假 wav 开头补这么多秒静音（模仿克隆出来句首的静音），测句首静音只留 HEAD_KEEP
  VOICE_TEST_TAIL    假 wav 结尾补这么多秒静音，测时间线裁静音
  VOICE_TEST_MUTE    =1：假 wav 整段都是静音（音量 0），测「读不到声音就不裁」
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODE = os.environ.get("VOICE_TEST_SYNTH", "fake")
spec = importlib.util.spec_from_file_location("voice", ROOT / "video" / "voice.py")
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)

LOG = os.environ.get("VOICE_TEST_LOG")
if os.environ.get("VOICE_TEST_SERIES"):
    voice.SERIES = Path(os.environ["VOICE_TEST_SERIES"])
if os.environ.get("VOICE_TEST_ASSETS"):
    voice.ASSETS = Path(os.environ["VOICE_TEST_ASSETS"])
    voice.VOICES = voice.ASSETS / "audio" / "voices"
if os.environ.get("VOICE_TEST_VOICES"):
    voice.VOICES = Path(os.environ["VOICE_TEST_VOICES"])
real_run_worker = voice.run_worker


def wav(path, seconds, freq, speed_pad=""):
    af = []
    if os.environ.get("VOICE_TEST_MUTE") == "1":
        af.append("volume=0")
    head = float(os.environ.get("VOICE_TEST_HEAD", "0"))
    if head > 0:
        af.append(f"adelay={int(head * 1000)}:all=1")
    tail = float(os.environ.get("VOICE_TEST_TAIL", "0"))
    if tail > 0:
        af.append(f"apad=pad_dur={tail}")
    tmp = Path(str(path) + ".part")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds:.3f}:sample_rate=24000",
                    *(["-af", ",".join(af)] if af else []), "-ac", "1", "-f", "wav", str(tmp)], check=True)
    os.replace(tmp, path)


def fake_run_worker(job, workdir):
    def log(**kw):
        if LOG:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(kw, ensure_ascii=False) + "\n")
    if MODE == "none" and (job["design"] or job["speak"]):
        raise SystemExit(f"不该调用 worker！设计 {[d['id'] for d in job['design']]}，念 {[j['text'] for j in job['speak']]}")
    if MODE == "real":
        return real_run_worker(job, workdir)
    sp = os.environ.get("VOICE_TEST_SPEED", "1.0")
    speeds = dict(x.split("=") for x in sp.split(",")) if "=" in sp else {"*": sp}
    res = {"design": {}, "speak": {}, "load_s": 0.0, "peak_alloc_gib": 0.0}
    for d in job["design"]:
        log(kind="design", id=d["id"], instruct=d["instruct"], n=d["n"], anchor=d["anchor"])
        freq = 300 + int(hashlib.sha1((d["id"] + str(time.time_ns())).encode("utf-8")).hexdigest(), 16) % 200   # 每次设计出来都不一样（像真的一样）
        wav(d["wav"], 3.0, freq)
        res["design"][d["id"]] = {"chosen": 0, "cands": []}
    for j in job["speak"]:
        log(kind="speak", text=j["text"], voice=j["voice"], job=j["job"])
        n = len("".join(c for c in j["text"] if c.isalnum()))
        freq = 300 + int(hashlib.sha1((j["voice"] + j["text"]).encode("utf-8")).hexdigest(), 16) % 500
        dur = 0.3 + 0.25 * n / float(speeds.get(j["voice"], speeds.get("*", 1.0)))
        wav(j["out"], dur, freq)
        res["speak"][j["job"]] = {"dur": round(dur, 2), "gen_s": 0.1}
    return res


voice.run_worker = fake_run_worker
sys.argv = ["voice.py"] + sys.argv[1:]
voice.main()
