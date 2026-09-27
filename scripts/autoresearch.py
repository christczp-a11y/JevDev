"""自动研究循环（照 TypeSafe 文档 cookbooks/autoresearch_feature_discovery 的做法）：
Claude 提问题 → Jev 给每篇赛道笔记回答 → 用真实互动量做回归 → 交叉验证决定去留 → 看预测最差的笔记，提下一轮问题。

防止自欺欺人：
  - 按 note_id 的哈希固定留出 25% 的笔记作测试集，循环全程不看，最后只评一次（--final）
  - 基线已经包含控制变量（采样来源、发布天数、视频）、代码能数出来的特征（字数、数字、emoji…）
    和封面的客观描述（版式、有没有人脸…）；Jev 的问题必须在这个基线之上还有增量才算有用
  - 新加的问题：只要答案不是千篇一律（标准差 ≥ 0.05）就先留；修改 / 删除：同一组折的交叉验证误差下降才接受

题目在 rubrics/xhs_features_current.json（每个问题带 input：title / body / cover，决定给 Jev 看什么）。
Jev 的答案按「笔记 × 问题内容的哈希」缓存在 feat_answers 表，改题只会重打改动的题。

用法：
  python scripts/autoresearch.py --eval                 # 给缺的答案打分，报告开发集交叉验证
  python scripts/autoresearch.py --rounds 3             # 跑 3 轮「Claude 提议 → Jev 打分 → 验证去留」
  python scripts/autoresearch.py --final                # 只在最后跑一次：留出测试集上的成绩
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db, jev  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

RUBRIC = ROOT / "rubrics" / "xhs_features_current.json"
HISTORY = ROOT / "data" / "autoresearch"
PROPOSER_MODEL = "claude-opus-5-5"
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")
PLACES = ["温哥华", "列治文", "本拿比", "素里", "高贵林", "北温", "西温", "大温", "Vancouver", "Richmond", "Burnaby"]
CONTEXT = {"account_positioning": "温哥华（大温）本地美食推荐，读者是本地华人、留学生和新移民"}
FLAT_STD = 0.05
CV_SEEDS = (0, 1, 2)


# ---------- 数据 ----------

def is_holdout(note_id):
    return int(hashlib.md5(note_id.encode()).hexdigest(), 16) % 4 == 0


def load_notes(con):
    rows = con.execute("""
        SELECT n.*, c.desc_json AS cover,
               (SELECT MAX(COALESCE(liked,0)+COALESCE(collected,0)+COALESCE(comments,0))
                  FROM snapshots s WHERE s.note_id = n.id) AS engagement,
               (SELECT MAX(sort_by = '最新') FROM search_hits h WHERE h.note_id = n.id) AS from_latest,
               (SELECT MAX(sort_by = '综合') FROM search_hits h WHERE h.note_id = n.id) AS from_top
        FROM notes n LEFT JOIN cover_desc c ON c.note_id = n.id
        WHERE n.is_ours = 0 AND n.title IS NOT NULL AND n.title != ''""").fetchall()
    notes = []
    for r in rows:
        n = dict(r)
        n["cover"] = json.loads(n["cover"]) if n["cover"] else None
        if n["cover"]:
            n["cover"].pop("note_id", None)
        n["y"] = math.log1p(n["engagement"] or 0)
        notes.append(n)
    return notes


def base_features(n):
    """控制变量 + 代码特征 + 封面客观描述（都不经过 Jev）。"""
    t, d, c = n["title"] or "", n["desc"] or "", n["cover"] or {}
    f = {
        # 控制变量
        "c_from_latest": n["from_latest"] or 0,
        "c_from_top": n["from_top"] or 0,
        "c_has_age": int(n["publish_ts"] is not None),
        "c_log_age": math.log1p(max(0.0, (time.time() * 1000 - n["publish_ts"]) / 86400000)) if n["publish_ts"] else 0.0,
        "c_video": int(n["note_type"] == "video"),
        # 代码特征
        "k_title_len": len(t),
        "k_title_digit": int(bool(re.search(r"\d", t))),
        "k_title_emoji": len(EMOJI.findall(t)),
        "k_title_question": int("?" in t or "？" in t),
        "k_title_place": int(any(p in t for p in PLACES)),
        "k_cover_ratio": (n["cover_h"] / n["cover_w"]) if n["cover_w"] else 1.0,
        "k_has_desc": int(bool(d)),
        "k_desc_len": math.log1p(len(d)),
        "k_desc_lines": d.count("\n"),
        "k_desc_emoji": len(EMOJI.findall(d)),
        "k_desc_tags": d.count("#"),
        "k_desc_price": int(bool(re.search(r"\$|刀|加币|CAD|人均", d))),
        "k_images": n["image_count"] or 0,
        # 封面客观描述（Claude 看图得到）
        "v_has_cover": int(bool(c)),
    }
    if c:
        for lay in ("single_photo", "photo_with_text", "collage", "text_card"):
            f[f"v_layout_{lay}"] = int(c.get("layout") == lay)
        f["v_panels"] = c.get("collage_panels", 1)
        f["v_headline_len"] = len(c.get("headline_text", ""))
        f["v_any_text"] = int(bool(c.get("headline_text") or c.get("other_text")))
        f["v_dishes"] = min(c.get("dish_count", 0), 10)
        f["v_face"] = int(bool(c.get("face_visible")))
        f["v_person"] = int("person" in c.get("subjects", []))
        f["v_polished"] = int(c.get("photo_style") == "polished_photo")
        f["v_dark"] = int(c.get("brightness") == "dark")
        if "headline_prominence" in c:
            f["v_headline_large"] = int(c["headline_prominence"] == "large")
            f["v_emphasis"] = int(bool(c["text_emphasis"]))
            f["v_emoji"] = int(bool(c["emoji_on_image"]))
            f["v_stickers"] = int(bool(c["stickers_or_decorations"]))
            f["v_watermark"] = int(bool(c["watermark_or_handle"]))
    if d:
        f.update(rule_code_features(d))
    return f


# 10 个 skill 里能用代码检查的规则（docs/research/10个skill-提取.md 的 20–29、40、43 条）
AI_CLICHE = re.compile("说白了|值得注意的是|不难发现|综上所述|总的来说|此外|与此同时|这意味着|本质上|不可否认|值得一提的是"
                       "|毋庸置疑|可以说|某种程度上|至关重要|深入探讨|彰显|格局|充满活力|首先|其次|不仅|不仅仅是")
GENERIC_TAG = re.compile(r"#(生活|日常|推荐|好物推荐|分享|记录|美食分享)[\[#\s]")


def rule_code_features(d):
    lines = [s.strip() for s in d.split("\n") if s.strip()]
    per100 = 100 / max(len(d), 1)
    return {
        "r_len_100_300": int(100 <= len(d) <= 300),
        "r_para_avg_len": float(np.mean([len(s) for s in lines])) if lines else 0.0,
        "r_long_para_share": float(np.mean([len(s) > 50 for s in lines])) if lines else 0.0,
        "r_emoji_density": len(EMOJI.findall(d)) * per100,
        "r_generic_tags": len(GENERIC_TAG.findall(d + " ")),
        "r_ai_cliche": len(AI_CLICHE.findall(d)),
        "r_dash": d.count("——"),
        "r_first_person": d.count("我") * per100,
        "r_bracket_emph": d.count("【"),
    }


# ---------- Jev 打分（带缓存） ----------

def akey(n, q):
    """缓存键 = 题面 + Jev 实际看到的内容。题 id、_source 备注不影响答案，不算进去；
    所以改名或改写被采纳时不用重打，而正文 / 封面描述更新后会自动重打。"""
    core = {k: q[k] for k in ("type", "instructions", "criteria") if k in q}
    blob = json.dumps([core, build_state(n, q["input"])], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS feat_answers (
        note_id TEXT, qhash TEXT, qid TEXT, answer TEXT, PRIMARY KEY (note_id, qhash))""")


