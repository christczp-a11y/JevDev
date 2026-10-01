"""对一条已经出好的成片做空白检测（M7）：每隔几秒抽一帧，报出画面中间的淡色空白块和分层之间的白缝（见 engine/blank.py）。
合成器出片时自带这项检查（只看场景，不含字幕）；这个脚本是给已经有的成片用的（标定阈值、reviewer 对老片子查一遍）。
用法：.venv/Scripts/python video/motion/blank_scan.py video/out/tj01/full/tj01_full.mp4 [tj01] [--every 0.5]
第二个参数（集名或分镜表路径）可选：给了就把每个时间点对到镜头号。退出码：0 = 没有空白，1 = 有。
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import blank  # noqa: E402
from engine import consts as C  # noqa: E402


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("episode", nargs="?", help="集名（video/stories/<集>/storyboard.json）或分镜表路径：给了才标镜头号")
    ap.add_argument("--every", type=float, default=0.5, help="每隔几秒抽一帧（默认 0.5）")
    a = ap.parse_args(argv)
    w, h = blank.WORK_W, blank.WORK_H
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-vf", f"fps={1 / a.every},scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                       capture_output=True)
    raw = p.stdout
    n = len(raw) // (w * h * 3)
    frames = np.frombuffer(raw, np.uint8).reshape(n, h, w, 3)
    shots = None
    if a.episode:
        from engine.plan import build_plan
        sb = Path(a.episode)
        sb = sb if sb.exists() else C.ROOT / "video" / "stories" / a.episode / "storyboard.json"
        shots = build_plan(sb).shots
    hits = []
    for k in range(n):
        t = k * a.every
        for e in blank.detect(frames[k]):
            sid = next((s.id for s in shots if s.f0 <= t * C.FPS < s.f1), "?") if shots else None
            hits.append((t, sid, e))
    for t, sid, e in hits:
        print(f"{mmss(t)}{'  ' + sid if sid else ''}  {e['kind']}  bbox {e['bbox']}  面积 {e['area']:.1%}")
    ids = sorted({sid for _, sid, _ in hits if sid})
    print(f"共 {len(hits)} 处（抽了 {n} 帧）" + (f"，镜头：{', '.join(ids)}" if ids else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
