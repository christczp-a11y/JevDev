"""系列插画（Codex 画的绿底单件）→ 抠掉绿底、修白纸边、裁边，存到 video/assets/ 下。
    .venv/Scripts/python video/assets/codex_series/split_series.py page_edge card_attr bubble_cloud ...     处理表里登记的名字
    .venv/Scripts/python video/assets/codex_series/split_series.py --list                                    看有哪些名字
步骤（同 video/motion/stickers/build.py）：video/split_sheet.py 去绿底 → 去绿边 → 修白纸边（半透明的一圈换成最近的不透明像素的颜色）→ 裁边。
洋红（#FF00FF）的地方也抠成透明（人物卡的画框：合成器把人物半身放在洋红窗口后面）；窗口的位置写进 <名字>.layout.json。
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
VIDEO = HERE.parents[1]
sys.path.insert(0, str(VIDEO))
sys.path.insert(0, str(VIDEO / "motion" / "stickers"))
from build import despill, solid_edge, trim   # noqa: E402
from split_sheet import key_out               # noqa: E402

ASSETS = VIDEO / "assets"
# 名字 → (来源表, 存到哪里, 保留哪些块: all = 所有大块合并 / 最大的一块 / 序号列表, 有没有洋红窗口)
JOBS = {
    "page_edge": ("page_edge.png", "props/page_edge.png", "all", False),
    "card_attr": ("card_attr.png", "props/card_attr.png", "all", False),
    "bubble_cloud": ("bubble_cloud.png", "props/bubble_cloud.png", "all", False),
    "screen_frame": ("screen_frame.png", "props/screen_frame.png", "all", False),
    "sgm_hi_remote": ("sgm_hi_remote.png", "chars/sgm_hi_remote.png", "all", False),
    "card_char": ("card_char.png", "props/card_char.png", "all", True),
    "map_paper": ("map_paper.png", "props/map_paper.png", "all", False),
}
# 整幅（不抠底，原样存）
OPAQUE = {"study_wall": ("study_wall.png", "sets/study/wall.png")}
# 素材表（多件）：名字 → (来源表, 存到哪个目录, [从左到右的名字]；桌子在最上面一行，单独按面积最大认出来)
SHEETS = {"study_items": ("study_items.png", "sets/study", ["desk", "chair", "books", "basket", "lamp_stand"])}


def magenta_mask(rgb):
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    return (r > 200) & (b > 200) & (g < 90)


def process(name):
    src, dst, keep, magenta = JOBS[name]
    im = Image.open(HERE / src)
    rgb = np.array(im.convert("RGB"))
    rgba = key_out(rgb)
    layout = {}
    if magenta:
        mm = ndimage.binary_opening(magenta_mask(rgb), iterations=2)
        mm = ndimage.binary_dilation(mm, iterations=2) & (magenta_mask(rgb) | ndimage.binary_dilation(magenta_mask(rgb), iterations=3))
        rgba[mm, 3] = 0
        lab, n = ndimage.label(mm)
        if n:
            sizes = ndimage.sum(mm, lab, range(1, n + 1))
            k = int(np.argmax(sizes)) + 1
            ys, xs = np.nonzero(lab == k)
            layout["window"] = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]   # 原表坐标，下面裁边后再减掉偏移
    a = rgba[..., 3] > 60
    lab, n = ndimage.label(ndimage.binary_closing(a, iterations=3))
    if keep == "all":
        big = [i for i in range(1, n + 1) if (lab == i).sum() > 2500]
        m = np.isin(lab, big)
    else:
        sizes = ndimage.sum(a, lab, range(1, n + 1))
        m = lab == int(np.argmax(sizes)) + 1
    # 洋红窗口是透明的，但窗口在卡片里面：算进「这一件」里，别被当成背景
    holes = ndimage.binary_fill_holes(m)
    rgba[..., 3] = np.where(m, rgba[..., 3], 0)
    out = solid_edge(despill(rgba))
    if magenta:
        out[..., 3] = np.where(holes & ~m & (rgba[..., 3] == 0), 0, out[..., 3])
    ys, xs = np.nonzero(out[..., 3] > 8)
    off = (int(max(xs.min() - 6, 0)), int(max(ys.min() - 6, 0)))
    out = trim(out)
    if "window" in layout:
        x0, y0, x1, y1 = layout["window"]
        layout["window"] = [int(x0 - off[0]), int(y0 - off[1]), int(x1 - off[0]), int(y1 - off[1])]
    p = ASSETS / dst
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(p)
    if layout:
        (p.with_suffix(".layout.json")).write_text(json.dumps(layout), encoding="utf-8")
    print(f"{name} → {dst}  {out.shape[1]}x{out.shape[0]}", layout or "")


def process_opaque(name):
    src, dst = OPAQUE[name]
    im = Image.open(HERE / src).convert("RGB")
    p = ASSETS / dst
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p)
    print(f"{name} → {dst}  {im.width}x{im.height}")


def process_sheet(name):
    from split_sheet import pieces
    src, dst_dir, names = SHEETS[name]
    ps = pieces(HERE / src, min_area=6000)
    desk = max(ps, key=lambda p: p[2].shape[0] * p[2].shape[1])
    rest = sorted([p for p in ps if p is not desk], key=lambda p: p[1])
    order = [desk] + rest
    if len(order) != len(names):
        raise SystemExit(f"{name}：切出 {len(order)} 件，要 {len(names)} 件（{names}）")
    for (y, x, c), nm in zip(order, names):
        out = trim(solid_edge(despill(c)))
        p = ASSETS / dst_dir / f"{nm}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(out, "RGBA").save(p)
        print(f"{name}/{nm} → {dst_dir}/{nm}.png  {out.shape[1]}x{out.shape[0]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--list"]:
        print(" ".join([*JOBS, *OPAQUE, *SHEETS]))
        sys.exit()
    for n in args:
        if n in JOBS:
            process(n)
        elif n in OPAQUE:
            process_opaque(n)
        elif n in SHEETS:
            process_sheet(n)
        else:
            raise SystemExit(f"不认识 {n}（--list 看有哪些）")