def applicable(n, q):
    return {"title": True, "body": bool(n["desc"]), "cover": bool(n["cover"])}[q["input"]]


def build_state(n, inp):
    s = dict(CONTEXT, title=n["title"])
    if inp == "body":
        s["body"] = n["desc"][:1500]
    if inp == "cover":
        s["cover"] = n["cover"]
    return s


def score(con, notes, questions, workers=8):
    """给缺答案的（笔记, 问题版本）调用 Jev。同一篇、同一种输入的问题放在一个请求里。"""
    have = {(r[0], r[1]) for r in con.execute("SELECT note_id, qhash FROM feat_answers")}
    jobs = []
    for n in notes:
        for inp in ("title", "body", "cover"):
            qs = {qid: q for qid, q in questions.items()
                  if q["input"] == inp and applicable(n, q) and (n["id"], akey(n, q)) not in have}
            if qs:
                jobs.append((n, inp, qs))
    if not jobs:
        return
    print(f"  Jev 打分：{len(jobs)} 个请求")

    def run(job):
        n, inp, qs = job
        wire = {qid: {k: v for k, v in q.items() if k in ("type", "instructions", "criteria")} for qid, q in qs.items()}
        for attempt in range(3):
            try:
                answers, usage = jev.ask(build_state(n, inp), wire)
                return n, qs, answers, usage["input_tokens"]
            except Exception as e:
                if attempt == 2:
                    print(f"  打分失败 {n['id']}：{e}")
                    return n, qs, {}, 0
                time.sleep(3)

    tokens = 0
    with ThreadPoolExecutor(workers) as ex:
        for n, qs, answers, tk in ex.map(run, jobs):
            tokens += tk
            for qid, a in answers.items():
                con.execute("INSERT OR REPLACE INTO feat_answers VALUES (?,?,?,?)",
                            (n["id"], akey(n, qs[qid]), qid, json.dumps(a, ensure_ascii=False)))
            con.commit()
    print(f"  输入 token {tokens}（约 ${tokens * 0.042 / 1e6:.4f}）")


