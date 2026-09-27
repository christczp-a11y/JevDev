"""首页图：图库实物照片 → Jev 选图 → 抠图 → 放到爆款背景上（templates/cover_cutout.html）。

只用允许商用、允许修改的图：
  - Pexels（首选；许可允许商用、修改、不用署名）：需要环境变量 PEXELS_API_KEY
  - Openverse 上的 CC0 / 公共领域图（没有 Pexels key 时的兜底）
图上标「示意图」，正文说明「非本店实物」：照片里的菜是这一类菜，不是这家店的。
分工：代码搜图、下载、抠图；Claude 看图写描述、翻译搜索词、检查成品；Jev 判断「是不是这道菜、有没有食欲、好不好抠」并选图。
"""
import json
import os
import subprocess
from io import BytesIO
from pathlib import Path

import httpx2 as httpx
from PIL import Image

from jevdev import jev
from jevdev.writer import CLAUDE_EXE

LABEL = "示意图"
BODY_NOTE = "🖼 封面图片为图库示意图，非本店实物"

PICK_QUESTIONS = {
    "match": {"type": "noul",
              "instructions": "`photo` 描述的照片里，主体食物就是 `dish`（同一道菜或同一类做法，例如都是港式叉烧），而不是别的菜"},
    "appetite": {"type": "score",
                 "instructions": "根据 `photo` 的描述，这张照片里的食物看起来有多诱人？",
                 "criteria": ["看不清食物，或者食物看起来不新鲜、不好吃",
                              "能看出是什么，但平淡，没有食欲",
                              "普通的好看，色泽正常",
                              "色泽油亮、质感清楚，让人想吃",
                              "非常诱人：光泽、质感、分量都很突出，一眼就饿"]},
    "cutout": {"type": "noul",
               "instructions": "根据 `photo` 的描述，主体食物是一整盘或一整块、轮廓完整没有被画面边缘裁掉，而且和背景容易分开（适合抠图）"},
    "blocker": {"type": "noul",
                "instructions": "根据 `photo` 的描述，画面里有人脸、清晰的品牌 logo 或招牌文字"},
}

DESC_SCHEMA = {"type": "object", "properties": {"photos": {"type": "array", "items": {
    "type": "object",
    "properties": {"id": {"type": "string"},
                   "description": {"type": "string",
                                   "description": "客观描述：主体是什么食物、几盘、怎么摆、轮廓是否完整、背景是什么、有没有人或文字"}},
    "required": ["id", "description"]}}}, "required": ["photos"]}


def _claude(prompt, schema, tools="", add_dir=None, model="claude-sonnet-5"):
    cmd = [str(CLAUDE_EXE), "-p", "--model", model, "--output-format", "json", "--tools", tools,
           "--json-schema", json.dumps(schema, ensure_ascii=False)]
    if tools:
        cmd += ["--allowedTools", tools]
    if add_dir:
        cmd += ["--add-dir", str(add_dir)]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600)
    out = json.loads(proc.stdout).get("structured_output")
    if not out:
        raise RuntimeError(f"claude -p 没有返回结构化结果：{proc.stdout[-300:] or proc.stderr[-300:]}")
    return out


def search_queries(dish):
    """中文菜名 → 图库用的英文搜索词（Claude 翻译）。"""
    out = _claude(f"把这道菜翻译成图库网站的英文搜索词，给 2 个，从最精确到稍宽泛：{dish}",
                  {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
                   "required": ["queries"]})
    return out["queries"][:2]


def search(query, n=12):
    """返回候选 [{id, thumb, full, source, author, page}]。"""
    key = os.environ.get("PEXELS_API_KEY")
    if key:
        r = httpx.get("https://api.pexels.com/v1/search", params={"query": query, "per_page": n},
                      headers={"Authorization": key}, timeout=30)
        r.raise_for_status()
        return [{"id": f"pexels_{p['id']}", "thumb": p["src"]["medium"], "full": p["src"]["large2x"],
                 "source": "Pexels（Pexels License）", "author": p["photographer"], "page": p["url"]}
                for p in r.json()["photos"]]
    r = httpx.get("https://api.openverse.org/v1/images/", params={"q": query, "license": "cc0,pdm", "page_size": n},
                  headers={"User-Agent": "JevDev/0.1"}, timeout=30)
    r.raise_for_status()
    return [{"id": f"ov_{p['id'][:8]}", "thumb": p.get("thumbnail") or p["url"], "full": p["url"],
             "source": f"Openverse（{p['license'].upper()}）", "author": p.get("creator") or "", "page": p["foreign_landing_url"]}
            for p in r.json()["results"]]


