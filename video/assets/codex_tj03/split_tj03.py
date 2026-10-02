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
}
# 任务名: 目的路径（整张图抠绿、去碎点、裁到外框）
SINGLE = {}
# 同一块画布、不对位（两张图里的人本来就画在差不多的位置，不平移；只按两张的并集外框裁成同样大小）：任务名: ([原图...], [目的路径...])
SAME_CANVAS = {
    "rower": (["rower_row", "rower_stop"], ["chars/rower_row.png", "chars/rower_stop.png"]),
}
# 对位组: 任务名: ([原图...], [目的路径...], 对位用的行段（占第一张人物高度的 (起, 止) 比例；用「应该不动」的那一部分）)
ALIGN = {
    "wuh_hi": (["wuh_hi_a", "wuh_hi_b", "wuh_hi_c"], ["chars/wuh_hi_nod.png", "chars/wuh_hi_laugh.png", "chars/wuh_hi_sweat.png"], (0.55, 1.0)),
    "wq_hi": (["wq_hi_a", "wq_hi_b", "wq_hi_c"], ["chars/wq_hi_frown.png", "chars/wq_hi_speak.png", "chars/wq_hi_nod.png"], (0.55, 1.0)),
}


def do_sheet(name):
    dst, rows, names = SHEETS[name]
    ps = split_sheet.pieces(str(HERE / f"{name}.png"))
    if len(ps) != sum(rows):
        S2.show(name, ps, f"预期 {sum(rows)}  <-- 数量不对，不拆")
        return
    for (y, x, c), nm in zip(S2.order(ps, rows), names):
        c = c.copy()
        c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])
        S5.save(f"{dst}/{nm}.png", c)


def do_single(name):
    S5.save(SINGLE[name], S5.crop(S5.keyed_full(HERE / f"{name}.png")))


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
                S2.show(k, split_sheet.pieces(str(HERE / f"{k}.png")), f"预期 {sum(SHEETS[k][1])}")
        return
    for k in args or [k for k in TASKS if ready[k]]:
        if not ready[k]:
            print(f"缺原图，跳过 {k}")
            continue
        print(f"== {k}")
        TASKS[k]()


if __name__ == "__main__":
    main()
