"""同龄追踪：在笔记发布后第 1、3、7 天各记录一次互动快照。

追踪对象：
  - 我们自己发的笔记（notes.is_ours = 1）
  - 「最新」排序采集到、且已知发布时间的笔记（阶段 1 的同龄样本）
每个检查点只在「刚到期的 2 天窗口」内补抓；错过窗口就放弃（避免年龄不一致的数据混进来）。

用法：python scripts/track.py [--max 40]
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from collect_xhs import save_detail  # noqa: E402
from jevdev import db, xhs  # noqa: E402

CHECKPOINTS_DAYS = [1, 3, 7]
WINDOW_DAYS = 2
DAY_MS = 86400000


def due_notes(con, now_ms):
    rows = con.execute("""
        SELECT n.id, n.xsec_token, n.publish_ts,
               (SELECT MAX(CAST(strftime('%s', s.fetched_at) AS INTEGER) * 1000) FROM snapshots s
                 WHERE s.note_id = n.id) AS last_snap_ms
        FROM notes n
        WHERE n.publish_ts IS NOT NULL AND n.xsec_token IS NOT NULL
          AND (n.is_ours = 1 OR EXISTS (SELECT 1 FROM search_hits h WHERE h.note_id = n.id AND h.sort_by = '最新'))
    """).fetchall()
    due = []
    for r in rows:
        age = (now_ms - r["publish_ts"]) / DAY_MS
        last_age = ((r["last_snap_ms"] or 0) - r["publish_ts"]) / DAY_MS
        for cp in CHECKPOINTS_DAYS:
            if cp <= age < cp + WINDOW_DAYS and last_age < cp:
                due.append((r["id"], r["xsec_token"], cp))
                break
    return due


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=40)
    args = ap.parse_args()
    con = db.connect()
    due = due_notes(con, time.time() * 1000)
    print(f"到期需要记录的笔记：{len(due)} 篇（本次最多 {args.max}）")
    for i, (nid, tok, cp) in enumerate(due[: args.max], 1):
        try:
            save_detail(con, nid, xhs.call("get_feed_detail", {"feed_id": nid, "xsec_token": tok}))
            print(f"[{i}] {nid} 第 {cp} 天 ok")
        except Exception as e:
            print(f"[{i}] {nid} 失败: {e}")
        xhs.polite_sleep()


if __name__ == "__main__":
    main()
