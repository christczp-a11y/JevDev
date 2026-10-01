#!/usr/bin/env python
"""人物图的脸框：每张图自己的脸在哪（storyboard_check 的 [字幕] [压脸] [遮挡] [速度线] [集中线] [安全区] 都用它；PITFALLS M6 再犯、待补 18）。

脸框 = 额头到下巴（有胡子的算到胡子底）、左右到脸边，比例坐标 [x0, x1, y0, y1]（占图宽 / 图高；图的原方向，翻转的人物检查时镜像）。
戴斗笠 / 官帽的人，脸框从帽檐下面的额头算起（帽子不算脸）。

查法（faces.lookup）：
  1. 数据文件 video/assets/faces.json：{"chars/yr_hi_cry_l.png": [0.22, 0.66, 0.2, 0.57], ...}（路径相对 video/assets/）——量过、看过的，优先
  2. 数据文件里没写：自动估（estimate）——取图里肤色像素最上面的那一团（脸；手在下面），往下多留一点给下巴 / 胡子；估得不合理（太大、太小、太碎，
     比如斗笠和脸同一个橙色分不开）= 放弃
  3. 估不出来：旧的默认 DEFAULT = 上面 40%、中间 50% 宽
自动估只是兜底：新人物图出来以后用 `faces.py sheet` 画框看一眼，不对就在 faces.json 里写一行。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  python video/motion/faces.py sheet chars/yr_hi_cry_l.png chars/sgm_hi_point.png ...   把脸框画在图上，存成联系表到 video/out/faces_check/（来源：json / auto / default 标在图上）
  python video/motion/faces.py sheet --glob "chars/wwh_*.png"                           按通配符
  python video/motion/faces.py auto chars/xxx.png ...                                    只打印自动估的结果
  python video/motion/faces.py check                                                     faces.json 里每一行的格式和图在不在
"""
import argparse
import functools
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

MOTION = Path(__file__).resolve().parent
ASSETS = MOTION.parent / "assets"
DEFAULT = (0.25, 0.75, 0.0, 0.40)          # 旧默认：脸在图的最上面 40%、中间 50% 宽
FACES_JSON = "faces.json"

# 自动估的参数
EST_SIDE = 256                             # 缩到这么大再算
SKIN_H, SKIN_S, SKIN_V = (8, 40), (0.14, 0.60), 0.65      # 肤色：色相（度）、饱和度、亮度下限
MIN_BLOB = 0.004                           # 肤色块至少占整张图的这么多
CHIN_PAD = 0.18                            # 往下多留脸高的 18%（下巴 / 山羊胡）
SIDE_PAD = 0.03                            # 左右各多留脸宽的 3%
SANE_H, SANE_W = (0.07, 0.60), (0.10, 0.80)    # 估出来的脸框高 / 宽占整张图的比例要在这个范围里，否则放弃
MIN_FILL = 0.30                            # 肤色块占它外框的比例（太碎 = 不是脸）


class FaceError(Exception):
    pass


def _check_box(box, where):
    try:
        x0, x1, y0, y1 = (float(v) for v in box)
    except (TypeError, ValueError):
        raise FaceError(f"{where}：要写成 [x0, x1, y0, y1] 四个数")
    if len(box) != 4 or not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise FaceError(f"{where}：[x0, x1, y0, y1] 要是 0–1 的比例，而且 x0 < x1、y0 < y1，现在是 {list(box)}")
    return (x0, x1, y0, y1)


def load(path):
    """faces.json → {相对路径: (x0, x1, y0, y1)}；文件不存在 = 空；写坏了 FaceError。"""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise FaceError(f"{p} 读不了或不是 JSON：{e}")
    if not isinstance(raw, dict):
        raise FaceError(f"{p} 顶层要是对象 {{路径: [x0, x1, y0, y1]}}")
    return {k: _check_box(v, f"{p.name} 的 {k}") for k, v in raw.items() if not k.startswith("_")}


@functools.lru_cache(maxsize=1024)
def _estimate_cached(path, mtime_ns):
    return _estimate(path)


def estimate(path):
    """自动估脸框：(x0, x1, y0, y1) 或 None（估不出来 / 不合理）。"""
    p = Path(path)
    try:
        return _estimate_cached(str(p), p.stat().st_mtime_ns)
    except OSError:
        return None


def _estimate(path):
    try:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            im.thumbnail((EST_SIDE, EST_SIDE))
    except (OSError, ValueError):
        return None
    a = np.asarray(im)
    H, W = a.shape[:2]
    opaque = a[..., 3] > 40
    if opaque.sum() < 0.05 * H * W:
        return None
    hsv = cv2.cvtColor(np.ascontiguousarray(a[..., :3]), cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0] * 2.0, hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    skin = opaque & (h >= SKIN_H[0]) & (h <= SKIN_H[1]) & (s >= SKIN_S[0]) & (s <= SKIN_S[1]) & (v >= SKIN_V)
    k = max(3, int(0.03 * max(H, W))) | 1
    closed = cv2.morphologyEx(skin.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))       # 眼睛、嘴、胡子把脸切碎了，先合起来
    n, _lab, stats, cent = cv2.connectedComponentsWithStats(closed, connectivity=8)
    blobs = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= MIN_BLOB * H * W]
    if not blobs:
        return None
    big = max(stats[i, cv2.CC_STAT_AREA] for i in blobs)
    cand = [i for i in blobs if stats[i, cv2.CC_STAT_AREA] >= 0.25 * big]
    i = min(cand, key=lambda j: cent[j][1])                          # 最上面的一团：脸（手在下面）
    x, y, w, hh, area = (int(stats[i, c]) for c in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT, cv2.CC_STAT_AREA))
    if area < MIN_FILL * w * hh:
        return None
    x0, x1 = (x - SIDE_PAD * w) / W, (x + w + SIDE_PAD * w) / W
    y0, y1 = y / H, (y + hh + CHIN_PAD * hh) / H
    box = (max(x0, 0.0), min(x1, 1.0), max(y0, 0.0), min(y1, 1.0))
    if not (SANE_H[0] <= box[3] - box[2] <= SANE_H[1] and SANE_W[0] <= box[1] - box[0] <= SANE_W[1]) or box[2] > 0.7:
        return None
    return tuple(round(float(c), 3) for c in box)


