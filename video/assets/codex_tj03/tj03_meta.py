"""tj03 第 5 步（提前）的共用数据：新角色表（前缀、名字、站姿图、目标身高、PX）。board_tj03.py（阵容总览）和 register_tj03.py（登记表）都读这里。

PX 的算法同 tj02_meta：场景里的比例 = 目标身高（引擎单位）÷ 这个人站着时的图高（像素，同一张姿势表里量的）。
照 tj02：魏文侯 192、吴起 205、司马光 sgm_ 沿用 0.62（finger 474 × 0.62 ≈ 294，系列讲解人，比古人大）。
划桨的士兵是坐姿群像，没有「身高」：目标是「坐着的普通士兵」约 130 单位高（站着约 180 的人，坐下来头顶到凳面约 0.72 倍）。
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent

# 前缀: (名字, 站姿图, 目标身高[, 图里这个人的高度（像素；不写 = 图高）, 图里有几个人])；PX = 目标身高 ÷ 站姿图高（在 px() 里算）
CHARS = {
    "wuh": ("魏武侯", "chars/wuh_stand.png", 190),
    "wq": ("吴起", "chars/wq_speak.png", 205),
    "rower": ("划桨的士兵（5 人群像）", "chars/rower_row.png", 130, 470, 5),   # 群像图高 621 含桨叶；坐着的人（头顶到脚底）约 470 像素
    "zs": ("子思", "chars/zs_stand.png", 172),
    "gb": ("苟变", "chars/gb_stand_l.png", 188),
    "wh": ("卫侯", "chars/wh_stand_l.png", 182),
}
# 阵容图的参考人物：前缀: (名字, 图, PX)
REFS = {
    "wwh": ("魏文侯（父亲，对比身高）", "chars/wwh_stand.png", 0.453),
    "sgm": ("司马光（系列）", "chars/sgm_finger.png", 0.62),
}


def px(prefix, std_h=None):
    name, rel, tgt, *rest = CHARS[prefix]
    h = std_h or (rest[0] if rest else Image.open(ASSETS / rel).height)
    return round(tgt / h, 3)


def persons(prefix):
    """图里有几个人（群像 > 1）：阵容图按「每人不小于 min-w 像素宽」算比例时用。"""
    ent = CHARS.get(prefix)
    return ent[4] if ent and len(ent) > 4 else 1
