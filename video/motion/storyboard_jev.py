#!/usr/bin/env python
"""让 Jev 逐镜看一遍分镜表（工作流第 4 步的第二道关；用法和约定见 .claude/skills/jev-decisions/SKILL.md，PITFALLS E6、P8）。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8 和 TYPESAFE_API_KEY）
  python video/motion/storyboard_jev.py video/stories/tj01/storyboard.json     （也可以只写集名 tj01）
  --only s01,s02        只看这几个镜头（改完再跑一遍用，省钱；对照镜头照常混进去）
  --verbose             每个镜头的四个概率都打印（默认只打印被标出来的）
  --out 结果.json       {episode, rubric, model, flagged, shots: [{id, t0, t1, probs, flags, state}], controls, calls}
  --cache 路径          缓存文件（默认 video/out/storyboard_jev_cache.json）；--workers N 并行数（默认 8）
  --registry 路径 / --assets-root 目录    换素材登记表 / 素材根目录（测试用）
退出码：0 = 所有镜头都过、对照镜头都照预期；1 = 有镜头没过（列出镜头 id 和原因），或者对照镜头没照预期被标出来（这次的结果不可信）；
        2 = 输入有错 / 没有 TYPESAFE_API_KEY（立刻报错，不做别的）；3 = 连不上 Jev / 调用失败。

做法：每个镜头拼一份文字描述（Jev 看不到图，只看得到字），一次请求问四道是 / 否题（题目在 rubrics/storyboard_v1.json，改题不改代码）：
  subject  画面主体（最大、最靠前）是不是台词说到的人，或者正在说话的人                     「是」的概率 < 0.5 标「主体不对」
  kid      6–12 岁的孩子顺着看下来，有没有完全听不懂 / 看不懂的地方（连上一镜台词也猜不出来）   「是」的概率 > 0.6 标「孩子看不懂」
  scary    会不会吓到孩子、血腥                                                          「是」的概率 > 0.5 标「可能吓到孩子」
  meme     台词和贴纸里有没有大人的网络流行语、成人的梗、脏话                            「是」的概率 > 0.5 标「梗不是孩子的梗」
描述从哪来（分镜表写得越清楚，Jev 判断得越准）：
  台词        这个镜头时段里配音说的话（配音时间线）：说话人：台词
  画面主体    人物里占画面面积最大的（差不多大时取画在最上面的）；没有人物就取最大的前景 / 道具 / 布景
  人物        名字 = actor 的 who（没写用 id）；样子 = actor 里写的 note（推荐：一句话写这一镜他在干什么），没写就用素材登记表里这张图的备注第一段
  布景 / 道具  素材登记表里的名称和备注；贴纸和特效 = 每个特效的类型加它带的字（text / name / items ……）；导演备注 = 镜头 note
放行：个别镜头确实要留难的句子（比如系列固定的金句原文），在那个镜头的 notes 里写 {"jev_allow": ["kid"], "why": "……"}，
  这一项照样问、照样打印，但不算没过（列在「放行」里）。
按输入哈希缓存（模型 + 描述 + 题目一样就不再请求，结果在缓存文件里，不进 git）：改一个镜头只多花一次请求。
对照镜头：自动混进 5 个（一个好的 + 主体不对 / 孩子看不懂 / 吓人 / 不是孩子的梗各一个，写在题目文件的 controls 里）：好的必须一项都不标，坏的必须被自己那一项标出来，
  否则这次结果不可信（退出码 1）。对照镜头的描述是固定的，请求只花第一次。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

MOTION = Path(__file__).resolve().parent
VIDEO = MOTION.parent
ROOT = VIDEO.parent
for p in (MOTION, VIDEO, ROOT):
    sys.path.insert(0, str(p))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import jev_pick as JP  # noqa: E402
import storyboard_check as SC  # noqa: E402
from engine import consts as C  # noqa: E402
from engine.sprites import AssetError, AssetStore  # noqa: E402
from engine.timeline import AnchorError, Timeline  # noqa: E402
from jevdev import jev  # noqa: E402

RUBRIC_NAME = "storyboard_v1"          # 新旧分数不混着比：改题另存 storyboard_v2.json
RUBRIC = jev.load_rubric(RUBRIC_NAME)
QUESTIONS = RUBRIC["questions"]
CACHE = VIDEO / "out" / "storyboard_jev_cache.json"
Fail = JP.Fail
SIZE_ZH = {"wide": "远景 / 全景", "medium": "中景", "close": "特写"}
STICKER_ZH = {"question": "问号", "exclaim": "感叹号", "bulb": "灯泡", "sweat": "汗滴", "anger": "怒气符号", "stars": "星星眼", "heart": "小心心",
              "dong": "咚", "pa": "啪", "sou": "嗖"}
FX_TEXT_KEYS = ("text", "name", "label", "title", "person", "items", "options", "words", "role")
MIN_OVERLAP = 0.3                      # 台词和镜头时段重叠超过这么多秒才算「这个镜头里的台词」
SUBJECT_LATER_WINS = 0.85              # 后画的人物面积 ≥ 最大的 85% 时，取画在上面的


def require_key():
    """没有 key 就立刻退出：不许等到解析完一大堆东西之后才报（P8）。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise Fail("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 逐镜检查跑不了。检查不许跳过（P8）。\n"
                   "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                   "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


# ------------------------------------------------------------------ 分镜表 → 每镜一份描述
def pose_desc(note):
    """登记表备注的第一段：去掉 ** 和（尺寸），到第一个「；」为止。"""
    t = re.sub(r"\*\*", "", note or "")
    t = re.sub(r"（\d+×\d+）", "", t)
    return re.split(r"[；;]", t)[0].strip("：: ，,")[:80]


def set_name(owner, rel):
    m = re.search(r"（(.+?)）", owner or "")
    if m:
        name = re.split(r"[：:]", m.group(1))[0]
        return None if name.startswith("共用") else name
    return re.sub(r"^布景\s*", "", owner or "").strip() or None


class Ctx:
    pass


def load(sb_arg, registry, assets_root):
    """读分镜表 + 配音时间线 + 镜头时间范围。格式 / 锚点有错就 Fatal（退出码 2）：先跑 storyboard_check.py。"""
    sb, path = SC.load_storyboard(sb_arg)
    rep = SC.Report()
    SC.check_format(sb, rep)
    base = path.parent
    tl = Timeline.load(SC.find_voice(sb, base))
    ctx = Ctx()
    ctx.sb, ctx.path, ctx.tl, ctx.base = sb, path, tl, base
    ctx.registry = SC.load_registry(registry)
    ctx.assets_root = Path(assets_root) if assets_root else C.ASSETS
    ctx.store = AssetStore(1.0, [base])
    ctx.store.roots = [ctx.assets_root, base]
    ctx.shots = [SC.Shot(i, s) for i, s in enumerate(sb["shots"])]
    SC.compute_ranges(ctx.shots, tl, rep)
    specs = {sh.id: dict(sh.spec) for sh in ctx.shots}
    if not rep.errors:
        for j, r in enumerate(sb.get("rituals", []) or []):
            try:
                f = round(tl.resolve(r["at"]) * C.FPS)
            except (AnchorError, KeyError, TypeError, ValueError) as e:
                rep.err("锚点", f"rituals[{j}]：{e}")
                continue
            home = next((sh for sh in ctx.shots if sh.f0 <= f < sh.f1), ctx.shots[-1])
            specs[home.id]["fx"] = list(specs[home.id].get("fx", []) or []) + [dict(r)]
    if rep.errors:
        raise SC.Fatal("分镜表的格式 / 锚点有错，先跑 storyboard_check.py 改好再来：\n  " + "\n  ".join(SC.fmt(e) for e in rep.errors[:5]))
    for sh in ctx.shots:
        sh.spec = specs[sh.id]
    return ctx


def image_facts(ctx, path):
    """(登记行, 相对路径, 宽高比)；找不到图就 (None, None, 0.85)。"""
    try:
        f = ctx.store.resolve(path)
    except AssetError:
        return None, None, 0.85
    try:
        rel = Path(f).resolve().relative_to(ctx.assets_root.resolve()).as_posix()
    except ValueError:
        rel = None
    w, h = SC.img_size(f)
    return (ctx.registry.get(rel) if rel else None), rel, w / h


def side_of(x):
    return "画面偏左" if x < 400 else "画面偏右" if x > 680 else "画面中间"


def fx_text(e):
    typ = e.get("type", "?")
    kind = SC.kind_of(typ)
    bits = []
    for k in FX_TEXT_KEYS:
        v = e.get(k)
        if isinstance(v, str):
            bits.append(STICKER_ZH.get(v, v))
        elif isinstance(v, list) and all(isinstance(x, str) for x in v):
            bits.append("、".join(v))
    label = {"sticker": "贴纸", "slam": "砸字", "namecard": "人名牌", "list": "清单", "flash": "闪白", "title": "大字标题", "gamecard": "游戏卡片",
             "stat": "属性卡", "map": "地图", "gauge": "进度物", "ritual": "系列仪式"}.get(kind, typ)
    return f"{label}「{' '.join(bits)}」" if bits else label


def shot_lines(ctx, sh):
    """这个镜头时段里的台词 → ([说话人：台词], {说话人})。"""
    tl, lines, speakers = ctx.tl, [], set()
    for i, ln in enumerate(tl.lines):
        if not tl.is_speech(i):
            continue
        s0, s1 = tl.speech_span(i)
        if min(s1, sh.t1) - max(s0, sh.t0) >= MIN_OVERLAP:
            lines.append(f"{ln['who']}：{ln['text']}")
            speakers.add(ln["who"])
    return lines, speakers


def describe_shot(ctx, sh, prev=None):
    """prev = 上一个镜头（有的话，它的台词作为「上一镜台词」给 Jev 当上下文：孩子是顺着看下来的，不是单看一镜）。"""
    spec = sh.spec
    lines, speakers = shot_lines(ctx, sh)
    people = []
    for a in spec.get("actors", []) or []:
        row, rel, aspect = image_facts(ctx, a["img"])
        h = float(a.get("h", 400))
        who = a.get("who") or a.get("id") or (SC.owner_name(row["owner"])[0] if row else "人物")
        desc = a.get("note") or (pose_desc(row["note"]) if row else "")
        for sw in [x for x in (a.get("acts", []) or []) if "swap" in x]:
            r2, _, _ = image_facts(ctx, sw["swap"])
            d2 = pose_desc(r2["note"]) if r2 else ""
            if d2:
                desc += f"；后来换成：{d2}"
        pos = a.get("pos", [540, 1500])
        people.append({"who": who, "area": h * h * aspect, "text": f"{who}{'（正在说话）' if a.get('who', a.get('id')) in speakers else ''}：{desc}；{side_of(float(pos[0]))}，占画面高度 {round(h / C.H * 100)}%"})
    subject, others = None, []
    if people:
        best = max(range(len(people)), key=lambda k: people[k]["area"])
        for k in range(len(people) - 1, best, -1):            # 画在上面的、面积差不多的取它
            if people[k]["area"] >= SUBJECT_LATER_WINS * people[best]["area"]:
                best = k
                break
        subject = people[best]["text"]
        others = [p["text"] for k, p in enumerate(people) if k != best]
    sets, props = [], []
    for grp in ("bg", "fg"):
        for e in spec.get(grp, []) or []:
            row, rel, _ = image_facts(ctx, e["img"])
            if rel and rel.startswith("props/") and row:
                props.append(pose_desc(row["note"]) or Path(rel).stem)
            elif rel and rel.startswith("sets/") and row:
                n = set_name(row["owner"], rel)
                if n and n not in sets:
                    sets.append(n)
    if subject is None:                                       # 没有人物：主体取最大的道具，再不行就是布景
        subject = f"没有人物；画面上最大的是{props[0]}" if props else f"没有人物；画面是{'、'.join(sets) or '背景'}"
    fxs = [fx_text(e) for e in spec.get("fx", []) or []]
    note = spec.get("note") or spec.get("notes")
    before = shot_lines(ctx, prev)[0][-2:] if prev is not None else []
    shot = {"景别": SIZE_ZH.get(spec.get("size"), spec.get("size")),
            "上一镜台词": before,
            "台词": lines or ["（这个镜头没有台词）"],
            "画面主体（最大、最靠前）": subject,
            "其他人物": others,
            "布景": "、".join(sets),
            "道具": props[:4],
            "贴纸和特效": fxs,
            "导演备注": json.dumps(note, ensure_ascii=False) if isinstance(note, (dict, list)) else note}
    return {k: v for k, v in shot.items() if v not in (None, "", [])}


# ------------------------------------------------------------------ 问 Jev
def questions():
    return {q: {"type": "noul", "instructions": v["instructions"]} for q, v in QUESTIONS.items()}


def ask(cache, shot):
    return cache.ask({"audience": RUBRIC["audience"], "task": RUBRIC["task"], "shot": shot}, questions())


def flags_of(probs):
    """哪几项没过：good 题「是」的概率 < min，坏事题「是」的概率 > max。"""
    out = []
    for q, v in QUESTIONS.items():
        p = probs[q]
        if (v["good"] and p < v["min"]) or (not v["good"] and p > v["max"]):
            out.append(q)
    return out


def why(q, p):
    v = QUESTIONS[q]
    return f"{v['label']}（{q}：{p:.2f}，{'低于 ' + format(v['min'], 'g') if v['good'] else '高于 ' + format(v['max'], 'g')}）"


def run(ctx, only, cache, workers):
    picked = [sh for sh in ctx.shots if not only or sh.id in only]
    if only:
        unknown = [x for x in only if x not in {sh.id for sh in ctx.shots}]
        if unknown:
            raise Fail(f"错误：--only 里没有这些镜头：{unknown}（分镜表里有：{[sh.id for sh in ctx.shots]}）")
    prevs = {sh.id: (ctx.shots[k - 1] if k else None) for k, sh in enumerate(ctx.shots)}
    states = [(sh, describe_shot(ctx, sh, prevs[sh.id])) for sh in picked]
    ctrl = list(RUBRIC["controls"].items())
    fns = [(lambda st=st: ask(cache, st)) for _, st in states] + [(lambda c=c: ask(cache, c["shot"])) for _, c in ctrl]
    res = JP.run_parallel(fns, workers)
    shots = []
    for (sh, st), probs in zip(states, res[:len(states)]):
        notes = sh.spec.get("notes")
        allow = [q for q in notes.get("jev_allow", []) if q in QUESTIONS] if isinstance(notes, dict) and isinstance(notes.get("jev_allow"), list) else []
        got = flags_of(probs)
        shots.append({"id": sh.id, "t0": round(sh.t0, 2), "t1": round(sh.t1, 2), "probs": {q: round(p, 3) for q, p in probs.items()},
                      "flags": [q for q in got if q not in allow], "allowed": [q for q in got if q in allow],
                      "allow_why": notes.get("why") if allow and isinstance(notes, dict) else None, "state": st})
    controls = []
    for (name, c), probs in zip(ctrl, res[len(states):]):
        got = flags_of(probs)
        ok = (not got) if not c["expect_flag"] else all(q in got for q in c["expect_flag"])
        controls.append({"name": name, "why": c["why"], "probs": {q: round(p, 3) for q, p in probs.items()}, "flags": got, "expect": c["expect_flag"], "ok": ok})
    return shots, controls


def short(s, n=44):
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def print_result(ctx, shots, controls, verbose):
    flagged = [s for s in shots if s["flags"]]
    print(f"storyboard_jev {ctx.sb.get('episode')}：{len(shots)} 个镜头 + {len(controls)} 个对照镜头，题目 {RUBRIC_NAME}，模型 {jev.MODEL}")
    for s in shots:
        if s["flags"] or s["allowed"] or verbose:
            head = f"  镜头 {s['id']}（{s['t0']:.1f}–{s['t1']:.1f} 秒）"
            pr = " ".join(f"{q}={s['probs'][q]:.2f}" for q in QUESTIONS)
            if s["allowed"]:
                print(f"{head} 放行：{'；'.join(why(q, s['probs'][q]) for q in s['allowed'])}（{s['allow_why'] or '没写原因'}）")
            if s["flags"]:
                print(f"{head} 没过：{'；'.join(why(q, s['probs'][q]) for q in s['flags'])}")
                st = s["state"]
                print(f"      主体：{short(st.get('画面主体（最大、最靠前）', ''), 70)}")
                print(f"      台词：{short(' / '.join(st.get('台词', [])), 70)}")
            elif not s["allowed"]:
                print(f"{head} 过  {pr}")
    bad = [c for c in controls if not c["ok"]]
    print(f"对照镜头：{len(controls) - len(bad)} / {len(controls)} 个照预期" + ("" if not bad else "；没照预期的：" + "；".join(
        f"{c['name']}（{c['why']}）应标 {c['expect'] or '不标'}、实际标了 {c['flags'] or '没标'}，" + " ".join(f"{q}={p:.2f}" for q, p in c["probs"].items()) for c in bad)))
    if verbose:
        for c in controls:
            print(f"  对照 {c['name']:<8} " + " ".join(f"{q}={p:.2f}" for q, p in c["probs"].items()) + f"  标：{c['flags'] or '无'}  预期：{c['expect'] or '无'}")
    return flagged, bad


def main():
    ap = argparse.ArgumentParser(description="让 Jev 逐镜看分镜表：主体对不对、看不看得懂、吓不吓人、梗对不对（第 4 步第二道关）")
    ap.add_argument("storyboard", help="分镜表 JSON，或集名（video/stories/<集>/storyboard.json）")
    ap.add_argument("--only", help="只看这几个镜头（逗号分隔的镜头编号）")
    ap.add_argument("--verbose", action="store_true", help="每个镜头的概率都打印")
    ap.add_argument("--out", help="结果写到这个 JSON")
    ap.add_argument("--cache", default=str(CACHE), help=f"缓存文件（默认 {CACHE.relative_to(ROOT)}）")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--registry", default=str(SC.REGISTRY))
    ap.add_argument("--assets-root")
    a = ap.parse_args()
    cache = None
    try:
        require_key()
        ctx = load(a.storyboard, a.registry, a.assets_root)
        cache = JP.Cache(a.cache)
        only = [x.strip() for x in a.only.split(",") if x.strip()] if a.only else None
        shots, controls = run(ctx, only, cache, a.workers)
    except Fail as e:
        print(str(e), file=sys.stderr)
        return e.code
    except SC.Fatal as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except Exception as e:     # 连不上、401、超时、限流……都算 Jev 调用失败：不许静默跳过（P8）
        msg = f"{type(e).__name__}: {e}".replace(os.environ.get("TYPESAFE_API_KEY", "\0"), "***")
        print(f"错误：Jev 调用失败，没有结果。{msg}", file=sys.stderr)
        return 3
    finally:
        if cache is not None and cache.fresh:
            cache.save()          # 已经花掉的调用不要白花
    flagged, bad_controls = print_result(ctx, shots, controls, a.verbose)
    c = cache.calls()
    print(f"调用 {c['requests']} 次新请求，{c['cached']} 次用了缓存（输入 {c['input_tokens']} / 输出 {c['output_tokens']} 词元）")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"episode": ctx.sb.get("episode"), "rubric": RUBRIC_NAME, "model": jev.MODEL,
                                           "flagged": [s["id"] for s in flagged], "shots": shots, "controls": controls, "calls": c},
                                          ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"结果写到 {a.out}")
    if bad_controls:
        print("⚠ 对照镜头没照预期：这次的结果不可信，先改题（rubrics/storyboard_v1.json）再跑。", file=sys.stderr)
    if flagged:
        print(f"没过：{len(flagged)} 个镜头（{'、'.join(s['id'] for s in flagged)}）：由导演改完再跑。", file=sys.stderr)
    if flagged or bad_controls:
        return 1
    print("所有镜头都过，对照镜头都照预期：这次的结果可信。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
