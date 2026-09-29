"""voice.py / audio.py 测试共用的小工具：造测试用的剧本目录、跑 voice.py（假合成 / 真合成 / 禁止合成）、读日志。
输出都写到 video/out/voice_test/run_all/<测试名>/（video/out/ 不进 git）。"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "video" / "out" / "voice_test" / "run_all"
PY = sys.executable
BASE_COMMIT = "99338a0"   # 这一步动 voice.py、audio.py 之前的提交：audio.py 的回归对照用它的 audio.py

MALE = {"voice": "zh-CN-YunyangNeural", "rate": "-4%", "pitch": "-6Hz"}
AUNT = {"voice": "zh-CN-liaoning-XiaobeiNeural", "rate": "+4%", "pitch": "+0Hz"}


def workdir(name):
    d = OUT / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d


def make_case(d, lines, cast=None, banned=None, voice_text=None, source_md=None, story_id="T1", extra_episode=None):
    """在目录 d 里写 episode.json（可选 cast、banned）、剧本 T1.json（lines 是 [(谁, 台词), ...]，可选 voice_text）、source.md。返回剧本路径。"""
    ep = {"core_question": "测试"}
    if cast is not None:
        ep["cast"] = cast
    if banned is not None:
        ep["banned"] = banned
    ep.update(extra_episode or {})
    (d / "episode.json").write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
    story = {"id": story_id, "name": story_id, "framework": "测试", "title": ["测试"]}
    if voice_text is not None:
        story["voice_text"] = voice_text
    story["lines"] = [[i * 3.0, i * 3.0 + 2.5, who, text, ""] for i, (who, text) in enumerate(lines)]
    p = d / f"{story_id}.json"
    p.write_text(json.dumps(story, ensure_ascii=False, indent=1), encoding="utf-8")
    if source_md is not None:
        (d / "source.md").write_text(source_md, encoding="utf-8")
    return p


def run_voice(*args, synth="fake", log=None, series=None, assets=None, env=None):
    """跑 fake_run.py（= voice.py 的 main）。返回 subprocess.CompletedProcess（stdout、stderr 已按 utf-8 解码）。"""
    e = dict(os.environ, PYTHONIOENCODING="utf-8", VOICE_TEST_SYNTH=synth)
    e.pop("NARRATOR_RATE", None)
    if log:
        e["VOICE_TEST_LOG"] = str(log)
    if series:
        e["VOICE_TEST_SERIES"] = str(series)
    if assets:
        e["VOICE_TEST_ASSETS"] = str(assets)
    e.update(env or {})
    return subprocess.run([PY, str(HERE / "fake_run.py"), *[str(a) for a in args]], cwd=ROOT, env=e, capture_output=True, text=True, encoding="utf-8")


def read_log(path):
    p = Path(path)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def timeline(out):
    return json.loads((Path(out) / "timeline.json").read_text(encoding="utf-8"))


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def count_line(stdout):
    """从 voice.py 最后的汇总行读出 (合成, 缓存命中, 系列录音)。"""
    import re
    m = re.search(r"合成 (\d+) 句，缓存命中 (\d+) 句，系列录音 (\d+) 句", stdout)
    return tuple(int(x) for x in m.groups())
