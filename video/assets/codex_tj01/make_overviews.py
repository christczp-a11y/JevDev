"""姿势总览、道具总览、特写总览（联系表，给 Chris 一眼看全）：输出 video/assets/ref/tj01/{poses,props,closeups}_overview.png
用法（仓库根目录）：.venv/Scripts/python video/assets/codex_tj01/make_overviews.py
"""
import glob
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(HERE))
import contact_tj01 as c  # noqa: E402

os.chdir(ASSETS)
ORDER = ["sgm_", "zb_", "zxz_", "zmt_", "hkz_", "dg_", "wgh_", "zgo_", "zgu_", "zwl_", "zxu_", "sold_", "folk_", "pupil_"]
BG = (214, 206, 192)


def main():
    out = Path("ref/tj01")
    out.mkdir(parents=True, exist_ok=True)
    ch = [f.replace("\\", "/") for f in glob.glob("chars/*.png")]
    ch = [f for f in ch if os.path.basename(f).startswith(tuple(ORDER)) and "pillow" not in f and "_hi_" not in f and "stand_hi" not in f]
    ch.sort(key=lambda f: (next(i for i, p in enumerate(ORDER) if os.path.basename(f).startswith(p)), os.path.basename(f)))
    c.make(str(out / "poses_overview.png"), ch, h=300, bg=BG)
    props = ["chariot", "horse", "flag_zhi", "flag_zhao", "flag_han", "flag_wei", "flag_zhou", "cup_lacquer", "cup_spill", "stove", "map_silk",
             "city_icon1", "city_icon2", "city_icon3", "hand_grab", "hand_open", "hand_candy", "hands_stack", "candy", "ant", "towel", "cup_plain",
             "cup_plain_spill", "frog_wait", "frog_croak", "frog_tongue", "frog_wave", "frog_shoe", "frog_hat", "frog_flat", "frog_jump",
             "gauge_wall_hi", "banzhu_frame", "gauge_camp", "wall_section", "icon_tall", "icon_bow", "icon_qin", "icon_mouth", "icon_fist",
             "icon_heart", "plaque_zhi", "plaque_back", "boat", "captain", "captain_hat", "char_cai", "char_de", "teaser_rain"]
    props = [f"props/{p}.png" for p in props if os.path.exists(f"props/{p}.png")]
    c.make(str(out / "props_overview.png"), props, h=300, bg=BG)
    hi = sorted(f.replace("\\", "/") for f in glob.glob("chars/*_hi_*.png"))
    if hi:
        c.make(str(out / "closeups_overview.png"), hi, h=800, bg=BG)
    print("ok", len(ch), "姿势", len(props), "道具", len(hi), "特写")


if __name__ == "__main__":
    main()
