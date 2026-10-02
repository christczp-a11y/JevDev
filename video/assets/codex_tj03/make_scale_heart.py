"""tj03 builder 用现成图做的 props/scale_heart_a.png、scale_heart_b.png：天平上的金饼换成「山河」、空白纸条换成「人心」。

用法：.venv/Scripts/python video/assets/codex_tj03/make_scale_heart.py [--check]
  scale_a（金饼那边低）→ scale_heart_a：左盘山河、右盘红心，**山那边低、心那边高**；
  scale_b（纸条那边沉下去）→ scale_heart_b：同样换图，**心那边「咚」地沉下去**。
  底座、立柱、横梁、托盘的位置和 scale_a/b 逐像素一样（只改盘里的东西），所以 a、b 之间换图不跳（和 scale_a / scale_b 的关系一样）。
做法：
  1. 金饼：按颜色抠出金饼的形状；金饼比盘子里能放的东西大，所以用比它大一点的 `mini_mountains`（矮胖拱形，底边平）整个盖住；
     没盖住的少数金饼像素：在托盘后沿以上（背后是透明的）改成透明，在托盘里的用 inpaint 补成木头色。
  2. 纸条：按颜色抠出纸条，用 cv2.inpaint 补成盘底的深棕木头，再把红心的尖尖立在盘底上（红心比纸条窄，两边露出补好的盘底）。
  3. 盘子的前沿（金饼 / 纸条底边以下的几行）从原图贴回来，东西就像放在盘子里（盘沿在前）。
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

ASSETS = Path(__file__).resolve().parent.parent
P = ASSETS / "props"
MT_W, MT_H = 300, 176          # 山河在图里的大小（原图 1294×628 → 横向缩 0.232、纵向缩 0.28，略拉高一点：盖得住金饼两侧的弧）
HEART_W = 236                  # 红心宽（纸条宽 228）

CFG = {
    # 名字: (金饼搜索框 x0,y0,x1,y1, 纸条搜索框)
    "a": ((60, 640, 360, 810), (880, 500, 1190, 625)),
    "b": ((60, 360, 360, 530), (880, 725, 1190, 850)),
}


def coin_mask(a, box):
    R, G, B = (a[..., i].astype(int) for i in range(3))
    m = ((R > 225) & (G > 165) & (B < 130) & (R - B > 110)) | ((R >= 150) & (B <= 40) & (G >= 75) & (G <= 150) & (R - B >= 110))
    sel = np.zeros_like(m)
    x0, y0, x1, y1 = box
    sel[y0:y1, x0:x1] = True
    m &= sel
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))
    m = ndimage.binary_opening(m, iterations=3)
    lab, n = ndimage.label(m)
    return lab == 1 + int(np.argmax(ndimage.sum(m, lab, range(1, n + 1))))


def paper_mask(a, box, dy=0):
    R, G, B = (a[..., i].astype(int) for i in range(3))
    m = (R > 225) & (G > 195) & (B > 165) & (R - B >= 28) & (R - B <= 80)
    sel = np.zeros(m.shape, np.uint8)       # 纸条是个四边形（scale_a 里的四个角；scale_b 整体下移 dy）：只在它外面扩 5 像素的范围里找
    quad = np.array([(968, 516), (1146, 530), (1126, 604), (904, 594)]) + np.array([0, dy])
    cv2.fillConvexPoly(sel, quad.astype(np.int32), 1)
    m &= ndimage.binary_dilation(sel.astype(bool), iterations=5)
    m = ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=2))
    lab, n = ndimage.label(m)
    return lab == 1 + int(np.argmax(ndimage.sum(m, lab, range(1, n + 1))))


def floor_fill(rgb, m, ytop, ybot):
    """纸条盖住的盘底补成深棕木头：用纸条周围「盘底」像素（深棕、不是绳子、不是前沿浅色盘沿）做归一化高斯平滑得到底色，
    再压一层横向的细木纹，边缘羽化 1.5 像素。（cv2.inpaint 会把前面盘沿的浅色拉进来，补出一块发白的楔子；单一渐变色又像一块贴上去的补丁，所以都不用。）"""
    f = rgb.astype(float)
    R, G, B = f[..., 0], f[..., 1], f[..., 2]
    ring = ndimage.binary_dilation(m, iterations=26) & ~ndimage.binary_dilation(m, iterations=3)
    yy = np.mgrid[0:rgb.shape[0], 0:rgb.shape[1]][0]
    valid = ring & (R < 178) & (R > 45) & (G < 0.66 * R) & (yy < ybot - 4)      # 周围的盘底：偏红的棕（绳子、前沿浅色盘沿 G/R 更高，排除）
    k = 22.0
    num = np.stack([ndimage.gaussian_filter(f[..., c] * valid, k) for c in range(3)], -1)
    den = ndimage.gaussian_filter(valid.astype(float), k)[..., None]
    mean = np.array([f[..., c][valid].mean() for c in range(3)])             # 周围盘底的平均色：离得远（平滑权重太小）的地方用它
    wgt = np.clip(den / 0.12, 0, 1)
    base = (num / np.maximum(den, 1e-4)) * wgt + mean * (1 - wgt)
    rng = np.random.default_rng(3)
    n1 = ndimage.gaussian_filter(rng.normal(0, 1, R.shape), (0.9, 16.0))
    n1 = n1 / n1.std()
    dark = np.clip((-n1 - 0.9) / 1.2, 0, 1) * 0.32                                  # 几条深色木纹
    light = np.clip((n1 - 1.0) / 1.2, 0, 1) * 0.12
    new = base * (1 - dark[..., None] + light[..., None]) + ndimage.gaussian_filter(rng.normal(0, 1, R.shape), 1.0)[..., None] * 4
    w = ndimage.gaussian_filter(ndimage.binary_erosion(m, iterations=2).astype(float), 2.5)[..., None]
    return (f * (1 - w) + new * w).clip(0, 255).astype(np.uint8)


def paste(dst, src, x0, y0):
    """src（RGBA）按 alpha 叠到 dst（RGBA 数组）的 (x0, y0)。"""
    s = np.array(src).astype(float)
    h, w = s.shape[:2]
    ys, xs = max(0, y0), max(0, x0)
    ye, xe = min(dst.shape[0], y0 + h), min(dst.shape[1], x0 + w)
    s = s[ys - y0:ye - y0, xs - x0:xe - x0]
    d = dst[ys:ye, xs:xe].astype(float)
    sa = s[..., 3:4] / 255
    da = d[..., 3:4] / 255
    oa = sa + da * (1 - sa)
    rgb = (s[..., :3] * sa + d[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    dst[ys:ye, xs:xe] = np.concatenate([rgb, oa * 255], -1).clip(0, 255).astype(np.uint8)


def rim_top(x, dx=0, dy=0):
    """托盘后沿（连白纸边）的上缘：椭圆近似（scale_a 的左盘；scale_b 平移 dx、dy）。"""
    return 772 + dy - 68 * np.sqrt(np.clip(1 - ((x - dx - 207) / 190) ** 2, 0, 1)) - 8


def build(key):
    src = np.array(Image.open(P / f"scale_{key}.png").convert("RGBA"))
    a = src.copy()
    cbox, pbox = CFG[key]
    coin, paper = coin_mask(src, cbox), paper_mask(src, pbox, 0 if key == "a" else 224)
    cy, cx = np.nonzero(coin)
    base_y, ccx = int(cy.max()) + 1, int(round((cx.min() + cx.max()) / 2))
    py, px = np.nonzero(paper)
    pbase, pcx = int(py.max()) + 1, int(round(px.mean()))
    # 1. 纸条 → 补成盘底
    pm = ndimage.binary_dilation(ndimage.binary_closing(paper, iterations=8), iterations=10)
    qb = 604 + (0 if key == 'a' else 224)                       # 纸条四边形的最低点：这一行以下是盘沿内侧，原样保留
    pm[qb:] = False
    a[..., :3] = floor_fill(a[..., :3], pm, py.min(), py.max())
    # 2. 金饼没被山河盖住的部分先处理：托盘后沿以上（背后是透明的）→ 透明；托盘里的 → inpaint
    dx, dy = ccx - 209, base_y - 797
    mt = Image.open(P / "mini_mountains.png").convert("RGBA").resize((MT_W, MT_H), Image.LANCZOS)
    mx0, my0 = ccx - MT_W // 2, base_y - MT_H
    cover = np.zeros(coin.shape, bool)
    cover[my0:my0 + MT_H, mx0:mx0 + MT_W] = np.array(mt)[..., 3] > 128
    left = ndimage.binary_dilation(coin, iterations=2) & ~ndimage.binary_erosion(cover, iterations=2)
    yy, xx = np.mgrid[0:coin.shape[0], 0:coin.shape[1]]
    above = left & (yy < rim_top(xx, dx, dy))
    inside = left & ~above
    a[..., :3] = cv2.inpaint(np.ascontiguousarray(a[..., :3]), inside.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
    a[above, 3] = 0
    print(f"scale_{key}: 金饼 x {cx.min()}–{cx.max()} y {cy.min()}–{cy.max()}，山河盖不住的 {int(left.sum())} 像素（托盘后沿以上 {int(above.sum())}，盘里 {int(inside.sum())}）；纸条 y {py.min()}–{py.max()}")
    # 3. 放山河、红心
    paste(a, mt, mx0, my0)
    hr = Image.open(P / "heart_paper.png").convert("RGBA")
    hh = round(HEART_W * hr.height / hr.width)
    hr = hr.resize((HEART_W, hh), Image.LANCZOS)
    paste(a, hr, pcx - HEART_W // 2, pbase - 6 - hh)
    # 4. 盘子的前沿（东西底边以下）从原图贴回来
    a[base_y:, :425] = src[base_y:, :425]
    a[qb:, 830:1225] = src[qb:, 830:1225]
    # 山河底边正好落在盘沿内侧；贴回来的行里没有金饼 / 纸条，所以不会带回旧东西
    return a


def main():
    for key in ("a", "b"):
        a = build(key)
        Image.fromarray(a, "RGBA").save(P / f"scale_heart_{key}.png")
        print(f"props/scale_heart_{key}.png {a.shape[1]}x{a.shape[0]}")
    if "--check" in sys.argv:
        for key in ("a", "b"):
            im = Image.open(P / f"scale_heart_{key}.png").convert("RGBA")
            bg = Image.new("RGBA", im.size, (226, 214, 190, 255))
            bg.alpha_composite(im)
            bg.convert("RGB").save(ASSETS.parent / "out/tj03" / f"_check_scale_heart_{key}.png")


if __name__ == "__main__":
    main()
