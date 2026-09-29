"""两张图的对比，带容差（回归测试和参考帧对比用）。

为什么要有容差：同一份代码、同一个时刻连续截两次，字幕区也可能有 4 万多个像素不一样（最大差值 66，是文字抗锯齿，reviewer 09-29 实测），
逐像素完全相同这个要求太严，会天天误报；但字体没生效、牌子挪了位置这类真问题差值大、面积也大，容差拦不住它们才是问题。
所以：差值 > thresh（默认 32，满分 255）的像素才算「变了」；变了的像素连成片（各向膨胀 2 像素再连通），面积 ≥ min_area（默认 50 像素）的片才算「变化区域」；
没有变化区域 = 一致。同时把「完全逐像素相同」也报出来（exact），方便看字体本地化以后是不是真的每次都一样。

用法（命令行）：python video/imgdiff.py a.png b.png [--thresh 32] [--min-area 50]   退出码 0 = 一致，1 = 有变化区域
"""
import argparse
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)


def report(a, b, thresh=32, min_area=50):
    """a、b：np 数组（load 的结果）。返回 dict：same（没有变化区域）、exact（逐像素完全相同）、diff_pixels（任何差异的像素数）、max_diff、
    big_pixels（差值 > thresh 的像素数）、regions（[{area, bbox: (x0, y0, x1, y1)}]，按面积从大到小，只列 ≥ min_area 的）。"""
    if a.shape != b.shape:
        return {"same": False, "exact": False, "diff_pixels": -1, "max_diff": -1, "big_pixels": -1, "regions": [], "error": f"尺寸不同 {a.shape} {b.shape}"}
    d = np.abs(a - b).max(axis=2)
    big = d > thresh
    lab, n = ndimage.label(ndimage.binary_dilation(big, iterations=2))
    regions = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        area = int(big[sl][lab[sl] == i].sum())
        if area >= min_area:
            regions.append({"area": area, "bbox": (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)})
    regions.sort(key=lambda r: -r["area"])
    return {"same": not regions, "exact": not d.any(), "diff_pixels": int((d > 0).sum()), "max_diff": int(d.max()), "big_pixels": int(big.sum()), "regions": regions}


def describe(r):
    if r.get("error"):
        return r["error"]
    s = f"{'一致' if r['same'] else '有变化区域 %d 处' % len(r['regions'])}（{'逐像素相同' if r['exact'] else '不是逐像素相同：%d 个像素有差，最大差值 %d，差值 > 阈值的 %d 个' % (r['diff_pixels'], r['max_diff'], r['big_pixels'])}）"
    for reg in r["regions"][:3]:
        s += f"；区域 面积 {reg['area']} 范围 {reg['bbox']}"
    return s


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("a"), ap.add_argument("b")
    ap.add_argument("--thresh", type=int, default=32)
    ap.add_argument("--min-area", type=int, default=50)
    args = ap.parse_args()
    r = report(load(args.a), load(args.b), args.thresh, args.min_area)
    print(describe(r))
    sys.exit(0 if r["same"] else 1)