def jev_features(con, notes, questions):
    """每篇笔记 → {特征名: 值}。不适用的问题（没正文 / 没封面）留空，之后用均值填。"""
    cur = {}
    for nid, h, a in con.execute("SELECT note_id, qhash, answer FROM feat_answers"):
        cur[(nid, h)] = json.loads(a)
    out = []
    for n in notes:
        f = {}
        for qid, q in questions.items():
            a = cur.get((n["id"], akey(n, q))) if applicable(n, q) else None
            if a:
                f.update({k: v for k, v in jev.flatten({qid: a}).items() if not k.endswith("__conf")})
        out.append(f)
    return out


# ---------- 评估 ----------

def matrix(dicts, keys, fill=None):
    X = np.array([[d.get(k, np.nan) for k in keys] for d in dicts], dtype=float)
    fill = np.nanmean(X, axis=0) if fill is None else fill
    fill = np.where(np.isnan(fill), 0.0, fill)
    idx = np.where(np.isnan(X))
    X[idx] = np.take(fill, idx[1])
    return X, fill


def model():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20)))


def cv(X, y):
    """3 × 5 折交叉验证（折固定，方便前后配对比较）。返回 (RMSE, Spearman, 每篇的平均预测)。"""
    preds = np.zeros((len(CV_SEEDS), len(y)))
    for i, seed in enumerate(CV_SEEDS):
        for tr, te in KFold(5, shuffle=True, random_state=seed).split(X):
            preds[i, te] = model().fit(X[tr], y[tr]).predict(X[te])
    rmse = float(np.mean([np.sqrt(np.mean((p - y) ** 2)) for p in preds]))
    rho = float(np.mean([spearmanr(p, y).statistic for p in preds]))
    return rmse, rho, preds.mean(axis=0)


class Data:
    def __init__(self, con, questions, split="dev"):
        notes = [n for n in load_notes(con) if is_holdout(n["id"]) == (split == "test")]
        self.notes = notes
        self.y = np.array([n["y"] for n in notes])
        self.base = [base_features(n) for n in notes]
        self.jev = jev_features(con, notes, questions)
        self.base_keys = sorted({k for d in self.base for k in d})

    def X(self, jev_keys):
        Xb, _ = matrix(self.base, self.base_keys)
        if not jev_keys:
            return Xb
        Xj, _ = matrix(self.jev, jev_keys)
        return np.hstack([Xb, Xj])


def cols_of(questions, data):
    """问题 → 它展开出的特征列（choice 每个选项一列）。"""
    cols = {}
    for qid in questions:
        cols[qid] = sorted({k for d in data.jev for k in d if k == qid or k.startswith(qid + "=")})
    return cols


def flat(data, keys):
    X, _ = matrix(data.jev, keys)
    return X.std(axis=0).max() < FLAT_STD if len(keys) else True


def report(data, questions, label=""):
    cols = cols_of(questions, data)
    keys = [k for qid in questions for k in cols[qid]]
    r0 = cv(data.X([]), data.y)
    r1 = cv(data.X(keys), data.y)
    print(f"{label}开发集 {len(data.y)} 篇 | 基线 RMSE {r0[0]:.3f} ρ {r0[1]:+.3f} | 基线+Jev({len(questions)}题) "
          f"RMSE {r1[0]:.3f} ρ {r1[1]:+.3f}")
    return r0, r1, keys


