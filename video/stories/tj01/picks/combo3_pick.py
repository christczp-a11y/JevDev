"""第 3 轮（10-02，发布后改标题）：Jev 只当「没看过片子的陌生家长」，只看得到封面和标题，不给剧情（第 1、2 轮把剧情给了 Jev，高估了「要地给不给」这种圈内人才懂的标题）。"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "C:/Users/Chris/Claude x Jev/JevDev"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8")
from jevdev import jev  # noqa: E402

CTX = ""
CTX = "你没看过这条视频，也不知道里面讲什么故事，只能看到信息流卡片：封面是一个古装男人被水浇成落汤鸡的卡通大特写（嘴里喷水、冠上蹲着一只青蛙），左上角「第1集」「三家分晋」，下方大字「本事满分 尊重0分」；卡片下面是标题，再下面是小字账号名「光爷爷的资治通鉴大冒险」。"
AUD = "在小红书首页刷双列信息流的家长（孩子 6–12 岁），没看过这条视频，一张卡片只扫一两秒"

COMBOS = {
    "k0": ("本事满分 尊重0分", "跟孩子读《资治通鉴》①：要地给不给？"),
    "k1": ("本事满分 尊重0分", "本事再大，不懂尊重也会输光｜资治通鉴①"),
    "k2": ("本事满分 尊重0分", "智伯本事满分，为什么一夜输光？"),
    "k3": ("本事满分 尊重0分", "本事和品德，哪个更重要？｜资治通鉴①"),
    "k4": ("本事满分 尊重0分", "有本事却不尊重人，会怎样？｜资治通鉴①"),
    "k5": ("本事满分 尊重0分", "样样都强的智伯，为什么一夜输光？"),
    "k6": ("本事满分 尊重0分", "跟孩子读《资治通鉴》①：本事和品德"),
    "_ctrl": ("本事满分 尊重0分", "《资治通鉴》卷一周纪一威烈王二十三年史事综述"),
}

AB = {"a": "笔记 a", "b": "笔记 b"}
QS = {
    "click": {"type": "choice", "criteria": AB, "instructions":
              "`a` 和 `b` 是同一条视频的两种标题（封面一样，见 `context`）。家长刷到时，更想点开哪一条？"},
    "clear": {"type": "choice", "criteria": AB, "instructions":
              "`a` 和 `b` 是同一条视频的两种标题（封面一样，见 `context`）。只看封面和标题，哪一条让家长一眼明白：这条视频讲什么、对孩子有什么用？"},
    "fit": {"type": "choice", "criteria": AB, "instructions":
            "`a` 和 `b` 是同一条视频的两种标题（封面一样，见 `context`）。哪一条标题和封面说的是同一件事、合成一个整体，而不是各说各的？"},
}


def view(k):
    cover, title = COMBOS[k]
    return f"封面大字：「{cover}」；标题：「{title}」"


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
          open(f"{REPO}/video/stories/tj01/picks/combo3_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
