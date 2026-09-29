"""video/jev_pick.py 的离线逻辑测试：用假的 jev.ask 代替 Jev，不要网络、不要真 key、不花钱。
测：正反两个顺序各问一次并取平均（位置偏差被抵消）、对照项自动混进去、对照项没排最后就退出码 1、缓存（第二次不再请求）、
API 失败退出码 3 且 key 不出现在输出里、classify 的对照评论、rubric 里 score 题的 criteria 都是列表（PITFALLS E6）。
用法（仓库根目录）：.venv/Scripts/python video/tests/jev_pick/test_logic.py     退出码 0 = 全过。"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "video"))
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
os.environ["TYPESAFE_API_KEY"] = "SECRET-KEY-FOR-TEST"       # 假 key：假的 ask 不会联网

import jev_pick  # noqa: E402
from jevdev import jev  # noqa: E402

FAILS = []
TMP = Path(tempfile.mkdtemp(prefix="jev_pick_test_"))
CTRL = jev_pick.RUBRIC["categories"]["title"]["control"]
QUALITY = {"好标题": 0.9, "中标题": 0.55, "差标题": 0.2}     # 假 Jev 的「真实水平」，对照项默认最差
calls = []


def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  {detail}"))
    if not cond:
        FAILS.append(name)


def q_of(text):
    return QUALITY.get(text, 0.02 if text == CTRL else 0.5)


def fake_ask(state, questions):
    """按候选的「真实水平」回答：score 题 = 4 × 水平；pair 题 a 赢的概率 = 0.5 + (a − b) / 2。"""
    calls.append((state, questions))
    out = {}
    for q, spec in questions.items():
        if spec["type"] == "score":
            out[q] = {"type": "score", "score": 4 * q_of(state["candidate"])}
        elif spec["type"] == "choice":
            pa = min(0.99, max(0.01, 0.5 + (q_of(state["a"]) - q_of(state["b"])) / 2))
            out[q] = {"type": "choice", "probabilities": {"a": pa, "b": 1 - pa}}
    return out, {"input_tokens": 10, "output_tokens": 1}


def cands(*texts):
    return {"category": "title", "context": "测试背景", "candidates": [{"id": f"t{i}", "text": t} for i, t in enumerate(texts, 1)]}


def cli(argv, cand, ask=fake_ask, name="c.json"):
    """在进程内跑 main()：返回 (退出码, 标准输出, 标准错误, 结果 JSON)。"""
    f = TMP / name
    f.write_text(json.dumps(cand, ensure_ascii=False), encoding="utf-8")
    out_json = TMP / (name + ".out.json")
    out_json.unlink(missing_ok=True)
    calls.clear()
    old, old_argv = jev.ask, sys.argv
    jev.ask = ask
    sys.argv = ["jev_pick.py", argv[0], str(f), "--out", str(out_json), "--cache", str(TMP / (name + ".cache.json"))] + argv[1:]
    o, e = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            jev_pick.main()
    except SystemExit as x:
        code = x.code or 0
    finally:
        jev.ask, sys.argv = old, old_argv
    return code, o.getvalue(), e.getvalue(), (json.loads(out_json.read_text(encoding="utf-8")) if out_json.exists() else None)


# ---- rubric：score 题的 criteria 是列表（E6）、5 档；choice 题的 criteria 是 a / b
R = jev_pick.RUBRIC
bad = [f"{c}.{q}" for c, cfg in R["categories"].items() for q, s in cfg["score"].items()
       if not (isinstance(s["criteria"], list) and len(s["criteria"]) == 5)]
check("rubric：所有 score 题的 criteria 是 5 档的列表（E6）", not bad, str(bad))
bad = [f"{c}.{q}" for c, cfg in R["categories"].items() for q, s in cfg["pair"].items() if list(s["criteria"]) != ["a", "b"]]
check("rubric：所有 pair 题是 a / b 二选一", not bad, str(bad))
check("rubric：每个类别都有 control", all(cfg.get("control") for cfg in R["categories"].values()) and R["classify"]["control"])

# ---- 正常：对照项自动混进去、排最后，正反各问一次
code, out, err, r = cli(["title"], cands("好标题", "中标题", "差标题"))
check("正常：退出码 0", code == 0, f"{code}\n{err}")
check("正常：名次 好 > 中 > 差", [x["text"] for x in r["ranking"]] == ["好标题", "中标题", "差标题"], str([x["text"] for x in r["ranking"]]))
check("正常：ranking 里没有对照项，control 单独放", all(x["id"] != "_ctrl" for x in r["ranking"]) and r["control"]["id"] == "_ctrl")
check("正常：对照项自动混进去了（池子 4 个）、排最后", r["control"]["pool_size"] == 4 and r["control"]["rank_in_pool"] == 4 and r["control_last"])
n_score = sum(1 for s, qs in calls if "candidate" in s)
n_pair = sum(1 for s, qs in calls if "a" in s)
check("正常：4 次打分 + 6 对 × 2 个顺序 = 12 次两两比较", (n_score, n_pair) == (4, 12), f"{n_score}，{n_pair}")
seen = {(s["a"], s["b"]) for s, qs in calls if "a" in s}
check("正常：每一对都是正反两个顺序各问了一次", all((b, a) in seen for a, b in seen))
check("正常：Jev 看到的状态里没有候选的 id", not any("t1" in json.dumps(s, ensure_ascii=False) for s, qs in calls))
check("正常：胜率、分数都在 0–1", all(0 <= x["winrate"] <= 1 and 0 <= x["score"] <= 1 for x in r["ranking"]))
check("正常：输出里有排名和对照项那一行", "对照 _ctrl" in out and "对照项排在最后" in out)

# ---- 缓存：同样的输入再跑一次，一次请求都不发
cache_before = json.loads((TMP / "c.json.cache.json").read_text(encoding="utf-8"))
code, out, err, r2 = cli(["title"], cands("好标题", "中标题", "差标题"))
check("缓存：第二次跑没有新请求", not calls and r2["calls"]["requests"] == 0 and r2["calls"]["cached"] == 16, f"{len(calls)}，{r2['calls']}")
check("缓存：结果一样", r2["ranking"] == r["ranking"])
code, out, err, r3 = cli(["title"], cands("好标题", "中标题", "差标题", "新标题"))
check("缓存：加一个候选只花和它有关的调用（1 次打分 + 4 对 × 2 = 9，其余用缓存）", r3["calls"]["requests"] == 9, str(r3["calls"]))

# ---- 位置偏差：假 Jev 永远说 a 赢 90%，两个顺序取平均后每个候选的胜率都该是 0.5
def always_a(state, questions):
    calls.append((state, questions))
    return {q: ({"type": "score", "score": 2.0} if s["type"] == "score" else {"type": "choice", "probabilities": {"a": 0.9, "b": 0.1}})
            for q, s in questions.items()}, {}
code, out, err, r = cli(["title"], cands("甲", "乙", "丙"), ask=always_a, name="bias.json")
check("位置偏差：永远偏向 a 的 Jev，正反平均后胜率全是 0.5", all(abs(x["winrate"] - 0.5) < 1e-9 for x in r["ranking"]), str([x["winrate"] for x in r["ranking"]]))
check("位置偏差：分不出高低时对照项不算排最后（平分）→ 退出码 1", code == 1 and r["control_last"] is False, f"{code}")

# ---- 对照项没排最后：警告 + 退出码 1，结果照样写出来（标明不可信）
QUALITY_BAK = dict(QUALITY)
QUALITY[CTRL] = 0.99
code, out, err, r = cli(["title"], cands("好标题", "中标题", "差标题"), name="ctrl_best.json")
QUALITY.clear(); QUALITY.update(QUALITY_BAK)
check("对照项最好：退出码 1", code == 1, str(code))
check("对照项最好：打印警告，说了排第几", "对照项排在池子里第 1 / 4，没排最后" in err, err)
check("对照项最好：--out 照样写出来，control_last = false", r is not None and r["control_last"] is False and r["control"]["last"] is False)

# ---- API 失败：退出码 3，key 不出现
def boom(state, questions):
    raise RuntimeError("connect failed to https://api.typesafe.ai with key SECRET-KEY-FOR-TEST")
code, out, err, r = cli(["title"], cands("好标题", "中标题"), ask=boom, name="boom.json")
check("API 失败：退出码 3、没有结果文件", code == 3 and r is None, f"{code}")
check("API 失败：说了「Jev 调用失败」", "Jev 调用失败" in err, err)
check("API 失败：key 没有出现在任何输出里", "SECRET-KEY-FOR-TEST" not in err + out and "***" in err, err)

# ---- 没有 key
os.environ["TYPESAFE_API_KEY"] = ""
code, out, err, r = cli(["title"], cands("好标题", "中标题"), name="nokey.json")
check("没有 key：退出码 2、没有调用、报错里点名 TYPESAFE_API_KEY", code == 2 and not calls and "TYPESAFE_API_KEY" in err, f"{code} {err}")
os.environ["TYPESAFE_API_KEY"] = "SECRET-KEY-FOR-TEST"

# ---- quiz：拆成四段再发给 Jev
q = {"category": "quiz", "context": "测试背景",
     "candidates": [{"id": "q1", "text": "给不给？｜给｜不给｜给，因为计策"}, {"id": "q2", "text": "输不输？｜输｜不输｜输，因为没人帮"}]}
def quiz_ask(state, questions):
    calls.append((state, questions))
    return {k: ({"type": "score", "score": 2.0} if s["type"] == "score" else {"type": "choice", "probabilities": {"a": 0.5, "b": 0.5}})
            for k, s in questions.items()}, {}
code, out, err, r = cli(["quiz"], q, ask=quiz_ask, name="quiz.json")
sent = [s["candidate"] for s, qs in calls if "candidate" in s]
check("quiz：发给 Jev 的是拆好的四段", all(isinstance(x, dict) and list(x) == list(jev_pick.QUIZ_PARTS) for x in sent) and sent[0]["选项A"] == "给", str(sent[:1]))

# ---- classify：四个是 / 否题；对照评论分对了才可信
def cls_ask(state, questions):
    calls.append((state, questions))
    t = state["comment"]
    hit = {"没看懂": "confused", "太吵": "complaint", "下一集": "next", "原来": "understood"}
    return {k: {"type": "noul", "noul": 0.9 if any(w in t and hit[w] == k for w in hit) else 0.05} for k in questions}, {}
cl = {"category": "classify", "context": "测试背景", "candidates": [{"id": "c1", "text": "没看懂"}, {"id": "c2", "text": "太吵了"}, {"id": "c3", "text": "哈哈"}]}
code, out, err, r = cli(["classify"], cl, ask=cls_ask, name="cls.json")
check("classify：退出码 0，对照评论分对了", code == 0 and r["control"]["ok"], f"{code} {err}")
check("classify：标签对得上，都不到 0.5 的算「其他」", [x["labels"] for x in r["items"]] == [["没看懂"], ["有意见"], ["其他"]], str([x["labels"] for x in r["items"]]))
check("classify：每条评论只发了一次请求（四个题一起问）", len(calls) == 4 and all(len(qs) == 4 for s, qs in calls), str(len(calls)))
def cls_wrong(state, questions):
    return {k: {"type": "noul", "noul": 0.9 if k == "complaint" else 0.05} for k in questions}, {}
code, out, err, r = cli(["classify"], cl, ask=cls_wrong, name="cls_wrong.json")
check("classify：对照评论没分对 → 退出码 1", code == 1 and r["control"]["ok"] is False, f"{code}")

print()
if FAILS:
    print(f"test_logic：{len(FAILS)} 项不过：{FAILS}")
    sys.exit(1)
print("test_logic：全过")
