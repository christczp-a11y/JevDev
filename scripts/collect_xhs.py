"""采集温哥华美食赛道的小红书笔记，建立训练 / 验证数据集。

同时抓「综合」和「最新」两种排序：只看综合排序会只剩爆款（幸存者偏差），
「最新」能带进来低互动的普通笔记，作为对照样本。

用法：
  python scripts/collect_xhs.py --max-searches 16 --details 60
节奏：每次操作之间随机停顿 8–20 秒；只读，不做任何互动。
"""
import argparse
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db, xhs  # noqa: E402

KEYWORDS = [
    "温哥华美食", "温哥华探店", "温哥华餐厅", "温哥华宝藏餐厅", "温哥华平价美食",
    "温哥华早茶", "温哥华火锅", "温哥华日料", "温哥华韩餐", "温哥华中餐",
    "温哥华烧烤", "温哥华甜品", "温哥华咖啡", "温哥华brunch", "温哥华约会餐厅",
    "温哥华避雷", "列治文美食", "列治文探店", "列治文早茶", "本拿比美食",
]
SORTS = ["综合", "最新"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_search(con, keyword, sort_by, feeds):
    ts = now()
    for rank, f in enumerate(feeds):
        nc = f.get("noteCard") or {}
        ii = nc.get("interactInfo") or {}
        cover = nc.get("cover") or {}
        user = nc.get("user") or {}
        con.execute(
            """INSERT INTO notes (id, xsec_token, title, note_type, author_id, author_name,
                                  cover_w, cover_h, cover_url, first_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET xsec_token=excluded.xsec_token""",
            (f["id"], f.get("xsecToken"), nc.get("displayTitle"), nc.get("type"),
             user.get("userId"), user.get("nickname"), cover.get("width"), cover.get("height"),
             cover.get("urlDefault"), ts))
        con.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?)",
                    (f["id"], ts, xhs.parse_count(ii.get("likedCount")),
                     xhs.parse_count(ii.get("collectedCount")), xhs.parse_count(ii.get("commentCount")),
                     xhs.parse_count(ii.get("sharedCount")), "search"))
        con.execute("INSERT INTO search_hits VALUES (?,?,?,?,?)", (keyword, sort_by, f["id"], rank, ts))
    con.commit()


def save_detail(con, note_id, d):
    n = (d.get("data") or {}).get("note") or {}
    ii = n.get("interactInfo") or {}
    ts = now()
    con.execute("""UPDATE notes SET desc=?, publish_ts=?, image_count=?, detail_at=?,
                   title=COALESCE(NULLIF(?, ''), title) WHERE id=?""",
                (n.get("desc"), n.get("time"), len(n.get("imageList") or []), ts, n.get("title"), note_id))
    con.execute("INSERT INTO snapshots VALUES (?,?,?,?,?,?,?)",
                (note_id, ts, xhs.parse_count(ii.get("likedCount")), xhs.parse_count(ii.get("collectedCount")),
                 xhs.parse_count(ii.get("commentCount")), xhs.parse_count(ii.get("sharedCount")), "detail"))
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-searches", type=int, default=16)
    ap.add_argument("--details", type=int, default=60)
    args = ap.parse_args()

    con = db.connect()
    done = {(r["keyword"], r["sort_by"]) for r in con.execute("SELECT DISTINCT keyword, sort_by FROM search_hits")}
    todo = [(k, s) for k in KEYWORDS for s in SORTS if (k, s) not in done][: args.max_searches]

    for i, (kw, sort_by) in enumerate(todo, 1):
        filters = {"sort_by": sort_by}
        if sort_by == "综合":
            filters["publish_time"] = "半年内"
        try:
            feeds = xhs.call("search_feeds", {"keyword": kw, "filters": filters}).get("feeds") or []
        except Exception as e:  # 单次失败不影响整批
            print(f"[search {i}/{len(todo)}] {kw}/{sort_by} 失败: {e}")
            xhs.polite_sleep()
            continue
        feeds = [f for f in feeds if f.get("modelType") == "note"]
        save_search(con, kw, sort_by, feeds)
        print(f"[search {i}/{len(todo)}] {kw}/{sort_by}: {len(feeds)} 条")
        xhs.polite_sleep()

    # 优先补「最新」排序的笔记：它们是同龄追踪的样本，需要详情里的发布时间；其余随机抽样
    rows = con.execute("""SELECT id, EXISTS(SELECT 1 FROM search_hits h WHERE h.note_id=notes.id AND h.sort_by='最新') AS latest
                          FROM notes WHERE detail_at IS NULL AND xsec_token IS NOT NULL AND note_type='normal'""").fetchall()
    random.shuffle(rows)
    pending = [r["id"] for r in sorted(rows, key=lambda r: -r["latest"])]
    for i, nid in enumerate(pending[: args.details], 1):
        tok = con.execute("SELECT xsec_token FROM notes WHERE id=?", (nid,)).fetchone()[0]
        try:
            save_detail(con, nid, xhs.call("get_feed_detail", {"feed_id": nid, "xsec_token": tok}))
            print(f"[detail {i}] {nid} ok")
        except Exception as e:
            print(f"[detail {i}] {nid} 失败: {e}")
        xhs.polite_sleep()

    total = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    detailed = con.execute("SELECT COUNT(*) FROM notes WHERE detail_at IS NOT NULL").fetchone()[0]
    print(f"完成：共 {total} 篇笔记，其中 {detailed} 篇有详情")


if __name__ == "__main__":
    main()
