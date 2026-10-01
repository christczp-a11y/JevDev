"""tj02 第 5 步（画面素材）：把 Codex 新画的整幅图、布景、表情组、泡泡、道具拆好放进 sets/ chars/ props/。

用法（仓库根目录，Git Bash，PYTHONIOENCODING=utf-8）：
  .venv/Scripts/python video/assets/codex_tj02/split_tj02_5.py --list         # 列出所有任务和原图有没有画好
  .venv/Scripts/python video/assets/codex_tj02/split_tj02_5.py <任务> ...      # 只拆指定的（不写 = 全部画好的）；不覆盖第 5 步以前拆好的东西

任务分四类：
  PLAIN   绿底素材表，按位置（先行后列）一一对应名字：直接用 split_tj02.split 的 pieces
  SINGLE  一张图一个东西（整幅人物、布景、泡泡）：整张抠绿，去碎点，裁到外框
  ALIGN   表情组 / 同底座的两张图：每张单独抠绿后，按「应该不动的那一部分」对位，裁成同样大小的画布
  其他    sky_rain（整幅不透明原样拷贝）、mud（路面条+炭盆+纸鸟）、magnifier（镜片抠成透明）、boat（一条船拆前后两层）
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
import split_sheet  # noqa: E402
import split_tj02 as S2  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 表名: (目的文件夹, 每行几件, 名字从左到右)
PLAIN = {
    "paperman": ("props", [3], ["paperman_wave", "paperman_shrug", "paperman_thumb"]),
    "flags_pigeon": ("props", [4], ["flag_plain_a", "flag_plain_b", "flag_plain_c", "pigeon_king"]),
    "frogs": ("props", [3], ["frog_leaf", "frog_leaf_sigh", "frog_proud"]),
    "hands_remote": ("props", [2], ["hands_suoyi", "remote"]),
    "yr_l_a": ("chars", [2], ["yr_sit_l", "yr_kneel_l"]),
}
# 任务名: 目的路径（整张图抠绿、去碎点、裁到外框）
SINGLE = {
    "sgm_hi_magnify": "chars/sgm_hi_magnify.png",
    "wuh_point": "chars/wuh_point.png",
    "wdc_run": "chars/wdc_run.png",
    "wdc_pant": "chars/wdc_pant.png",
    "yr_l_b": "chars/yr_helped_l.png",
    "magnet": "props/magnet.png",
    "set_hut": "sets/mountain/hut.png",
    "bubble_sweeper": "props/bubble_sweeper.png",
    "bubble_shoe_mud": "props/bubble_shoe_mud.png",
    "bubble_rain_meet": "props/bubble_rain_meet.png",
    "bubble_watch_msg": "props/bubble_watch_msg.png",
    "bubble_door": "props/bubble_door.png",
}
# 对位组: 任务名: ([原图...], [目的路径...], 对位用的行段（占第一张人物高度的 (起, 止) 比例；用「应该不动」的那一部分）)
ALIGN = {
    "wwh_rain": (["wwh_rain_a", "wwh_rain_b", "wwh_rain_c"],
                 ["chars/wwh_hi_rain_firm.png", "chars/wwh_hi_rain_mud.png", "chars/wwh_hi_rain_smile.png"], (0.0, 0.45)),
    "yr_hi": (["yr_hi_a", "yr_hi_b", "yr_hi_c"],
              ["chars/yr_hi_sigh_l.png", "chars/yr_hi_cry_l.png", "chars/yr_hi_laugh_l.png"], (0.0, 0.40)),
    "scale": (["scale_a", "scale_b"], ["props/scale_a.png", "props/scale_b.png"], (0.90, 1.0)),
}
SPECIAL = ["sky_rain", "mud", "magnifier", "boat"]


# ---------------------------------------------------------------- 基础函数
def keyed_full(path, min_area=150):
    """整张图抠绿 -> RGBA（和原图同大小），去掉面积小于 min_area 的碎点。"""
    src = Image.open(path)
    if src.mode == "RGBA" and (np.array(src)[..., 3] < 20).mean() > 0.2:
        rgba = np.array(src)
    else:
        rgba = split_sheet.key_out(np.array(src.convert("RGB")))
    rgba = rgba.copy()
    mask = rgba[..., 3] > 60
    lab, n = ndimage.label(ndimage.binary_closing(mask, iterations=2))
    if n:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= min_area])
        rgba[~keep, 3] = 0
    return rgba


def bbox(a, thr=60):
    ys, xs = np.where(a[..., 3] > thr)
    return int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1


def crop(a, box=None):
    y0, y1, x0, x1 = box or bbox(a)
    return a[y0:y1, x0:x1].copy()


def save(dst, arr):
    p = ASSETS / dst
    p.parent.mkdir(parents=True, exist_ok=True)
    arr = arr.copy()
    arr[..., 3] = np.where(arr[..., 3] >= 240, 255, arr[..., 3])
    Image.fromarray(arr, "RGBA").save(p)
    print(f"{dst} {arr.shape[1]}x{arr.shape[0]}")


def shifted(a, dy, dx, H, W):
    out = np.zeros((H, W, 4), np.uint8)
    ys, xs = max(0, dy), max(0, dx)
    ye, xe = min(H, H + dy), min(W, W + dx)
    out[ys:ye, xs:xe] = a[ys - dy:ye - dy, xs - dx:xe - dx]
    return out


def best_shift(ref, mov, rows, search=90):
    """把 mov 平移 (dy, dx) 才能和 ref 在 rows=(y0,y1) 这几行的轮廓对上。用 alpha 的互相关（FFT）。"""
    A = np.zeros(ref.shape[:2], np.float32)
    A[rows[0]:rows[1]] = (ref[rows[0]:rows[1], :, 3] > 60)
    B = (mov[..., 3] > 60).astype(np.float32)
    corr = np.fft.irfft2(np.fft.rfft2(A) * np.conj(np.fft.rfft2(B)), s=A.shape)   # corr[dy,dx] = sum A(y,x) B(y-dy,x-dx)
    H, W = A.shape
    best, arg = -1, (0, 0)
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            v = corr[dy % H, dx % W]
            if v > best:
                best, arg = v, (dy, dx)
    return arg


def align_group(srcs, rows_frac, report=True):
    """每张抠绿 -> 以第一张为准平移对位 -> 按所有张的并集外框裁成同样大小。返回 [RGBA...]。"""
    arrs = [keyed_full(HERE / f"{s}.png") for s in srcs]
    H, W = arrs[0].shape[:2]
    y0, y1, _, _ = bbox(arrs[0])
    rows = (y0 + int((y1 - y0) * rows_frac[0]), y0 + int((y1 - y0) * rows_frac[1]))
    out, info = [arrs[0]], []
    for s, a in zip(srcs[1:], arrs[1:]):
        dy, dx = best_shift(arrs[0], a, rows)
        out.append(shifted(a, dy, dx, H, W))
        # 对位行段内轮廓的重合度（IoU）
        ra, rb = arrs[0][rows[0]:rows[1], :, 3] > 60, out[-1][rows[0]:rows[1], :, 3] > 60
        info.append((s, dy, dx, (ra & rb).sum() / max(1, (ra | rb).sum())))
    boxes = [bbox(a) for a in out]
    box = (min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes))
    if report:
        for s, dy, dx, iou in info:
            print(f"   对位 {s}: 平移 dy={dy} dx={dx}，对位行段轮廓重合 {iou:.3f}")
    return [crop(a, box) for a in out]


# ---------------------------------------------------------------- 各类任务
def do_plain(name):
    dst, rows, names = PLAIN[name]
    ps = S2.load_pieces(name)
    if len(ps) != sum(rows):
        S2.show(name, ps, f"预期 {sum(rows)}  <-- 数量不对，不拆")
        return
    for (y, x, c), nm in zip(S2.order(ps, rows), names):
        save(f"{dst}/{nm}.png", c)
    if name == "frogs":
        fix_frog_leaves()


def recolor_leaf(rel, region):
    """荷叶被 Codex 画成了灰黑色：把区域里「偏中性灰的暗色」改成中绿（保留明暗和叶脉）。手工修（和 wdc_c_cup 涂白水珠同类）。"""
    p = ASSETS / rel
    a = np.array(Image.open(p).convert("RGBA")).astype(np.float32)
    rgb = a[..., :3]
    mx, mn = rgb.max(2), rgb.min(2)
    sat = (mx - mn) / np.maximum(mx, 1)
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    reg = region(yy, xx)
    leaf = reg & (a[..., 3] > 40) & (mx < 175) & (sat < 0.38) & (rgb[..., 1] >= rgb[..., 2] - 2)
    leaf = ndimage.binary_closing(leaf, iterations=2) & reg & (a[..., 3] > 40) & (mx < 190)
    v = mx / 255.0
    new = np.clip(np.stack([v * 255 * 0.50, v * 255 * 1.02 + 10, v * 255 * 0.42], axis=-1), 0, 255)
    wgt = ndimage.gaussian_filter(leaf.astype(np.float32), 0.8)[..., None] * leaf[..., None]
    out = a.copy()
    out[..., :3] = rgb * (1 - wgt) + new * wgt
    Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA").save(p)
    print(f"   {rel}：荷叶 {int(leaf.sum())} 像素改成中绿")


def fix_frog_leaves():
    recolor_leaf("props/frog_leaf.png", lambda yy, xx: yy < 250)                    # 头顶的大荷叶（青蛙头顶在 y≈250 以下）
    recolor_leaf("props/frog_leaf_sigh.png", lambda yy, xx: (xx < 215) & (yy > 250))   # 脚边卷着的荷叶


def do_single(name):
    save(SINGLE[name], crop(keyed_full(HERE / f"{name}.png")))


def do_align(name):
    srcs, dsts, rows = ALIGN[name]
    for d, a in zip(dsts, align_group(srcs, rows)):
        save(d, a)


def do_sky_rain():
    im = Image.open(HERE / "set_sky_rain.png").convert("RGBA")
    p = ASSETS / "sets/jin_land/sky_rain.png"
    im.save(p)
    print(f"sets/jin_land/sky_rain.png {im.width}x{im.height}")


def seamless(a, n=70):
    """路面条左右无缝：最右边 n 列逐渐过渡成「最左边那一列的镜像」，这样最右一列和最左一列接得上（宽度不变）。"""
    out = a.copy().astype(np.float32)
    W = a.shape[1]
    for j in range(n):                      # j=0 是最右一列
        w = 1 - j / n
        out[:, W - 1 - j] = (1 - w) * a[:, W - 1 - j] + w * a[:, j]
    return out.round().clip(0, 255).astype(np.uint8)


def do_mud():
    ps = split_sheet.pieces(str(HERE / "set_mud.png"))
    if len(ps) != 3:
        S2.show("set_mud", ps, "预期 3 <-- 数量不对，不拆")
        return
    ps = sorted(ps, key=lambda p: p[2].shape[1], reverse=True)       # 最宽的是路面条
    strip = ps[0][2]
    rest = sorted(ps[1:], key=lambda p: p[1])                        # 左：炭盆，右：纸鸟
    seam = np.abs(strip[:, 0, :3].astype(int) - strip[:, -1, :3].astype(int)).mean()
    print(f"   路面条原宽 {strip.shape[1]}x{strip.shape[0]}，左右两列平均色差 {seam:.1f}")
    save("sets/mountain/mud_road.png", seamless(strip))
    save("props/brazier.png", rest[0][2])
    save("props/bird_news.png", rest[1][2])


def do_magnifier():
    a = keyed_full(HERE / "magnifier.png", min_area=40)
    solid = a[..., 3] > 60
    lab, n = ndimage.label(solid)
    sizes = ndimage.sum(solid, lab, range(1, n + 1))
    ring = lab == (1 + int(np.argmax(sizes)))                           # 框 + 柄是最大的一块
    lens = ndimage.binary_fill_holes(ring) & ~ring                      # 圆框里面
    inner = lens & solid                                                 # 镜片里的白色反光弧线：变成半透明
    a[inner, 3] = (a[inner, 3] * 0.45).astype(np.uint8)
    a[lens & ~solid, 3] = 0
    ys, xs = np.where(lens)
    print(f"   镜片内径 约 {xs.max() - xs.min()}x{ys.max() - ys.min()}（镜片面积 {int(lens.sum())} 像素）")
    save("props/magnifier.png", crop(a))


def do_boat():
    """一整条船拆成两层（同一块画布，叠起来 = 原图）。near = 近侧船舷（上沿线以下的船身）；back = 其余（舱、远侧、橹、甲板）。
    近侧船舷上沿线由 BOAT_LINE 给出（在裁完边的画布上量的）；没量好之前只裁边、不拆。"""
    a = crop(keyed_full(HERE / "boat.png"))
    Image.fromarray(a, "RGBA").save(HERE / "boat_crop.png")           # 裁完边的整条船（量近侧船舷线用；不进 assets，不用登记）
    print(f"   整条船裁边后 {a.shape[1]}x{a.shape[0]}（boat_crop.png）")
    if not BOAT_LINE:
        print("   BOAT_LINE 还没量，先只存 boat_crop.png")
        return
    H, W = a.shape[:2]
    xs = np.arange(W)
    px, py = zip(*BOAT_LINE)
    top = np.interp(xs, px, py)                                          # 每一列近侧船舷上沿的 y
    yy = np.arange(H)[:, None]
    F = yy >= top[None, :]
    front, back = a.copy(), a.copy()
    front[~F] = 0
    back[F] = 0
    save("props/boat_back.png", back)
    save("props/boat_front.png", front)


BOAT_LINE = [(0, 1000), (236, 1000), (237, 105), (242, 106), (300, 114), (350, 123), (400, 137), (500, 152), (600, 166), (700, 178),
             (800, 186), (900, 193), (1000, 198), (1100, 201), (1200, 203), (1300, 203), (1400, 199), (1500, 191), (1550, 187),
             (1650, 172), (1750, 152), (1800, 135), (1850, 115), (1890, 92), (1915, 76), (1925, 72), (1926, 0), (1969, 0)]
# 近侧船舷上沿线（在 boat_crop.png 上逐段对着放大图量的：1969×410）：这条线以下是近侧船身（前层），以上是舱、远侧船舷、甲板、橹（后层）；
# 船尾（x<236）只有橹，全在后层；船头 x>=1926 的艏柱算前层


TASKS = {}
TASKS.update({k: (lambda k=k: do_plain(k)) for k in PLAIN})
TASKS.update({k: (lambda k=k: do_single(k)) for k in SINGLE})
TASKS.update({k: (lambda k=k: do_align(k)) for k in ALIGN})
TASKS.update({"sky_rain": do_sky_rain, "mud": do_mud, "magnifier": do_magnifier, "boat": do_boat})
SOURCES = {"sky_rain": ["set_sky_rain"], "mud": ["set_mud"], "magnifier": ["magnifier"], "boat": ["boat"]}
SOURCES.update({k: [k] for k in list(PLAIN) + list(SINGLE)})
SOURCES.update({k: v[0] for k, v in ALIGN.items()})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ready = {k: all((HERE / f"{s}.png").exists() for s in SOURCES[k]) for k in TASKS}
    if "--list" in sys.argv:
        for k in TASKS:
            print(f"{'已画' if ready[k] else '未画'}  {k}")
        return
    for k in args or [k for k in TASKS if ready[k]]:
        if not ready[k]:
            print(f"缺原图，跳过 {k}")
            continue
        print(f"== {k}")
        TASKS[k]()


if __name__ == "__main__":
    main()
