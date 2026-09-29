"""测试共用：路径、跑 render.py、读报告。输出都写到 video/out/tests/motion/（不进 git）。"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
MOTION = TESTS.parent
ROOT = MOTION.parents[1]
OUT = ROOT / "video" / "out" / "tests" / "motion"
PROTO = TESTS / "proto17"
FEATURE = TESTS / "feature_case"
sys.path.insert(0, str(MOTION))

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def ensure_proto_assets():
    if not (PROTO / "gen" / "cards" / "page.png").exists() or not (PROTO / "sfx" / "tick.wav").exists():
        subprocess.run([sys.executable, str(PROTO / "make_assets.py")], check=True, env=ENV)


def render(sb, out, cache, *args, check=False):
    """跑 render.py；返回 (退出码, 输出文字, 报告 dict 或 None)。"""
    cmd = [sys.executable, str(MOTION / "render.py"), str(sb), "--out", str(out), "--cache-dir", str(cache), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=ENV, cwd=ROOT)
    reports = sorted(Path(out).glob("*.report.json"), key=lambda f: f.stat().st_mtime) if Path(out).exists() else []
    rep = json.loads(reports[-1].read_text(encoding="utf-8")) if reports and p.returncode in (0, 1) else None
    if check and p.returncode != 0:
        raise RuntimeError(f"render.py 退出码 {p.returncode}\n{p.stdout}\n{p.stderr}")
    return p.returncode, p.stdout + p.stderr, rep


def fresh(name):
    d = OUT / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d


def ffprobe_duration(path, stream):
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(p.stdout.strip().splitlines()[0])
