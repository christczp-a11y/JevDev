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


LIMBS = ("upper", "fore_", "thigh", "shin")


def fill_rims(im):
    """手肘、膝盖的关节圆片内部还有一圈浅色描边：用最近的非浅色像素（皮肤、布料）的颜色填掉。"""
    a = np.asarray(im).astype(np.int16)
    rgb, al = a[..., :3], a[..., 3]
    rim = (al > 20) & (rgb.min(-1) > 212) & ((rgb.max(-1) - rgb.min(-1)) < 36)
    if not rim.any():
        return im
    _, (iy, ix) = ndimage.distance_transform_edt(rim | (al <= 20), return_indices=True)
    src = ~rim & (al > 20)
    # 只用「非浅色的实心像素」当颜色来源：先求到最近来源像素的索引
    _, (sy, sx) = ndimage.distance_transform_edt(~src, return_indices=True)
    out = a.copy()
    out[rim, :3] = a[sy[rim], sx[rim], :3]
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def cut_skin(im):
    """鞋上露出的那截脚脖子（皮肤色）挖掉：鞋口变空，小腿直接插进鞋里（Chris 2026-09-28：脚踝穿帮）。"""
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    skin = (a[..., 3] > 20) & (r > 185) & (r - g > 28) & (r - b > 48)
    skin = ndimage.binary_opening(skin, iterations=2)
    skin = ndimage.binary_dilation(skin, iterations=2) & (a[..., 3] > 0)
    out = a.copy()
    out[skin, 3] = 0
    return Image.fromarray(out.astype(np.uint8), "RGBA")


for rig in sys.argv[1:]:
    d = ROOT / rig
    parts = json.loads((d / "rig.json").read_text(encoding="utf-8"))["parts"]
    for n in parts:
        im, k = strip(Image.open(d / f"{n}.png"))
        if n.startswith(LIMBS):
            im = fill_rims(im)
        if n == "foot":
            im = cut_skin(im)
        im.save(d / f"{n}_core.png")
        print(f"{rig}/{n}: 去掉 {k} 个白边像素")
