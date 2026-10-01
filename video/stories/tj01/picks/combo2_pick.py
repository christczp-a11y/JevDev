"""第 2 轮（10-01，PITFALLS P20）：封面字固定「本事满分 尊重0分」，比标题；加一道「语气谦虚厚重」题。"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "C:/Users/Chris/Claude x Jev/JevDev"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8")
from jevdev import jev  # noqa: E402

CTX = json.load(open(f"{REPO}/video/stories/tj01/picks/title.json", encoding="utf-8"))["context"]
CTX += "封面画面：智伯被大浪浇成落汤鸡的夸张大特写（冠歪了、头顶蹲着一只青蛙），左上角「第1集」。"
AUD = "在小红书刷双列信息流的家长（孩子 6–12 岁），有时和孩子一起看；信息流里每条笔记只露出封面（带大字）和下面一行标题"

COMBOS = {
    "k1": ("本事满分 尊重0分", "要地给不给？2400年前的一道选择题"),
    "k2": ("本事满分 尊重0分", "资治通鉴第1集｜要地，给还是不给？"),
    "k3": ("本事满分 尊重0分", "《资治通鉴》第一课：要地，给不给？"),
    "k4": ("本事满分 尊重0分", "跟孩子读《资治通鉴》①：要地给不给？"),
    "k5": ("本事满分 尊重0分", "要地给不给？《资治通鉴》开篇的选择题"),
    "k6": ("本事满分 尊重0分", "读《资治通鉴》第1课：智伯为什么输了？"),
    "_ctrl": ("第一集　资治通鉴卷一　内容简介", "《资治通鉴》卷一周纪一威烈王二十三年史事综述"),
}

AB = {"a": "笔记 a", "b": "笔记 b"}
QS = {
    "click": {"type": "choice", "criteria": AB, "instructions":
              "`a` 和 `b` 是同一条视频的两种发法（封面大字 + 标题，`context` 里有视频内容）。家长在小红书信息流里刷到，更想点开哪一条？"},
    "comment": {"type": "choice", "criteria": AB, "instructions":
                "`a` 和 `b` 是同一条视频的两种发法（封面大字 + 标题）。看完视频以后，哪一种发法让家长或孩子更想在评论区说两句（回答问题、说自己的看法）？"},
    "tone": {"type": "choice", "criteria": AB, "instructions":
             "`a` 和 `b` 是同一条视频的两种发法（封面大字 + 标题）。哪一种的气质更谦虚厚重：不浮夸、不吆喝、不卖弄，像认真读书、敬重历史的人写的，家长看了觉得踏实可信？"},
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
          open(f"{REPO}/video/stories/tj01/picks/combo2_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