class FaceTable:
    """一份素材目录的脸框表：faces.json + 自动估。"""

    def __init__(self, assets_root=ASSETS):
        self.root = Path(assets_root)
        self.data = load(self.root / FACES_JSON)

    def lookup(self, file, rel=None):
        """→ ((x0, x1, y0, y1), 来源 "json" / "auto" / "default")。file = 图的文件，rel = 相对素材目录的路径（不在素材目录下 = None）。"""
        if rel and rel in self.data:
            return self.data[rel], "json"
        if file:
            est = estimate(file)
            if est:
                return est, "auto"
        return DEFAULT, "default"

    def box(self, file, rel=None):
        return self.lookup(file, rel)[0]


def mirrored(box):
    """人物翻身（flip）：脸框左右镜像。"""
    return (1.0 - box[1], 1.0 - box[0], box[2], box[3])


# ------------------------------------------------------------------ 画框看对不对
def _font(size):
    for name in ("msyh.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


COLORS = {"json": (255, 0, 80), "auto": (0, 120, 255), "default": (140, 140, 140)}


def draw_sheet(rels, table, out, per_row=6, cell_h=520, grid=False):
    """把每张图画在灰底上，脸框画成线（红 = faces.json，蓝 = 自动估，灰 = 旧默认），标上路径，存成联系表；返回写出的文件。"""
    tiles = []
    for rel in rels:
        f = table.root / rel
        im = Image.open(f).convert("RGBA")
        box, src = table.lookup(f, rel)
        w, h = im.size
        sc = cell_h / h
        im = im.resize((max(1, round(w * sc)), cell_h))
        bg = Image.new("RGBA", im.size, (150, 150, 150, 255))
        bg.alpha_composite(im)
        d = ImageDraw.Draw(bg)
        W, H = bg.size
        d.rectangle([box[0] * W, box[2] * H, box[1] * W, box[3] * H], outline=COLORS[src] + (255,), width=4)
        if grid:                                                              # 每 0.1 一条淡线，边上标比例，方便照着量脸框
            for k in range(1, 10):
                d.line([(W * k / 10, 0), (W * k / 10, H)], fill=(0, 0, 255, 90), width=1)
                d.line([(0, H * k / 10), (W, H * k / 10)], fill=(0, 0, 255, 90), width=1)
                d.text((W * k / 10 - 6, 28), str(k), fill=(255, 255, 0, 255), font=_font(16), stroke_width=2, stroke_fill=(0, 0, 0, 255))
                d.text((2, H * k / 10 - 8), str(k), fill=(255, 255, 0, 255), font=_font(16), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        d.text((6, 4), f"{Path(rel).stem} [{src}]", fill=(255, 255, 255, 255), font=_font(20), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        tiles.append(bg.convert("RGB"))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [tiles[i:i + per_row] for i in range(0, len(tiles), per_row)]
    written = []
    for r, row in enumerate(rows):
        sheet = Image.new("RGB", (sum(t.width for t in row) + 8 * (len(row) - 1), cell_h), (255, 255, 255))
        x = 0
        for t in row:
            sheet.paste(t, (x, 0))
            x += t.width + 8
        p = out.with_name(f"{out.stem}_{r + 1}{out.suffix}") if len(rows) > 1 else out
        sheet.save(p, quality=88)
        written.append(p)
    return written


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="人物图的脸框：画框看对不对 / 自动估 / 查 faces.json")
    ap.add_argument("cmd", choices=["sheet", "auto", "check"])
    ap.add_argument("images", nargs="*", help="相对 video/assets/ 的路径，例如 chars/yr_hi_cry_l.png")
    ap.add_argument("--glob", help="通配符，例如 \"chars/wwh_*.png\"")
    ap.add_argument("--assets-root", default=str(ASSETS))
    ap.add_argument("--out", default=str(MOTION.parent / "out" / "faces_check" / "sheet.jpg"))
    ap.add_argument("--per-row", type=int, default=6)
    ap.add_argument("--grid", action="store_true", help="sheet：画 0.1 间隔的格子线，方便照着量")
    a = ap.parse_args()
    table = FaceTable(a.assets_root)
    rels = list(a.images)
    if a.glob:
        rels += sorted(p.relative_to(table.root).as_posix() for p in table.root.glob(a.glob))
    if a.cmd == "check":
        bad = [k for k in table.data if not (table.root / k).exists()]
        print(f"{FACES_JSON}：{len(table.data)} 行" + (f"，这些图不存在：{bad}" if bad else "，格式都对、图都在"))
        return 1 if bad else 0
    if not rels:
        ap.error("要给图的路径或 --glob")
    if a.cmd == "auto":
        for rel in rels:
            print(rel, estimate(table.root / rel))
        return 0
    for p in draw_sheet(rels, table, a.out, a.per_row, grid=a.grid):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
