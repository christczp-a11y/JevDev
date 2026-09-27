"""封面「看图」：下载赛道笔记的封面，让 Claude 把每张封面客观描述成文字，存进 cover_desc 表。

分工：Claude 只负责「看见了什么」（感知），好不好由 Jev 判断（rubrics/xhs_note_features_v1.json）。

用法：
  python scripts/covers.py --download        # 下载还没下载的封面（data/raw/covers/，不入库）
  python scripts/covers.py --describe        # 描述还没描述的封面（每批 8 张）
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import httpx2 as httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

COVER_DIR = db.DB_PATH.parent / "raw" / "covers"
MODEL = "claude-sonnet-5"  # 只做客观描述，不需要最强的模型

SYSTEM = """你是图片描述员。你会收到几张小红书美食笔记的封面图（文件路径）。
逐张用 Read 工具打开，只客观描述看到的内容，不评价好坏、不猜测效果。
图上的文字要逐字抄写（看不清的字用 □ 代替）。"""

SCHEMA = {
    "type": "object",
    "properties": {"covers": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "note_id": {"type": "string"},
            "layout": {"type": "string", "enum": ["single_photo", "photo_with_text", "collage", "text_card", "other"],
                       "description": "single_photo=一张照片无文字；photo_with_text=照片上叠了文字；collage=多张照片拼图；text_card=以文字为主的设计卡片"},
            "collage_panels": {"type": "integer", "description": "拼图的格数，不是拼图填 1"},
            "headline_text": {"type": "string", "description": "图上最大、最显眼的那行文字，逐字抄写；没有就空字符串"},
            "other_text": {"type": "string", "description": "图上其他文字，逐字抄写，用 / 分隔；没有就空字符串"},
            "subjects": {"type": "array", "items": {"type": "string",
                         "enum": ["food_closeup", "food_table_spread", "drink_dessert", "person", "interior", "storefront", "menu_or_receipt", "scenery", "other"]}},
            "dish_count": {"type": "integer", "description": "能看清的不同菜品数量，大约即可"},
            "face_visible": {"type": "boolean"},
            "photo_style": {"type": "string", "enum": ["phone_snapshot", "polished_photo", "graphic_design", "screenshot", "no_photo"],
                            "description": "phone_snapshot=随手拍感；polished_photo=构图打光讲究、像精修或商业图"},
            "brightness": {"type": "string", "enum": ["bright", "medium", "dark"]},
            "headline_prominence": {"type": "string", "enum": ["none", "small", "medium", "large"],
                                    "description": "最大那行字在画面里有多醒目：small=缩到手机信息流小图时看不清；large=占画面宽度一半以上、小图也能一眼读出"},
            "text_emphasis": {"type": "boolean", "description": "有没有某个词或数字被单独放大、换色或加底色强调"},
            "emoji_on_image": {"type": "boolean", "description": "图上有没有 emoji 或表情符号"},
            "stickers_or_decorations": {"type": "boolean", "description": "有没有贴纸、手绘涂鸦、装饰边框、光斑等装饰元素"},
            "watermark_or_handle": {"type": "boolean", "description": "有没有水印、账号名、@用户名"},
            "description": {"type": "string", "description": "2–3 句中性描述：画面里有什么、怎么排布、文字在哪"}
        },
        "required": ["note_id", "layout", "collage_panels", "headline_text", "other_text", "subjects",
                     "dish_count", "face_visible", "photo_style", "brightness", "headline_prominence",
                     "text_emphasis", "emoji_on_image", "stickers_or_decorations", "watermark_or_handle", "description"]
    }}},
    "required": ["covers"]
}


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS cover_desc (
        note_id TEXT PRIMARY KEY, model TEXT, desc_json TEXT, described_at TEXT)""")


def download(con):
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    rows = con.execute("SELECT id, cover_url FROM notes WHERE cover_url IS NOT NULL AND is_ours = 0").fetchall()
    todo = [(r["id"], r["cover_url"]) for r in rows if not (COVER_DIR / f"{r['id']}.jpg").exists()]
    print(f"待下载 {len(todo)} 张")

    def one(item):
        nid, url = item
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.thumbnail((600, 800))  # 缩小省 token，文字仍看得清
            img.save(COVER_DIR / f"{nid}.jpg", quality=85)
            return None
        except Exception as e:  # 链接过期等：跳过，下次重新搜索时会拿到新链接
            return f"{nid}: {e}"

    with ThreadPoolExecutor(4) as ex:
        errs = [e for e in ex.map(one, todo) if e]
    print(f"下载完成，失败 {len(errs)} 张", *errs[:5], sep="\n  ")


def describe_batch(paths, add_dir=COVER_DIR):
    listing = "\n".join(f"- note_id={p.stem}  路径={p}" for p in paths)
    proc = subprocess.run(
        [CLAUDE_EXE, "-p", "--model", MODEL, "--output-format", "json", "--tools", "Read",
         "--allowedTools", "Read", "--add-dir", str(add_dir),
         "--system-prompt", SYSTEM, "--json-schema", json.dumps(SCHEMA, ensure_ascii=False)],
        input=f"逐张描述下面 {len(paths)} 张封面：\n{listing}",
        capture_output=True, text=True, encoding="utf-8", timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[:500] or proc.stdout[:500])
    out = json.loads(proc.stdout)
    if not out.get("structured_output"):
        raise RuntimeError(str(out.get("result"))[:500])
    return out["structured_output"]["covers"]


def describe(con, batch=8, workers=3, limit=10000):
    # 描述字段有增减时，旧描述（缺字段）重新描述
    need = set(SCHEMA["properties"]["covers"]["items"]["required"])
    done = {r[0] for r in con.execute("SELECT note_id, desc_json FROM cover_desc")
            if need <= set(json.loads(r[1]))}
    paths = [p for p in sorted(COVER_DIR.glob("*.jpg")) if p.stem not in done][:limit]
    batches = [paths[i:i + batch] for i in range(0, len(paths), batch)]
    print(f"待描述 {len(paths)} 张，{len(batches)} 批")

    def run(b):
        try:
            return describe_batch(b)
        except Exception as e:
            print(f"  一批失败：{e}")
            return []

    n = 0
    with ThreadPoolExecutor(workers) as ex:
        for covers in ex.map(run, batches):
            for c in covers:
                if c["note_id"] in {p.stem for p in paths}:
                    con.execute("INSERT OR REPLACE INTO cover_desc VALUES (?,?,?,?)",
                                (c["note_id"], MODEL, json.dumps(c, ensure_ascii=False), time.strftime("%Y-%m-%dT%H:%M:%S")))
                    n += 1
            con.commit()
            print(f"  已描述 {n}/{len(paths)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--limit", type=int, default=10000)
    args = ap.parse_args()
    con = db.connect()
    ensure_table(con)
    if args.download:
        download(con)
    if args.describe:
        describe(con, limit=args.limit)


if __name__ == "__main__":
    main()
