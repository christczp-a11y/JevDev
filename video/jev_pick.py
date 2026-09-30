"""让 Jev 从候选里挑（工作流第 2 步和第 9 步；用法见 .claude/skills/jev-decisions/SKILL.md；PITFALLS E6、P8）。
创作还是 Claude 来做，这里只做「批量比较」：候选各打分，再两两比较，混进一个故意很差的对照项验证结果可不可信。

用法（Git Bash，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8 和 TYPESAFE_API_KEY）
  python video/jev_pick.py <类别> <候选.json> [--out 结果.json] [--cache 缓存路径] [--workers 8]
  类别：analogy（古今对照）、quiz（「考你」题）、catchphrase（金句）、title（标题）、cover_text（封面文字）、classify（评论分类）
  退出码：0 = 完成、对照项排在最后（结果可信）；1 = 对照项没排最后（结果不可信，要改候选或改题再跑）；2 = 输入有错、没有 TYPESAFE_API_KEY；3 = 连不上 Jev / 调用失败。

候选文件（analogy、quiz、catchphrase、title、cover_text 通用）
  {"category": "analogy",                     // 可以不写；写了要和命令行的类别一致
   "context": "给 Jev 看的背景：这一集讲什么、候选用在哪一句",   // 必填
   "candidates": [{"id": "a1", "text": "智伯天天要地，就像同桌天天要你的零食"}, ...]}   // 至少 2 个；id 不重复，不能叫 _ctrl
  quiz 的 text 写成「题目｜选项A｜选项B｜答案和理由」（全角竖线，共 4 段），脚本拆开再发给 Jev。
  context 要写清楚这一集的史实：analogy 靠它判断有没有歪曲史实。

评论分类 classify 的候选文件（同样的键，text 是评论原文，至少 1 条）
  {"category": "classify", "context": "这条视频讲什么", "candidates": [{"id": "c1", "text": "没看懂，人太多了"}, ...]}
  每条评论问四个是 / 否题：看懂了、没看懂、想看下一集、有意见（概率 ≥ 0.5 算属于这一类，可以同时属于几类，都不到算「其他」）。
  自动混进一条一眼能看出类别的对照评论（「下一集什么时候更新」），它没被分到「想看下一集」，就报警、退出码 1。

做法（题目在 rubrics/pick_v2.json，改题不改代码）
  每个候选按类别问几道 score 题（5 档，换成 0–1），再和其他每个候选两两比较，a、b 两种顺序各问一次取平均，得胜率；
  综合 = 0.5 × 平均分 + 0.5 × 胜率。对照项是自动混进去的、故意很差的一项（每个类别一句固定的话）。
  结果按（模型、状态、题目）的哈希缓存在 video/out/jev_pick_cache.json，重跑不重复花钱；加一个候选只多花和它有关的调用。

--out 结果.json
  {category, rubric, model, context, control_last, ranking: [{rank, id, text, flags, scores, score, winrate, winrate_by_q, combined}],
   control: {id, text, rank_in_pool, pool_size, score, winrate, combined, last}, pairs, calls}
  ranking 里只有真实候选（名次是在含对照项的池子里排的）；flags 是低于阈值的提醒（目前只有 analogy：a_true < 0.4 标「疑似歪曲史实」），只提醒，不改退出码。
  classify 的结果：{category, control_last, summary: {类别: 条数}, items: [{id, text, probs: {类别: 概率}, labels}], control: {…, ok}}。
"""
import argparse
import hashlib
import itertools
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from jevdev import jev  # noqa: E402

RUBRIC_NAME = "pick_v2"   # 新旧分数不混着比：改题另存新版本（v2：金句加「一听就懂」，PITFALLS S21）
RUBRIC = jev.load_rubric(RUBRIC_NAME)
AUDIENCE = RUBRIC["audience"]
W_SCORE, W_WIN = RUBRIC["weights"]["score"], RUBRIC["weights"]["winrate"]
CATEGORIES = list(RUBRIC["categories"]) + ["classify"]
CACHE = ROOT / "out" / "jev_pick_cache.json"
CTRL_ID = "_ctrl"
YES = 0.5          # classify：概率 ≥ 0.5 算属于这一类
QUIZ_PARTS = ("题目", "选项A", "选项B", "答案和理由")


class Fail(Exception):
    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code


