"""去掉部件图里 Codex 画进去的白色贴纸边，得到「纸芯」：python video/strip_border.py youth youth_q

纸偶的每块部件（上臂、前臂、大腿、小腿、鞋）原图都自带一圈白边。整条肢体拼在一起时，
这圈白边会在手肘、膝盖、鞋口露出一道白线（Chris 2026-09-28）。引擎改为用纸芯拼好整条肢体、再统一描外轮廓，
所以要先把原图的白边去掉：从透明区域出发，把与外面连通的「近白色」像素一圈圈剥掉。
输出：video/assets/rig/<角色>/<部件>_core.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent / "assets/rig"


def strip(im):
    a = np.asarray(im.convert("RGBA")).astype(np.int16)
    rgb, al = a[..., :3], a[..., 3]
    whiteish = (rgb.min(-1) > 205) & ((rgb.max(-1) - rgb.min(-1)) < 40)
    solid = al > 20
    # 从外面（透明）往里长：只穿过近白色的像素，最多 24 圈——这就是那圈贴纸边
    outside = ~solid
    edge = np.zeros_like(solid)
    front = outside
    for _ in range(24):
        grow = ndimage.binary_dilation(front) & solid & whiteish & ~edge
        if not grow.any():
            break
        edge |= grow
        front = grow
    # 白边和纸芯之间常有一两像素半透明 / 发白的过渡，再往里吃 1 像素
    keep = solid & ~edge
    keep = ndimage.binary_erosion(keep, iterations=1) | (keep & ~ndimage.binary_dilation(edge, iterations=1))
    out = a.copy()
    out[..., 3] = np.where(keep, al, 0)
    return Image.fromarray(out.astype(np.uint8), "RGBA"), int(edge.sum())


for rig in sys.argv[1:]:
    d = ROOT / rig
    parts = json.loads((d / "rig.json").read_text(encoding="utf-8"))["parts"]
    for n in parts:
        im, k = strip(Image.open(d / f"{n}.png"))
        im.save(d / f"{n}_core.png")
        print(f"{rig}/{n}: 去掉 {k} 个白边像素")
