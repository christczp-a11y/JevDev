"""tj01 整集分镜表（素材清单第六节）：从已经画好的表里拆 15 张，只存清单要的那几件，文件名照 split_tj01.py 的 SHEETS。

  .venv/Scripts/python video/assets/codex_tj01/split_scene_rest.py [--list]

绿底的表用 video/split_sheet.py 的 pieces（抠绿）；prop_boat 是透明底（Codex 自己抠的）用 video/split_alpha.py 的 pieces（只留实心部分）；teaser_rain 整张不透明原样拷贝。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS.parent))
sys.path.insert(0, str(HERE))
import split_alpha  # noqa: E402
import split_sheet  # noqa: E402
import split_tj01 as T  # noqa: E402

KEEP = {
    "pose_crowd": {"sold_run1", "sold_run2", "folk_man_wave", "folk_woman_wave", "folk_child_wave", "folk_man_firm"},
    "hr_zmt_wgh": {"zmt_hi_teeth"},
    "pose_zg_zgu": {"zgo_window"},
    "pose_sgm2": {"sgm_doze", "sgm_bonk", "sgm_rub", "sgm_towel"},
    "prop_boat": {"char_cai", "char_de"},
}
ALPHA = {"prop_boat"}


def main():
    listing = "--list" in sys.argv
    for s, keep in KEEP.items():
        dst, rows, names = T.SHEETS[s]
        p = str(HERE / f"{s}.png")
        ps = split_alpha.pieces(p) if s in ALPHA else split_sheet.pieces(p)
        if len(ps) != sum(rows):
            T.show(s, ps, f"预期 {sum(rows)}  <-- 数量不对，不拆")
            continue
        if s == "prop_boat":
            # split_tj01.SHEETS 里的顺序（按 x 排一行）是错的：上排 船、船长、船长帽，下排 才、德（按 y 分两行再按 x 排）
            ps = T.order(ps, [3, 2])
            names = ["boat", "captain", "captain_hat", "char_cai", "char_de"]
        else:
            ps = T.order(ps, rows)
        for (y, x, c), nm in zip(ps, names):
            if nm not in keep:
                continue
            c = c.copy()
            c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])
            print(f"{dst}/{nm}.png {c.shape[1]}x{c.shape[0]}  (原表 x={x} y={y})")
            if listing:
                continue
            d = ASSETS / dst
            d.mkdir(parents=True, exist_ok=True)
            Image.fromarray(c, "RGBA").save(d / f"{nm}.png")
    src = HERE / "teaser_rain.png"
    im = Image.open(src).convert("RGBA")
    print(f"props/teaser_rain.png {im.width}x{im.height}")
    if not listing:
        (ASSETS / "props").mkdir(parents=True, exist_ok=True)
        im.save(ASSETS / "props/teaser_rain.png")


if __name__ == "__main__":
    main()
