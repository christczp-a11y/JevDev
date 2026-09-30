"""tj01 整集分镜表（素材清单第六节）：登记拆出来的 15 张 + 4 张朝左重画的图（幂等：已登记的跳过，文件没有的也跳过）。

  .venv/Scripts/python video/assets/codex_tj01/register_rest.py

前 15 张的朝向和备注沿用 register_tj01.py 的 CH / PROP（那里是逐张看图定的，这次拆出来又对着图看过一遍，一致）；
朝左的 4 张（PITFALLS M1：交领人物不许翻转，重画的）登记「左」。
"""
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(HERE))
import register_tj01 as R  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
REG = R.REG

FROM_TJ01 = [
    "folk_man_wave", "folk_woman_wave", "folk_child_wave", "folk_man_firm", "sold_run1", "sold_run2",
    "zmt_hi_teeth", "zgo_window", "sgm_doze", "sgm_bonk", "sgm_rub", "sgm_towel",
]
PROPS15 = ["char_cai", "char_de", "teaser_rain"]
LEFT = {   # 新文件名 -> (原图, 备注)
    "zxz_no_l": ("zxz_no", "**跪坐**，嘴唇紧闭、眉头平平、一手抬到胸前掌心朝外轻轻一挡（「不给。」，第 31 句）；和 zxz_no 同一个人、同样的姿势和表情，**朝左**（3/4）；**重画的，不是镜像**（PITFALLS M1）：交领右衽按朝左画对，近侧（人物左半身）左襟在最上面、领边是一条连续的斜线，近侧腋下没有收口"),
    "hkz_stand_l": ("hkz_stand", "站姿，抱着红绳系的地图卷，咬牙为难；和 hkz_stand 同一个人同样的姿势表情，**朝左**（3/4）；**重画的，不是镜像**（PITFALLS M1）：右衽按朝左画对"),
    "zb_cheer_l": ("zb_cheer", "站，双臂张开仰头大笑，后面那只手握弓（弓竖着立在身侧，不搭箭；战车上大笑「水也能灭国」）；和 zb_cheer 同一个人同样的姿势表情，**朝左**（3/4）；**重画的，不是镜像**（PITFALLS M1）：右衽按朝左画对"),
    "wgh_reins_l": ("wgh_reins", "站，微微前倾、双手握着皮缰绳向前（画面左边）伸（驾车「魏桓子御」，末端有铜环）；和 wgh_reins 同一个人同样的姿势表情，**朝左**（3/4）；**重画的，不是镜像**（PITFALLS M1）：右衽按朝左画对"),
}


def limit_note(rel):
    w, h = R.size_of(rel).split("×")
    return f"（原图 {w}×{h}，屏幕显示不超过 {int(int(w) * 1.3)}×{int(int(h) * 1.3)}）"


def main():
    md = REG.read_text(encoding="utf-8")
    lines = md.split("\n")
    registered = set(re.findall(r"^\| `((?:chars|props|rig|sets|brand)/[^`]+\.png)`", md, re.M))
    rows_c, rows_p = [], []
    for stem in FROM_TJ01:
        rel = f"chars/{stem}.png"
        if not (ASSETS / rel).exists() or rel in registered:
            continue
        face, note = R.CH[stem]
        pre = stem.split("_")[0]
        own = "司马光 `sgm_`" if pre == "sgm" else R.owner_of(stem)
        scope = "系列" if pre == "sgm" else "tj01"
        rows_c.append(f"| `{rel}` | {own} | {face} | {R.size_of(rel)} | 无 | 定稿 | {note}{limit_note(rel)} | {scope} |")
    for stem, (orig, note) in LEFT.items():
        rel = f"chars/{stem}.png"
        if not (ASSETS / rel).exists() or rel in registered:
            continue
        rows_c.append(f"| `{rel}` | {R.owner_of(stem)} | 左 | {R.size_of(rel)} | 无 | 定稿 | {note}；比原图 {orig} 大{limit_note(rel)} | tj01 |")
    for stem in PROPS15:
        rel = f"props/{stem}.png"
        if not (ASSETS / rel).exists() or rel in registered:
            continue
        face, note = R.PROP[stem]
        rows_p.append(f"| `{rel}` | 道具 | {face} | {R.size_of(rel)} | 无 | 定稿 | {note}{limit_note(rel)} | tj01 |")

    def insert_before(heading_prefix, rows):
        if not rows:
            return
        j = next(k for k, l in enumerate(lines) if l.startswith(heading_prefix))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = rows

    insert_before("### 2.2", rows_c)
    insert_before("### 2.3", rows_p)
    REG.write_text("\n".join(lines), encoding="utf-8")
    print(f"登记：姿势图 {len(rows_c)}，道具 {len(rows_p)}")


if __name__ == "__main__":
    main()