def require_key():
    """没有 Jev 的 key 就立刻退出：不许等到白跑很久之后才报（P8）。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise Fail("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 挑选跑不了。挑选不许跳过（P8）。\n"
                   "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                   "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


def parse_quiz(text):
    """「题目｜选项A｜选项B｜答案和理由」→ 四段；不是四段返回 None。"""
    parts = [p.strip() for p in text.replace("|", "｜").split("｜")]
    return dict(zip(QUIZ_PARTS, parts)) if len(parts) == 4 and all(parts) else None


def load_candidates(path, category):
    """读候选文件并检查格式（不花钱）。返回 (context, [{id, text}])。"""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Fail(f"错误：候选文件读不了或不是 JSON：{path}（{e}）")
    if not isinstance(d, dict):
        raise Fail("错误：候选文件顶层要是对象 {category, context, candidates}")
    if d.get("category", category) != category:
        raise Fail(f"错误：候选文件里的 category 是「{d['category']}」，命令行给的是「{category}」")
    ctx = d.get("context")
    if not isinstance(ctx, str) or not ctx.strip():
        raise Fail("错误：候选文件要有 context（给 Jev 看的背景：这一集讲什么、候选用在哪一句），Jev 看不到别的东西")
    cands = d.get("candidates")
    need = 1 if category == "classify" else 2
    if not isinstance(cands, list) or len(cands) < need:
        raise Fail(f"错误：candidates 要是列表，至少 {need} 个")
    seen = set()
    for i, c in enumerate(cands):
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"].strip() \
                or not isinstance(c.get("text"), str) or not c["text"].strip():
            raise Fail(f"错误：candidates[{i}] 要是 {{\"id\": \"...\", \"text\": \"...\"}}，两项都不能空")
        if c["id"] == CTRL_ID or c["id"] in seen:
            raise Fail(f"错误：candidates[{i}] 的 id「{c['id']}」重复了（{CTRL_ID} 是自动混进去的对照项，也不能用）")
        seen.add(c["id"])
        if category == "quiz" and not parse_quiz(c["text"]):
            raise Fail(f"错误：candidates[{i}]（{c['id']}）的 text 要写成「题目｜选项A｜选项B｜答案和理由」，共 4 段、都不能空")
    return ctx.strip(), [{"id": c["id"], "text": c["text"].strip()} for c in cands]


def cand_view(category, text):
    """发给 Jev 的样子：quiz 拆成四段，其他就是原文。"""
    return parse_quiz(text) if category == "quiz" else text


class Cache:
    """按（模型、状态、题目）的哈希缓存；线程安全。"""

    def __init__(self, path):
        self.path = Path(path)
        self.d = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.lock = threading.Lock()
        self.fresh = self.hits = self.tokens_in = self.tokens_out = 0

    def ask(self, state, questions):
        k = hashlib.sha1(json.dumps([jev.MODEL, state, questions], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if k in self.d:
            with self.lock:
                self.hits += 1
            return self.d[k]
        a, usage = jev.ask(state, questions)
        r = {q: (v["score"] if v["type"] == "score" else v["noul"] if v["type"] == "noul" else v["probabilities"])
             for q, v in a.items()}
        with self.lock:
            self.d[k] = r
            self.fresh += 1
            self.tokens_in += usage.get("input_tokens", 0)
            self.tokens_out += usage.get("output_tokens", 0)
        return r

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")

    def calls(self):
        return {"requests": self.fresh, "cached": self.hits, "input_tokens": self.tokens_in, "output_tokens": self.tokens_out}


def run_parallel(fns, workers):
    """先串行做第一个（连不上就马上停，不等一堆并行请求都超时），其余并行。返回按顺序的结果。"""
    if not fns:
        return []
    out = [fns[0]()]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(f) for f in fns[1:]]
        try:
            out += [f.result() for f in futs]
        except BaseException:
            ex.shutdown(wait=True, cancel_futures=True)
            raise
    return out


def run_pick(category, ctx, cands, cache, workers):
    """打分 + 两两比较，返回结果字典（还没判断对照项）。"""
    cfg = RUBRIC["categories"][category]
    pool = [{"id": c["id"], "text": c["text"], "control": False} for c in cands]
    pool.append({"id": CTRL_ID, "text": cfg["control"], "control": True})
    n = len(pool)
    task = cfg["task"]
    base = {"audience": AUDIENCE, "task": task, "context": ctx}

    def score_fn(i):
        return lambda: cache.ask({**base, "candidate": cand_view(category, pool[i]["text"])}, cfg["score"])

    def pair_fn(i, j):     # i 放在 a，j 放在 b
        return lambda: cache.ask({**base, "a": cand_view(category, pool[i]["text"]), "b": cand_view(category, pool[j]["text"])}, cfg["pair"])

    combos = list(itertools.combinations(range(n), 2))
    jobs = [score_fn(i) for i in range(n)]
    jobs += [pair_fn(i, j) for i, j in combos] + [pair_fn(j, i) for i, j in combos]
    res = run_parallel(jobs, workers)
    scores = res[:n]
    fwd = dict(zip(combos, res[n:n + len(combos)]))          # (i, j)：i 在 a
    rev = dict(zip(combos, res[n + len(combos):]))           # (i, j)：j 在 a，i 在 b
    qs = list(cfg["pair"])

    # p_win[i][j][q] = i 赢 j 的概率（两种顺序的平均）
    p_win = {}
    for i, j in combos:
        p_win[(i, j)] = {q: (fwd[(i, j)][q]["a"] + rev[(i, j)][q]["b"]) / 2 for q in qs}
        p_win[(j, i)] = {q: 1 - p_win[(i, j)][q] for q in qs}
    rows = []
    for i, c in enumerate(pool):
        opp = [j for j in range(n) if j != i]
        by_q = {q: sum(p_win[(i, j)][q] for j in opp) / len(opp) for q in qs}
        wr = sum(by_q.values()) / len(by_q)
        levels = scores[i]
        norm = {q: levels[q] / (len(cfg["score"][q]["criteria"]) - 1) for q in levels}
        sc = sum(norm.values()) / len(norm)
        flags = [f["text"] for q, f in cfg.get("flags", {}).items() if norm[q] < f["below"]]
        rows.append({"id": c["id"], "text": c["text"], "control": c["control"], "flags": flags,
                     "scores": {q: round(v, 2) for q, v in levels.items()},
                     "score": round(sc, 3), "winrate": round(wr, 3),
                     "winrate_by_q": {q: round(v, 3) for q, v in by_q.items()},
                     "combined": round(W_SCORE * sc + W_WIN * wr, 3)})
    order = sorted(range(n), key=lambda k: (-rows[k]["combined"], k))
    for rank, k in enumerate(order, 1):
        rows[k]["rank_in_pool"] = rank
    ranked = [rows[k] for k in order]
    ctrl = next(r for r in rows if r["control"])
    real = [r for r in ranked if not r["control"]]
    for k, r in enumerate(real, 1):
        r["rank"] = k
    worst_real = min(r["combined"] for r in real)
    last = ctrl["combined"] < worst_real          # 平分也不算「排最后」
    pairs = {f"{pool[i]['id']}|{pool[j]['id']}": {q: round(v, 3) for q, v in p_win[(i, j)].items()} for i, j in combos}
    return {"category": category, "rubric": RUBRIC_NAME, "model": jev.MODEL, "context": ctx, "control_last": last,
            "ranking": [{k: r[k] for k in ("rank", "id", "text", "flags", "scores", "score", "winrate", "winrate_by_q", "combined")} for r in real],
            "control": {"id": CTRL_ID, "text": ctrl["text"], "rank_in_pool": ctrl["rank_in_pool"], "pool_size": n,
                        "score": ctrl["score"], "winrate": ctrl["winrate"], "combined": ctrl["combined"], "last": last},
            "pairs": pairs}


def run_classify(ctx, cands, cache, workers):
    """每条评论问四个是 / 否题（一次请求）。对照评论必须被分到 expect 那一类，而且是概率最大的一类。"""
    cfg = RUBRIC["classify"]
    labels = cfg["labels"]
    questions = {k: {"type": v["type"], "instructions": v["instructions"]} for k, v in labels.items()}
    pool = [dict(c, control=False) for c in cands] + [{"id": CTRL_ID, "text": cfg["control"]["text"], "control": True}]
    fns = [(lambda t=c["text"]: cache.ask({"audience": AUDIENCE, "task": cfg["task"], "video": ctx, "comment": t}, questions)) for c in pool]
    res = run_parallel(fns, workers)
    items = []
    for c, r in zip(pool, res):
        probs = {v["label"]: round(r[k], 3) for k, v in labels.items()}
        got = [name for name, p in probs.items() if p >= YES]
        items.append({"id": c["id"], "text": c["text"], "control": c["control"], "probs": probs, "labels": got or ["其他"]})
    ctrl = next(x for x in items if x["control"])
    exp = labels[cfg["control"]["expect"]]["label"]
    ok = ctrl["probs"][exp] >= YES and max(ctrl["probs"], key=ctrl["probs"].get) == exp
    real = [x for x in items if not x["control"]]
    summary = {v["label"]: sum(v["label"] in x["labels"] for x in real) for v in labels.values()}
    summary["其他"] = sum(x["labels"] == ["其他"] for x in real)
    return {"category": "classify", "rubric": RUBRIC_NAME, "model": jev.MODEL, "context": ctx, "control_last": ok,
            "summary": summary, "items": [{k: x[k] for k in ("id", "text", "probs", "labels")} for x in real],
            "control": {"id": CTRL_ID, "text": ctrl["text"], "expect": exp, "probs": ctrl["probs"], "labels": ctrl["labels"], "ok": ok}}


def short(s, n=34):
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def print_pick(r):
    cfg = RUBRIC["categories"][r["category"]]
    n = r["control"]["pool_size"]
    print(f"jev_pick {r['category']}（{cfg['label']}）：{n - 1} 个候选 + 1 个对照项，{n * (n - 1) // 2} 对（每对正反各问一次），题目 {RUBRIC_NAME}")
    print(f"综合 = {W_SCORE:g} × 平均分 + {W_WIN:g} × 胜率；分数是 0–1，各题分数在括号里")
    for x in r["ranking"]:
        sc = " ".join(f"{q}={v / (len(cfg['score'][q]['criteria']) - 1):.2f}" for q, v in x["scores"].items())
        print(f"  {x['rank']:>2}  {x['id']:<8} 综合 {x['combined']:.3f}  分数 {x['score']:.3f}（{sc}）  胜率 {x['winrate']:.3f}  {short(x['text'])}"
              + "".join(f"  ⚠ {f}" for f in x["flags"]))
    c = r["control"]
    print(f"  对照 {c['id']:<8} 综合 {c['combined']:.3f}  分数 {c['score']:.3f}  胜率 {c['winrate']:.3f}  排在池子里第 {c['rank_in_pool']} / {n}  {short(c['text'])}")


def print_classify(r):
    print(f"jev_pick classify（评论分类）：{len(r['items'])} 条评论 + 1 条对照，题目 {RUBRIC_NAME}；概率 ≥ {YES:g} 算属于这一类")
    for x in r["items"]:
        print(f"  {x['id']:<8} " + " ".join(f"{k}={v:.2f}" for k, v in x["probs"].items()) + f"  → {'、'.join(x['labels'])}  {short(x['text'])}")
    print("  合计：" + "，".join(f"{k} {v}" for k, v in r["summary"].items()))
    c = r["control"]
    print(f"  对照评论「{short(c['text'])}」应该是「{c['expect']}」，分成了「{'、'.join(c['labels'])}」  " + " ".join(f"{k}={v:.2f}" for k, v in c["probs"].items()))


def main():
    ap = argparse.ArgumentParser(description="让 Jev 从候选里挑（第 2 步、第 9 步）")
    ap.add_argument("category", choices=CATEGORIES)
    ap.add_argument("candidates", help="候选 JSON（格式见文件头）")
    ap.add_argument("--out", help="结果写到这个 JSON")
    ap.add_argument("--cache", default=str(CACHE), help=f"缓存文件（默认 {CACHE.relative_to(ROOT.parent)}）")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cache = None
    try:
        ctx, cands = load_candidates(a.candidates, a.category)
        require_key()
        cache = Cache(a.cache)
        if a.category == "classify":
            r = run_classify(ctx, cands, cache, a.workers)
        else:
            r = run_pick(a.category, ctx, cands, cache, a.workers)
    except Fail as e:
        print(str(e), file=sys.stderr)
        sys.exit(e.code)
    except Exception as e:     # 连不上、401、超时、限流……都算 Jev 调用失败：不许静默跳过（P8）
        msg = f"{type(e).__name__}: {e}".replace(os.environ.get("TYPESAFE_API_KEY", "\0"), "***")
        print(f"错误：Jev 调用失败，没有结果。{msg}", file=sys.stderr)
        sys.exit(3)
    finally:
        if cache is not None and cache.fresh:
            cache.save()          # 已经花掉的调用不要白花
    r["calls"] = cache.calls()
    if a.category == "classify":
        print_classify(r)
    else:
        print_pick(r)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    c = r["calls"]
    print(f"调用 {c['requests']} 次新请求，{c['cached']} 次用了缓存（输入 {c['input_tokens']} / 输出 {c['output_tokens']} 词元）" + (f"；结果写到 {a.out}" if a.out else ""))
    if not r["control_last"]:
        if a.category == "classify":
            print("⚠ 对照评论没分对：这次的分类不可信，先改题（rubrics/pick_v2.json）或检查评论文本再跑。", file=sys.stderr)
        else:
            c = r["control"]
            if c["rank_in_pool"] == c["pool_size"]:
                print("⚠ 对照项和最差的候选平分：分不出高低，这次的排名不可信。先改候选或改题（rubrics/pick_v2.json）再跑。", file=sys.stderr)
                sys.exit(1)
            print(f"⚠ 对照项排在池子里第 {c['rank_in_pool']} / {c['pool_size']}，没排最后：这次的排名不可信。先改候选（是不是几个都差不多）或改题（rubrics/pick_v2.json）再跑。", file=sys.stderr)
        sys.exit(1)
    print("对照项排在最后：这次的排名可信。" if a.category != "classify" else "对照评论分对了：这次的分类可信。")


if __name__ == "__main__":
    main()
