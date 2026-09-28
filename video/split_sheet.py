"""把 Codex 生成的「绿底素材图」抠掉绿色（或直接用已经透明的底）、切成单件 PNG。

用法：python video/split_sheet.py <素材图.png> <输出目录> <名字1> <名字2> ...
名字按「从上到下、从左到右」的顺序对应每一件素材（先打印一遍 --list 看顺序）。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def key_out(rgb):
    """绿幕抠像：越绿越透明；边缘半透明；去掉溢到边缘的绿色。"""
    r, g, b = (rgb[..., i].astype(float) for i in range(3))
    k = g - np.maximum(r, b)                       # 「有多绿」
    alpha = np.clip(1 - (k - 30) / 90, 0, 1)       # k<30 完全不透明，k>120 完全透明
    alpha[(g > 200) & (r < 90) & (b < 90)] = 0
    g2 = np.where(k > 0, np.maximum(r, b) + np.minimum(k, 0), g)   # 去绿边
    out = np.dstack([r, g2, b, alpha * 255]).clip(0, 255).astype(np.uint8)
    return out


def pieces(path, min_area=3000):
    src = Image.open(path)
    if src.mode == "RGBA" and (np.array(src)[..., 3] < 20).mean() > 0.2:   # Codex 有时自己把绿底抠成了透明：直接用透明度
        rgba = np.array(src)
    else:
        rgba = key_out(np.array(src.convert("RGB")))
    mask = rgba[..., 3] > 60
    lab, n = ndimage.label(ndimage.binary_closing(mask, iterations=4))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        area = (lab[sl] == i).sum()
        if area < min_area:
            continue
        crop = rgba[sl].copy()
        crop[..., 3] = np.where(lab[sl] == i, crop[..., 3], 0)   # 只留这一件
        out.append((sl[0].start, sl[1].start, crop))
    out.sort(key=lambda p: (p[0] // 150, p[1]))                 # 从上到下、从左到右
    return out


if __name__ == "__main__":
    src, dst, names = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
    ps = pieces(src)
    if names == ["--list"]:
        for y, x, c in ps:
            print(f"y={y} x={x} {c.shape[1]}x{c.shape[0]}")
        sys.exit()
    assert len(names) == len(ps), f"切出 {len(ps)} 件，给了 {len(names)} 个名字"
    dst.mkdir(parents=True, exist_ok=True)
    for (y, x, c), nm in zip(ps, names):
        Image.fromarray(c, "RGBA").save(dst / f"{nm}.png")
        print(nm, f"{c.shape[1]}x{c.shape[0]}")
