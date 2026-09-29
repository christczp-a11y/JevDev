"""tj01 第 3 步：把 Codex 出的素材表拆成单件 PNG 放进 chars/、props/、sets/（用 video/split_sheet.py 的 pieces：绿底和透明底都行）。

用法（仓库根目录）：
  .venv/Scripts/python video/assets/codex_tj01/split_tj01.py --list            # 每张表切出几件、每件多大（先看数量对不对）
  .venv/Scripts/python video/assets/codex_tj01/split_tj01.py [表名 ...]        # 拆图；不写表名 = 全部已经画好的
排序：先按每件的竖直中心分成行（rows 写每行几件），再在行内从左到右；名字和 Codex 提示词（同名 .txt）里的顺序一一对应。
rows 写 "opaque" = 整张不透明图原样拷贝（天空、海报）；写 "assembled" = 皮影表（面积最大的一件是拼好的整个人，其余 6 件按 [3,3] 排）。
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
    # ---- 人物姿势（chars/）----
    "pose_zb1": ("chars", [3, 3], ["zb_cup", "zb_point", "zb_grab", "zb_slap", "zb_shake", "zb_spill"]),
    "pose_zb2": ("chars", [3, 2], ["zb_angry", "zb_cheer", "zb_glance", "zb_soaked", "zb_gaze"]),
    "pose_zxz": ("chars", [3, 2], ["zxz_kneel", "zxz_no", "zxz_walk", "zxz_order", "zxz_calm"]),
    "pose_hkz": ("chars", [3, 3], ["hkz_low", "hkz_hug", "hkz_give", "hkz_lookup", "hkz_step", "hkz_nod"]),
    "pose_wgh": ("chars", [3, 2], ["wgh_kneel", "wgh_give", "wgh_reins", "wgh_elbow", "wgh_nod"]),
    "pose_dg": ("chars", [3, 2], ["dg_kneel", "dg_whisper", "dg_pull", "dg_wink", "dg_nod"]),
    "pose_zmt": ("chars", [3, 2], ["zmt_sneak", "zmt_teeth", "zmt_startle", "zmt_bow", "zmt_shh"]),
    "pose_sgm2": ("chars", [3, 3], ["sgm_pop", "sgm_front", "sgm_doze", "sgm_bonk", "sgm_towel", "sgm_rub"]),
    "pose_zg_zgu": ("chars", [3, 3], ["zgo_window", "zgo_plead", "zgo_sigh", "zgu_kneel", "zgu_plead", "zgu_sigh"]),
    "pose_zwl": ("chars", [3], ["zwl_kneel", "zwl_give", "zwl_allow"]),
    "pose_crowd": ("chars", [4, 4], ["sold_guard", "sold_run1", "sold_run2", "sold_march", "folk_man_wave", "folk_woman_wave", "folk_child_wave", "folk_man_firm"]),
    "pose_kids": ("chars", [3], ["pupil_sad", "pupil_laugh_girl", "pupil_laugh_boy"]),
    # ---- 特写高清半身像（chars/；屏幕高度 ÷ 原图 ≤ 1.3 靠它）----
    "hr_zb_dg": ("chars", [3], ["zb_hi_laugh", "zb_hi_angry", "dg_hi_tight"]),
    "hr_zxz_hkz_dg": ("chars", [3], ["zxz_hi_no", "hkz_hi_give", "dg_hi_wink"]),
    "hr_zmt_wgh": ("chars", [2], ["zmt_hi_teeth", "wgh_hi_elbow"]),
    "hr_sgm": ("chars", [3], ["sgm_hi_point", "sgm_hi_read", "sgm_hi_shock"]),
    # ---- 皮影（前史）：拼好的整个人 + 6 个部件（头、身体、上臂、前臂加手、大腿、小腿加脚）----
    "shadow_zxu": ("chars", "assembled", ["zxu_shadow", "zxu_s_head", "zxu_s_torso", "zxu_s_upper", "zxu_s_fore", "zxu_s_thigh", "zxu_s_shin"]),
    "shadow_zgo": ("chars", "assembled", ["zgo_shadow", "zgo_s_head", "zgo_s_torso", "zgo_s_upper", "zgo_s_fore", "zgo_s_thigh", "zgo_s_shin"]),
    # ---- 道具（props/）----
    "prop_chariot": ("props", [2], ["chariot", "horse"]),
    "prop_cups_stove": ("props", [3], ["cup_lacquer", "cup_spill", "stove"]),
    "flags": ("props", [5], ["flag_zhi", "flag_zhao", "flag_han", "flag_wei", "flag_zhou"]),
    "prop_map": ("props", [1, 1, 1, 1], ["city_icon1", "map_silk", "city_icon2", "city_icon3"]),
    "prop_hands": ("props", [3, 3, 3], ["hand_grab", "hand_open", "hand_candy", "hands_stack", "candy", "ant", "towel", "cup_plain", "cup_plain_spill"]),
    "prop_frogs": ("props", [3, 3, 2], ["frog_wait", "frog_croak", "frog_tongue", "frog_wave", "frog_shoe", "frog_hat", "frog_flat", "frog_jump"]),
    "prop_gauge_hi": ("props", [1], ["gauge_wall_hi"]),
    "prop_gauge_kit": ("props", [3], ["banzhu_frame", "gauge_camp", "wall_section"]),
    "prop_icons": ("props", [4, 4], ["icon_tall", "icon_bow", "icon_qin", "icon_mouth", "icon_fist", "icon_heart", "plaque_zhi", "plaque_back"]),
    "prop_boat": ("props", [5], ["boat", "captain", "captain_hat", "char_cai", "char_de"]),
    "teaser_rain": ("props", "opaque", ["teaser_rain"]),
    "patches": ("props", [5, 5, 7], [f"tape_{i}" for i in range(1, 11)] + ["string_1", "string_2", "string_3", "pin_1", "pin_2", "clip_1", "clip_2"]),
    # ---- 布景（sets/）：共用的天空、山、地面、水、前景框放 jin_land；各地点自己的东西放各自的目录 ----
    "set_sky": ("sets/jin_land", "opaque", ["sky"]),
    "set_ridges": ("sets/jin_land", [1, 1, 1], ["ridge_far", "ridge_mid", "ridge_near"]),
    "set_ground": ("sets/jin_land", [1, 1, 1], ["ground", "water", "fore"]),
    "set_jinyang": ("sets/jinyang", [1, 1], ["wall", "gate"]),
    "set_lantai": ("sets/lantai", [1, 6], ["terrace", "table", "cup", "cup_spill", "mat", "hu", "ding"]),
    "set_camp": ("sets/camp", [3, 1, 2], ["tent_s1", "tent_big", "tent_s2", "dike", "dike_breach", "palisade"]),
    "set_palace": ("sets/palace", [1, 5], ["hall", "ding_a", "ding_b", "slips_table", "jade_gui", "table_red"]),
    "set_study_wall": ("sets/study", "opaque", ["wall"]),
    "set_study_items": ("sets/study", [1, 5], ["desk", "chair", "books", "basket", "lamp_stand"]),
    "set_theater": ("sets/theater", [1, 2, 1], ["valance", "curtain", "sign", "stage_floor"]),
    "set_audience": ("sets/theater", [3, 3], ["aud_1", "aud_2", "aud_3", "aud_4", "aud_5", "aud_6"]),
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
        if rows == "opaque":
            if listing:
                print(f"{s}: 整张原样拷贝 -> {dst}/{names[0]}.png")
                continue
            d.mkdir(parents=True, exist_ok=True)
            im = Image.open(HERE / f"{s}.png").convert("RGBA")
            im.save(d / f"{names[0]}.png")
            print(f"{dst}/{names[0]}.png {im.width}x{im.height}")
            continue
        ps = load_pieces(s)
        if rows == "assembled":
            big = max(ps, key=lambda p: p[2].shape[0] * p[2].shape[1])
            rest = [p for p in ps if p is not big]
            if listing or len(rest) != 6:
                show(s, ps, "" if len(rest) == 6 else "预期 7  <-- 数量不对，不拆")
                continue
            ps = [big] + order(rest, [3, 3])
        else:
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
