"""替代「2D 横版卷轴」的画面方案：同一个段落用 11 种画面讲，加现版本和一个反面对照，让 Jev 打分、两两对比（正反各问一次）。

用法（仓库根目录）：.venv/Scripts/python docs/research/jev/style_jev.py
"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jevdev import jev  # noqa: E402

SERIES = {
    "内容": "《资治通鉴》历史故事儿童动画，每集约 2 分钟，竖屏 9:16，给 6–12 岁孩子和家长看；讲解人是 Q 版司马光",
    "品牌": "纸艺立体书：所有人物和场景都是带白色纸边、有纸纹的彩色卡纸；史料要准确",
    "这段剧情": "秦国都城集市：一个小伙把一根 7 米高、很重的木杆从南门搬到北门，全城人围观，商鞅当场给了他五十金",
}

STYLE = {
    "S0 现版本：2D 横版卷轴": "镜头始终从侧面平移，跟着小伙从左往右走；背后的城墙、店铺一层层横向滚动；人物是纸片关节动画，走路、弯腰、抱杆；全程镜头距离和角度都不变。",
    "S1 3D 立体书舞台": "一本打开的大书平放着，书页上的城门、店铺、人群都是竖起来的纸片（有厚度、纸边和投影）。镜头像无人机一样在书上方环绕、俯冲、推近：小伙抱起木杆时，镜头贴地仰拍，显出木杆有 7 米高；他走向北门时镜头拉高，俯瞰整个集市和围观的人群；换场时整页纸景折倒，下一页的纸景「啪」地弹起来。",
    "S2 动态漫画分格": "画面分成漫画格子，一格一个动作：小伙挽袖子（特写）→ 抱起木杆，大字拟声「嘿！」→ 一排小格子里是全城人探头 → 金块砸进怀里，冲破格子边框。镜头在格子之间滑动，关键的一格放大占满全屏。",
    "S3 等距游戏地图": "从斜上方 45° 俯看整座秦国都城，像一张游戏地图。小伙像游戏角色，沿着虚线路线从南门走到北门；头顶飘出「任务：搬到北门」「+50 金」；镜头像游戏一样缩放跟随，到终点时弹出通关动画。",
    "S4 皮影纸影剧场": "一块发光的幕布，所有角色是透光的彩色剪纸皮影，用细杆操纵。小伙搬木杆的影子投在幕上，灯光一晃，影子忽大忽小；两侧有红色幕布，配锣鼓声；换场时灯暗、幕布合上。",
    "S5 桌面微缩模型": "故事发生在一张木桌上的纸模型小城里，像用手机拍微缩景观（移轴镜头，前景后景虚化）。镜头贴着桌面跟拍小伙，木杆比他高好几倍；偶尔司马光的大手从画外伸进来，翻书页或把纸片人挪个位置。",
    "S6 电影分镜式 2D": "还是纸片画面，但像电影一样分镜：远景看全城 → 中景小伙走来 → 特写他咬牙的脸和汗珠 → 低角度仰拍木杆的高度 → 围观群众的快切反应特写。前后多层纸片有景深虚化和视差，用推拉镜头代替横向平移。",
    "S7 分屏平行结局": "画面一分为二：左边是「搬」，小伙扛着木杆走向北门；右边是「不搬」，他转身回家。两边同时演，最后左边金块砸下来，右边空空如也，观众自己比较。",
    "S8 纸片物理动效": "所有东西都遵守纸的物理：木杆放下时纸片弹一下、弯一下；五十个金块一个个带碰撞地掉进怀里，堆成小山，有几块滚了出去；告示被风吹得哗哗响；围观的纸片人像多米诺骨牌一样一个接一个探出头。",
    "S9 司马光书桌画中画": "司马光坐在书桌前讲故事，桌上摊开的书页里在演这段剧情（画中画）；他时不时把手伸进书里拨动纸片、把人物捏起来放到别处，边拨边讲。",
    "S10 扁平 MG 信息图": "扁平几何图形：一个圆点代表小伙，沿着箭头从「南门」图标移动到「北门」图标；数字「10 → 50」大字翻滚；一个进度条显示信用值变化；图标一个个弹跳出现。",
    "S11 混合：立体书舞台 + 分镜 + 纸片物理": "3D 立体书舞台（纸片竖在书页上、镜头能环绕推拉），同时用电影分镜：贴地仰拍木杆 → 特写小伙咬牙 → 俯瞰全城围观；金块带物理碰撞掉进怀里堆成小山；换场时纸景折倒、新一页弹起。",
    "C 对照：静态插画幻灯片": "一张张静止的插画依次淡入淡出，配字幕和旁白，人物没有动作，镜头也不动。",
}

Q = {
    "s_kid": {"type": "score", "instructions": "6–12 岁的孩子看这段用 `style` 做出来的约 10 秒画面，会觉得多好看、多想看下去？",
              "criteria": ["无聊，想划走", "平淡，勉强看", "还可以", "好看，想看下去", "非常好看，会想再看一遍或叫别人来看"]},
    "s_fresh": {"type": "score", "instructions": "和孩子常看的普通横版 2D 动画相比，`style` 的画面有多新鲜、多让人记得住？",
                "criteria": ["和普通动画一样，甚至更旧", "略有不同", "有一点新意", "明显新鲜、有记忆点", "非常独特，看一眼就记得是这个系列"]},
    "s_clarity": {"type": "score", "instructions": "`style` 能不能让 6–8 岁的孩子一眼看懂 `series.这段剧情` 里发生了什么（谁在做什么、结果怎样）？",
                  "criteria": ["看不懂", "要费劲才懂一部分", "大概能懂", "看得懂", "一眼就懂，重点很突出"]},
    "s_impact": {"type": "score", "instructions": "`style` 能不能让观众真切感受到这段剧情的分量：木杆有多高多重、围观的人有多少、五十金有多惊人？",
                 "criteria": ["完全感受不到", "有一点", "能感受到一些", "感受很明显", "非常震撼，印象深刻"]},
    "s_brand": {"type": "score", "instructions": "`style` 和 `series.品牌`（纸艺立体书、历史准确、司马光讲书）搭不搭？",
                "criteria": ["冲突", "不太搭", "一般", "搭", "非常搭，能放大品牌特色"]},
    "s_parent": {"type": "score", "instructions": "家长看到 `style` 做出来的画面，觉得有品质、精致，愿意让孩子看、自己也想关注的程度",
                 "criteria": ["觉得廉价或反感", "一般", "还行", "有品质", "很精致，愿意推荐给别的家长"]},
    "n_overload": {"type": "noul", "instructions": "`style` 的画面信息太多、太吵太乱，孩子反而看不清重点"},
    "n_cheap": {"type": "noul", "instructions": "`style` 看起来廉价，像 PPT 或套模板"},
}
PAIR_Q = {
    "p_watch": {"type": "choice", "instructions": "同一段剧情（`series.这段剧情`）用两种画面方式 `a` 和 `b` 做。7 岁的孩子更想接着看哪一个？",
                "criteria": {"a": "方式 a", "b": "方式 b"}},
    "p_parent": {"type": "choice", "instructions": "家长看到两种画面方式 `a` 和 `b`，更愿意关注、转发给别的家长的是哪一个？",
                 "criteria": {"a": "方式 a", "b": "方式 b"}},
    "p_series": {"type": "choice", "instructions": "做成每周更新的系列，孩子连看 10 集也不腻、还能一眼认出是这个系列的，是哪一种画面方式（`a` 还是 `b`）？",
                 "criteria": {"a": "方式 a", "b": "方式 b"}},
}


def score(k):
    ans, _ = jev.ask({"series": SERIES, "style": STYLE[k]}, Q)
    return k, jev.flatten(ans)


def comp(f):
    return (f["s_kid"] + f["s_fresh"] + f["s_clarity"] + f["s_impact"] + f["s_brand"] + f["s_parent"]) / 6 - 1.5 * f["n_overload"] - 1.5 * f["n_cheap"]


with ThreadPoolExecutor(8) as ex:
    scores = dict(ex.map(score, STYLE))
rows = sorted(scores.items(), key=lambda kv: -comp(kv[1]))
print(f"{'方案':<32} 综合  孩子 新鲜 看懂 分量 品牌 家长 | 过载 廉价")
for k, f in rows:
    print(f"{k:<32} {comp(f):5.2f}  {f['s_kid']:.2f} {f['s_fresh']:.2f} {f['s_clarity']:.2f} {f['s_impact']:.2f} {f['s_brand']:.2f} {f['s_parent']:.2f} | {f['n_overload']:.2f} {f['n_cheap']:.2f}")

top = [k for k, _ in rows if not k.startswith("C")][:6]
if "S0 现版本：2D 横版卷轴" not in top:
    top.append("S0 现版本：2D 横版卷轴")


def pair(ab):
    a, b = ab
    r1, _ = jev.ask({"series": SERIES, "a": STYLE[a], "b": STYLE[b]}, PAIR_Q)
    r2, _ = jev.ask({"series": SERIES, "a": STYLE[b], "b": STYLE[a]}, PAIR_Q)
    f1, f2 = jev.flatten(r1), jev.flatten(r2)
    return a, b, {q: (f1[f"{q}=a"] + f2[f"{q}=b"]) / 2 for q in PAIR_Q}


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(pair, itertools.combinations(top, 2)))
win = {k: {q: 0.0 for q in PAIR_Q} for k in top}
for a, b, p in res:
    for q, v in p.items():
        win[a][q] += v
        win[b][q] += 1 - v
m = len(top) - 1
print(f"\n两两对比（{m} 场平均胜率）：孩子想看 / 家长转发 / 适合做系列")
for k in sorted(top, key=lambda k: -sum(win[k].values())):
    print(f"{k:<32} {win[k]['p_watch'] / m:.2f} / {win[k]['p_parent'] / m:.2f} / {win[k]['p_series'] / m:.2f}")
(Path(__file__).parent / "style_result.json").write_text(
    json.dumps({"scores": scores, "top": top, "pairs": res, "win": win}, ensure_ascii=False, indent=1), encoding="utf-8")
