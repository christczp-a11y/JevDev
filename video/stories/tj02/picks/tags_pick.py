"""频道话题标签（10-02，Chris 发来的标签文章：4–6 个，大领域 1 + 细分 2–3 + 长尾 1–2，核心固定每篇带，专属标签，不重复核心词）。
每一层的候选各问三道 score 题（贴合、家长会不会搜、点进来的是不是我们要的人），同层两两比较（正反各问一次），每层混一个不相关的对照标签。
综合 = 0.5 × 三题平均 + 0.5 × 同层胜率。结果写到 tags_result.json。
"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor

REPO = "C:/Users/Chris/Claude x Jev/JevDev"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8")
from jevdev import jev  # noqa: E402

CHANNEL = ("小红书账号「光爷爷的资治通鉴大冒险」：按《资治通鉴》的顺序，把书里的历史故事一个一个做成 3 分钟左右的纸艺动画，"
           "写书的司马光爷爷当讲解人；给 6–12 岁的孩子和陪着看的家长，每集讲一个做人的道理（比如守信、尊重人）。")
TIERS = {
    "大领域": ["#历史", "#历史故事", "#亲子教育", "#育儿", "#儿童教育", "#国学", "#穿搭"],
    "细分": ["#资治通鉴", "#历史启蒙", "#儿童历史", "#亲子共读", "#国学启蒙", "#儿童动画", "#少儿历史", "#中国历史故事", "#减脂餐"],
    "长尾": ["#儿童历史动画", "#给孩子讲资治通鉴", "#小学生历史启蒙", "#资治通鉴儿童版", "#少儿资治通鉴", "#历史启蒙动画", "#小学生必看的历史故事", "#小红书运营技巧"],
    "专属": ["#光爷爷讲资治通鉴", "#光爷爷的资治通鉴大冒险", "#跟孩子读资治通鉴", "#我的日常"],
}
CONTROLS = {"#穿搭", "#减脂餐", "#小红书运营技巧", "#我的日常"}

L5 = lambda *c: list(c)  # noqa: E731
SCORE = {
    "fit": {"type": "score", "instructions": "`tag` 是一个小红书话题标签。它和 `channel` 这个账号的内容有多贴合？",
            "criteria": L5("完全不相关", "沾一点边", "相关，但太泛了", "贴合", "非常贴合，一看就是这类内容")},
    "demand": {"type": "score", "instructions": "带 6–12 岁孩子的家长，会不会在小红书搜索或点进 `tag` 这个话题找内容？",
               "criteria": L5("几乎不会", "偶尔会", "有一些人会", "经常会", "这是他们找这类内容最常用的词")},
    "precise": {"type": "score", "instructions": "点进 `tag` 这个话题的人，大多数是不是 `channel` 想找的人（想给 6–12 岁孩子找历史故事、学做人道理的家长）？",
                "criteria": L5("几乎都不是", "少数是", "一半一半", "多数是", "几乎都是")},
}
PAIR = {"push": {"type": "choice", "criteria": {"a": "标签 a", "b": "标签 b"},
                 "instructions": "`a` 和 `b` 是两个小红书话题标签。给 `channel` 这个账号的视频加哪一个，更能把视频推给对的家长、带来真正会看完的人？"}}


def score(tag):
    return jev.ask({"channel": CHANNEL, "tag": tag}, SCORE)[0]


def pair(a, b):
    return jev.ask({"channel": CHANNEL, "a": a, "b": b}, PAIR)[0]["push"]["probabilities"]


out = {}
with ThreadPoolExecutor(8) as ex:
    for tier, tags in TIERS.items():
        sc = dict(zip(tags, ex.map(score, tags)))
        combos = list(itertools.combinations(tags, 2))
        jobs = combos + [(b, a) for a, b in combos]
        res = dict(zip(jobs, ex.map(lambda p: pair(*p), jobs)))
        win = {t: [] for t in tags}
        for a, b in combos:
            p = (res[(a, b)]["a"] + res[(b, a)]["b"]) / 2
            win[a].append(p)
            win[b].append(1 - p)
        rows = []
        for t in tags:
            s = {q: sc[t][q]["score"] / 4 for q in SCORE}
            mean = sum(s.values()) / len(s)
            wr = sum(win[t]) / len(win[t])
            rows.append({"tag": t, "control": t in CONTROLS, **{q: round(v, 2) for q, v in s.items()},
                         "winrate": round(wr, 3), "combined": round(0.5 * mean + 0.5 * wr, 3)})
        rows.sort(key=lambda r: -r["combined"])
        out[tier] = rows
        ctrl_last = rows[-1]["control"]
        print(f"\n=== {tier}（对照项{'排在最后，可信' if ctrl_last else '没排最后，不可信'}）===")
        for r in rows:
            print(f"{r['combined']:.3f}  贴合 {r['fit']:.2f}  会搜 {r['demand']:.2f}  对的人 {r['precise']:.2f}  胜率 {r['winrate']:.2f}  {r['tag']}{'（对照）' if r['control'] else ''}")
json.dump({"channel": CHANNEL, "tiers": out}, open(f"{REPO}/video/stories/tj02/picks/tags_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