def _download(url, dst, max_side=None):
    r = httpx.get(url, timeout=60, follow_redirects=True, headers={"User-Agent": "JevDev/0.1"})
    r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGB")
    if max_side:
        img.thumbnail((max_side, max_side))
    img.save(dst, quality=90)
    return dst


def pick(dish, cands, work):
    """Claude 看缩略图写描述 → Jev 按 PICK_QUESTIONS 判断 → 按分数排序（有人脸 / logo 的排除）。"""
    thumbs = []
    for c in cands:
        try:
            thumbs.append((c, _download(c["thumb"], work / f"{c['id']}.jpg", 600)))
        except Exception:
            continue
    if len(thumbs) < len(cands):
        print(f"  （{len(cands) - len(thumbs)} 张候选图下载失败，只评估了 {len(thumbs)} 张）")
    if not thumbs:
        return []
    listing ="\n".join(f"- id={c['id']} 路径={p}" for c, p in thumbs)
    desc = _claude(f"逐张用 Read 打开这些图库照片，客观描述每一张：\n{listing}", DESC_SCHEMA, "Read", work)["photos"]
    desc = {d["id"]: d["description"] for d in desc}
    ranked = []
    for c, _ in thumbs:
        if c["id"] not in desc:
            continue
        a, _ = jev.ask({"dish": dish, "photo": desc[c["id"]]}, PICK_QUESTIONS)
        s = {k: (v.get("noul") if v["type"] == "noul" else v["score"] / 4) for k, v in a.items()}
        c = dict(c, description=desc[c["id"]], jev=s,
                 score=round(s["match"] * (0.6 * s["appetite"] + 0.4 * s["cutout"]) * (1 - s["blocker"]), 3))
        ranked.append(c)
    return sorted(ranked, key=lambda c: -c["score"])


def cutout(src, dst):
    """抠图（rembg），裁到主体边界，返回 PNG 路径。"""
    from rembg import new_session, remove
    img = Image.open(src)
    img.thumbnail((1600, 1600))
    out = remove(img, session=new_session("isnet-general-use"))
    out = out.crop(out.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox())
    out.save(dst)
    return str(dst)


CHECK_SCHEMA = {"type": "object", "properties": {
    "edges_clean": {"type": "boolean", "description": "抠图边缘干净：没有残留的原背景色块、没有缺角、没有明显锯齿"},
    "recognizable": {"type": "boolean", "description": "一眼能认出这是什么菜"},
    "problem": {"type": "string"}}, "required": ["edges_clean", "recognizable", "problem"]}


def check_cover(png, dish):
    """成品自检：Claude 看渲染后的封面，抠图边缘和菜品辨识度都要过关。"""
    out = _claude(f"用 Read 打开这张小红书封面：{png}\n封面中间是一张抠出来的食物照片（应该是：{dish}）。检查抠图质量。",
                  CHECK_SCHEMA, "Read", Path(png).parent)
    return out["edges_clean"] and out["recognizable"], out["problem"]


def make_cover(draft, work, render, tries=3):
    """整条流程：菜名 → 搜图 → Jev 选图 → 抠图 → 渲染 → 自检。返回 (抠图 PNG, 来源信息)；没有合格的图抛 RuntimeError。
    render(cutout_path) 由调用方提供：用这张抠图渲染封面并返回 PNG 路径（用于自检）。"""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    dish = main_dish(draft)
    cands, seen = [], set()
    for q in search_queries(dish):
        for c in search(q):
            if c["id"] not in seen:
                seen.add(c["id"])
                cands.append(c)
    if not cands:
        raise RuntimeError(f"图库里没搜到「{dish}」")
    ranked = [c for c in pick(dish, cands, work) if c["jev"]["match"] >= 0.5 and c["jev"]["blocker"] < 0.5]
    tried = []
    for c in ranked[:tries]:
        full = _download(c["full"], work / f"{c['id']}_full.jpg")
        cut = cutout(full, work / f"{c['id']}_cut.png")
        ok, problem = check_cover(render(cut), dish)
        tried.append({"id": c["id"], "score": c["score"], "ok": ok, "problem": problem})
        if ok:
            meta = {k: c[k] for k in ("id", "source", "author", "page", "description", "jev", "score")}
            return cut, dict(meta, dish=dish, candidates=len(cands), tried=tried)
    raise RuntimeError(f"「{dish}」没有合格的图（候选 {len(cands)} 张，Jev 认为对得上的 {len(ranked)} 张，试了 {tried}）")


def main_dish(draft):
    """封面放哪道菜：正文「✅ 必点」那行的第一道菜。"""
    import re
    m = re.search(r"✅[^\n：:]*[：:]\s*([^\n，,、。；;]+)", draft["body"])
    return (m.group(1) if m else draft["title"]).strip()
