"""voice.py / audio.py 测试共用的小工具：造测试用的剧本目录、跑 voice.py（假合成 / 真合成 / 禁止合成）、读日志。
输出都写到 video/out/voice_test/run_all/<测试名>/（video/out/ 不进 git）。
每个测试目录里有自己的 voices/（复制了系列声音的参考音）：本集角色自动设计的参考音写在这里，不会弄脏真的 video/assets/audio/voices/。"""
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
BASE_COMMIT = "99338a0"   # audio.py 的回归对照用它的 audio.py（voice.py 换引擎没动 audio.py）
REAL_VOICES = ROOT / "video" / "assets" / "audio" / "voices"

# 本集角色的声音描述（都是测试用的，互不相同；不含 BANNED_DESC 里的词）
MALE = "一位三十岁左右的男性，声音沉稳有力，语速平缓，像在认真讲道理。"
AUNT = "一位四十多岁的大婶，声音热情响亮，爱说话，带着笑意。"
KID = "一个七八岁的小男孩，声音清脆明亮，很有精神，说话很快。"
YOUNG = "一位二十岁出头的小伙子，声音爽朗，带着笑意。"


def copy_series_voices(dest):
    """把系列声音的参考音（旁白、司马光和仪式录音用的语气变体）复制到 dest。"""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for p in REAL_VOICES.iterdir():
        if p.name.startswith(("旁白", "司马光")):
            shutil.copyfile(p, dest / p.name)
    return dest


def workdir(name):
    d = OUT / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    copy_series_voices(d / "voices")
    return d


def make_case(d, lines, cast=None, banned=None, voice_text=None, tone=None, source_md=None, story_id="T1", extra_episode=None):
    """在目录 d 里写 episode.json（可选 cast、banned）、剧本 T1.json（lines 是 [(谁, 台词), ...]，可选 voice_text、tone）、source.md。返回剧本路径。"""
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
    if tone is not None:
        story["tone"] = tone
    story["lines"] = [[i * 3.0, i * 3.0 + 2.5, who, text, ""] for i, (who, text) in enumerate(lines)]
    p = d / f"{story_id}.json"
    p.write_text(json.dumps(story, ensure_ascii=False, indent=1), encoding="utf-8")
    if source_md is not None:
        (d / "source.md").write_text(source_md, encoding="utf-8")
    return p


def run_voice(*args, synth="fake", log=None, series=None, assets=None, voices=None, env=None):
    """跑 fake_run.py（= voice.py 的 main）。返回 subprocess.CompletedProcess（stdout、stderr 已按 utf-8 解码）。
    voices：参考音目录；不写就用剧本所在目录里的 voices/（workdir 建好的）。"""
    e = dict(os.environ, PYTHONIOENCODING="utf-8", VOICE_TEST_SYNTH=synth)
    if log:
        e["VOICE_TEST_LOG"] = str(log)
    if series:
        e["VOICE_TEST_SERIES"] = str(series)
    if assets:
        e["VOICE_TEST_ASSETS"] = str(assets)
    if voices is None and args and str(args[0]).endswith(".json") and (Path(args[0]).parent / "voices").is_dir():
        voices = Path(args[0]).parent / "voices"
    if voices:
        e["VOICE_TEST_VOICES"] = str(voices)
    e.update(env or {})
    return subprocess.run([PY, str(HERE / "fake_run.py"), *[str(a) for a in args]], cwd=ROOT, env=e, capture_output=True, text=True, encoding="utf-8")


def read_log(path, kind="speak"):
    """假合成的调用日志：kind="speak" 是每句念的（text、voice），kind="design" 是设计参考音的（id、instruct、n）。"""
    p = Path(path)
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return [r for r in rows if r["kind"] == kind]


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
