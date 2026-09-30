"""给 reviewer / 自己看片的抽帧：从成片里抽
  contact_1fps_<n>.png       每秒 1 帧的联系表（每张 8 格，每格标时间和镜头名）
  action_10fps/<镜头>.png    每个镜头动作段每秒 10 帧的抽帧条（前 2 秒 20 帧，5 格一行；转场镜头从切点前半个转场开始）
用法：.venv/Scripts/python video/motion/review_frames.py video/out/tj01/scene1/tj01_scene1.mp4 tj01 [--out 目录] [--action-sec 2.0]
第二个参数是集名或分镜表路径（用来算每个镜头从哪一帧开始）。同 fx_reel/make_review.py 的办法，不限于特效样片。
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import consts as C  # noqa: E402
from engine import plan as P  # noqa: E402


def tile(img, w, h, text=None):
    t = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if text:
        cv2.putText(t, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(t, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("episode", help="集名（video/stories/<集>/storyboard.json）或分镜表路径")
    ap.add_argument("--out")
    ap.add_argument("--action-sec", type=float, default=2.0)
    a = ap.parse_args()
    sb = Path(a.episode)
    if not sb.exists():
        sb = C.ROOT / "video" / "stories" / a.episode / "storyboard.json"
    plan = P.build_plan(sb)
    out = Path(a.out) if a.out else Path(a.video).parent
    (out / "action_10fps").mkdir(parents=True, exist_ok=True)
    fps = C.FPS
    base = min(sp.f0 for sp in plan.selected)
    ranges = []
    for sp in plan.selected:
        lead = (sp.trans["a"] if sp.trans else 0)          # 转场切点前多渲的帧
        ranges.append((sp.id, sp.f0 - base - lead, sp.f0 - base, sp.f1 - base))
    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / 10)))
    nact = int(round(a.action_sec * 10))
    want = set(min(int(round((s + 0.5) * fps)), n - 1) for s in range(int(n / fps)))
    for sid, fa, f0, f1 in ranges:
        for j in range(nact):
            fi = fa + j * step
            if fi < f1:
                want.add(min(max(fi, 0), n - 1))
    small, i = {}, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            small[i] = cv2.resize(f, (360, 640), interpolation=cv2.INTER_AREA)
        i += 1
    keys = sorted(small)

    def frame(fi):
        return small[fi] if fi in small else small[max(k for k in keys if k <= fi)]

    def shot_of(fi):
        for sid, fa, f0, f1 in ranges:
            if f0 <= fi < f1:
                return sid
        return "?"

    secs = list(range(int(n / fps)))
    for c in range(0, len(secs), 8):
        chunk = secs[c:c + 8]
        tiles = [tile(frame(min(int(round((s + 0.5) * fps)), n - 1)), 360, 640, f"{s + 0.5:.1f}s {shot_of(int(round((s + 0.5) * fps)))}") for s in chunk]
        while len(tiles) % 4:
            tiles.append(np.full((640, 360, 3), 255, np.uint8))
        rows = [np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]
        cv2.imwrite(str(out / f"contact_1fps_{c // 8 + 1}.png"), np.vstack(rows))
    for sid, fa, f0, f1 in ranges:
        tiles = []
        for j in range(nact):
            fi = fa + j * step
            if fi >= f1:
                break
            fi_c = min(max(fi, 0), n - 1)
            tiles.append(tile(frame(fi_c), 270, 480, f"{sid} {fi_c / fps:.1f}s"))
        while len(tiles) % 5:
            tiles.append(np.full((480, 270, 3), 255, np.uint8))
        rows = [np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]
        cv2.imwrite(str(out / "action_10fps" / f"{sid}.png"), np.vstack(rows))
    print(f"→ {out}（{len(secs)} 秒联系表 {(len(secs) + 7) // 8} 张，动作条 {len(ranges)} 张）")


if __name__ == "__main__":
    main()
