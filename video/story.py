"""剧本质检：Jev 按 rubrics/story_v2.json 给每一版剧本打分，再两两比较。

三种判断：
  - script：整部剧本一次问完（钩子、讲清为什么、办法妙在哪、代价、升级、留存、寓意、生活联系、大人层、孩子笑点、游戏机制、清晰）+ 三道闸门（史实、儿童不宜、两代人对立）
  - beat：逐句问「这一句给了观众继续看的新理由吗」，代码算出最长的「平淡段」有几秒
  - pair：两两比较（孩子更可能看完 / 更能说清道理 / 家长更想转发），a、b 两种顺序各问一次抵消位置偏差

剧本格式（video/stories/<集>/<版本>.json）：
  {"id", "name", "framework", "title": [两行标题], "lines": [[开始秒, 结束秒, 谁, 台词, 画面], ...]}
这一集要讲清的问题和史料放在同目录的 episode.json：{"core_question", "core_answer", "source", "trick", "pitfalls"}
episode.json 里的 cast（谁用哪个声音）只给配音用，打分前会去掉，不发给 Jev。

读剧本时先查秒数，不满足就报出「文件、第几句（lines 下标，和 voice.py 的行号一致）、文件行号、秒数」，非 0 退出：
  每句的开始秒 ≥ 上一句的开始秒；有台词的句子结束秒 > 开始秒；没有台词的句子结束秒 ≥ 开始秒。
一开头就检查环境变量 TYPESAFE_API_KEY，没有就非 0 退出（P8）。

用法：python video/story.py video/stories/ep01 [--pairs] [--only A,B] [--timeline <voice.py 输出目录>/timeline.json] [--out 报告路径]
  --timeline 按真实配音时间线重算最长平淡段，并列出没有台词、超过 4 秒的动作段（第 4 步用）：
      必须和 --only 一起用、只选一版剧本，而且 timeline.json 要是用这一版剧本配出来的（句数和台词逐句对得上，否则报错退出）。
      不重新问 Jev：沿用估算秒数下 Jev 对每句「有没有新理由」的判断，只把时钟换成真实的，
      所以「估算」和「真实时间线」两个数的差别只来自时间，不夹着 Jev 的波动。结果写进 report.json 的 beats.timeline。
"""
import argparse
import hashlib
import itertools
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from jevdev import jev  # noqa: E402

RUBRIC = jev.load_rubric("story_v2")   # 新旧分数不混着比：v1 的分数不能和 v2 比
AUDIENCE = RUBRIC["audience"]
CACHE = ROOT / "out" / "story_cache.json"
MAX_RATE = 5.0   # 每秒最多几个字：配音读得完、孩子跟得上
SILENT_LIMIT = 4.0   # 没有台词的动作段最长几秒（第 4 步的过关线，悬念除外）


