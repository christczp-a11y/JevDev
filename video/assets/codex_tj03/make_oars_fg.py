"""tj03 builder 做的前景层 chars/rower_oars_fg.png：从 chars/rower_row.png 里把 5 支桨「从近侧船舷上沿往下」的那一截（桨杆 + 桨叶 + 白纸边）抠出来，别的透明，画布和 rower_row 一样大（1526×621）。

用法：.venv/Scripts/python video/assets/codex_tj03/make_oars_fg.py [--cut-y 400] [--check]
  桨不是「靠颜色一把抠」：桨是木棕色，凳子、草鞋带也是木棕色，所以先在每个人身上找桨的轴线（木棕色像素的主轴），
  再只取轴线附近的带状区域里的木棕色（桨杆 + 桨叶 + 深色描边），去掉凳子伸进来的小楔子，最后只留最大的一块；
  白纸边不用原图的（会和凳子、腿的白边连成一片），照原来的宽度（约 11 像素）重画一圈干净的白边。
  --cut-y：船舷上沿在 rower_row 画布里的 y（默认 400：在凳面 y≈420 之上、手和前臂 y≈380 之下，所以 400 以下桨前面没有任何人体）。
  合成时：rower_oars_fg 和 rower_row 同 pos、同 h，叠在 boat_front 前面。船舷上沿线比 cut-y 低没关系（上面那截和 rower_row 里画的一样）；
  比 cut-y 高（> 20 像素）桨在船舷里会有一小段被船身挡掉。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ASSETS = Path(__file__).resolve().parent.parent
SRC = ASSETS / "chars/rower_row.png"
DST = ASSETS / "chars/rower_oars_fg.png"
# 每个人的桨：手握的一端（上）和桨叶尖（下）的大致位置（看 rower_row 定的）
OARS = [((300, 235), (50, 595)), ((590, 235), (335, 600)), ((890, 235), (640, 600)), ((1190, 255), (945, 595)), ((1490, 255), (1235, 600))]
SHAFT_HW, BLADE_HW = 19, 52      # 带状区域的半宽（垂直于轴线，像素）：桨杆木头本身半宽约 15（加深色描边 17），桨叶最宽处半宽约 45


def wood(a):
    r, g, b = (a[..., i].astype(int) for i in range(3))
    return (a[..., 3] > 200) & (r - b >= 45) & (r <= 215) & (g <= 150) & (r >= 60)


def band(shape, p0, p1, hw_shaft, hw_blade):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.array(p1, float) - np.array(p0, float)
    L = np.hypot(*d)
    u = d / L
    t = ((xx - p0[0]) * u[0] + (yy - p0[1]) * u[1])
    n = np.abs(-(xx - p0[0]) * u[1] + (yy - p0[1]) * u[0])
    hw = hw_shaft + (hw_blade - hw_shaft) * np.clip((t - 0.40 * L) / (0.30 * L), 0, 1)       # 桨杆 → 桨叶：从 40% 到 70% 渐宽
    return (t >= -10) & (t <= L + 25) & (n <= hw)


def main():
    cut = int(sys.argv[sys.argv.index("--cut-y") + 1]) if "--cut-y" in sys.argv else 400
    a = np.array(Image.open(SRC).convert("RGBA"))
    H, W = a.shape[:2]
    W_ = wood(a)
    out = np.zeros_like(a)
    for k, (p0, p1) in enumerate(OARS, 1):
        b = band((H, W), p0, p1, SHAFT_HW + 8, BLADE_HW + 12)
        m = W_ & b
        m[:cut] = False
        lab, n = ndimage.label(ndimage.binary_closing(m, iterations=2))
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m &= (lab == 1 + int(np.argmax(sizes)))
        ys, xs = np.nonzero(m)
        # 主轴（PCA）：重新定带
        pts = np.stack([xs, ys], 1).astype(float)
        c = pts.mean(0)
        ev, evec = np.linalg.eigh(np.cov((pts - c).T))
        u = evec[:, -1]
        if u[1] < 0:
            u = -u
        # 沿着轴线从 cut 到桨叶尖
        yb = ys.max()
        end = c + u * ((yb - c[1]) / u[1])
        start = c + u * ((cut - 30 - c[1]) / u[1])
        bd = band((H, W), tuple(start), tuple(end), SHAFT_HW, BLADE_HW)
        core = W_ & bd
        core[:cut] = False
        lab, n = ndimage.label(ndimage.binary_closing(core, iterations=2))
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        core &= (lab == 1 + int(np.argmax(sizes)))
        core = ndimage.binary_closing(core, iterations=3)
        core = ndimage.binary_opening(core, iterations=7)          # 去掉凳子伸进带子里的小楔子（又薄又短）
        lab, n = ndimage.label(core)
        core = lab == 1 + int(np.argmax(ndimage.sum(core, lab, range(1, n + 1))))
        core = ndimage.binary_fill_holes(core)
        # 白纸边：原图里桨边上的白边会和旁边凳子、腿的白边连在一起，所以不用原图的白边，
        # 照原图的宽度（约 11 像素）重画一圈干净的白纸边（和系列其他图的白纸边同色）
        d = ndimage.distance_transform_edt(~core)
        ring_a = np.clip(11.5 - d, 0, 1)
        res = np.zeros_like(a)
        res[..., :3] = (250, 248, 243)
        res[..., 3] = (ring_a * 255).astype(np.uint8)
        res[core] = a[core]
        res[:cut, :, 3] = 0
        out = np.where((res[..., 3:4] > 0), res, out)
        print(f"桨 {k}: 轴方向 {np.degrees(np.arctan2(u[1], u[0])):.0f}°，木头 {int(core.sum())} 像素，y {ys.min()}..{ys.max()}")
    Image.fromarray(out, "RGBA").save(DST)
    print(f"{DST.relative_to(ASSETS)} {W}x{H}")
    if "--check" in sys.argv:
        bg = Image.new("RGBA", (W, H), (200, 230, 255, 255))
        bg.alpha_composite(Image.fromarray(out, "RGBA"))
        bg.convert("RGB").save(ASSETS.parent / "out/tj03/_check_oars_fg.png")


if __name__ == "__main__":
    main()
