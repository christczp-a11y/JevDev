"""阶段 1 离线验证：Jev 的判断能不能预测笔记互动？

对比两组特征，看交叉验证下的预测效果：
  A. 基线：只用代码算的特征（标题字数、数字、emoji、封面比例……）
  B. 基线 + Jev 对标题 / 正文的判断
B 明显好于 A，才说明 Jev 在这个赛道有用（PLAN.md 阶段 1 的过关标准）。

用法：
  python scripts/phase1_eval.py --rubric xhs_title_v1_zh --score   # 先给还没打分的笔记打分（会花 Jev 费用）
  python scripts/phase1_eval.py --rubric xhs_title_v1_zh           # 只评估
"""
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db, jev  # noqa: E402

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")
PLACES = ["温哥华", "列治文", "本拿比", "素里", "高贵林", "北温", "西温", "Vancouver", "Richmond", "Burnaby"]


def code_features(n):
    t = n["title"] or ""
    d = n["desc"] or ""
    return {
        "title_len": len(t),
        "title_has_digit": int(bool(re.search(r"\d", t))),
        "title_emoji": len(EMOJI.findall(t)),
        "title_exclaim": int("!" in t or "！" in t),
        "title_question": int("?" in t or "？" in t),
        "title_place": int(any(p in t for p in PLACES)),
        "cover_ratio": (n["cover_h"] / n["cover_w"]) if n["cover_w"] else 1.0,
        "is_video": int(n["note_type"] == "video"),
        "has_desc": int(bool(d)),
        "desc_len": len(d),
        # 控制变量：采样来源（「最新」排序的笔记更新、互动还没攒起来）和发布天数
        "from_latest": n["from_latest"] or 0,
        "from_top": n["from_top"] or 0,
        "has_age": int(n["publish_ts"] is not None),
        "log_age_days": math.log1p(max(0.0, (time.time() * 1000 - n["publish_ts"]) / 86400000))
                        if n["publish_ts"] else 0.0,
    }


def build_state(n, rubric):
    """只放 rubric 声明需要的字段（fields），外加 rubric 的背景信息（context）。"""
    available = {"title": n["title"] or "", "body": (n["desc"] or "")[:1500]}
    state = dict(rubric.get("context", {}))
    state.update({f: available[f] for f in rubric["fields"]})
    return state


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS jev_answers (
        note_id TEXT, rubric TEXT, answers TEXT, input_tokens INTEGER,
        PRIMARY KEY (note_id, rubric))""")


def score_missing(con, rubric_name, limit):
    rubric = jev.load_rubric(rubric_name)
    need_body = "body" in rubric["fields"]
    rows = con.execute(f"""SELECT * FROM notes WHERE title IS NOT NULL AND title != ''
                          {"AND desc IS NOT NULL AND desc != ''" if need_body else ""}
                          AND id NOT IN (SELECT note_id FROM jev_answers WHERE rubric=?) LIMIT ?""",
                       (rubric_name, limit)).fetchall()
    tokens = 0
    for i, n in enumerate(rows, 1):
        answers, usage = jev.ask(build_state(n, rubric), rubric["questions"])
        con.execute("INSERT OR REPLACE INTO jev_answers VALUES (?,?,?,?)",
                    (n["id"], rubric_name, json.dumps(answers, ensure_ascii=False), usage["input_tokens"]))
        con.commit()
        tokens += usage["input_tokens"]
        if i % 20 == 0:
            print(f"  已打分 {i}/{len(rows)}")
    print(f"打分完成 {len(rows)} 篇，输入 token {tokens}（约 ${tokens * 0.042 / 1e6:.4f}）")


def load_dataset(con, rubric_name, only_latest=False):
    rows = con.execute("""
        SELECT n.*, a.answers,
               (SELECT MAX(COALESCE(liked,0)+COALESCE(collected,0)+COALESCE(comments,0))
                  FROM snapshots s WHERE s.note_id = n.id) AS engagement,
               (SELECT MAX(sort_by = '最新') FROM search_hits h WHERE h.note_id = n.id) AS from_latest,
               (SELECT MAX(sort_by = '综合') FROM search_hits h WHERE h.note_id = n.id) AS from_top
        FROM notes n JOIN jev_answers a ON a.note_id = n.id AND a.rubric = ?
        WHERE n.is_ours = 0""", (rubric_name,)).fetchall()
    X_code, X_jev, y = [], [], []
    for n in rows:
        if only_latest and not (n["from_latest"] and not n["from_top"]):
            continue
        X_code.append(code_features(n))
        X_jev.append(jev.flatten(json.loads(n["answers"])))
        y.append(math.log1p(n["engagement"] or 0))
    return X_code, X_jev, np.array(y)


def to_matrix(dicts, keys):
    return np.array([[d.get(k, 0.0) for k in keys] for d in dicts], dtype=float)


def evaluate(X, y, label, repeats=20):
    """重复 20 次随机 5 折交叉验证，报告 Spearman 的均值 ± 标准差（看结果稳不稳）。"""
    model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20)))
    rhos = []
    for seed in range(repeats):
        pred = cross_val_predict(model, X, y, cv=KFold(n_splits=5, shuffle=True, random_state=seed))
        rhos.append(spearmanr(pred, y).statistic)
    print(f"{label:<28} Spearman={np.mean(rhos):+.3f} ± {np.std(rhos):.3f}")
    return model.fit(X, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rubric", default="xhs_title_v1_zh")
    ap.add_argument("--score", action="store_true", help="先给未打分的笔记调用 Jev")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--only-latest", action="store_true",
                    help="只用仅出现在「最新」排序里的笔记：发布时间相近、没经过热度筛选，最干净的检验")
    args = ap.parse_args()

    con = db.connect()
    ensure_table(con)
    if args.score:
        score_missing(con, args.rubric, args.limit)

    X_code, X_jev, y = load_dataset(con, args.rubric, args.only_latest)
    print(f"样本 {len(y)} 篇；互动量 log1p 均值 {y.mean():.2f}，标准差 {y.std():.2f}")
    if len(y) < 40:
        print("样本太少（<40），先继续采集")
        return

    code_keys = sorted({k for d in X_code for k in d})
    jev_keys = sorted({k for d in X_jev for k in d if not k.endswith("__conf")})
    Xa = to_matrix(X_code, code_keys)
    Xb = np.hstack([Xa, to_matrix(X_jev, jev_keys)])
    rng = np.random.default_rng(0)
    evaluate(rng.permutation(Xb), y, "对照：打乱特征（应≈0）")
    evaluate(Xa, y, "A 基线（代码特征）")
    evaluate(to_matrix(X_jev, jev_keys), y, "Jev 特征单独")
    model = evaluate(Xb, y, "B 基线 + Jev")

    coefs = model[-1].coef_
    names = code_keys + jev_keys
    top = sorted(zip(names, coefs), key=lambda t: -abs(t[1]))[:15]
    print("\n影响最大的特征（标准化系数；正=互动更高）：")
    for k, c in top:
        print(f"  {c:+.3f}  {k}")


if __name__ == "__main__":
    main()
