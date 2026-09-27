"""一家店 → 一篇待发布的小红书笔记（草稿包）。

流程：Google 评价 + 小红书笔记（+ 可选 Reddit）→ Jev 逐条判断 → 代码汇总画像
     → Claude 写 N 篇草稿 → 代码检查 + Jev 审稿（合规闸门 + 质量）+ 标题表现预测
     → 选稿（80% 选最高分，20% 随机探索）→ 渲染卡片 → data/posts/<时间>_<店>/
发布不在这里做：先人工看草稿包，再用 publish.py 发布。

用法：
  python scripts/make_post.py --query "HK BBQ Master Richmond BC" --name "明家烧腊 HK BBQ Master" --xhs-keyword "明家烧腊"
        [--my-notes "本人体验……"] [--reddit] [--n 4]
"""
import argparse
import json
import math
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import collect_xhs  # noqa: E402
import google_reviews  # noqa: E402
import phase1_eval  # noqa: E402
from jevdev import cards, db, jev, restaurant, writer, xhs  # noqa: E402

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
        "SELECT review_id, stars, when_text, text, 'google' AS source FROM reviews WHERE query=?", (query,))]
    return dict(row), reviews


def xhs_data(con, keyword, max_details=4):
    log(f"搜小红书「{keyword}」…")
    feeds = [f for f in (xhs.call("search_feeds", {"keyword": keyword}).get("feeds") or []) if f.get("modelType") == "note"]
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


def reddit_data(name):
    log("通过 Codex 搜 Reddit…")
    prompt = (f"Use web search to find Reddit threads discussing the restaurant {name} in Metro Vancouver. "
              "Return up to 5 items as JSON lines: {\"url\":..., \"summary\": one or two sentences paraphrasing what "
              "commenters said, good and bad}. Only include threads you actually saw. Output JSON lines only.")
    proc = subprocess.run(["codex", "--search", "exec", "--skip-git-repo-check", "-s", "read-only", prompt],
                          capture_output=True, text=True, encoding="utf-8", timeout=400, shell=True)
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and "summary" in line:
            try:
                j = json.loads(line)
                out.append({"review_id": "reddit:" + j.get("url", str(len(out))), "stars": None, "when_text": None,
                            "text": j["summary"], "source": "reddit"})
            except json.JSONDecodeError:
                pass
    return out


# ---------- 事实包 ----------

