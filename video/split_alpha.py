"""把 Codex 直接输出的「透明底」素材图切成单件 PNG（split_sheet.py 处理绿幕，这个处理透明底）。

只保留不透明的实心部分：去掉半透明的发光边、背景里的碎点。
用法：python video/split_alpha.py <素材图.png> <输出目录> <名字1> <名字2> ...   （先用 --list 看顺序：从上到下、从左到右）
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


def pieces(path, min_area=3000, solid=170):
    im = np.array(Image.open(path).convert("RGBA"))
    mask = im[..., 3] > solid
    mask = ndimage.binary_fill_holes(ndimage.binary_opening(mask, iterations=2))
    lab, n = ndimage.label(mask)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        m = lab[sl] == i
        if m.sum() < min_area:
            continue
        crop = im[sl].copy()
        keep = ndimage.binary_dilation(m, iterations=1)
        crop[..., 3] = np.where(keep, np.maximum(crop[..., 3], np.where(m, 255, 0)), 0)
        out.append((sl[0].start, sl[1].start, crop))
    out.sort(key=lambda p: (p[0] // 180, p[1]))
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
