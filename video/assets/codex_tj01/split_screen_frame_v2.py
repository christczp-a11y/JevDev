"""把 codex_series/screen_frame_v2.png（4:3 纸屏幕）拆图，替换 props/screen_frame.png，并把框里纸面的位置写进 props/screen_frame.layout.json。
  .venv/Scripts/python video/assets/codex_tj01/split_screen_frame_v2.py
做法同 codex_series/split_series.py（去绿底、修白纸边、裁边）；纸面位置 = 输出图里那块最大的米黄色连通区域的外接矩形（往里收 3 像素，避开框的内缘阴影）。
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS / "codex_series"))
import split_series as S  # noqa: E402

S.JOBS["screen_frame"] = ("screen_frame_v2.png", "props/screen_frame.png", "all", False)
S.process("screen_frame")
p = ASSETS / "props/screen_frame.png"
im = np.array(Image.open(p).convert("RGBA")).astype(int)
r, g, b, a = im[..., 0], im[..., 1], im[..., 2], im[..., 3]
paper = (a > 200) & (r > 215) & (r < 252) & (g > 190) & (g < 240) & (b > 150) & (b < 225) & (r - b > 18)   # 米黄纸面（白纸边 r-b 很小，木框是棕色 g 低）
paper = ndimage.binary_opening(paper, iterations=3)
lab, n = ndimage.label(paper)
sizes = ndimage.sum(paper, lab, range(1, n + 1))
k = 1 + int(np.argmax(sizes))
ys, xs = np.nonzero(lab == k)
box = [int(xs.min()) + 3, int(ys.min()) + 3, int(xs.max()) + 1 - 3, int(ys.max()) + 1 - 3]
lay = {"screen": box, "size": [int(im.shape[1]), int(im.shape[0])], "note": f"坐标是 props/screen_frame.png 的像素（{im.shape[1]}×{im.shape[0]}）：screen = 框里那块米黄纸面的位置 [x0,y0,x1,y1]（{box[2]-box[0]}×{box[3]-box[1]}，比例 {(box[2]-box[0])/(box[3]-box[1]):.3f}，约 4:3）；来自 codex_series/screen_frame_v2.png。"}
(ASSETS / "props/screen_frame.layout.json").write_text(json.dumps(lay), encoding="utf-8")
print(lay)
