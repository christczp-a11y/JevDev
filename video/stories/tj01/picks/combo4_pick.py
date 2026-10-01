"""第 4 轮（10-02，Chris「标题还是不行」「最重要怎么做首页图和起标题」）：大字放上半部分的三版新封面 + 标题，和现在用的比；Jev 只当没看过片子的陌生家长。"""
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
IMG_ZB = "纸艺卡通画：一个古装男人被水浇成落汤鸡（嘴里喷水、冠上蹲着一只青蛙）的大特写"
IMG_A = "纸艺卡通画：一位笑眯眯的古装老爷爷拿着小遥控器，旁边一个古装男人被水浇成落汤鸡、冠上蹲着青蛙"
IMG_C = "纸艺卡通画：一位古装老爷爷举着放大镜贴在眼前、笑着看你"

COMBOS = {
    "now": (IMG_ZB + "；封面下方大字「本事满分 尊重0分」", "本事再大，不懂尊重也会输光｜资治通鉴①"),
    "A1": (IMG_A + "；封面上方大字「我把《资治通鉴》做成了动画」", "第1集：样样都强的人，为什么一夜输光？"),
    "A2": (IMG_A + "；封面上方大字「我把《资治通鉴》做成了动画」", "我把《资治通鉴》做成了儿童动画①"),
    "B1": (IMG_ZB + "；封面上方大字「样样都强的人，为什么一夜输光？」", "我把《资治通鉴》做成了儿童动画①"),
    "C1": (IMG_C + "；封面上方大字「砸缸的司马光，写了本什么书？」", "司马光写了19年的书，讲给孩子听①"),
    "_ctrl": (IMG_ZB + "；封面下方大字「第一集　资治通鉴卷一　内容简介」", "《资治通鉴》卷一周纪一威烈王二十三年史事综述"),
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
          open(f"{REPO}/video/stories/tj01/picks/combo4_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
