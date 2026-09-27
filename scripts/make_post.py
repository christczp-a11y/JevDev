"""一家店 → 一篇待发布的小红书笔记（草稿包）。

流程：Google 评价 + 小红书笔记（+ 可选 Reddit）→ Jev 逐条判断 → 代码汇总画像
     → Claude 写 N 篇草稿 → 代码检查 + Jev 审稿（合规闸门 + 质量）+ 标题表现预测
     → 选稿（80% 选最高分，20% 随机探索）→ 渲染卡片 → data/posts/<时间>_<店>/
发布不在这里做：先人工看草稿包，再用 publish.py 发布。

用法：
  python scripts/make_post.py --query "HK BBQ Master Richmond BC" --name "明家烧腊 HK BBQ Master" --xhs-keyword "明家烧腊"
        [--my-notes "本人体验……"] [--no-reddit] [--n 4]
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import collect_xhs  # noqa: E402
import google_reviews  # noqa: E402
from jevdev import db, engagement, jev, restaurant, writer, xhs  # noqa: E402

# 极限词 / 诱导 / 导流的词表拦截（放过「最近、最后、第一次」这类普通用法）
BANNED = re.compile(r"最(?!近|后|早|晚|初|终)|第一(?!次|口|眼|天|步)|唯一|顶级|天花板|封神|绝了|吊打|全网|No\.?1|神仙"
                    r"|点赞|收藏起来|关注我|扣\s?1|私信|微信|vx|VX|抖音|淘宝|https?://")
EXPLORE_RATE = 0.2
GATES = ["g_absolute", "g_induce", "g_redirect", "g_adlike", "g_accuse", "g_fake_visit"]
GATE_MAX = 0.3
# 导流：提到「Google 评分」这类信息来源会让 Jev 给出 0.3–0.4 的中间值，不算导流；放宽到 0.5
GATE_LIMITS = {"g_redirect": 0.5}
LEVEL_WORD = {1: "差", 2: "一般", 3: "好", 4: "很好"}


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------- 采集 ----------

def google_data(con, query):
    con.executescript(google_reviews.SCHEMA)
    row = con.execute("SELECT * FROM places WHERE query=?", (query,)).fetchone()
    fresh = row and (datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])).days < 3
    if not fresh:
        log("抓 Google 评价…")
        google_reviews.save(con, query, google_reviews.scrape(query, 50))
        row = con.execute("SELECT * FROM places WHERE query=?", (query,)).fetchone()
    reviews = [dict(r) for r in con.execute(
        "SELECT review_id, stars, when_text, text, source FROM reviews WHERE query=? AND source='google'", (query,))]
    return dict(row), reviews


def xhs_cached(con, keyword):
    """MCP 出错时退回数据库里上次抓到的笔记和正文。"""
    rows = con.execute("""SELECT DISTINCT n.id, n.title, n.desc FROM notes n JOIN search_hits h ON h.note_id = n.id
                          WHERE h.keyword = ? AND n.desc IS NOT NULL""", (keyword,)).fetchall()
    notes = [{"title": r["title"], "likes": None, "collects": None} for r in rows]
    reviews = [{"review_id": "xhs:" + r["id"], "stars": None, "when_text": None, "text": r["desc"][:1500],
                "source": "xhs_note"} for r in rows]
    log(f"  改用缓存：{len(rows)} 篇笔记")
    return notes, reviews


def xhs_data(con, keyword, max_details=4):
    log(f"搜小红书「{keyword}」…")
    feeds = None
    for attempt in range(2):
        try:
            feeds = [f for f in (xhs.call("search_feeds", {"keyword": keyword}).get("feeds") or [])
                     if f.get("modelType") == "note"]
            break
        except Exception as e:
            log(f"  搜索失败（第 {attempt + 1} 次）：{str(e)[:80]}")
            xhs.polite_sleep(5, 10)
    if feeds is None:
        return xhs_cached(con, keyword)
    collect_xhs.save_search(con, keyword, "综合", feeds)
    notes, reviews = [], []
    for f in feeds[:max_details]:
        xhs.polite_sleep(4, 9)
        try:
            d = xhs.call("get_feed_detail", {"feed_id": f["id"], "xsec_token": f.get("xsecToken")})
        except Exception as e:
            log(f"  详情失败 {f['id']}: {e}")
            continue
        collect_xhs.save_detail(con, f["id"], d)
        n = (d.get("data") or {}).get("note") or {}
        ii = n.get("interactInfo") or {}
        notes.append({"title": n.get("title"), "likes": ii.get("likedCount"), "collects": ii.get("collectedCount")})
        if n.get("desc"):
            reviews.append({"review_id": "xhs:" + f["id"], "stars": None, "when_text": None,
                            "text": n["desc"][:1500], "source": "xhs_note"})
        for c in ((d.get("data") or {}).get("comments") or {}).get("list", [])[:10]:
            if len(c.get("content") or "") >= 8:
                reviews.append({"review_id": "xhsc:" + c["id"], "stars": None, "when_text": None,
                                "text": c["content"], "source": "xhs_comment"})
    return notes, reviews


CODEX_EXE = str(Path.home() / "AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64"
                / "vendor/x86_64-pc-windows-msvc/bin/codex.exe")
REDDIT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["threads"],
    "properties": {"threads": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["url", "subreddit", "date", "points"],
        "properties": {"url": {"type": "string"}, "subreddit": {"type": "string"}, "date": {"type": "string"},
                       "points": {"type": "array", "items": {"type": "string"}}}}}},
}


def reddit_data(con, query, name):
    """Reddit 讨论：Claude 的搜索和本机脚本都被 Reddit 挡住，所以通过 Codex CLI（ChatGPT 会员）的联网搜索获取。
    每条讨论要点当作一条「评价」交给 Jev；7 天内同一家店复用缓存。"""
    con.executescript(google_reviews.SCHEMA)
    cached = [dict(r) for r in con.execute(
        """SELECT review_id, stars, when_text, text, 'reddit' AS source FROM reviews
           WHERE query=? AND source='reddit' AND fetched_at > datetime('now', '-7 days')""", (query,))]
    if cached:
        log(f"Reddit 用缓存 {len(cached)} 条")
        return cached
    log("通过 Codex 搜 Reddit（约 1–2 分钟）…")
    prompt = (f"Use web search to find Reddit threads (reddit.com) that discuss the restaurant \"{name}\" "
              f"(Google Maps query: \"{query}\") in Metro Vancouver. Return up to 5 threads you actually saw in "
              "search results. For each, give the URL, subreddit, approximate date, and 1-4 short points "
              "paraphrasing what commenters said about THIS restaurant (dishes, taste, price, service, wait, "
              "payment), good and bad. Do not invent anything; return an empty list if nothing relevant is found.")
    tmp = ROOT / "data" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    schema_file, out_file = tmp / "reddit_schema.json", tmp / "reddit_out.json"
    schema_file.write_text(json.dumps(REDDIT_SCHEMA), encoding="utf-8")
    out_file.unlink(missing_ok=True)
    proc = subprocess.run(
        [CODEX_EXE, "--search", "exec", "--skip-git-repo-check", "-s", "read-only",
         "--output-schema", str(schema_file), "-o", str(out_file)],
        input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600)
    if not out_file.exists():
        log(f"  Codex 没有返回结果（exit {proc.returncode}）：{proc.stderr[-300:]}")
        return []
    threads = json.loads(out_file.read_text(encoding="utf-8")).get("threads", [])
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for t in threads:
        for i, p in enumerate(t["points"]):
            rid = f"reddit:{t['url']}#{i}"
            out.append({"review_id": rid, "stars": None, "when_text": t["date"],
                        "text": f"[r/{t['subreddit'].removeprefix('r/')} {t['date']}] {p}", "source": "reddit"})
            con.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?)",
                        (rid, query, "reddit", t["subreddit"], None, t["date"], out[-1]["text"], ts))
    con.commit()
    log(f"  Reddit：{len(threads)} 个帖子，{len(out)} 条要点")
    return out


# ---------- 事实包 ----------

def build_facts(name, place, prof, reviews, answers, xhs_notes, my_notes):
    dims = {}
    for d, v in prof["dimensions"].items():
        if v:
            dims[d] = {"评价": LEVEL_WORD[round(v["score"])], "分数_1到4": v["score"],
                       "提及次数": v["mentions"], "分歧度": v["disagreement"]}
    # 按来源分配名额，避免 Google 的大量评价把 Reddit / 小红书挤掉
    quota = {"google": 15, "reddit": 10, "xhs_note": 4, "xhs_comment": 6}
    used = {s: 0 for s in quota}
    evidence = []
    for r in reviews:
        a = answers.get(r["review_id"])
        src = r["source"]
        if a and a["relevant"]["noul"] >= 0.7 and a["ad_like"]["noul"] < 0.5 and used.get(src, 0) < quota.get(src, 5):
            used[src] = used.get(src, 0) + 1
            evidence.append(f"[{src}{'·' + str(r['stars']) + '星' if r['stars'] else ''}] {r['text'][:280]}")
    facts = {
        "餐厅": name,
        "谷歌评分": {"评分": place.get("rating"), "评价总数": place.get("review_count")},
        "评价维度画像（Jev 汇总）": dims,
        "排队": None if prof["wait_long_share"] is None else f"提到排队的评价中约 {int(prof['wait_long_share'] * 100)}% 说要等很久",
        # cash_only 信号只说明「有评价提到只收现金 / 不收卡」，具体支付方式以评价原文为准
        "支付": ("有评价提到只收现金、不收信用卡（具体支付方式看评价摘录，可能还支持其他方式）"
                 if prof["cash_only_signal"] is not None and prof["cash_only_signal"] > 0.7 else None),
        "评价摘录（只供参考，不要照抄）": evidence,
        "小红书上已有的相关笔记（标题和互动，用来找差异化角度）": xhs_notes,
    }
    if my_notes:
        facts["本人体验（可以写成亲身经历）"] = my_notes
    return facts


# ---------- 审稿与选稿 ----------

def code_checks(d):
    problems = []
    if len(d["title"]) > 20:
        problems.append(f"标题 {len(d['title'])} 字，超过 20")
    for field in ("title", "body"):
        hit = BANNED.findall(d[field])
        if hit:
            problems.append(f"{field} 命中禁用词 {sorted(set(hit))}")
    if not 5 <= len(d["tags"]) <= 8:
        problems.append(f"话题 {len(d['tags'])} 个（应为 5–8）")
    return problems


def claim_lines(d):
    """草稿里所有可能含事实的文字：正文每一行 + 卡片上的文字。"""
    lines = [ln.strip() for ln in d["body"].splitlines() if ln.strip()]
    for c in [d["cover"]] + d["pages"]:
        lines += [c["title"].replace("[[", "").replace("]]", ""), c["subtitle"]]
        lines += [f"{it['name']}：{it.get('meta', '')}" for it in c.get("items") or []]
    return [ln for ln in lines if ln]


def unsupported(d, evidence):
    """逐行事实核查（一次请求、每行一题），返回 [(行, 有依据的概率)] 中不达标的行。"""
    tpl = jev.load_rubric("claim_check_v1")["template"]
    lines = claim_lines(d)
    qs = {f"line_{i}": {**tpl, "instructions": tpl["instructions"].replace("{i}", str(i))} for i in range(len(lines))}
    a, _ = jev.ask({"evidence": evidence, "lines": lines}, qs)
    return [(lines[i], round(a[f"line_{i}"]["noul"], 2)) for i in range(len(lines)) if a[f"line_{i}"]["noul"] < 0.5]


def review_drafts(con, drafts, facts, work_dir):
    draft_rubric = jev.load_rubric("draft_v1")
    evidence = {k: v for k, v in facts.items() if not k.startswith("小红书上已有")}

    # 逐句核查 + 禁用词：有问题的句子让 Claude 修一次（并发），修完再核查
    for d in drafts:
        d["unsupported_before"] = unsupported(d, evidence)
        d["banned_lines"] = [ln for ln in claim_lines(d) + [d["title"]] if BANNED.search(ln)]
    need = [d for d in drafts if d["unsupported_before"] or d["banned_lines"]]
    if need:
        log(f"  {len(need)} 篇有无依据或含禁用词的句子，交给 Claude 修改…")
        from concurrent.futures import ThreadPoolExecutor

        def fix(d):
            issues = [f"（数据里找不到依据）{ln}" for ln, _ in d["unsupported_before"]]
            issues += [f"（含禁用词「{'、'.join(sorted(set(BANNED.findall(ln))))}」，换一种说法）{ln}" for ln in d["banned_lines"]]
            return writer.revise_draft(d, issues, facts)
        with ThreadPoolExecutor(max_workers=4) as pool:
            fixed = list(pool.map(fix, need))
        for d, f in zip(need, fixed):
            d.update({k: f[k] for k in ("title", "cover", "pages", "body", "tags")})
            d["revised"] = True
    for d in drafts:
        d["unsupported"] = unsupported(d, evidence) if d.get("revised") else []

    for d in drafts:
        d["code_problems"] = code_checks(d)
        a, _ = jev.ask({"title": d["title"], "body": d["body"], "evidence": evidence}, draft_rubric["questions"])
        d["jev"] = jev.flatten(a)
        d["gate_fail"] = [g for g in GATES if a[g]["noul"] > GATE_LIMITS.get(g, GATE_MAX)]
        if d["unsupported"]:
            d["gate_fail"].append("unsupported_claims")
        q = [a[k]["score"] / 4 for k in ("q_hook", "q_useful", "q_scan", "q_save", "q_voice")]
        d["quality"] = round((sum(q) / len(q) + a["q_balance"]["noul"] * 0.2 + a["q_deliver"]["noul"] * 0.2) / 1.4, 3)

    # 选稿依据：赛道数据验证过的复合分（标题 + 正文 + 渲染后的封面，见 jevdev/engagement.py）
    log("  渲染每篇的卡片，Claude 描述封面，Jev 按验证过的规则打复合分…")
    n_rules = engagement.score_drafts(drafts, work_dir)
    log(f"  （复合分用 {n_rules} 条规则）")
    ok = [d for d in drafts if not d["gate_fail"] and not d["code_problems"]]
    for d in ok:
        d["rank_score"] = d["pred"]
    return ok


def pick(ok):
    if not ok:
        return None, None
    if len(ok) > 1 and random.random() < EXPLORE_RATE:
        return random.choice(ok), "explore"
    return max(ok, key=lambda d: d["rank_score"]), "best"


# ---------- 输出 ----------

def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:40] or "post"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True, help="Google 地图搜索词（英文店名 + 城市）")
    ap.add_argument("--name", required=True, help="写进笔记的店名")
    ap.add_argument("--xhs-keyword", required=True, help="小红书搜索词（中文店名）")
    ap.add_argument("--my-notes", default="", help="Chris 的亲身体验（可选）")
    ap.add_argument("--no-reddit", action="store_true", help="跳过 Reddit（默认会通过 Codex 搜索）")
    ap.add_argument("--n", type=int, default=4)
    args = ap.parse_args()

    con = db.connect()
    place, reviews = google_data(con, args.query)
    xhs_notes, xhs_reviews = xhs_data(con, args.xhs_keyword)
    reviews += xhs_reviews
    if not args.no_reddit:
        reviews += reddit_data(con, args.query, args.name)
    by_src = {s: sum(r["source"] == s for r in reviews) for s in sorted({r["source"] for r in reviews})}
    log(f"评价共 {len(reviews)} 条 {by_src}，Jev 判断中…")
    answers = restaurant.judge_reviews(con, args.name, reviews)
    prof = restaurant.profile(reviews, answers)
    facts = build_facts(args.name, place, prof, reviews, answers, xhs_notes, args.my_notes)

    log(f"Claude 写 {args.n} 篇草稿…")
    drafts, meta = writer.write_drafts(facts, args.n)
    log(f"  完成（{meta['duration_ms'] / 1000:.0f}s）。Jev 审稿…")
    out_dir = ROOT / "data" / "posts" / f"{datetime.now():%Y%m%d-%H%M}_{slug(args.query)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = review_drafts(con, drafts, facts, out_dir / "_drafts")
    chosen, mode = pick(ok)

    if chosen:
        chosen["images"] = []
        for i, src in enumerate(chosen["card_paths"], 1):  # 选中那篇的卡片放到草稿包根目录（publish.py 读这里）
            dst = out_dir / f"card_{i:02d}.png"
            shutil.copy(src, dst)
            chosen["images"].append(str(dst))
        chosen["pick_mode"] = mode
    (out_dir / "package.json").write_text(json.dumps(
        {"query": args.query, "name": args.name, "facts": facts, "profile": prof, "drafts": drafts,
         "chosen_index": drafts.index(chosen) if chosen else None, "writer_meta": meta},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 草稿审稿结果 =====")
    for i, d in enumerate(drafts):
        flag = "✅" if d is chosen else ("·" if d in ok else "❌")
        print(f"{flag} [{i}] {d['angle']} | 《{d['title']}》 质量 {d['quality']} 预测互动 {d['pred']}"
              f"{' 排序分 ' + str(d.get('rank_score')) if d in ok else ''}")
        if d.get("unsupported_before"):
            print(f"     首轮无依据 {len(d['unsupported_before'])} 句 → 修改后剩 {len(d['unsupported'])} 句")
        if d["gate_fail"] or d["code_problems"]:
            print(f"     淘汰原因：{d['gate_fail'] + d['code_problems']}")
            for ln, p in d["unsupported"]:
                print(f"       无依据({p}): {ln[:60]}")
    if chosen:
        print(f"\n选中（{mode}）：《{chosen['title']}》\n{chosen['body']}\n#" + " #".join(chosen["tags"]))
    print(f"\n草稿包：{out_dir}")


if __name__ == "__main__":
    main()
