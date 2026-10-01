"""tj02 第 5 步（提前）的共用数据：新角色表（前缀、名字、站姿图、目标身高、PX）。board_tj02.py（阵容总览）和 register_tj02.py（登记表）都读这里。

PX 的算法同 tj01_meta：场景里的比例 = 目标身高（引擎单位）÷ 这个人站着时的图高（像素，同一张姿势表里量的）。
试做集商鞅 sy2_ = 467 像素高 × 0.40 = 187 单位；智伯 215；魏桓子 190；司马光 sgm_ 沿用 0.62（474 × 0.62 ≈ 294，系列讲解人，比古人大）。
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent

# 前缀: (名字, 站姿图, 目标身高)；PX = 目标身高 ÷ 站姿图高（在 px() 里算）
CHARS = {
    "wwh": ("魏文侯", "chars/wwh_stand.png", 192),
    "yr": ("虞人（看林人）", "chars/yr_stand.png", 172),
    "wdc_a": ("魏国大臣甲", "chars/wdc_a_stand.png", 180),
    "wdc_b": ("魏国大臣乙", "chars/wdc_b_stand.png", 176),
    "wdc_c": ("魏国大臣丙", "chars/wdc_c_stand.png", 178),
    "wq": ("吴起", "chars/wq_stand.png", 205),
    "ly": ("乐羊", "chars/ly_stand.png", 195),
    "lk": ("李克", "chars/lk_stand.png", 180),
    "xmb": ("西门豹", "chars/xmb_stand.png", 188),
    # 第 5 步（画面素材）新角色：魏文侯的儿子，二十岁上下，照吴起（205）、魏文侯（192）的比例取 190；图是「指向远山」的全身（1391 高，冠顶到脚底）
    "wuh": ("魏武侯", "chars/wuh_point.png", 190),
}
# 阵容图的参考人物：前缀: (名字, 图, PX)
REFS = {
    "wgh": ("魏桓子（第一集，同家参考）", "chars/wgh_stand.png", 0.389),
    "sgm": ("司马光（系列）", "chars/sgm_finger.png", 0.62),
}


def px(prefix, std_h=None):
    name, rel, tgt = CHARS[prefix]
    h = std_h or Image.open(ASSETS / rel).height
    return round(tgt / h, 3)
