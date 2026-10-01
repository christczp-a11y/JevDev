"""tj02 第 5 步（提前）：把 Codex 出的素材表拆成单件 PNG 放进 chars/、props/（用 video/split_sheet.py 的 pieces：绿底和透明底都行）。

用法（仓库根目录）：
  .venv/Scripts/python video/assets/codex_tj02/split_tj02.py --list            # 每张表切出几件、每件多大（先看数量对不对）
  .venv/Scripts/python video/assets/codex_tj02/split_tj02.py [表名 ...]        # 拆图；不写表名 = 全部已经画好的
排序：先按每件的竖直中心分成行（rows 写每行几件），再在行内从左到右；名字和提示词（同名 .txt）里的顺序一一对应。
数量对不上就不拆，只打印每件的位置和大小，照着改 SHEETS。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS.parent))
import split_sheet  # noqa: E402

SHEETS = {
    # ---- 魏文侯 wwh_ ----
    "pose_wwh_a": ("chars", [2, 2], ["wwh_stand", "wwh_stand_l", "wwh_kneel", "wwh_rise"]),
    "pose_wwh_b": ("chars", [3, 2], ["wwh_cape", "wwh_cape_l", "wwh_reins", "wwh_help_l", "wwh_help"]),
    "wwh_expr_a": ("chars", [2], ["wwh_hi_happy", "wwh_hi_firm"]),
    "wwh_expr_b": ("chars", [2], ["wwh_hi_smile", "wwh_hi_shock"]),
    "wwh_expr_c": ("chars", [2], ["wwh_hi_nod", "wwh_hi_worry"]),
    "wwh_slip": ("props", [1], ["wwh_slip"]),
    # ---- 虞人 yr_ ----
    "pose_yr": ("chars", [3, 2], ["yr_stand", "yr_sit", "yr_shock", "yr_kneel", "yr_helped"]),
    # ---- 魏国大臣 wdc_（甲、乙、丙）----
    "pose_wdc_a": ("chars", [3, 2], ["wdc_a_stand", "wdc_a_cup", "wdc_a_shock", "wdc_a_urge", "wdc_a_soaked"]),
    "pose_wdc_b": ("chars", [3, 2], ["wdc_b_stand", "wdc_b_cup", "wdc_b_shock", "wdc_b_urge", "wdc_b_soaked"]),
    "pose_wdc_c": ("chars", [3, 2], ["wdc_c_stand", "wdc_c_cup", "wdc_c_shock", "wdc_c_urge", "wdc_c_soaked"]),
    # ---- 四位人才：吴起 wq_、乐羊 ly_、李克 lk_、西门豹 xmb_ ----
    "lineup_talents": ("chars", [4], ["wq_stand", "ly_stand", "lk_stand", "xmb_stand"]),
    "pose_talents_walk": ("chars", [4], ["wq_walk", "ly_walk", "lk_walk", "xmb_walk"]),
    "wq_extra": ("chars", [2], ["wq_hi_arms", "wq_hi_point_l"]),
}


def load_pieces(sheet):
    return split_sheet.pieces(str(HERE / f"{sheet}.png"))


def order(ps, rows):
    ps = sorted(ps, key=lambda p: p[0] + p[2].shape[0] / 2)
    out, i = [], 0
    for n in rows:
        out += sorted(ps[i:i + n], key=lambda p: p[1])
        i += n
    return out


def show(sheet, ps, note=""):
    print(f"{sheet}: 切出 {len(ps)} 件 {note}")
    for y, x, c in sorted(ps, key=lambda p: (p[0] + p[2].shape[0] / 2, p[1])):
        print(f"   y={y} x={x} {c.shape[1]}x{c.shape[0]}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    listing = "--list" in sys.argv
    todo = args or [s for s in SHEETS if (HERE / f"{s}.png").exists()]
    for s in todo:
        dst, rows, names = SHEETS[s]
        d = ASSETS / dst
        ps = load_pieces(s)
        if listing or len(ps) != sum(rows):
            show(s, ps, f"预期 {sum(rows)}" + ("" if len(ps) == sum(rows) else "  <-- 数量不对，不拆"))
            continue
        ps = order(ps, rows)
        d.mkdir(parents=True, exist_ok=True)
        for (y, x, c), nm in zip(ps, names):
            c = c.copy()
            c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])   # Codex 自己抠底的表，人物 alpha 常常是 253：补成 255
            Image.fromarray(c, "RGBA").save(d / f"{nm}.png")
            print(f"{dst}/{nm}.png {c.shape[1]}x{c.shape[0]}")


if __name__ == "__main__":
    main()
