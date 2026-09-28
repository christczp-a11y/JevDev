import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "C:/Users/Chris/Claude x Jev/JevDev")
from jevdev import jev  # noqa: E402

OUT = Path(__file__).parent / "names_result.json"

ACCOUNT = {
    "平台": "小红书（用户以年轻妈妈为主）",
    "内容": "把《资治通鉴》里的历史故事做成 2 分钟左右的儿童动画：纸艺立体书画风、Q 版角色、横版闯关、每集中途停下来考观众「你会怎么选」，结尾由作者司马光出来点题",
    "目标观众": "6–12 岁的孩子，和陪孩子看视频的家长",
    "头像": "Q 版司马光：紫色宋代官服、戴两边有长帽翅的官帽、捧着书笑",
    "账号卖点": "史料逐句核对；每集讲清楚古人为什么这么做",
}

CANDS = {
    # 纸艺 / 翻书
    "纸上资治通鉴": "纸艺", "翻开资治通鉴": "纸艺", "会动的资治通鉴": "纸艺", "立体书里的资治通鉴": "纸艺",
    "一页通鉴": "纸艺", "通鉴立体书": "纸艺", "历史翻翻书": "纸艺", "资治通鉴翻翻乐": "纸艺", "翻书就闯关": "纸艺",
    # 人物（司马光）
    "光爷爷讲资治通鉴": "人物", "光爷爷的立体书": "人物", "臣光曰": "人物", "臣光曰·资治通鉴动画": "人物",
    "砸缸之后": "人物", "司马光的书房": "人物",
    # 好奇 / 问题
    "古人为什么这么做": "好奇", "历史里的为什么": "好奇", "考考你·资治通鉴": "好奇",
    # 闯关 / 游戏
    "资治通鉴大冒险": "闯关", "通鉴闯关记": "闯关", "闯关吧资治通鉴": "闯关",
    # 亲子 / 时长
    "陪娃看通鉴": "亲子", "两分钟资治通鉴": "亲子", "通鉴里的小故事": "亲子",
    # 谐音 / 双关 / 数字
    "一鉴钟情": "双关", "看鉴历史": "双关", "以史为鉴小剧场": "双关", "通鉴纸剧场": "双关",
    "纸片历史馆": "双关", "1362年故事书": "双关",
    # 对照组（故意起得差，用来检验 Jev 的打分靠不靠谱）
    "资治通鉴学习资料分享": "对照", "历史视频123": "对照", "国学经典诵读": "对照",
}

Q = {
    "s_memorable": {"type": "score", "instructions": "账号名字 `name` 好不好记：看一眼、念一遍之后，第二天还能不能想起来、能不能准确搜出来？",
                    "criteria": {"1": "拗口或很普通，转头就忘", "2": "勉强记得大概意思，但记不住原字", "3": "念一遍能记住", "4": "顺口、有画面感，很容易记住", "5": "过目不忘，还会忍不住念给别人听"}},
    "s_curious": {"type": "score", "instructions": "一位妈妈在小红书刷到这个账号名字 `name`（结合 `account` 的头像和内容），她有多想点进主页看看？",
                  "criteria": {"1": "完全不想点，像营销号或资料号", "2": "不太想点，看不出特别之处", "3": "可能会点", "4": "挺好奇，大概率会点进去", "5": "非常想点，名字本身就是一个钩子"}},
    "s_clear": {"type": "score", "instructions": "只看名字 `name`，家长能不能猜到这个账号是做什么的（给孩子看的历史故事动画，讲《资治通鉴》）？",
                "criteria": {"1": "完全猜不到，甚至会猜错方向", "2": "只能猜到跟历史或国学有关", "3": "能猜到是讲历史故事", "4": "能猜到是给孩子讲历史或资治通鉴的内容", "5": "一看就知道是给孩子看的资治通鉴故事或动画"}},
    "s_kidfun": {"type": "score", "instructions": "6–12 岁的孩子听到这个账号名字 `name`，会不会觉得好玩、想看？",
                 "criteria": {"1": "像课本或作业，孩子会排斥", "2": "有点严肃无聊", "3": "中性，不排斥也不兴奋", "4": "有点好玩，孩子愿意看", "5": "孩子会觉得很好玩，主动想看"}},
    "s_distinct": {"type": "score", "instructions": "和小红书上常见的历史、国学、读书类账号名字相比，`name` 有多与众不同？",
                   "criteria": {"1": "和一大堆账号名字几乎一样", "2": "比较常见", "3": "有一点自己的特点", "4": "明显不同，有辨识度", "5": "非常独特，别人很难撞名"}},
    "n_misread": {"type": "noul", "instructions": "账号名字 `name` 是否容易被误读、有不雅或负面的谐音、或者让人误会成别的内容（比如成人向、营销号、卖课、恋爱等）？"},
    "n_adult": {"type": "noul", "instructions": "账号名字 `name` 是否听起来主要是给成年人看的严肃读书、学术或国学账号，而不是给孩子看的？"},
}