def require_key():
    """没有 Jev 的 key 就立刻退出：不许等到白跑很久之后才报（P8）。放在 main() 开头而不是模块开头，别的脚本 import 本文件时不受影响。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 打分跑不了。质检不许跳过（P8）。\n"
                 "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                 "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


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


def line_numbers(text):
    """每一句在剧本文件里从第几行开始（从 1 数）：只用来报错，让人能在文件里找到这一句。格式认不出来就返回空表。"""
    dec, ws = json.JSONDecoder(), " \t\r\n"

    def skip(i, chars):
        while i < len(text) and text[i] in chars:
            i += 1
        return i
    try:
        i = skip(text.index("{") + 1, ws + ",")
        while text[i] != "}":
            key, i = dec.raw_decode(text, i)
            i = skip(i, ws + ":")
            if key == "lines":
                nums, i = [], skip(i + 1, ws)
                while text[i] != "]":
                    nums.append(text.count("\n", 0, i) + 1)
                    _, i = dec.raw_decode(text, i)
                    i = skip(i, ws + ",")
                return nums
            _, i = dec.raw_decode(text, i)
            i = skip(i, ws + ",")
    except (ValueError, IndexError):
        pass
    return []


def check_seconds(path, text, tr):
    """秒数查不过的地方，一条一条返回（文件、句序、文件行号、秒数）。N6 结尾回到教室的三句写成 0–0 就是这样漏过去的。"""
    nums, errs, prev = line_numbers(text), [], None
    for i, (t0, t1, who, line, _) in enumerate(tr["lines"]):
        where = f"{path}：lines[{i}]（第 {i + 1} 句" + (f"，文件第 {nums[i]} 行起" if i < len(nums) else "") + f"，{who}）"
        if not all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in (t0, t1)):
            errs.append(f"{where}：开始秒 {t0!r}、结束秒 {t1!r} 不是数字")
            continue
        if prev is not None and t0 < prev:
            errs.append(f"{where}：开始秒 {t0:g} 小于上一句的开始秒 {prev:g}（写成 0–0 的句子会这样）")
        if line.strip() and t1 <= t0:
            errs.append(f"{where}：有台词，但结束秒 {t1:g} 不大于开始秒 {t0:g}")
        elif t1 < t0:
            errs.append(f"{where}：结束秒 {t1:g} 小于开始秒 {t0:g}")
        prev = t0
    return errs


def load_folder(folder, only=None):
    """读 episode.json（去掉 cast）和这个目录里的所有候选剧本；标题写成字符串的，当成一行的标题。
    返回 (ep, [(路径, 剧本)])。秒数查不过就打印所有问题，非 0 退出。只查选中的版本：没选中的版本有问题不挡别的版本。"""
    ep = json.loads((folder / "episode.json").read_text(encoding="utf-8"))
    ep = {k: v for k, v in ep.items() if k != "cast"}   # cast 只给 voice.py 用，不发给 Jev
    loaded = []
    for p in sorted(folder.glob("*.json")):
        if p.name == "episode.json":
            continue
        text = p.read_text(encoding="utf-8")
        loaded.append((p, text, json.loads(text)))
    if only:
        keep = set(only.split(","))
        missing = keep - {tr["id"] for _, _, tr in loaded}
        if missing:
            sys.exit(f"错误：--only 里的 {sorted(missing)} 在 {folder} 里找不到；现有的 id：{[tr['id'] for _, _, tr in loaded]}")
        loaded = [x for x in loaded if x[2]["id"] in keep]
    errs = [e for p, text, tr in loaded for e in check_seconds(p, text, tr)]
    if errs:
        sys.exit("错误：剧本的秒数有问题，先改剧本（不然最长平淡段和语速都会算错）：\n" + "\n".join("  " + e for e in errs))
    for _, _, tr in loaded:
        if isinstance(tr["title"], str):   # 字符串会被 ' / '.join 拆成单字
            tr["title"] = [tr["title"]]
    return ep, [(p, tr) for p, _, tr in loaded]


def load_timeline(path, script_path, tr):
    """voice.py 输出的 timeline.json：句数、说话人、台词都要和剧本逐句对上，对不上就退出（配音是用另一版剧本配的）。"""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["lines"]
    if len(rows) != len(tr["lines"]):
        sys.exit(f"错误：{path} 有 {len(rows)} 句，{script_path} 有 {len(tr['lines'])} 句，不是同一版剧本配的音")
    bad = [f"lines[{i}]：剧本「{ln[2]}：{ln[3][:12]}」，timeline「{r['who']}：{r['text'][:12]}」"
           for i, (r, ln) in enumerate(zip(rows, tr["lines"])) if (r["who"], r["text"]) != (ln[2], ln[3])]
    if bad:
        sys.exit(f"错误：{path} 和 {script_path} 的台词对不上（配完音后剧本改过？重新配音）：\n" + "\n".join("  " + b for b in bad[:10]))
    return rows


def longest_flat(ps, spans):
    """有新理由的句子（概率 ≥ 0.5）的开始时刻，两两之间最长隔了多久。spans 是每句的（开始, 结束）。"""
    hits = [0.0] + [t0 for (t0, _), p in zip(spans, ps) if p >= 0.5] + [spans[-1][1]]
    gaps = [(b - a, a) for a, b in zip(hits, hits[1:])]
    worst = max(gaps)
    return round(worst[0], 1), worst[1]


def long_silent(rows):
    """timeline.json 里没有台词、超过 4 秒的段（动作、停顿）。"""
    return [{"i": r["i"], "t0": r["t0"], "t1": r["t1"], "seconds": round(r["t1"] - r["t0"], 1), "visual": r["visual"]}
            for r in rows if not r["text"].strip() and r["t1"] - r["t0"] > SILENT_LIMIT]


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
    flat, flat_from = longest_flat(ps, [(t0, t1) for t0, t1, *_ in tr["lines"]])
    return {"b_new": [round(p, 2) for p in ps], "longest_flat": flat, "flat_from": flat_from}


def pair(cache, ep, a, b):
    """a 赢的概率：两种顺序的平均。"""
    st = lambda x, y: {"audience": AUDIENCE, "core_question": ep["core_question"], "a": fmt(x), "b": fmt(y)}
    r1, r2 = cache.ask(st(a, b), RUBRIC["pair"]), cache.ask(st(b, a), RUBRIC["pair"])
    return {q: round((r1[q]["a"] + r2[q]["b"]) / 2, 3) for q in RUBRIC["pair"]}


def main():
    require_key()
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--timeline", help="voice.py 输出的 timeline.json：按真实配音时间重算最长平淡段（要配 --only，只选一版）")
    ap.add_argument("--out", help="报告写到这个文件（默认 video/out/story_<目录名>/report.json，每次运行都会覆盖它；要留住的结果用 --out 另存）")
    args = ap.parse_args()
    folder = Path(args.folder)
    ep, loaded = load_folder(folder, args.only)
    trs = [tr for _, tr in loaded]
    rows = None
    if args.timeline:
        if len(trs) != 1:
            sys.exit(f"错误：--timeline 只能对应一版剧本，请加 --only <剧本 id>（现在选中了 {len(trs)} 版）")
        rows = load_timeline(args.timeline, loaded[0][0], trs[0])
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
    if rows:
        flat, flat_from = longest_flat(beats[0]["b_new"], [(r["t0"], r["t1"]) for r in rows])
        beats[0]["timeline"] = {"file": str(args.timeline), "longest_flat": flat, "flat_from": flat_from,
                                "silent_over_4s": long_silent(rows), "duration": rows[-1]["t1"]}

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
    if rows:
        tl = beats[0]["timeline"]
        print(f"\n按真实时间线（{tl['file']}）：最长平淡段 {tl['longest_flat']}s（从 {tl['flat_from']:g}s 起）；估算秒数下是 {beats[0]['longest_flat']}s（从 {beats[0]['flat_from']:g}s 起）")
        print(f"没有台词、超过 {SILENT_LIMIT:g} 秒的段（{len(tl['silent_over_4s'])} 个）：" + ("无" if not tl["silent_over_4s"] else ""))
        for x in tl["silent_over_4s"]:
            print(f"  lines[{x['i']}] {x['t0']:g}–{x['t1']:g}s（{x['seconds']}s）{x['visual'][:40]}")
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
    dest = Path(args.out) if args.out else ROOT / "out" / f"story_{folder.name}" / "report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n报告：{dest}")


if __name__ == "__main__":
    main()
