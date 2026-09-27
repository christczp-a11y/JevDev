"""规则总账：把所有出现过的题（第 0 轮 + 每轮 Claude 提议的，无论最后留没留在模型里）逐条和互动量做检验。

模型里的题要「整体」有增量才留；而写作规则只需要「单条」方向可靠。这份总账服务后者：
开发集上扣掉控制变量后的 Spearman + 95% 区间；传 --test 时再给出留出测试集上的方向复核。

用法：python scripts/rule_catalog.py [--test]   → data/autoresearch/rule_catalog.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import autoresearch as ar  # noqa: E402
from jevdev import db  # noqa: E402


def all_questions():
    qs = json.loads((ar.HISTORY / "questions_round0.json").read_text(encoding="utf-8"))["questions"]
    for f in sorted(ar.HISTORY.glob("round_[0-9][0-9].json")):
        for a in json.loads(f.read_text(encoding="utf-8"))["actions"]:
            if a["op"] in ("add", "revise"):
                try:
                    q = ar.to_question(a)
                except (json.JSONDecodeError, KeyError):
                    continue
                qs[a["id"] if a["op"] == "add" else f"{a['id']}__{f.stem}"] = q
    qs.update(json.loads(ar.RUBRIC.read_text(encoding="utf-8"))["questions"])
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="同时在留出测试集上复核方向（会给测试集打分）")
    args = ap.parse_args()
    con = db.connect()
    qs = all_questions()
    dev = ar.Data(con, qs, "dev")
    ar.score(con, dev.notes, qs)
    dev = ar.Data(con, qs, "dev")
    rows = ar.rule_report(dev, qs)
    if args.test:
        test = ar.Data(con, qs, "test")
        ar.score(con, test.notes, qs)
        test = ar.Data(con, qs, "test")
        t = {r["feature"]: r for r in ar.rule_report(test, qs, boot=500)}
        for r in rows:
            tr = t.get(r["feature"])
            r["test_rho"] = tr["rho"] if tr else None
            r["test_n"] = tr["n"] if tr else 0
            r["same_sign"] = bool(tr and np.sign(tr["rho"]) == np.sign(r["rho"]))
    for r in rows:
        q = qs.get(r["feature"].split("=")[0])
        r["instructions"] = q["instructions"] if q else ""
    (ar.HISTORY / "rule_catalog.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        if r["verdict"] != "不确定":
            extra = f"  测试 {r['test_rho']:+.3f} {'✓' if r['same_sign'] else '✗'}" if args.test and r.get("test_rho") is not None else ""
            print(f"{r['rho']:+.3f} [{r['ci'][0]:+.3f},{r['ci'][1]:+.3f}] n={r['n']:<4}{extra}  {r['feature']}")
    print(f"共 {len(rows)} 个特征，{sum(r['verdict'] != '不确定' for r in rows)} 个在开发集上显著")


if __name__ == "__main__":
    main()