for q in Q.values():   # score 题的档位要按从低到高的列表给
    if q["type"] == "score":
        q["criteria"] = list(q["criteria"].values())

PAIR_Q = {
    "p_click": {"type": "choice", "instructions": "一位妈妈在小红书上同时刷到两个做同样内容（见 `account`）的账号，名字分别是 `a` 和 `b`。她更可能关注哪一个？",
                "criteria": {"a": "名字 a", "b": "名字 b"}},
    "p_kid": {"type": "choice", "instructions": "6–12 岁的孩子看到两个做同样内容的账号，名字分别是 `a` 和 `b`。孩子更喜欢、更愿意让妈妈点开的是哪一个？",
              "criteria": {"a": "名字 a", "b": "名字 b"}},
}


def score(name):
    ans, _ = jev.ask({"account": ACCOUNT, "name": name}, Q)
    return name, jev.flatten(ans)


with ThreadPoolExecutor(8) as ex:
    scores = dict(ex.map(score, CANDS))

rows = []
for n, f in scores.items():
    comp = (f["s_memorable"] + f["s_curious"] + f["s_clear"] + f["s_kidfun"] + f["s_distinct"]) / 5 - 1.5 * f["n_misread"] - 0.8 * f["n_adult"]
    rows.append((comp, n, f))
rows.sort(reverse=True)
print(f"{'名字':<16} 组别  综合  好记 好奇 看懂 孩子 独特 误读 偏成人")
for comp, n, f in rows:
    print(f"{n:<16} {CANDS[n]:<4} {comp:5.2f}  {f['s_memorable']:.2f} {f['s_curious']:.2f} {f['s_clear']:.2f} {f['s_kidfun']:.2f} {f['s_distinct']:.2f} {f['n_misread']:.2f} {f['n_adult']:.2f}")

# 前 8 名（不含对照组）两两比较，正反各问一次
top = [n for _, n, _ in rows if CANDS[n] != "对照"][:8]
pairs = list(itertools.combinations(top, 2))


def pair(ab):
    a, b = ab
    r1, _ = jev.ask({"account": ACCOUNT, "a": a, "b": b}, PAIR_Q)
    r2, _ = jev.ask({"account": ACCOUNT, "a": b, "b": a}, PAIR_Q)
    f1, f2 = jev.flatten(r1), jev.flatten(r2)
    return a, b, {k: (f1[f"{k}=a"] + f2[f"{k}=b"]) / 2 for k in PAIR_Q}


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(pair, pairs))
win = {n: {k: 0.0 for k in PAIR_Q} for n in top}
for a, b, p in res:
    for k, v in p.items():
        win[a][k] += v
        win[b][k] += 1 - v
print("\n两两比较（7 场里的平均胜率）：妈妈更想关注 / 孩子更喜欢")
for n in sorted(top, key=lambda n: -(win[n]["p_click"] + win[n]["p_kid"])):
    print(f"{n:<16} {win[n]['p_click'] / 7:.2f} / {win[n]['p_kid'] / 7:.2f}")
OUT.write_text(json.dumps({"scores": scores, "top": top, "pairs": res, "win": win}, ensure_ascii=False, indent=1), encoding="utf-8")