def importances(data, keys):
    """标准化系数 + 控制基线后的偏相关（方便人读：哪些特征和互动正相关）。"""
    X = data.X(keys)
    m = model().fit(X, data.y)
    names = data.base_keys + keys
    coef = dict(zip(names, m[-1].coef_))
    Xb = data.X([])
    resid_y = data.y - model().fit(Xb, data.y).predict(Xb)
    out = []
    Xj, _ = matrix(data.jev, keys)
    for i, k in enumerate(keys):
        col = Xj[:, i]
        rho = spearmanr(col, resid_y).statistic if col.std() > 0 else 0.0
        out.append({"feature": k, "coef": round(float(coef[k]), 3), "partial_rho": round(float(rho), 3)})
    base = [{"feature": k, "coef": round(float(coef[k]), 3)} for k in data.base_keys]
    return sorted(out, key=lambda d: -abs(d["partial_rho"])), sorted(base, key=lambda d: -abs(d["coef"]))


def rule_report(data, questions, boot=1000):
    """逐条检验：每个特征和互动量的关系（先扣掉控制变量：采样来源、发布天数、视频）。
    只用这个特征适用的笔记（没正文的笔记不参与正文特征）。给出 Spearman 和 bootstrap 95% 区间。"""
    ctrl = [k for k in data.base_keys if k.startswith("c_")]
    Xc, _ = matrix(data.base, ctrl)
    resid = data.y - model().fit(Xc, data.y).predict(Xc)
    rng = np.random.default_rng(0)
    rows = []
    feats = [(k, data.base) for k in data.base_keys if not k.startswith("c_")]
    cols = cols_of(questions, data)
    feats += [(k, data.jev) for qid in questions for k in cols[qid]]
    for k, src in feats:
        x = np.array([d.get(k, np.nan) for d in src], dtype=float)
        m = ~np.isnan(x)
        if m.sum() < 30 or x[m].std() == 0:
            continue
        xs, rs = x[m], resid[m]
        rho = spearmanr(xs, rs).statistic
        bs = []
        for _ in range(boot):
            i = rng.integers(0, len(xs), len(xs))
            if xs[i].std() > 0:
                bs.append(spearmanr(xs[i], rs[i]).statistic)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        rows.append({"feature": k, "n": int(m.sum()), "rho": round(float(rho), 3),
                     "ci": [round(float(lo), 3), round(float(hi), 3)],
                     "verdict": "正相关" if lo > 0 else ("负相关" if hi < 0 else "不确定")})
    return sorted(rows, key=lambda r: -abs(r["rho"]))


# ---------- Claude 提议 ----------

PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "actions": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["add", "revise", "drop"]},
                "id": {"type": "string", "description": "问题 id，小写英文+下划线；revise/drop 用已有 id"},
                "input": {"type": "string", "enum": ["title", "body", "cover"]},
                "type": {"type": "string", "enum": ["score", "noul"]},
                "instructions": {"type": "string"},
                "criteria_json": {"type": "string", "description": "score: 5 个字符串的 JSON 数组（从低到高，每档描述具体情形）；noul: 空字符串或 {\"true\":…, \"false\":…}"},
                "why": {"type": "string"},
            },
            "required": ["op", "id", "input", "type", "instructions", "criteria_json", "why"],
        }},
    },
    "required": ["analysis", "actions"],
}

PROPOSER_SYSTEM = """你在帮一个温哥华美食小红书账号做「自动研究」：找出哪些可判断的内容特征能预测笔记的互动量（点赞+收藏+评论）。
每个特征是一道交给 Jev（TypeSafe 的判断模型）回答的题。只用两种题型：score（强度，5 档）和 noul（是 / 否，给出「是」的概率）；想问「属于哪一类」时，拆成几道 noul。Jev 不擅长数数、算术、日期（这些已经由代码算好放在基线里了，不要再出这类题）。
每道题的 input 决定 Jev 看到什么：title=只看标题；body=标题+正文；cover=标题+封面的文字描述（版式、图上文字、画面内容）。
出题规则：
- 一道题只问一个判断；score 的 5 档每档都要描述一个具体情形，能独立读懂
- 题干里用反引号引用字段，如 `title`、`body`、`cover.headline_text`
- 用中文出题
- 目标是「可操作」：找到的特征最终要变成写作 / 配图规则。优先出能指导写作的题，而不是「这篇是不是大号发的」这种没法照做的题
- 不要出基线已经覆盖的题（采样来源、发布天数、字数、有无数字 / emoji / 地名、封面版式、有无人脸等）
你会看到当前的题、每个特征在控制基线后和互动的偏相关、以及模型预测误差最大的笔记。据此提议：add（新题）、revise（改写效果差或含义模糊的题，保留 id）、drop（删掉没用或重复的题）。"""


