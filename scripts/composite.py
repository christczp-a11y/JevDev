"""选稿用的复合分（composite scoring）：开发集上显著、而且我们能照着写的规则，标准化后按方向等权平均。

为什么不用 autoresearch 的大回归：39 个特征 × 300 篇在留出测试集上过拟合（RMSE 比基线还差），
而单条规则 23 条里有 21 条在测试集上方向一致。等权复合分没有要拟合的权重，小样本下更稳。

规则的挑选只用开发集的结果（data/autoresearch/rule_report.json 同口径），排除：
  - 违反平台规则、我们不会写的：t_hype（煽动词）、t_absolute（极限词）
  - 和我们红线冲突的：b_vague_attrib（模糊归因）
  - 意义不明、只是数据形态：r_generic_tags

用法：python scripts/composite.py --build     # 用开发集定义复合分 → rubrics/selection_composite_v1.json
     python scripts/composite.py --eval      # 在开发集和测试集上评估（测试集：第二次查看，结论打折扣）
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import autoresearch as ar  # noqa: E402
from jevdev import db  # noqa: E402

DEF = ar.ROOT / "rubrics" / "selection_composite_v1.json"
EXCLUDE = {"t_hype", "t_absolute", "b_vague_attrib", "r_generic_tags"}


def values(data, k):
    src = data.jev if k in {c for d in data.jev for c in d} else data.base
    return np.array([d.get(k, np.nan) for d in src], dtype=float)


def score(data, spec):
    """每篇笔记：可用特征的 (方向 × z 分数，截断到 ±3) 的平均（没正文的笔记只用标题和封面特征）。
    截断：稀有特征（如标题里用「你」）标准差很小，出现一次就是四五个标准差，会让一条规则压过其余所有规则。"""
    Z = []
    for f in spec["features"]:
        x = values(data, f["feature"])
        Z.append(np.clip(f["sign"] * (x - f["mean"]) / f["std"], -3, 3))
    return np.nanmean(np.vstack(Z), axis=0)


def build(con, questions):
    dev = ar.Data(con, questions, "dev")
    rules = [r for r in ar.rule_report(dev, questions) if r["verdict"] != "不确定" and r["feature"] not in EXCLUDE]
    feats = []
    for r in rules:
        x = values(dev, r["feature"])
        feats.append({"feature": r["feature"], "sign": 1 if r["rho"] > 0 else -1, "dev_rho": r["rho"],
                      "mean": float(np.nanmean(x)), "std": float(np.nanstd(x)) or 1.0})
    spec = {"about": __doc__.split("\n")[0], "built_from": "开发集（按 note_id 哈希划分的 75%）", "features": feats}
    DEF.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"复合分用 {len(feats)} 条规则：", ", ".join(f"{'+' if f['sign'] > 0 else '−'}{f['feature']}" for f in feats))


def evaluate(con, questions):
    spec = json.loads(DEF.read_text(encoding="utf-8"))
    dev, test = ar.Data(con, questions, "dev"), ar.Data(con, questions, "test")
    ctrl = [k for k in dev.base_keys if k.startswith("c_")]
    Xc_dev, fill = ar.matrix(dev.base, ctrl)
    Xc_te, _ = ar.matrix(test.base, ctrl, fill)
    ctrl_model = ar.model().fit(Xc_dev, dev.y)
    Xb_dev, fb = ar.matrix(dev.base, dev.base_keys)
    Xb_te, _ = ar.matrix(test.base, dev.base_keys, fb)
    for name, d, Xc, Xb in (("开发集", dev, Xc_dev, Xb_dev), ("测试集", test, Xc_te, Xb_te)):
        s = score(d, spec)
        resid = d.y - ctrl_model.predict(Xc)
        print(f"{name} {len(d.y)} 篇 | 复合分和互动（扣掉控制变量）Spearman {spearmanr(s, resid).statistic:+.3f}")
    # 基线 + 复合分（只多 1 列）：开发集训练、测试集评估
    s_dev, s_te = score(dev, spec)[:, None], score(test, spec)[:, None]
    for name, Xtr, Xte in (("基线", Xb_dev, Xb_te), ("基线+复合分", np.hstack([Xb_dev, s_dev]), np.hstack([Xb_te, s_te]))):
        p = ar.model().fit(Xtr, dev.y).predict(Xte)
        print(f"测试集 | {name:<10} RMSE {np.sqrt(np.mean((p - test.y) ** 2)):.3f}  ρ {spearmanr(p, test.y).statistic:+.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--eval", action="store_true")
    args = ap.parse_args()
    con = db.connect()
    questions = json.loads(ar.RUBRIC.read_text(encoding="utf-8"))["questions"]
    if args.build:
        build(con, questions)
    if args.eval:
        evaluate(con, questions)


if __name__ == "__main__":
    main()