def build_facts(name, place, prof, reviews, answers, xhs_notes, my_notes):
    dims = {}
    for d, v in prof["dimensions"].items():
        if v:
            dims[d] = {"评价": LEVEL_WORD[round(v["score"])], "分数_1到4": v["score"],
                       "提及次数": v["mentions"], "分歧度": v["disagreement"]}
    evidence = []
    for r in reviews:
        a = answers.get(r["review_id"])
        if a and a["relevant"]["noul"] >= 0.7 and a["ad_like"]["noul"] < 0.5:
            evidence.append(f"[{r['source']}{'·' + str(r['stars']) + '星' if r['stars'] else ''}] {r['text'][:280]}")
    facts = {
        "餐厅": name,
        "Google": {"评分": place.get("rating"), "评价总数": place.get("review_count")},
        "评价维度画像（Jev 汇总）": dims,
        "排队": None if prof["wait_long_share"] is None else f"提到排队的评价中约 {int(prof['wait_long_share'] * 100)}% 说要等很久",
        # cash_only 信号只说明「有评价提到只收现金 / 不收卡」，具体支付方式以评价原文为准
        "支付": ("有评价提到只收现金、不收信用卡（具体支付方式看评价摘录，可能还支持其他方式）"
                 if prof["cash_only_signal"] is not None and prof["cash_only_signal"] > 0.7 else None),
        "评价摘录（只供参考，不要照抄）": evidence[:25],
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


def title_model(con):
    """用阶段 1 的数据训练标题表现预测模型（Ridge）；返回 predict(draft_dict, jev_title_answers)。"""
    X_code, X_jev, y = phase1_eval.load_dataset(con, "xhs_title_v1_zh")
    code_keys = sorted({k for d in X_code for k in d})
    jev_keys = sorted({k for d in X_jev for k in d if not k.endswith("__conf")})
    from sklearn.linear_model import RidgeCV
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    X = np.hstack([phase1_eval.to_matrix(X_code, code_keys), phase1_eval.to_matrix(X_jev, jev_keys)])
    model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(X, y)

    def predict(draft, title_answers):
        n = {"title": draft["title"], "desc": draft["body"], "cover_w": 1080, "cover_h": 1440,
             "note_type": "normal", "from_latest": 1, "from_top": 0,
             "publish_ts": time.time() * 1000 - 7 * 86400000}   # 控制变量固定：同龄、未经热度筛选
        xc = phase1_eval.to_matrix([phase1_eval.code_features(n)], code_keys)
        xj = phase1_eval.to_matrix([jev.flatten(title_answers)], jev_keys)
        return float(model.predict(np.hstack([xc, xj]))[0])
    return predict


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


def review_drafts(con, drafts, facts):
    draft_rubric = jev.load_rubric("draft_v1")
    title_rubric = jev.load_rubric("xhs_title_v1_zh")
    predict = title_model(con)
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
        t, _ = jev.ask({**title_rubric["context"], "title": d["title"]}, title_rubric["questions"])
        d["jev"] = jev.flatten(a)
        d["gate_fail"] = [g for g in GATES if a[g]["noul"] > GATE_LIMITS.get(g, GATE_MAX)]
        if d["unsupported"]:
            d["gate_fail"].append("unsupported_claims")
        q = [a[k]["score"] / 4 for k in ("q_hook", "q_useful", "q_scan", "q_save", "q_voice")]
        d["quality"] = round((sum(q) / len(q) + a["q_balance"]["noul"] * 0.2 + a["q_deliver"]["noul"] * 0.2) / 1.4, 3)
        d["pred_engagement"] = round(predict(d, t), 3)
    ok = [d for d in drafts if not d["gate_fail"] and not d["code_problems"]]
    if ok:
        preds = np.array([d["pred_engagement"] for d in ok])
        z = (preds - preds.mean()) / (preds.std() or 1)
        for d, zi in zip(ok, z):
            d["rank_score"] = round(d["quality"] + 0.1 * float(zi), 3)
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
    ap.add_argument("--reddit", action="store_true")
    ap.add_argument("--n", type=int, default=4)
    args = ap.parse_args()

    con = db.connect()
    place, reviews = google_data(con, args.query)
    xhs_notes, xhs_reviews = xhs_data(con, args.xhs_keyword)
    reviews += xhs_reviews
    if args.reddit:
        reviews += reddit_data(args.query)
    log(f"评价共 {len(reviews)} 条（Google {sum(r['source'] == 'google' for r in reviews)}），Jev 判断中…")
    answers = restaurant.judge_reviews(con, args.name, reviews)
    prof = restaurant.profile(reviews, answers)
    facts = build_facts(args.name, place, prof, reviews, answers, xhs_notes, args.my_notes)

    log(f"Claude 写 {args.n} 篇草稿…")
    drafts, meta = writer.write_drafts(facts, args.n)
    log(f"  完成（{meta['duration_ms'] / 1000:.0f}s）。Jev 审稿…")
    ok = review_drafts(con, drafts, facts)
    chosen, mode = pick(ok)

    out_dir = ROOT / "data" / "posts" / f"{datetime.now():%Y%m%d-%H%M}_{slug(args.query)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if chosen:
        chosen["images"] = cards.render([chosen["cover"]] + chosen["pages"], out_dir)
        chosen["pick_mode"] = mode
    (out_dir / "package.json").write_text(json.dumps(
        {"query": args.query, "name": args.name, "facts": facts, "profile": prof, "drafts": drafts,
         "chosen_index": drafts.index(chosen) if chosen else None, "writer_meta": meta},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 草稿审稿结果 =====")
    for i, d in enumerate(drafts):
        flag = "✅" if d is chosen else ("·" if d in ok else "❌")
        print(f"{flag} [{i}] {d['angle']} | 《{d['title']}》 质量 {d['quality']} 预测 {d['pred_engagement']}"
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
