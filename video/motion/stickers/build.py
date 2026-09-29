"""把 Codex 画的系列贴纸表拆成单张贴纸，放进本目录（video/motion/stickers/<名字>.png）。
    .venv/Scripts/python video/motion/stickers/build.py
来源：video/assets/codex_series/stickers_v1.png（9 个：问号、感叹号、灯泡、汗滴、怒气、闪光星星、小心心、咚、啪）
      video/assets/codex_series/stickers_v2.png（嗖、星星眼、三个问号；画完才有，没有就跳过）
步骤：video/split_sheet.py 去绿底切件 → 同一个贴纸的几块碎片合并（闪光星星的两颗小星星）→ 去绿边（半透明边缘像素的绿色拉回到红蓝的水平）→
      修边（半透明的一圈换成最近的不透明像素的颜色，不留绿边、暗边、断口）→ 裁掉多余透明边，四周留 6 像素 → 存 PNG。
每件的边缘检查（绿边、断口）打印在输出里；改了别的贴纸表，在 SHEETS 里加一行。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
VIDEO = HERE.parents[1]
sys.path.insert(0, str(VIDEO))
from split_sheet import pieces   # noqa: E402

SERIES = VIDEO / "assets" / "codex_series"
# 表 → [(名字, [碎片序号...])]：碎片序号是 split_sheet 从上到下、从左到右的顺序；一个名字对应几块碎片就合并
SHEETS = {
    "stickers_v1.png": [("question", [0]), ("exclaim", [1]), ("bulb", [2]), ("sweat", [3]), ("anger", [4]), ("star", [5, 6]),
                        ("heart", [7]), ("dong", [8]), ("pa", [9])],
    "stickers_v2.png": [("sou", [0]), ("star_eyes", [1, 2]), ("question3", [3])],
}


def merge(parts):
    """几块碎片按它们在原图里的位置拼进同一张画布。parts = [(y, x, rgba)]。"""
    y0, x0 = min(p[0] for p in parts), min(p[1] for p in parts)
    y1, x1 = max(p[0] + p[2].shape[0] for p in parts), max(p[1] + p[2].shape[1] for p in parts)
    out = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    for y, x, c in parts:
        ys, xs = y - y0, x - x0
        dst = out[ys:ys + c.shape[0], xs:xs + c.shape[1]]
        m = c[..., 3] > dst[..., 3]
        dst[m] = c[m]
    return out


def despill(rgba):
    """去绿边：绿色通道超过红蓝的像素，把绿拉回到 max(r, b)（半透明的边缘最容易带绿）。"""
    a = rgba.astype(np.int32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lim = np.maximum(r, b)
    a[..., 1] = np.where((a[..., 3] > 0) & (g > lim), lim, g)
    return a.clip(0, 255).astype(np.uint8)


def solid_edge(rgba):
    """修边：边缘上半透明的一圈，颜色被背景的绿色拉暗、拉绿了（抠像的老毛病）。把它们的颜色换成最近的不透明像素的颜色（白纸边本来的奶白色），
    透明度保留（抗锯齿），这样白纸边一圈都是干净的奶白色，没有绿边、暗边、断口。"""
    a = rgba[..., 3]
    core = a >= 250
    ring = (a > 0) & ~core
    out = rgba.copy()
    _, (iy, ix) = ndimage.distance_transform_edt(~core, return_indices=True)
    out[ring, :3] = rgba[iy[ring], ix[ring], :3]
    return out


def trim(rgba, pad=6):
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    y0, y1, x0, x1 = max(ys.min() - pad, 0), ys.max() + pad + 1, max(xs.min() - pad, 0), xs.max() + pad + 1
    out = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    src = rgba[max(y0, 0):y1, max(x0, 0):x1]
    out[:src.shape[0], :src.shape[1]] = src
    return out


def main():
    for sheet, items in SHEETS.items():
        f = SERIES / sheet
        if not f.exists():
            print(f"跳过 {sheet}（还没画）")
            continue
        ps = pieces(f)
        print(f"{sheet}：切出 {len(ps)} 块")
        need = max(i for _, idx in items for i in idx) + 1
        if len(ps) < need:
            raise SystemExit(f"{sheet}：只切出 {len(ps)} 块，登记表要 {need} 块（改 SHEETS 里的序号）")
        for name, idx in items:
            im = trim(solid_edge(despill(merge([ps[i] for i in idx]))))
            Image.fromarray(im, "RGBA").save(HERE / f"{name}.png")
            a = im[..., 3]
            green = int(((a > 0) & (im[..., 1].astype(int) > np.maximum(im[..., 0], im[..., 2]).astype(int) + 8)).sum())
            print(f"  {name}.png  {im.shape[1]}x{im.shape[0]}  绿边像素 {green}")


if __name__ == "__main__":
    main()
