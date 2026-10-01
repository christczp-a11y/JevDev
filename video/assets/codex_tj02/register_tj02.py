"""tj02 第 5 步（提前）：把新角色登记进 video/assets/REGISTRY.md（幂等：已经登记的跳过；文件还没画出来的也跳过）。

  .venv/Scripts/python video/assets/codex_tj02/register_tj02.py

朝向是逐张看图定的（PITFALLS T13、T25）：朝右的记 `右`，要朝左的姿势（交领人物不许 flip）都是重新画的，记 `左`；
尺寸从文件里读。PX 从 tj02_meta.py 算（目标身高 ÷ 站姿图高）。
"""
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
REG = ASSETS / "REGISTRY.md"
sys.path.insert(0, str(HERE))
import tj02_meta as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OWNER = {
    "wwh": "魏文侯 `wwh_`", "yr": "虞人 `yr_`",
    "wdc_a": "魏国大臣甲 `wdc_`", "wdc_b": "魏国大臣乙 `wdc_`", "wdc_c": "魏国大臣丙 `wdc_`",
    "wq": "吴起 `wq_`", "ly": "乐羊 `ly_`", "lk": "李克 `lk_`", "xmb": "西门豹 `xmb_`",
}
# 文件名(不含 .png) -> (朝向, 备注)
CH = {
    # ---- 魏文侯 wwh_（橙黄 #d08a2e 交领右衽深衣配黑边、黑小冠；年轻方脸浓眉亮眼、下巴一小撮短须；腰间系竹片）----
    "wwh_stand": ("右", "站姿，两臂自然垂在身侧、温和微笑；腰间竹片（弓和太阳，没有字）挂在腰带旁；姿势表 pose_wwh_a 里的定稿站姿；3/4"),
    "wwh_stand_l": ("左", "站姿，同 wwh_stand 但**重新画成朝左**（不是 flip：衣襟仍是右衽）；3/4"),
    "wwh_kneel": ("右", "**跪坐**，笑逐颜开，一手端漆耳杯送到胸前、一手放膝上（宴会喝酒开心）；3/4"),
    "wwh_rise": ("右", "放下杯子、**起身的瞬间**：一膝抬起、一手按膝、一手向后撑，两手没有东西，严肃坚定、直视前方；3/4"),
    "wwh_cape": ("右", "**戴竹斗笠、披草蓑衣**（斗笠盖住发髻和小冠，头上只有这一顶；蓑衣是棕黄干草短披肩，到腰带下），站姿，两手握拳垂在身侧，坚定；3/4。在 pose_wwh_b 里，比 pose_wwh_a 的人大约 2.5%，PX 不另算"),
    "wwh_cape_l": ("左", "同 wwh_cape，**重新画成朝左**（不是 flip）；坚定"),
    "wwh_reins": ("右", "**驾车**：戴斗笠披蓑衣，站着两脚分开、身体前倾，双手握两根棕色皮缰绳向前伸（缰绳末端带铜环，垂向右下，是物件）；斗笠、蓑衣、衣摆有小黄泥点；已和 `props/chariot_back` / `chariot_front` 叠过，和 `wgh_reins` 同一位置同一比例，脚被近侧车栏挡住（检查图 `video/out/tj02/chariot_check.png`）；3/4"),
    "wwh_help_l": ("左", "**弯腰双手向前扶人**（掌心向上，画面里没有别人），温和带笑；戴斗笠披蓑衣；衣摆下沿、裤脚、布履溅满黄色泥点（两只鞋一样脏）；朝左"),
    "wwh_help": ("右", "同 wwh_help_l，**重新画成朝右**（不是 flip）；衣摆、裤脚、布履溅满黄泥"),
    "wwh_hi_happy": ("右", "**高清半身表情**（597×920）：开心，哈哈大笑、眼睛笑成缝；不戴斗笠、戴小冠；高清半身缩到和站姿同大小用 PX≈0.178（站姿 0.453 ÷ 2.55）；3/4"),
    "wwh_hi_firm": ("右", "**高清半身表情**：严肃坚定，眉头微皱、目光如电、一手握拳按胸；3/4"),
    "wwh_hi_smile": ("右", "**高清半身表情**：温和笑，一手掌心向上向前伸（扶人的样子）；3/4"),
    "wwh_hi_shock": ("右", "**高清半身表情**：吃惊，眼睛圆睁、眉毛高扬、嘴微张，一手抬到胸前张开；3/4"),
    "wwh_hi_nod": ("右", "**高清半身表情**：点头，眼睛轻闭、嘴角带笑、一手握拳按胸口（答应了）；3/4"),
    "wwh_hi_worry": ("右", "**高清半身表情**：着急，八字眉、额头一滴汗、嘴张开急着说话、一手向前伸开；3/4"),
    # ---- 虞人 yr_（慈祥爽朗的老伯伯：古铜色脸、灰白短胡子、笑纹；土褐交领右衽粗布短衣、绑腿、草鞋；旧草蓑衣和竹斗笠）----
    "yr_stand": ("右", "站姿，两手在身前拢着、眯眼笑，慈祥爽朗；戴旧竹斗笠、披旧草蓑衣（旧但不破烂）；绑腿、两只草鞋一样；3/4"),
    "yr_sit": ("右", "**席地而坐**缩着脖子望路、小小叹气：双膝弯起、双臂抱膝、脖子缩进衣领、嘴成小「o」（草棚下等人；草棚另画，这张不带）；3/4"),
    "yr_shock": ("右", "吃惊：眼睛睁圆、嘴成圆「O」、一手抬到胸前张开（5 指）、身体微后仰；3/4"),
    "yr_kneel": ("右", "**跪坐行礼**：双手在胸前合拢（拱手）、上身前倾低头约三十度，脸还看得见，恭敬激动；3/4"),
    "yr_helped": ("右", "被扶起来、眼泪汪汪地笑：微弓背、两臂向前抬起手半张（像被人扶着前臂；画面里没有别人）、眼角有泪珠；3/4"),
    # ---- 魏国大臣 wdc_（虚构群众；不用赭红/青绿/靛蓝/橙黄四家色，也不用第一集宾客的米白/灰褐/土黄）----
    "wdc_a_stand": ("右", "**大臣甲**：圆圆胖脸、小圆眼、红脸蛋、没有胡子；藕粉色（灰玫瑰粉 #c9868c）交领右衽深衣配深栗棕边、黑小冠；站姿，两手拢袖，憨厚微笑；3/4"),
    "wdc_a_cup": ("左", "大臣甲：**跪坐**举漆耳杯，脸喝得通红、笑眯眯（宴会）；朝左"),
    "wdc_a_shock": ("左", "大臣甲：跪坐，漆耳杯停在半空，**嘴张成大 O、眼珠瞪圆**，下巴好好的；朝左"),
    "wdc_a_urge": ("左", "大臣甲：站，前倾着急摆手劝（一手手掌朝前摆、一手拱在胸前）；朝左"),
    "wdc_a_soaked": ("右", "大臣甲：淋湿了、气喘吁吁、不好意思地低头（衣服湿透变深、衣摆袖口滴水珠、一手挠后脑勺一手扶膝）；朝右"),
    "wdc_b_stand": ("右", "**大臣乙**：瘦长脸、六十岁左右、灰白稀疏山羊胡、垂眉、微驼背；黛紫（灰紫 #6d5d84）交领右衽深衣配浅灰边、黑小冠；站姿，两手拢袖，带点担心的微笑；3/4"),
    "wdc_b_cup": ("左", "大臣乙：**跪坐**举漆耳杯，脸喝得通红、笑眯眯（宴会）；朝左"),
    "wdc_b_shock": ("左", "大臣乙：跪坐，漆耳杯停在半空，**嘴张成大 O、眼珠瞪圆**，下巴好好的；朝左"),
    "wdc_b_urge": ("左", "大臣乙：站，前倾着急摆手劝；朝左"),
    "wdc_b_soaked": ("右", "大臣乙：淋湿了、气喘吁吁、不好意思地低头（湿透滴水、一手挠后脑勺一手扶膝）；朝右"),
    "wdc_c_stand": ("右", "**大臣丙**：年轻、鼓鼓的圆脸、大圆眼、粗短眉、没有胡子；炭灰黑（#3e3b40）交领右衽深衣配白色宽边、黑小冠；站姿，两手拢袖，机灵微笑；3/4"),
    "wdc_c_cup": ("左", "大臣丙：**跪坐**举漆耳杯，脸喝得通红、笑眯眯（宴会）；朝左（衣摆右下角一滴误画的水珠已手工涂白）"),
    "wdc_c_shock": ("左", "大臣丙：跪坐，漆耳杯停在半空，**嘴张成大 O、眼珠瞪圆**，下巴好好的；朝左"),
    "wdc_c_urge": ("左", "大臣丙：站，前倾着急摆手劝；朝左"),
    "wdc_c_soaked": ("右", "大臣丙：淋湿了、气喘吁吁、不好意思地低头（湿透滴水、一手挠后脑勺一手扶膝）；朝右"),
    # ---- 四位人才（站姿在阵容表 lineup_talents，走路在 pose_talents_walk；都不拿兵器、不骑马）----
    "wq_stand": ("右", "**吴起**（魏国大将军，四人里最魁梧）：深炭黑褐色皮甲（方皮片缝成、肩上厚皮肩甲加铜铆钉）罩深灰交领右衽短袍、粗革腰带、护腕、黑小冠；方脸、粗浓黑眉、短胡茬；**双臂抱胸**，不拿兵器；阵容表原图；3/4"),
    "wq_walk": ("右", "吴起：背着深灰褐色粗布大包袱（布带在胸前打结、两手抓肩带），大步向右走；不骑马、不拿兵器；3/4"),
    "wq_hi_arms": ("右", "吴起**高清半身**（595×796）：双臂抱胸、目光锐利、嘴角自信冷笑；缩到和站姿同大小约 PX 0.16；3/4（下集还要用）"),
    "wq_hi_point_l": ("左", "吴起**高清半身**（671×788）：一手食指向前方远处一指、一手握拳按腰带、眉头微皱严肃笃定；**重新画成朝左**；不拿兵器（下集渡河「在德不在险」用）"),
    "ly_stand": ("右", "**乐羊**（魏国将军，稳重）：茶褐色皮革胸甲（只护胸口、没有肩甲和铆钉）罩灰褐交领右衽短袍、布腰带、黑小冠；圆方脸、浓眉温和、整齐短络腮胡；**双手在身前相握**；3/4"),
    "ly_walk": ("右", "乐羊：背着浅灰色麻布包袱，大步向右走；不骑马、不拿兵器；3/4"),
    "lk_stand": ("右", "**李克**（魏国学者）：六十岁左右、灰白长须垂到胸口、灰白眉、细长脸和蔼；深墨灰近黑色交领右衽长衣（到脚面）配浅灰边、浅灰腰带、黑小冠；**双手拢袖**；3/4"),
    "lk_walk": ("右", "李克：背着暗黄褐色小包袱，缓步向右走；3/4"),
    "xmb_stand": ("右", "**西门豹**（年轻精干的地方官）：二十多岁、清瘦、眼睛明亮、没有胡子；暖米色（燕麦色）粗麻交领右衽短袍配深栗边、黑布腰带、深灰裤子绑腿、黑小冠；**一手按腰带、一手背在身后**；3/4"),
    "xmb_walk": ("右", "西门豹：背着栗褐色包袱，轻快地向右走；3/4"),
}
PROP = {
    "wwh_slip": ("正面", "**高清特写道具**：魏文侯腰间的小竹片（浅黄色竹片、竹节横纹、上端小孔穿麻绳打结），片上用墨画着**上面一个小太阳、下面一张弓**（没有箭、没有任何字）；竖放，无方向；司马光的放大镜照它用"),
}
# 人物表整行：前缀 -> (人物, 前缀栏, 服饰要点, PX 栏)
PEOPLE = {
    "wwh": ("魏文侯（魏家，魏桓子的孙子；本集主角）", "`wwh_`", "橙黄 #d08a2e 交领右衽深衣配黑边、黑小冠（和魏桓子同一家配色，但不是同一个人）；二十多岁、方正脸方下巴、浓黑剑眉、眼睛明亮有神、没有八字胡（下巴一小撮短须）、站得笔直、温和带笑；腰间系一片小竹片（弓和太阳，没有字）；冒雨时戴竹斗笠、披草蓑衣（斗笠下不戴冠）", f"{M.px('wwh')}"),
    "yr": ("虞人（看林人，虚构外貌）", "`yr_`", "慈祥爽朗的老伯伯：古铜色脸、灰白短胡子、笑纹；土褐交领右衽粗布短衣、绑腿、草鞋（两只一致）；旧（不破烂）的草蓑衣和竹斗笠，头上只有斗笠", f"{M.px('yr')}"),
    "wdc": ("魏国大臣甲乙丙（虚构群众，魏文侯身边的朝臣）", "`wdc_`", "颜色避开四家色（赭红智、青绿赵、靛蓝韩、橙黄魏）和第一集宾客（米白、灰褐、土黄）：甲 藕粉（灰玫瑰粉）配深栗边、圆胖脸没胡子；乙 黛紫配浅灰边、瘦长脸灰白山羊胡、垂眉、微驼；丙 炭灰黑配白边、年轻圆脸没胡子。都是交领右衽深衣、黑小冠", f"甲 {M.px('wdc_a')}、乙 {M.px('wdc_b')}、丙 {M.px('wdc_c')}"),
    "wq": ("吴起（魏国大将军；下一集还要用）", "`wq_`", "最魁梧：深炭黑褐色皮甲（方皮片、厚肩甲、铜铆钉）罩深灰交领右衽短袍、粗革腰带、护腕、黑小冠；方脸、粗浓黑眉、短胡茬；不拿兵器、不骑马（战国早期没有马镫和骑兵）", f"{M.px('wq')}"),
    "ly": ("乐羊（魏国将军）", "`ly_`", "稳重：茶褐色皮革胸甲（只护胸口、没有肩甲和铆钉）罩灰褐交领右衽短袍、黑小冠；圆方脸、整齐短络腮胡；不拿兵器", f"{M.px('ly')}"),
    "lk": ("李克（魏国学者、谋士）", "`lk_`", "灰白长须到胸口、灰白眉；深墨灰交领右衽长衣配浅灰边、黑小冠；拢袖", f"{M.px('lk')}"),
    "xmb": ("西门豹（年轻的地方官）", "`xmb_`", "清瘦、没有胡子；暖米色交领右衽粗麻短袍配深栗边、黑布腰带、深灰裤子绑腿、黑小冠", f"{M.px('xmb')}"),
}
DIR_ROW = ("| `video/assets/codex_tj02/` | tj02 第 5 步（提前）：Codex 提示词（`*.txt`）、日志、原始素材表（`pose_*.png`、`lineup_talents`、`wwh_expr_*`、`wq_extra`、`wwh_slip`）、`_ref_*.png`（附给 Codex 的单人参考）、"
           "`split_tj02.py`（拆图）、`register_tj02.py`（登记）、`tj02_meta.py`（目标身高、PX）、`board_tj02.py`（阵容总览，输出 `video/out/tj02/lineup.png`，不进 git） |")


