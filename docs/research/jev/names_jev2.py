import itertools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

src = (Path(__file__).parent / "names_jev.py").read_text(encoding="utf-8")
exec(src.split("def score")[0])   # 复用第一轮的账号描述、题目和两两比较题

NEW = ["光爷爷的资治通鉴大冒险", "光爷爷的立体书·资治通鉴", "跟光爷爷闯资治通鉴", "资治通鉴立体大冒险"]
OLD = ["光爷爷的立体书", "资治通鉴大冒险", "闯关吧资治通鉴"]


def score(name):
    ans, _ = jev.ask({"account": ACCOUNT, "name": name}, Q)
    return name, jev.flatten(ans)


with ThreadPoolExecutor(8) as ex:
    sc = dict(ex.map(score, NEW))
print(f"{'名字':<18} 综合  好记 好奇 看懂 孩子 独特 误读 偏成人")
for n, f in sc.items():
    comp = (f["s_memorable"] + f["s_curious"] + f["s_clear"] + f["s_kidfun"] + f["s_distinct"]) / 5 - 1.5 * f["n_misread"] - 0.8 * f["n_adult"]
    print(f"{n:<18} {comp:5.2f}  {f['s_memorable']:.2f} {f['s_curious']:.2f} {f['s_clear']:.2f} {f['s_kidfun']:.2f} {f['s_distinct']:.2f} {f['n_misread']:.2f} {f['n_adult']:.2f}")

allc = NEW + OLD
pairs = list(itertools.combinations(allc, 2))


def pair(ab):
    a, b = ab
    r1, _ = jev.ask({"account": ACCOUNT, "a": a, "b": b}, PAIR_Q)
    r2, _ = jev.ask({"account": ACCOUNT, "a": b, "b": a}, PAIR_Q)
    f1, f2 = jev.flatten(r1), jev.flatten(r2)
    return a, b, {k: (f1[f"{k}=a"] + f2[f"{k}=b"]) / 2 for k in PAIR_Q}


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(pair, pairs))
win = {n: {k: 0.0 for k in PAIR_Q} for n in allc}
for a, b, p in res:
    for k, v in p.items():
        win[a][k] += v
        win[b][k] += 1 - v
m = len(allc) - 1
print(f"\n第二轮两两比较（{m} 场平均胜率）：妈妈更想关注 / 孩子更喜欢")
for n in sorted(allc, key=lambda n: -(win[n]["p_click"] + win[n]["p_kid"])):
    print(f"{n:<18} {win[n]['p_click'] / m:.2f} / {win[n]['p_kid'] / m:.2f}")
