"""tj02 封面 + 标题（第 9 步，照 tj01 第 4 轮的做法）：Jev 只当没看过片子的陌生家长，封面 + 标题成组比四题。"""
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
IMG = "纸艺卡通画：一位年轻古装男子戴竹斗笠、披草蓑衣，在大雨里神情坚定的大特写"

COMBOS = {
    "k1": (IMG + "；封面上方大字「下大雨了，约好的事还去吗？」", "冒大雨也不放鸽子的人｜资治通鉴②"),
    "k2": (IMG + "；封面上方大字「下大雨了，要不要放鸽子？」", "两千多年前，一个说到做到的人｜资治通鉴②"),
    "k3": (IMG + "；封面上方大字「什么叫一诺千金？」", "冒大雨赶去赴约的魏文侯｜资治通鉴②"),
    "k4": (IMG + "；封面上方大字「冒着大雨赶去，只为说一句话」", "说好的事，下雨也算数｜资治通鉴②"),
    "_ctrl": (IMG + "；封面下方大字「第二集　资治通鉴卷一　内容简介」", "《资治通鉴》卷一周纪一威烈王二十三年魏文侯期猎事"),
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
          open(f"{REPO}/video/stories/tj02/picks/combo_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