def size_of(rel):
    im = Image.open(ASSETS / rel)
    return f"{im.width}×{im.height}"


def owner_of(stem):
    for k in sorted(OWNER, key=len, reverse=True):
        if stem.startswith(k + "_"):
            return OWNER[k]
    raise KeyError(stem)


def main():
    md = REG.read_text(encoding="utf-8")
    lines = md.split("\n")
    registered = set(re.findall(r"^\| `((?:chars|props|rig|sets|brand)/[^`]+\.png)`", md, re.M))
    new_chars, new_props = [], []
    for stem, (face, note) in CH.items():
        rel = f"chars/{stem}.png"
        if not (ASSETS / rel).exists() or rel in registered:
            continue
        new_chars.append(f"| `{rel}` | {owner_of(stem)} | {face} | {size_of(rel)} | 无 | 定稿 | {note} | tj02 |")
    for stem, (face, note) in PROP.items():
        rel = f"props/{stem}.png"
        if not (ASSETS / rel).exists() or rel in registered:
            continue
        new_props.append(f"| `{rel}` | 道具 | {face} | {size_of(rel)} | 无 | 定稿 | {note} | tj02 |")
    new_people = []
    for pre, (nm, code, look, pxs) in PEOPLE.items():
        if f"`{pre}_`" in md:
            continue
        if not any((ASSETS / "chars").glob(f"{pre}_*.png")):
            continue
        new_people.append(f"| {nm} | {code} | tj02 | {look} | {pxs} | 定稿 |")

    def insert_before(prefix, rows):
        if not rows:
            return
        j = next(k for k, l in enumerate(lines) if l.startswith(prefix))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = rows

    insert_before("### 2.2", new_chars)
    insert_before("### 2.3", new_props)
    insert_before("tj01 的新角色（智、赵、韩、魏各家的人物）画完以后", new_people)
    if "`video/assets/codex_tj02/`" not in md:
        j = next(k for k, l in enumerate(lines) if l.startswith("| `video/assets/ref/tj01/`"))
        lines.insert(j + 1, DIR_ROW)
    REG.write_text("\n".join(lines), encoding="utf-8")
    print(f"登记：人物 {len(new_people)} 行，姿势图 {len(new_chars)}，道具 {len(new_props)}")


if __name__ == "__main__":
    main()
