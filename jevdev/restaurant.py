"""餐厅画像：Jev 逐条判断评价 → 代码加权汇总（PLAN.md「评分规则」）。

- 评价权重 = P(relevant) × (1 − P(ad_like)) × 时间衰减（半年减半）
- 维度分：只用提到该维度的部分，档位 差=1 / 一般=2 / 好=3 / 很好=4
- 贝叶斯收缩：(n·均值 + k·先验) / (n + k)，评价少的店被拉向先验，避免少量好评压过大量好评
- 分歧度：维度分的加权标准差，高分歧本身就是选题（争议店）
"""
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor

from jevdev import jev

DIMENSIONS = ["taste", "service", "value", "environment"]
LEVEL = {"bad": 1, "ok": 2, "good": 3, "great": 4}
PRIOR = 2.8          # 暂定的全市先验；积累足够多的店之后改成实际均值
PRIOR_K = 5.0        # 先验相当于几条评价
HALF_LIFE_DAYS = 180

SCHEMA = """CREATE TABLE IF NOT EXISTS review_answers (
    review_id TEXT, rubric TEXT, answers TEXT, PRIMARY KEY (review_id, rubric))"""


def age_days(when_text):
    """'2 hours ago' / 'a day ago' / '3 weeks ago' / 'Edited a year ago' -> 天数；无法解析返回 None。"""
    if not when_text:
        return None
    m = re.search(r"(a|an|\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", when_text)
    if not m:
        return None
    n = 1 if m.group(1) in ("a", "an") else int(m.group(1))
    unit = {"minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}[m.group(2)]
    return n * unit


def judge_reviews(con, restaurant, reviews, rubric_name="review_v1"):
    """给还没判断过的评价调用 Jev（并发），结果缓存在 review_answers。返回 {review_id: answers}。"""
    con.execute(SCHEMA)
    rubric = jev.load_rubric(rubric_name)
    cached = {r[0]: json.loads(r[1]) for r in con.execute(
        "SELECT review_id, answers FROM review_answers WHERE rubric=?", (rubric_name,))}
    todo = [r for r in reviews if r["review_id"] not in cached and r["text"]]

    def one(r):
        answers, _ = jev.ask({"restaurant": restaurant, "review": r["text"][:2000]}, rubric["questions"])
        return r["review_id"], answers

    with ThreadPoolExecutor(max_workers=8) as pool:
        for rid, answers in pool.map(one, todo):
            con.execute("INSERT OR REPLACE INTO review_answers VALUES (?,?,?)",
                        (rid, rubric_name, json.dumps(answers, ensure_ascii=False)))
            cached[rid] = answers
    con.commit()
    return {r["review_id"]: cached[r["review_id"]] for r in reviews if r["review_id"] in cached}


def profile(reviews, answers):
    """reviews: [{review_id, stars, when_text, text}]；answers: judge_reviews 的结果。"""
    dims = {d: [] for d in DIMENSIONS}   # (提及权重, 期望档位)
    wait_long, cash = [], []
    total_w = 0.0
    for r in reviews:
        a = answers.get(r["review_id"])
        if not a:
            continue
        age = age_days(r["when_text"])
        decay = 0.5 ** (age / HALF_LIFE_DAYS) if age is not None else 0.5
        w = a["relevant"]["noul"] * (1 - a["ad_like"]["noul"]) * decay
        total_w += w
        for d in DIMENSIONS:
            p = a[d]["probabilities"]
            mention = 1 - p.get("na", 0)
            if mention < 0.05:
                continue
            ev = sum(LEVEL[k] * v for k, v in p.items() if k in LEVEL) / mention
            dims[d].append((w * mention, ev))
        pw = a["wait"]["probabilities"]
        if 1 - pw.get("na", 0) > 0.5:
            wait_long.append(pw.get("long", 0) / (1 - pw.get("na", 0)))
        cash.append(a["cash_only"]["noul"])

    out = {"judged_reviews": len(answers), "effective_weight": round(total_w, 2), "dimensions": {}}
    for d, pts in dims.items():
        n = sum(w for w, _ in pts)
        if n == 0:
            out["dimensions"][d] = None
            continue
        mean = sum(w * v for w, v in pts) / n
        sd = math.sqrt(sum(w * (v - mean) ** 2 for w, v in pts) / n)
        out["dimensions"][d] = {
            "score": round((n * mean + PRIOR_K * PRIOR) / (n + PRIOR_K), 2),  # 收缩后的分数（1–4）
            "raw_mean": round(mean, 2), "mentions": round(n, 1), "disagreement": round(sd, 2)}
    out["wait_long_share"] = round(sum(wait_long) / len(wait_long), 2) if wait_long else None
    out["cash_only_signal"] = round(max(cash), 2) if cash else None
    return out