def propose(data, questions, imp, preds, round_no, extra="", max_add=8):
    err = preds - data.y
    order = np.argsort(err)
    worst = list(order[:6]) + list(order[-6:])  # 低估最多的 6 篇 + 高估最多的 6 篇

    def show(i):
        n = data.notes[i]
        c = n["cover"] or {}
        return {"实际互动": int(n["engagement"] or 0), "预测互动": int(math.expm1(preds[i])),
                "title": n["title"], "body": (n["desc"] or "")[:300],
                "cover": {k: c.get(k) for k in ("layout", "headline_text", "description")} if c else None}

    qs_view = {qid: {k: q[k] for k in ("input", "type", "instructions")} for qid, q in questions.items()}
    user = json.dumps({
        "round": round_no,
        "current_questions": qs_view,
        "feature_partial_correlation": imp[:40],
        "underpredicted_notes(实际比预测高)": [show(i) for i in worst[:6]],
        "overpredicted_notes(实际比预测低)": [show(i) for i in worst[6:]],
        "limits": f"本轮最多 add {max_add} 题、revise 4 题、drop 4 题",
    }, ensure_ascii=False, indent=1) + (f"\n\n补充材料：\n{extra}" if extra else "")
    proc = subprocess.run(
        [CLAUDE_EXE, "-p", "--model", PROPOSER_MODEL, "--output-format", "json", "--tools", "",
         "--system-prompt", PROPOSER_SYSTEM, "--json-schema", json.dumps(PROPOSE_SCHEMA, ensure_ascii=False)],
        input=user, capture_output=True, text=True, encoding="utf-8", timeout=900)
    out = json.loads(proc.stdout)
    if not out.get("structured_output"):
        raise RuntimeError(str(out.get("result"))[:500] or proc.stderr[:500])
    return out["structured_output"]


def to_question(a):
    q = {"input": a["input"], "type": a["type"], "instructions": a["instructions"]}
    cj = (a.get("criteria_json") or "").strip()
    if cj:
        q["criteria"] = json.loads(cj)
    return q


# ---------- 一轮 ----------

