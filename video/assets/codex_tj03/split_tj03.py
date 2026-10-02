"""tj03 第 5 步（提前）：把 Codex 出的素材表拆成单件 PNG 放进 chars/；表情组（同一块画布）抠绿后按「应该不动」的那一部分对位。

用法（仓库根目录，Git Bash，PYTHONIOENCODING=utf-8）：
  .venv/Scripts/python video/assets/codex_tj03/split_tj03.py --list         # 每个任务切出几件、原图画好没有
  .venv/Scripts/python video/assets/codex_tj03/split_tj03.py [任务 ...]     # 拆图；不写 = 全部画好的
数量对不上就不拆，只打印每件的位置和大小，照着改 SHEETS。排序：先按竖直中心分成行（rows 写每行几件），再在行内从左到右；名字和提示词里的顺序一一对应。
拆图、抠绿、对位的函数直接用 tj02 的（split_tj02_5.py），只把它读原图的目录换成本目录。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS.parent))
sys.path.insert(0, str(ASSETS / "codex_tj02"))
import split_sheet  # noqa: E402
import split_tj02 as S2  # noqa: E402
import split_tj02_5 as S5  # noqa: E402

S5.HERE = HERE
S2.HERE = HERE
sys.stdout.reconfigure(encoding="utf-8")

# 表名: (目的文件夹, 每行几件, 名字从左到右)
SHEETS = {
    "wuh_pose_a": ("chars", [2, 2], ["wuh_stand", "wuh_stand_l", "wuh_laugh", "wuh_ponder"]),
    "wuh_pose_b": ("chars", [3], ["wuh_shock", "wuh_shock_l", "wuh_bow_l"]),
    "wq_pose": ("chars", [3, 2], ["wq_frown_l", "wq_point_l", "wq_speak_l", "wq_speak", "wq_bow_l"]),
    "preview_chars": ("chars", [2, 2], ["zs_stand", "wh_stand_l", "gb_stand_l", "gb_scratch_l"]),
    # ---- 第 5 步（画面素材）新画的 ----
    "wuh_pose_c": ("chars", [2], ["wuh_bow", "wuh_ponder_l"]),                       # C1 朝右的拱手、C2 朝左的沉思（重画，不是 flip）
    "props_a": ("props", [2, 2], ["cloud_rain_small", "egg", "_mini_mountains_v1", "heart_paper"]),   # P4、P5、(P6 第一版：太扁盖不住金饼，换成 mini_mountains.png)、P7；名字以 _ 开头的不存
    "icons_boat": ("props", [2], ["icon_boat", "icon_guard"]),                        # P8、P9
}
# 新图只抠「外面」的绿底（从图边往里连通的纯绿）：里面的草地、山、灌木是绿的，不能被抠掉（split_sheet.key_out 会把 G>max(R,B)+30 的像素变半透明、改色）
EXT = {"wuh_pose_c", "props_a", "icons_boat", "mini_mountains", "card_sanmiao", "card_xiajie", "card_shangzhou",
       "bubble_wall_nap", "bubble_knight_a", "bubble_knight_bc", "bubble_knight_d"}
GROUP_CLOSING = {"props_a": 14}      # 云 + 雨滴要算同一件：闭运算 14 像素把它们连起来（件和件之间的空隙都大于 30）
# 任务名: 目的路径（整张图抠绿、去碎点、裁到外框）
SINGLE = {
    "mini_mountains": "props/mini_mountains.png",                 # P6（第二版：矮胖的拱形外轮廓，盖得住天平上的金饼）
    "card_sanmiao": "props/card_sanmiao.png", "card_xiajie": "props/card_xiajie.png", "card_shangzhou": "props/card_shangzhou.png",   # P1–P3
    "bubble_wall_nap": "props/bubble_wall_nap.png", "bubble_knight_a": "props/bubble_knight_a.png",                           # B1、B2
    "bubble_knight_bc": "props/bubble_knight_bc.png", "bubble_knight_d": "props/bubble_knight_d.png",                         # B3、B4
}
# 同一块画布、不对位（两张图里的人本来就画在差不多的位置，不平移；只按两张的并集外框裁成同样大小）：任务名: ([原图...], [目的路径...])
SAME_CANVAS = {
    "rower": (["rower_row", "rower_stop"], ["chars/rower_row.png", "chars/rower_stop.png"]),
}
# 对位组: 任务名: ([原图...], [目的路径...], 对位用的行段（占第一张人物高度的 (起, 止) 比例；用「应该不动」的那一部分）)
ALIGN = {
    "wuh_hi": (["wuh_hi_a", "wuh_hi_b", "wuh_hi_c"], ["chars/wuh_hi_nod.png", "chars/wuh_hi_laugh.png", "chars/wuh_hi_sweat.png"], (0.55, 1.0)),
    "wq_hi": (["wq_hi_a", "wq_hi_b", "wq_hi_c"], ["chars/wq_hi_frown.png", "chars/wq_hi_speak.png", "chars/wq_hi_nod.png"], (0.55, 1.0)),
}


def key_exterior(rgb):
    """只抠外面的绿底：从图边往里连通的「很绿」的像素 → 透明；紧贴它的 3 像素圈里按绿的程度半透明并去绿边；里面的绿色（草地、山、灌木）原样不动。"""
    r, g, b = (rgb[..., i].astype(float) for i in range(3))
    k = g - np.maximum(r, b)
    key = (k > 60) & (g > 150)
    lab, n = ndimage.label(key)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    ext = np.isin(lab, list(edge))
    ring = ndimage.binary_dilation(ext, iterations=3) & ~ext
    alpha = np.ones_like(k)
    alpha[ext] = 0
    alpha[ring] = np.clip(1 - (k[ring] - 15) / 70, 0, 1)
    g2 = g.copy()
    g2[ring] = np.minimum(g[ring], np.maximum(r, b)[ring])      # 圈里去绿边：绿不超过红蓝
    return np.dstack([r, g2, b, alpha * 255]).clip(0, 255).astype(np.uint8)


def pieces_ext(path, closing=4, min_area=3000):
    rgba = key_exterior(np.array(Image.open(path).convert("RGB")))
    mask = rgba[..., 3] > 60
    lab, n = ndimage.label(ndimage.binary_closing(mask, iterations=closing))
    objs = ndimage.find_objects(lab)
    for i, a in enumerate(objs, 1):          # 整个落在别的件的外框里的小件（云下面挂着的第三颗雨滴）并进那一件
        for j, b in enumerate(objs, 1):
            if i != j and (lab == j).any() and a[0].start >= b[0].start and a[0].stop <= b[0].stop and a[1].start >= b[1].start and a[1].stop <= b[1].stop                     and (lab[a] == i).sum() < (lab[b] == j).sum():
                lab[lab == i] = j
                break
    objs = ndimage.find_objects(lab)
    out = []
    for i, sl in enumerate(objs, 1):
        if sl is None or (lab[sl] == i).sum() < min_area:
            continue
        crop = rgba[sl].copy()
        crop[..., 3] = np.where(lab[sl] == i, crop[..., 3], 0)
        out.append((sl[0].start, sl[1].start, crop))
    return out


def get_pieces(name):
    if name in EXT:
        return pieces_ext(str(HERE / f"{name}.png"), GROUP_CLOSING.get(name, 4))
    return split_sheet.pieces(str(HERE / f"{name}.png"))


def fix_heart():
    """Codex 画的红心偏亮（平均 219,52,51），清单要系列红 #c8372d（200,55,45）：只把红色的纸面按通道比例拉到目标色（纹理、白纸边不动）。"""
    p = ASSETS / "props/heart_paper.png"
    a = np.array(Image.open(p).convert("RGBA")).astype(float)
    red = (a[..., 3] > 250) & (a[..., 0] > 150) & (a[..., 1] < 110) & (a[..., 2] < 110) & (a[..., 0] - a[..., 1] > 80)
    mean = a[red][:, :3].mean(0)
    k = np.array([200, 55, 45]) / mean
    w = ndimage.gaussian_filter(red.astype(float), 1.0)[..., None]
    a[..., :3] = a[..., :3] * (1 - w) + (a[..., :3] * k) * w
    Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA").save(p)
    print(f"   heart_paper 红色 {mean.round(0)} -> #c8372d")


