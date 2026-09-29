"""tj01 第 5 步（第一场）：拆第 1 场用到的 7 张表，只存清单第三节写的那几件（split_tj01.py 会存全部，这里不存不用的）。

  .venv/Scripts/python video/assets/codex_tj01/split_scene1.py [--list] [表名 ...]

透明底（Codex 自己抠了底、带一圈半透明的光晕）的表用 video/split_alpha.py 的 pieces（只留实心部分）；
绿底的表用 video/split_sheet.py 的 pieces（抠绿）。名字和放置的目录用 split_tj01.py 的 SHEETS，只存 KEEP 里的。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS.parent))
sys.path.insert(0, str(HERE))
import split_alpha  # noqa: E402
import split_sheet  # noqa: E402
import split_tj01 as T  # noqa: E402

KEEP = {
    "hr_sgm": None,   # None = 全存
    "prop_frogs": None,
    "prop_hands": {"hand_grab", "hand_open", "ant", "towel", "cup_plain", "cup_plain_spill"},
    "prop_gauge_hi": None,
    "prop_icons": {"icon_bow", "icon_qin", "icon_heart", "plaque_zhi", "plaque_back"},
    "shadow_zgo": {"zgo_shadow"},
    "shadow_zxu": {"zxu_shadow"},
}
ALPHA = {"prop_frogs", "prop_icons", "shadow_zgo", "shadow_zxu"}   # 透明底的表


def add_satellites(path, ps, reach=90, min_area=250, solid=170):
    """split_alpha 会丢掉面积 < 3000 的小碎片（青蛙头上的晕星星、呱呱叫的小火花）：把离某一件不到 reach 像素的小碎片并回那一件。"""
    im = np.array(Image.open(path).convert("RGBA"))
    lab, n = ndimage.label(im[..., 3] > solid)
    big = [(y, x, y + c.shape[0], x + c.shape[1]) for y, x, c in ps]
    out = [[y, x, y + c.shape[0], x + c.shape[1], c] for y, x, c in ps]
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        m = lab[sl] == i
        if m.sum() < min_area or m.sum() >= 3000:
            continue
        y0, x0, y1, x1 = sl[0].start, sl[1].start, sl[0].stop, sl[1].stop
        # 离哪一件最近（矩形之间的距离）
        best, bd = None, 1e9
        for k, (a, b, c2, d) in enumerate(big):
            dy = max(a - y1, y0 - c2, 0)
            dx = max(b - x1, x0 - d, 0)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < bd:
                best, bd = k, dist
        if best is not None and bd <= reach:
            out[best].append((sl, m))
    res = []
    for o in out:
        y0, x0, y1, x1, c = o[:5]
        extra = o[5:]
        if not extra:
            res.append((y0, x0, c))
            continue
        ny0 = min([y0] + [sl[0].start for sl, _ in extra]); nx0 = min([x0] + [sl[1].start for sl, _ in extra])
        ny1 = max([y1] + [sl[0].stop for sl, _ in extra]); nx1 = max([x1] + [sl[1].stop for sl, _ in extra])
        canvas = np.zeros((ny1 - ny0, nx1 - nx0, 4), np.uint8)
        canvas[y0 - ny0:y1 - ny0, x0 - nx0:x1 - nx0] = c
        for sl, m in extra:
            ys, xs = sl[0].start - ny0, sl[1].start - nx0
            sub = im[sl].copy()
            keep = ndimage.binary_dilation(m, iterations=1)
            sub[..., 3] = np.where(keep, np.maximum(sub[..., 3], np.where(m, 255, 0)), 0)
            region = canvas[ys:ys + sub.shape[0], xs:xs + sub.shape[1]]
            region[...] = np.where((sub[..., 3:4] > region[..., 3:4]), sub, region)
        res.append((ny0, nx0, canvas))
    return res


def fix_zxu(c):
    """智宣子皮影：胳膊和垂下来的竹签之间被 Codex 抠成了一大块半透明的琥珀色（原图那里是光晕，不是皮影）：把这块又平又光滑的棕色区域挖掉。"""
    rgb = c[..., :3].astype(float)
    lum = rgb.mean(-1)
    m1 = ndimage.uniform_filter(lum, 7)
    m2 = ndimage.uniform_filter(lum ** 2, 7)
    std = np.sqrt(np.maximum(m2 - m1 ** 2, 0))
    cand = (std < 4.0) & (c[..., 3] > 0)
    rect = np.zeros_like(cand)
    rect[430:940, 340:540] = True
    cand = ndimage.binary_opening(cand & rect, iterations=2)
    lab, n = ndimage.label(cand)
    sizes = ndimage.sum(cand, lab, range(1, n + 1))
    panel = lab == (1 + int(np.argmax(sizes)))
    panel = ndimage.binary_dilation(panel, iterations=4)
    c = c.copy()
    c[panel, 3] = 0
    return c


def get_pieces(sheet):
    p = str(HERE / f"{sheet}.png")
    if sheet not in ALPHA:
        return split_sheet.pieces(p)
    ps = split_alpha.pieces(p)
    return add_satellites(p, ps) if sheet == "prop_frogs" else ps


def main():
    listing = "--list" in sys.argv
    todo = [a for a in sys.argv[1:] if not a.startswith("--")] or list(KEEP)
    for s in todo:
        dst, rows, names = T.SHEETS[s]
        ps = get_pieces(s)
        if rows == "assembled":
            big = max(ps, key=lambda p: p[2].shape[0] * p[2].shape[1])
            ps, names = [big], names[:1]
        else:
            if len(ps) != sum(rows):
                T.show(s, ps, f"预期 {sum(rows)}  <-- 数量不对，不拆")
                continue
            ps = T.order(ps, rows)
        for (y, x, c), nm in zip(ps, names):
            if KEEP[s] is not None and nm not in KEEP[s]:
                continue
            c = c.copy()
            c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])
            if nm == "zxu_shadow":
                c = fix_zxu(c)
            print(f"{dst}/{nm}.png {c.shape[1]}x{c.shape[0]}  (原表 x={x} y={y})")
            if listing:
                continue
            d = ASSETS / dst
            d.mkdir(parents=True, exist_ok=True)
            Image.fromarray(c, "RGBA").save(d / f"{nm}.png")


if __name__ == "__main__":
    main()
