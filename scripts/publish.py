"""把草稿包里选中的那篇发布到小红书（通过本地 MCP）。

默认「仅自己可见」，用于测试；公开发布要显式传 --public。
必须加 --yes 才会真的发布（防止误发）。

用法：
  python scripts/publish.py data/posts/<草稿包目录> --yes            # 仅自己可见
  python scripts/publish.py data/posts/<草稿包目录> --yes --public   # 公开
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db, xhs  # noqa: E402

SCHEMA = """CREATE TABLE IF NOT EXISTS posts (
    package TEXT PRIMARY KEY, title TEXT, visibility TEXT, published_at TEXT,
    note_id TEXT, pick_mode TEXT, pred_engagement REAL, quality REAL, result TEXT)"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    pkg_dir = Path(args.package).resolve()
    pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
    if pkg["chosen_index"] is None:
        print("这个草稿包没有通过审稿的草稿")
        return
    d = pkg["drafts"][pkg["chosen_index"]]
    images = sorted(str(p) for p in pkg_dir.glob("card_*.png"))
    visibility = "公开可见" if args.public else "仅自己可见"

    print(f"标题：{d['title']}\n图片：{len(images)} 张\n话题：{d['tags']}\n可见范围：{visibility}\n")
    if not args.yes:
        print("预览模式：加 --yes 才会真的发布")
        return

    res = xhs.call("publish_content", {
        "title": d["title"], "content": d["body"], "images": images, "tags": d["tags"],
        "visibility": visibility}, timeout=600)
    print("发布结果：", json.dumps(res, ensure_ascii=False)[:500])

    con = db.connect()
    con.execute(SCHEMA)
    con.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?)",
                (str(pkg_dir), d["title"], visibility, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 None, d.get("pick_mode"), d.get("pred_engagement"), d.get("quality"),
                 json.dumps(res, ensure_ascii=False)))
    con.commit()


if __name__ == "__main__":
    main()
