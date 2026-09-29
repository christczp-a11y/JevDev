"""给 reviewer 的抽帧（阶段 B 交付物）：从出好的样片里抽
  contact_sheet_1fps_<n>.jpg    每秒 1 帧的联系表（每格标时间和镜头名，分几张，每张约 60 秒）
  action_10fps/<镜头>.jpg       每个镜头动作段（前 2 秒）每秒 10 帧的抽帧条（20 帧，每行 10 帧）
用法：.venv/Scripts/python video/motion/tests/fx_reel/make_review.py video/out/motion/fx_reel/fx_reel.mp4 [--out 目录]
"""
import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
TR_DUR = {"page_turn": 0.7, "paper_wipe": 0.8, "ink_wipe": 0.7, "iris": 0.7, "fade_paper": 0.7, "whip": 0.28, "tv_switch": 0.8}


def shot_ranges():
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    tl = json.loads((HERE / "voice" / "timeline.json").read_text(encoding="utf-8"))
    starts = [tl["lines"][s["from"]["line"]]["t0"] for s in sb["shots"]]
    ends = starts[1:] + [tl["duration"]]
    out = []
    for s, a, b in zip(sb["shots"], starts, ends):
        label = next(f["text"] for f in s["fx"] if f["type"] == "label")
        tr = s.get("transition")
        tr = {"type": tr} if isinstance(tr, str) else (tr or {})
        lead = min(0.5, float(tr.get("dur", TR_DUR.get(tr.get("type"), 0.7))) / 2 + 0.05) if tr else 0.0     # 转场以切点为中心：动作段从切点前半个转场开始
        out.append((s["id"], label, a, b, lead))
    return out


def tile(img, w, h, text=None):
    t = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if text:
        cv2.putText(t, text, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(t, text, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = Path(a.out) if a.out else Path(a.video).parent
    (out / "action_10fps").mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(a.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ranges = shot_ranges()
    # 要抽哪些帧先算好，顺序解码一遍只留这些（缩成小图再存，1080p 整片放不进内存）
    want = set()
    for s_ in range(int(n / fps)):
        want.add(min(int(round((s_ + 0.5) * fps)), n - 1))
    for sid, label, t0, t1, lead in ranges:
        for j in range(20):
            if t0 - lead + 0.1 * j < t1:
                want.add(min(int(round((t0 - lead + 0.1 * j) * fps)), n - 1))
    small = {}
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            small[i] = cv2.resize(f, (270, 480), interpolation=cv2.INTER_AREA)
        i += 1
    keys = sorted(small)

    class Frames:
        def __getitem__(self, fi):
            return small[fi] if fi in small else small[max(k for k in keys if k <= fi)]
    frames = Frames()
    n = i

    def shot_of(t):
        for sid, label, t0, t1, lead in ranges:
            if t0 <= t < t1:
                return sid
        return ""

    # ---- 每秒 1 帧的联系表 ----
    tw, th = 180, 320
    secs = list(range(int(n / fps)))
    per_sheet, cols = 60, 10
    for k in range(0, len(secs), per_sheet):
        chunk = secs[k:k + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        sheet = np.full((rows * (th + 4), cols * (tw + 4), 3), 50, np.uint8)
        for i, s in enumerate(chunk):
            f = frames[min(int(round((s + 0.5) * fps)), n - 1)]
            r, c = divmod(i, cols)
            sheet[r * (th + 4):r * (th + 4) + th, c * (tw + 4):c * (tw + 4) + tw] = tile(f, tw, th, f"{s + 0.5:.1f}s {shot_of(s + 0.5)}")
        p = out / f"contact_sheet_1fps_{k // per_sheet + 1}.jpg"
        cv2.imwrite(str(p), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print("→", p)
    # ---- 动作段每秒 10 帧 ----
    tw, th = 216, 384
    for sid, label, t0, t1, lead in ranges:
        idx = [min(int(round((t0 - lead + 0.1 * j) * fps)), n - 1) for j in range(20) if t0 - lead + 0.1 * j < t1]
        rows = (len(idx) + 9) // 10
        strip = np.full((rows * (th + 4), 10 * (tw + 4), 3), 50, np.uint8)
        for i, fi in enumerate(idx):
            r, c = divmod(i, 10)
            strip[r * (th + 4):r * (th + 4) + th, c * (tw + 4):c * (tw + 4) + tw] = tile(frames[fi], tw, th, f"{0.1 * i - lead:+.1f}s")
        name = "_".join(re.findall(r"[A-Za-z][A-Za-z_]*", label.split("  ", 1)[-1])) or "shot"
        cv2.imwrite(str(out / "action_10fps" / f"{sid}_{name}.jpg"), strip, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("→", out / "action_10fps", f"（{len(ranges)} 张）")


if __name__ == "__main__":
    main()