def do_sheet(name):
    dst, rows, names = SHEETS[name]
    ps = get_pieces(name)
    if len(ps) != sum(rows):
        S2.show(name, ps, f"预期 {sum(rows)}  <-- 数量不对，不拆")
        return
    for (y, x, c), nm in zip(S2.order(ps, rows), names):
        if nm.startswith("_"):
            continue
        c = c.copy()
        c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])
        S5.save(f"{dst}/{nm}.png", c)
    if name == "props_a":
        fix_heart()


def do_single(name):
    if name in EXT:
        split_sheet.key_out_saved, split_sheet.key_out = split_sheet.key_out, key_exterior      # keyed_full 里用的是 split_sheet.key_out
        try:
            a = S5.keyed_full(HERE / f"{name}.png")
        finally:
            split_sheet.key_out = split_sheet.key_out_saved
    else:
        a = S5.keyed_full(HERE / f"{name}.png")
    S5.save(SINGLE[name], S5.crop(a))


def do_align(name):
    srcs, dsts, rows = ALIGN[name]
    for d, a in zip(dsts, S5.align_group(srcs, rows)):
        S5.save(d, a)


def do_same_canvas(name):
    srcs, dsts = SAME_CANVAS[name]
    arrs = [S5.keyed_full(HERE / f"{s}.png") for s in srcs]
    boxes = [S5.bbox(a) for a in arrs]
    box = (min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes))
    for d, a in zip(dsts, arrs):
        S5.save(d, S5.crop(a, box))


TASKS = {}
TASKS.update({k: (lambda k=k: do_sheet(k)) for k in SHEETS})
TASKS.update({k: (lambda k=k: do_same_canvas(k)) for k in SAME_CANVAS})
TASKS.update({k: (lambda k=k: do_single(k)) for k in SINGLE})
TASKS.update({k: (lambda k=k: do_align(k)) for k in ALIGN})
SOURCES = {k: [k] for k in list(SHEETS) + list(SINGLE)}
SOURCES.update({k: v[0] for k, v in ALIGN.items()})
SOURCES.update({k: v[0] for k, v in SAME_CANVAS.items()})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ready = {k: all((HERE / f"{s}.png").exists() for s in SOURCES[k]) for k in TASKS}
    if "--list" in sys.argv:
        for k in TASKS:
            print(f"{'已画' if ready[k] else '未画'}  {k}")
            if ready[k] and k in SHEETS:
                S2.show(k, get_pieces(k), f"预期 {sum(SHEETS[k][1])}")
        return
    for k in args or [k for k in TASKS if ready[k]]:
        if not ready[k]:
            print(f"缺原图，跳过 {k}")
            continue
        print(f"== {k}")
        TASKS[k]()


if __name__ == "__main__":
    main()
