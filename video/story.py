"""剧本质检：Jev 按 rubrics/story_v1.json 给每一版剧本打分，再两两比较。

三种判断：
  - script：整部剧本一次问完（钩子、讲清为什么、办法妙在哪、代价、升级、留存、寓意、生活联系、大人层、孩子笑点、游戏机制、清晰）+ 三道闸门（史实、儿童不宜、两代人对立）
  - beat：逐句问「这一句给了观众继续看的新理由吗」，代码算出最长的「平淡段」有几秒
  - pair：两两比较（孩子更可能看完 / 更能说清道理 / 家长更想转发），a、b 两种顺序各问一次抵消位置偏差

剧本格式（video/stories/<集>/<版本>.json）：
  {"id", "name", "framework", "title": [两行标题], "lines": [[开始秒, 结束秒, 谁, 台词, 画面], ...]}
这一集要讲清的问题和史料放在同目录的 episode.json：{"core_question", "core_answer", "source"}

用法：python video/story.py video/stories/ep01 [--pairs] [--only A,B]
"""
import argparse
import hashlib
import itertools
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import jev  # noqa: E402

RUBRIC = jev.load_rubric("story_v1")
AUDIENCE = "6–9 岁孩子和家长在手机上刷到的竖屏动画短视频（1–2 分钟）：画面是纸艺立体书风格的横版闯关游戏，Q 版人物；顶部固定两行问句标题，下面是字幕"
CACHE = ROOT / "out" / "story_cache.json"
MAX_RATE = 5.0   # 每秒最多几个字：配音读得完、孩子跟得上


def fmt(tr, upto=None):
    rows = [f"[标题] {' / '.join(tr['title'])}"]
    for t0, t1, who, line, screen in tr["lines"][:upto]:
        rows.append(f"[{t0:g}–{t1:g}秒] {who}：{line}" + (f"（画面：{screen}）" if screen else ""))
    return "\n".join(rows)


def checks(tr):
    """代码能判断的：总时长、语速。"""
    out = {"duration": tr["lines"][-1][1]}
    fast = []
    for t0, t1, who, line, _ in tr["lines"]:
        n = len(re.sub(r"[^\w]", "", line))
        if n / max(t1 - t0, 0.1) > MAX_RATE:
            fast.append(f"{t0:g}s {n}字/{t1 - t0:g}秒")
    out["too_fast"] = fast
    return out


class Cache:
    def __init__(self):
        self.d = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    def ask(self, state, questions):
        k = hashlib.sha1(json.dumps([state, questions], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if k not in self.d:
            a, _ = jev.ask(state, questions)
            self.d[k] = {q: (v["score"] if v["type"] == "score" else v["noul"] if v["type"] == "noul"
                             else v["probabilities"]) for q, v in a.items()}
        return self.d[k]

    def save(self):
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(self.d, ensure_ascii=False), encoding="utf-8")


def score_script(cache, ep, tr):
    return cache.ask({"audience": AUDIENCE, "episode": ep, "script": fmt(tr)}, RUBRIC["script"])


def beat_map(cache, tr):
    """逐句的「新理由」概率 → 最长平淡段（秒）：两个有新理由的句子之间隔了多久。"""
    ps = [cache.ask({"audience": AUDIENCE, "earlier": fmt(tr, i) if i else "（这是第一句）",
                     "beat": fmt({"title": tr["title"], "lines": [tr["lines"][i]]}).split("\n", 1)[1]},
                    RUBRIC["beat"])["b_new"] for i in range(len(tr["lines"]))]
    hits = [0.0] + [tr["lines"][i][0] for i, p in enumerate(ps) if p >= 0.5] + [tr["lines"][-1][1]]
    gaps = [(b - a, a) for a, b in zip(hits, hits[1:])]
    worst = max(gaps)
    return {"b_new": [round(p, 2) for p in ps], "longest_flat": round(worst[0], 1), "flat_from": worst[1]}


def pair(cache, ep, a, b):
    """a 赢的概率：两种顺序的平均。"""
    st = lambda x, y: {"audience": AUDIENCE, "core_question": ep["core_question"], "a": fmt(x), "b": fmt(y)}
    r1, r2 = cache.ask(st(a, b), RUBRIC["pair"]), cache.ask(st(b, a), RUBRIC["pair"])
    return {q: round((r1[q]["a"] + r2[q]["b"]) / 2, 3) for q in RUBRIC["pair"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()
    folder = Path(args.folder)
    ep = json.loads((folder / "episode.json").read_text(encoding="utf-8"))
    trs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json")) if p.name != "episode.json"]
    if args.only:
        keep = set(args.only.split(","))
        trs = [t for t in trs if t["id"] in keep]
    cache = Cache()
    with ThreadPoolExecutor(8) as ex:
        scores = list(ex.map(lambda t: score_script(cache, ep, t), trs))
        beats = list(ex.map(lambda t: beat_map(cache, t), trs))
        pairs = {}
        if args.pairs:
            combos = list(itertools.combinations(range(len(trs)), 2))
            for (i, j), r in zip(combos, ex.map(lambda c: pair(cache, ep, trs[c[0]], trs[c[1]]), combos)):
                pairs[(i, j)] = r
    cache.save()

    dims = [k for k in RUBRIC["script"] if not k.startswith("g_")]
    report = []
    print("版本".ljust(14) + " ".join(d[:6].rjust(6) for d in dims) + "   均分  平淡段  史实?  不宜?  对立?  时长")
    for tr, s, b in zip(trs, scores, beats):
        c = checks(tr)
        mean = sum(s[d] for d in dims) / len(dims)
        print(tr["id"].ljust(14) + " ".join(f"{s[d]:6.2f}" for d in dims)
              + f"  {mean:5.2f}  {b['longest_flat']:5.1f}s  {s['g_accuracy']:.2f}   {s['g_kid_unsafe']:.2f}   {s['g_generation']:.2f}  {c['duration']:g}s"
              + (f"  语速过快：{c['too_fast']}" if c["too_fast"] else ""))
        report.append({"id": tr["id"], "name": tr["name"], "scores": s, "mean": round(mean, 2), "beats": b, "checks": c})
    if pairs:
        print("\n两两比较（行对列的胜率；每格：看完 / 讲懂 / 转发）")
        wins = {i: {q: [] for q in RUBRIC["pair"]} for i in range(len(trs))}
        for (i, j), r in pairs.items():
            for q, p in r.items():
                wins[i][q].append(p)
                wins[j][q].append(1 - p)
        for i, tr in enumerate(trs):
            w = {q: round(sum(v) / len(v), 2) for q, v in wins[i].items()}
            report[i]["pair_winrate"] = w
            print(f"{tr['id'].ljust(14)} 看完 {w['p_finish']:.2f}  讲懂 {w['p_understand']:.2f}  转发 {w['p_share']:.2f}")
    out = ROOT / "out" / f"story_{folder.name}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n报告：{out / 'report.json'}")


if __name__ == "__main__":
    main()