def run_round(con, questions, round_no, extra=""):
    data = Data(con, questions)
    r0, r1, keys = report(data, questions, f"[第 {round_no} 轮开始] ")
    imp, _ = importances(data, keys) if keys else ([], [])
    preds = cv(data.X(keys), data.y)[2]
    prop = propose(data, questions, imp, preds, round_no, extra)
    print(f"  Claude 分析：{prop['analysis'][:300]}")
    log = {"round": round_no, "start": {"base": r0[:2], "full": r1[:2]}, "analysis": prop["analysis"], "actions": []}

    # 先给所有新题、改写题打分
    trial = dict(questions)
    for a in prop["actions"]:
        if a["op"] in ("add", "revise"):
            try:
                trial[a["id"] + ("__new" if a["op"] == "revise" else "")] = to_question(a)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  跳过格式错误的题 {a['id']}：{e}")
    score(con, data.notes, trial)
    data = Data(con, trial)
    cols = cols_of(trial, data)

    def rmse_with(qs):
        d = Data(con, qs)
        return cv(d.X([k for qid in qs for k in cols_of(qs, d)[qid]]), d.y)[0]

    current = dict(questions)
    for a in prop["actions"]:
        qid = a["id"]
        if a["op"] == "add" and qid in trial and qid not in questions:
            ok = not flat(data, cols[qid])
            if ok:
                current[qid] = trial[qid]
            log["actions"].append({**a, "accepted": ok, "reason": "有区分度" if ok else "答案几乎都一样"})
        elif a["op"] == "revise" and qid in current and qid + "__new" in trial:
            before = rmse_with(current)
            cand = dict(current)
            cand[qid] = trial[qid + "__new"]
            after = rmse_with(cand)
            ok = after < before
            if ok:
                current = cand
            log["actions"].append({**a, "accepted": ok, "rmse_before": round(before, 4), "rmse_after": round(after, 4)})
        elif a["op"] == "drop" and qid in current:
            before = rmse_with(current)
            cand = {k: v for k, v in current.items() if k != qid}
            after = rmse_with(cand)
            ok = after < before
            if ok:
                current = cand
            log["actions"].append({**a, "accepted": ok, "rmse_before": round(before, 4), "rmse_after": round(after, 4)})

    data = Data(con, current)
    r0, r1, keys = report(data, current, f"[第 {round_no} 轮结束] ")
    log["end"] = {"base": r0[:2], "full": r1[:2], "n_questions": len(current)}
    HISTORY.mkdir(parents=True, exist_ok=True)
    (HISTORY / f"round_{round_no:02d}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return current, r1[0]


def save_questions(questions):
    doc = json.loads(RUBRIC.read_text(encoding="utf-8"))
    doc["questions"] = questions
    RUBRIC.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def final(con, questions):
    """留出测试集：开发集上训练，测试集上只评一次。"""
    dev, test = Data(con, questions, "dev"), Data(con, questions, "test")
    score(con, test.notes, questions)
    test = Data(con, questions, "test")
    keys = [k for qid in questions for k in cols_of(questions, dev)[qid]]
    Xb_dev, fill_b = matrix(dev.base, dev.base_keys)
    Xj_dev, fill_j = matrix(dev.jev, keys)
    Xb_te, _ = matrix(test.base, dev.base_keys, fill_b)
    Xj_te, _ = matrix(test.jev, keys, fill_j)
    res = {}
    for name, Xtr, Xte in (("基线", Xb_dev, Xb_te), ("基线+Jev", np.hstack([Xb_dev, Xj_dev]), np.hstack([Xb_te, Xj_te]))):
        p = model().fit(Xtr, dev.y).predict(Xte)
        res[name] = p
        print(f"测试集 {len(test.y)} 篇 | {name:<8} RMSE {np.sqrt(np.mean((p - test.y) ** 2)):.3f} "
              f"ρ {spearmanr(p, test.y).statistic:+.3f}")
    # 配对 bootstrap：Jev 带来的 RMSE 变化的 95% 区间
    rng = np.random.default_rng(0)
    e0, e1 = (res["基线"] - test.y) ** 2, (res["基线+Jev"] - test.y) ** 2
    diffs = []
    for _ in range(2000):
        i = rng.integers(0, len(e0), len(e0))
        diffs.append(np.sqrt(e1[i].mean()) - np.sqrt(e0[i].mean()))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    print(f"加入 Jev 后 RMSE 变化 {np.sqrt(e1.mean()) - np.sqrt(e0.mean()):+.3f}，95% 区间 [{lo:+.3f}, {hi:+.3f}]（负数 = 更准）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--rounds", type=int, default=0)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--extra", help="第一轮给提议者的补充材料（文件路径）")
    args = ap.parse_args()
    con = db.connect()
    ensure_table(con)
    questions = json.loads(RUBRIC.read_text(encoding="utf-8"))["questions"]

    if args.eval or args.rounds:
        dev = Data(con, questions)
        score(con, dev.notes, questions)
        dev = Data(con, questions)
        _, _, keys = report(dev, questions)
        imp, base = importances(dev, keys)
        print("\nJev 特征（控制基线后的偏相关，按绝对值排序）：")
        for d in imp[:25]:
            print(f"  {d['partial_rho']:+.3f}  {d['feature']}")
        print("\n基线里影响最大的特征（标准化系数）：")
        for d in base[:12]:
            print(f"  {d['coef']:+.3f}  {d['feature']}")
        rules = rule_report(dev, questions)
        HISTORY.mkdir(parents=True, exist_ok=True)
        (HISTORY / "rule_report.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n逐条检验（扣掉控制变量后和互动的 Spearman，95% 区间不跨 0 的才算有关系）：")
        for r in rules:
            if r["verdict"] != "不确定":
                print(f"  {r['rho']:+.3f} [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] n={r['n']:<4} {r['verdict']}  {r['feature']}")
        print(f"  （其余 {sum(r['verdict'] == '不确定' for r in rules)} 个特征：区间跨 0，不确定）")

    best = None
    for r in range(args.rounds):
        done = len(list(HISTORY.glob("round_*.json"))) if HISTORY.exists() else 0
        extra = Path(args.extra).read_text(encoding="utf-8") if (args.extra and r == 0) else ""
        questions, rmse = run_round(con, questions, done + 1, extra)
        save_questions(questions)
        if best is not None and rmse >= best:
            print("本轮没有进步，停止（平台期）")
            break
        best = rmse if best is None else min(best, rmse)

    if args.final:
        final(con, questions)


if __name__ == "__main__":
    main()
