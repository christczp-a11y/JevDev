"""tj03 第 4 轮（10-03）：封面 M（吴起放大在前、魏武侯缩小在后面船上冒冷汗，「“在德不在险” 原来是这么来的」）配三个带真实搜索词的标题，和第 1 轮选的旧组合比。"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "C:/Users/Chris/Claude x Jev/JevDev"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8")
from jevdev import jev  # noqa: E402

CTX = "你没看过这条视频，也不知道里面讲什么故事，只能看到小红书信息流里的一张卡片：封面图（下面 a、b 里有描述）、封面下面一行标题、再下面是小字账号名「光爷爷的资治通鉴大冒险」。"
AUD = "在小红书首页刷双列信息流的家长（孩子 6–12 岁），没看过这条视频，一张卡片只扫一两秒"
IMG_A = "纸艺卡通画：一位留胡子、穿皮甲的将军皱着眉头的大特写，背后是高山和大河"
IMG_B = "纸艺卡通画：一位留胡子、穿皮甲的将军皱着眉、张嘴说话、一手摊开的大特写，背后是高山和大河"
IMG_OLD = "纸艺卡通画：大河上的大木船里，左边一位年轻国君瞪圆眼睛、额头冒冷汗，右边一位穿皮甲的将军皱着眉认真对他说话"
IMG_M = "纸艺卡通画：前面一位留胡子、穿皮甲的将军皱着眉、张嘴认真说话的大特写；他身后的船上，一位年轻国君瞪圆眼睛、额头冒冷汗；背后是高山和大河"

COMBOS = {
    "M1": (IMG_M + "；封面上方大字「“在德不在险”，原来是这么来的」", "吴起给魏武侯上的一课｜资治通鉴儿童版③"),
    "M2": (IMG_M + "；封面上方大字「“在德不在险”，原来是这么来的」", "在德不在险是什么意思？｜资治通鉴儿童版③"),
    "M3": (IMG_M + "；封面上方大字「“在德不在险”，原来是这么来的」", "在德不在险：吴起给魏武侯上课｜资治通鉴③"),
    "old": (IMG_OLD + "；封面上方大字「成语「在德不在险」，原来是这么来的」", "吴起给魏武侯上的一课｜资治通鉴③"),
    "_ctrl": (IMG_A + "；封面下方大字「第三集　资治通鉴卷一　内容简介」", "《资治通鉴》卷一周纪一安王十五年武侯浮西河事"),
}

AB = {"a": "笔记 a", "b": "笔记 b"}
QS = {
    "click": {"type": "choice", "criteria": AB, "instructions":
              "`a` 和 `b` 是同一条视频的两种发法（封面 + 标题）。家长刷到时，更想点开哪一条？"},
    "clear": {"type": "choice", "criteria": AB, "instructions":
              "`a` 和 `b` 是同一条视频的两种发法（封面 + 标题）。只看封面和标题，哪一条让家长一眼明白：这条视频讲什么、对孩子有什么用？"},
    "fit": {"type": "choice", "criteria": AB, "instructions":
            "`a` 和 `b` 是同一条视频的两种发法（封面 + 标题）。哪一种的封面和标题合成一个整体、互相补充，而不是各说各的？"},
    "real": {"type": "choice", "criteria": AB, "instructions":
             "`a` 和 `b` 是同一条视频的两种发法（封面 + 标题）。哪一种更像真人用心做的作品，让家长觉得亲切可信，而不像营销号、广告或说教？"},
}


def view(k):
    cover, title = COMBOS[k]
    return f"封面：{cover}；标题：「{title}」"


def ask(i, j):
    state = {"audience": AUD, "context": CTX, "a": view(i), "b": view(j)}
    return jev.ask(state, QS)[0]


ids = list(COMBOS)
pairs = list(itertools.combinations(ids, 2))
jobs = [(i, j) for i, j in pairs] + [(j, i) for i, j in pairs]
with ThreadPoolExecutor(8) as ex:
    res = dict(zip(jobs, ex.map(lambda p: ask(*p), jobs)))

win = {k: {q: [] for q in QS} for k in ids}
for i, j in pairs:
    for q in QS:
        p = (res[(i, j)][q]["probabilities"]["a"] + res[(j, i)][q]["probabilities"]["b"]) / 2
        win[i][q].append(p)
        win[j][q].append(1 - p)

rows = []
for k in ids:
    by_q = {q: sum(v) / len(v) for q, v in win[k].items()}
    rows.append((sum(by_q.values()) / len(by_q), k, by_q))
rows.sort(reverse=True)
for total, k, by_q in rows:
    print(f"{k:6s} 总胜率 {total:.3f}  " + "  ".join(f"{q}={v:.2f}" for q, v in by_q.items()) + f"   {view(k)}")
json.dump({"combos": COMBOS, "result": [{"id": k, "total": round(t, 3), **{q: round(v, 3) for q, v in b.items()}} for t, k, b in rows]},
          open(f"{REPO}/video/stories/tj03/picks/combo4_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
