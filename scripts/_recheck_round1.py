"""一次性：用新的严格标准复查第 1 轮（宽松规则下）收下的新题：去掉后误差下降就删。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
import autoresearch as ar
from jevdev import db
con = db.connect()
qs = json.loads(ar.RUBRIC.read_text(encoding="utf-8"))["questions"]
r1 = json.loads((ar.HISTORY / "round_01.json").read_text(encoding="utf-8"))
adds = [a["id"] for a in r1["actions"] if a["op"] == "add" and a["accepted"]]

def rmse(q):
    d = ar.Data(con, q)
    return ar.cv(d.X([k for qid in q for k in ar.cols_of(q, d)[qid]]), d.y)[0]

log = []
for qid in adds:
    before = rmse(qs)
    cand = {k: v for k, v in qs.items() if k != qid}
    after = rmse(cand)
    keep = after >= before
    print(f"{qid:<20} 有它 {before:.4f}  去掉 {after:.4f}  → {'保留' if keep else '删除'}")
    log.append({"id": qid, "rmse_with": round(before, 4), "rmse_without": round(after, 4), "kept": keep})
    if not keep:
        qs = cand
ar.save_questions(qs)
(ar.HISTORY / "round_01_recheck.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"现在 {len(qs)} 题，开发集 RMSE {rmse(qs):.4f}")
