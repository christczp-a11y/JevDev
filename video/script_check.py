"""剧本结构自查（工作流第 2 步；PITFALLS S11、S17、S18、S19、S20、P10；待补 13）。
story.py 的 --lint 只查秒数和禁用词，Jev 只打分；这里查「剧本长什么样」：结构规则里能用代码判断的那部分。
只读，不调 Jev，不要 key。story.py 的读取函数（check_seconds、check_banned、checks、load_timeline）直接 import，不改 story.py。

用法（Git Bash，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）
  python video/script_check.py video/stories/tj01/<剧本>.json [--timeline <voice.py 输出目录>/timeline.json]
  退出码 0 = 没有错误（可以有警告），1 = 有错误。给了 --timeline，所有和时间有关的检查都按真实时间线算，不给就按剧本里估算的秒数。
  同目录的 episode.json 提供 cast（声音）、banned（禁用词）和 structure（这一集的结构设置，见下）。

episode.json 的 "structure"（每集自己的结构设置；整个字段或某个键没写，就用括号里的默认值 = 第一版写死的值，老剧本的结果不变；
不认识的键、类型不对直接报错，防止写错键名被悄悄当成默认值）
  opening_quiz      （true）开头 5 秒里要不要「考考你！」仪式：true = 第一句必须是司马光「考考你！」；false = 开头 5 秒里不许有「考考你！」
  quiz_count        （4）一集几次考你（含弹幕投票）
  quiz_pause        （true）考你后要不要停顿：true = 每次考你 = 台词 + 一行「停 X 秒」的动作行，后面跟「看答案！」；
                    false = 不许有「停 X 秒」行、不许有「看答案！」，一次考你 = 一句台词里有「考考」或「考你」（弹幕投票那句也要写）
  golden_count      （3）金句全集说几次
  golden_max_chars  （12）金句最多几个字
  bigq_by           （7.0 秒）大问题最晚几秒念完（容差 0.3 秒；估算秒数和 --timeline 真实时间线都按它）
  levels            （3）几关：notes.level_starts 要写这么多个下标
  pov_every_level   （true）视角人物要不要每一关都出现；false = 只要求 notes.pov 在剧本里出现过
  ending_ceremony   （true）结尾要不要系列固定句「写书的人，来了——」：true = 旁白单独成句、字面不差、全片只出现一次；false = 不查这句

剧本里要有的备注（顶层 "notes"，Jev 看不到）
  pov            视角人物的名字（文本里要能搜到）
  big_question   大问题，字面和剧本里念出来的那一句完全一样
  level_starts   各关第一句的下标（从 0 数，和 voice.py 的行号一致；个数 = structure.levels，默认三关），如 [8, 15, 34]；这几句的画面里要写「关」或「跟头」
  golden         金句（字数上限和次数看 structure.golden_max_chars / golden_count，默认 ≤ 12 字、恰好 3 次）
  stake_line     赌注那句里的关键词（必填，没有默认值），这一句要在第 20 秒前**念完**
  half_close     （可选）大问题「先关一半」那句里的关键词，要在全片 40%–60% 处
  ending_order   （可选）结尾各句的关键词，按先后顺序，例如 ["封为诸侯", "写书的人，来了", "德者，才之帅也", "下集"]
  level_end_key  （可选）最后一关到哪一句为止（这一句之前算最后一关），写这一句里的关键词，例如「五十年后」；
                 不写，就算到系列固定句「写书的人，来了——」之前
  dian_key       （可选）点题那一句里的关键词，默认「德者，才之帅也」（第一集的臣光曰②）；以后每集写自己的点题关键词

查什么（✗ = 错误，退出码 1；⚠ = 警告，只提醒）
  1  秒数和禁用词（story.py 的 check_seconds、check_banned，和 --lint 一样）
  2  两句仪式句：opening_quiz 为 true 时第一句是司马光「考考你！」（false 时开头 5 秒里不许有）；ending_ceremony 为 true 时旁白「写书的人，来了——」单独成句、只出现一次（false 时不查）
  3  大问题：恰好一句，**念完**（这一句的结束秒）≤ bigq_by 秒（默认 7.0），容差 0.3 秒（S20）
  4  「考你」（默认设置）：一次「考你」 = 台词后面跟一行「停 X 秒」的动作行。共 quiz_count 次（默认 4），停顿依次 1.0 / 1.2 / 1.2 / 1.8
     （不是 4 次时，每次停顿在 1.0–1.8 秒之间）；第 1 关之前恰好一次（开头的二选一；opening_quiz 为 false 时一次也不许有）；
     每关恰好一次（F-1；quiz_count 不够每关一次时，每关最多一次）；「看答案！」和考你次数一一对上。
     quiz_pause 为 false 时：不许有停顿行和「看答案！」，一次考你 = 一句台词里有「考考」或「考你」，总数 = quiz_count
  5  揭晓要念出答案（S18）：每个「看答案！」的画面里写出亮起的按钮（【…】亮起），这些按钮的字要在后面 1–2 句念出来的话里出现（去掉标点比）；
     点题（notes.dian_key 那一句，默认「德者，才之帅也」）之后 1–2 句里要出现金句（文言点题后要有白话翻译）
  6  视角人物（notes.pov）在每一关的时间段里，台词或画面至少出现一次（S17）；pov_every_level 为 false 时只查剧本里出现过
  7  笑点：画面里标了「笑点」的句子，前后间隔（包括开头到第一个、最后一个到结尾）≤ 25 秒
  8  单句 > 8 秒：警告；单句 > 15 字（去掉标点算）：只是警告，不硬卡（S26：长句用几个镜头撑，不硬拆）；旁白句数占全部台词的比例 > 50%：警告（这个系列以对话为主，
     能让人物自己说的改成对话）。「台词」不含动作行；「旁白」只算说话人写「旁白」的句子，司马光和其他角色算对话
  9  画面备注残留：出现「（某某版：…）」直接报错（S11）；道具第一次出现就已经「接住、握着、拿着、举着」也报错（前面没交代）
  10 金句恰好 golden_count 次、≤ golden_max_chars 字；男声连着说不超过两句（只认 cast 里有 voice 的 edge-tts 男声，Qwen 的 cast 没有 voice，只有司马光算男声）；说话人都有声音，同一版里没有两个角色同声音（按 voice 比，没有 voice 就按 desc 比）；旁白 / 司马光以外的说话人要在 cast 里；
     说话人写成 A+B+C（几个人齐声）时逐个查：每个人都要有声音；全是男声才算一句男声；
     台词里没有「然后」；每句语速 ≤ 每秒 5 字；赌注在 20 秒前念完；结尾顺序；大问题先关一半的位置
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import story  # noqa: E402  只 import 它的读取函数，不改它

KAO, XIE = "考考你！", "写书的人，来了——"
PAUSES = [1.0, 1.2, 1.2, 1.8]        # 四次「考你」的停顿（S10）
BIGQ_LIMIT = 7.0                      # 大问题念完的最晚秒数（S20：按裁过静音的真实时间线，念完算，不是开口算）
BIGQ_TOL = 0.3                        # 容差 0.3 秒（S20，09-29 主会话定）：不为了 0.2 秒把二选一砍成「给不给？」，不识字的孩子听不到「要地」，听懂比这 0.2 秒要紧
OPENING_SEC = 5.0                     # opening_quiz 为 false 时，开头这几秒里不许有「考考你！」
STAKE_BY = 20.0                       # 赌注要在第几秒前念完（工作流第 2 步：20 秒前讲清）
DIAN_DEFAULT = "德者，才之帅也"          # 点题句的默认关键词（第一集的臣光曰②）
MAX_GAG_GAP = 25.0                    # 两个笑点之间最长多少秒
LONG_LINE = 8.0
LONG_CHARS = 15                       # 单句最多几个字（去掉标点）：钩子和吸引力第三点五节的台词风格
MAX_NARR_SHARE = 0.5                  # 旁白句数占全部台词的比例上限：以对话为主
MALE_VOICES = {"zh-CN-YunjianNeural", "zh-CN-YunxiNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural",
               "zh-TW-YunJheNeural", "zh-HK-WanLungNeural"}
PROPS = ("毛笔", "警枕", "手巾", "地图", "竹简", "帽子")          # 道具第一次出现不能已经拿在手里
HOLD = ("接住", "握着", "拿着", "举着", "捧着", "抱着", "戴着")
PAUSE_RE = re.compile(r"^停\s*([0-9.]+)\s*秒")
QUIZ_RE = re.compile(r"考考|考你")         # quiz_pause 为 false 时，一句台词里有它 = 一次考你（没有停顿行可数）
VER_RE = re.compile(r"[（(][^（）()]{0,10}版[：:]")
BTN_RE = re.compile(r"【([^】]+)】")

# episode.json 的 structure：没写的键用这里的值（= 第一版写死的值，老剧本的结果不变）
STRUCTURE_DEFAULT = {"opening_quiz": True, "quiz_count": 4, "quiz_pause": True, "golden_count": 3, "golden_max_chars": 12,
                     "bigq_by": BIGQ_LIMIT, "levels": 3, "pov_every_level": True, "ending_ceremony": True}
BOOL_KEYS = ("opening_quiz", "quiz_pause", "pov_every_level", "ending_ceremony")
INT_MIN = {"quiz_count": 0, "golden_count": 0, "golden_max_chars": 1, "levels": 1}     # 整数键和它们的最小值
CN_NUM = {1: "一", 2: "两", 3: "三", 4: "四", 5: "五"}


def core(s):
    return re.sub(r"[^\w]", "", s)


def spoken(row):
    return row[2] != "动作" and bool(row[3].strip())


def parts(who):
    """说话人写成 A+B+C = 几个人齐声；单个说话人就是只有一项的列表。"""
    return [x.strip() for x in who.split("+") if x.strip()]


def read_structure(ep, E):
    """返回生效的结构设置（没写的键用默认值）。不认识的键、类型不对：报错，这个键退回默认值，后面的检查照常跑。"""
    S = dict(STRUCTURE_DEFAULT)
    given = ep.get("structure")
    if given is None:
        return S
    if not isinstance(given, dict):
        E("episode.json 的 structure 要写成 {键: 值}")
        return S
    for k, v in given.items():
        if k not in STRUCTURE_DEFAULT:
            E(f"episode.json 的 structure 里有不认识的键「{k}」（认识的键：{'、'.join(STRUCTURE_DEFAULT)}）")
        elif k in BOOL_KEYS:
            if isinstance(v, bool):
                S[k] = v
            else:
                E(f"episode.json 的 structure.{k} 要写 true 或 false，现在是 {v!r}")
        elif k in INT_MIN:
            if isinstance(v, int) and not isinstance(v, bool) and v >= INT_MIN[k]:
                S[k] = v
            else:
                E(f"episode.json 的 structure.{k} 要写整数（≥ {INT_MIN[k]}），现在是 {v!r}")
        else:      # bigq_by
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                S[k] = v
            else:
                E(f"episode.json 的 structure.{k} 要写大于 0 的秒数，现在是 {v!r}")
    return S


def load(path, timeline):
    """返回 (剧本, 每句 [t0, t1, 谁, 台词, 画面], 全长, 目录, 台词原文)。给了 timeline 就用真实秒数换掉估算秒数。"""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    tr = json.loads(text)
    rows = [list(r) for r in tr["lines"]]
    total = rows[-1][1] if rows else 0.0
    if timeline:
        tl_rows, total = story.load_timeline(timeline, p, tr)     # 对不上会直接退出
        for r, t in zip(rows, tl_rows):
            r[0], r[1] = t["t0"], t["t1"]
    return tr, rows, total, p.parent, text


def run(path, timeline=None):
    tr, rows, total, folder, text = load(path, timeline)
    p = Path(path)
    errs, warns, info = [], [], []
    notes = tr.get("notes") or {}
    ep_path = folder / "episode.json"
    ep = json.loads(ep_path.read_text(encoding="utf-8")) if ep_path.exists() else {}
    cast = ep.get("cast", {}) or {}

    def E(msg):
        errs.append(msg)

    def W(msg):
        warns.append(msg)

    def at(i):
        return f"lines[{i}]（{rows[i][2]}）"

    S = read_structure(ep, E)

    src = "真实时间线" if timeline else "剧本估算秒数"
    info.append(f"{tr.get('id')}：{len(rows)} 句，全长 {total:.1f}s（{src}）")
    if "structure" in ep:
        info.append("结构设置（episode.json 的 structure，没写的键用默认值）：" + "，".join(f"{k}={S[k]}" for k in STRUCTURE_DEFAULT))

    # 1 秒数、禁用词
    for e in story.check_seconds(p, text, tr):
        E("秒数：" + e)
    if ep_path.exists():
        banned = story.read_banned(folder, ep)
        for e in story.check_banned(p, text, tr, banned):
            E("禁用词：" + e)

    # 2 仪式句
    if S["opening_quiz"]:
        if not (rows[0][2] == "司马光" and rows[0][3] == KAO):
            E("第一句不是 司马光「考考你！」")
    else:
        for i, r in enumerate(rows):
            if spoken(r) and r[0] < OPENING_SEC and core(r[3]) == core(KAO):
                E(f"{at(i)} structure.opening_quiz 是 false：开头 {OPENING_SEC:g} 秒里不要「考考你！」仪式")
    xs = [i for i, r in enumerate(rows) if r[3] == XIE]
    if S["ending_ceremony"] and (len(xs) != 1 or rows[xs[0]][2] != "旁白"):
        E("「写书的人，来了——」要由旁白单独成句、字面不差、全片只出现一次")

    # 3 大问题念完
    bq = notes.get("big_question")
    if not bq:
        E("notes.big_question 没写")
    else:
        hit = [i for i, r in enumerate(rows) if r[3] == bq]
        if len(hit) != 1:
            E(f"大问题「{bq}」要恰好出现一次（现在 {len(hit)} 次）")
        else:
            r = rows[hit[0]]
            info.append(f"大问题「{bq}」{r[0]:.2f}–{r[1]:.2f}s")
            if r[1] > S["bigq_by"] + BIGQ_TOL + 1e-9:
                E(f"大问题在 {r[1]:.2f}s 才念完，超过 {S['bigq_by']:g} 秒（容差 {BIGQ_TOL:g} 秒，S20：按真实时间线，念完算）")

    # 4 考你：默认一次考你 = 台词 + 停顿行；structure.quiz_pause 为 false 时没有停顿行，一次考你 = 一句台词里有「考考」或「考你」
    pause_idx = [i for i, r in enumerate(rows) if r[2] == "动作" and PAUSE_RE.match(r[4])]
    pauses = [round(rows[i][1] - rows[i][0], 2) for i in pause_idx]
    reveals = [i for i, r in enumerate(rows) if r[3] == "看答案！"]
    nq = S["quiz_count"]
    if S["quiz_pause"]:
        quiz_idx = pause_idx
        info.append(f"考你 {len(pause_idx)} 次，停顿 {pauses}；「看答案！」{len(reveals)} 次")
        if nq == len(PAUSES):      # 四次：停顿依次 1.0 / 1.2 / 1.2 / 1.8（S10）
            if len(pause_idx) != nq or any(abs(a - b) > 0.06 for a, b in zip(pauses, PAUSES)):
                E(f"考你要 {nq} 次、停顿依次 {PAUSES}，现在是 {pauses}")
        else:                      # 别的次数：停顿在 1.0–1.8 秒之间
            if len(pause_idx) != nq:
                E(f"考你要 {nq} 次（structure.quiz_count），现在 {len(pause_idx)} 次，停顿 {pauses}")
            if any(not PAUSES[0] - 0.06 <= x <= PAUSES[-1] + 0.06 for x in pauses):
                E(f"考你的停顿要在 {PAUSES[0]:g}–{PAUSES[-1]:g} 秒之间，现在是 {pauses}")
        if len(reveals) != len(pause_idx):
            E(f"「看答案！」{len(reveals)} 次，考你 {len(pause_idx)} 次，要一一对上")
        for i in pause_idx:      # 停顿行前面要有提问的一句
            if i == 0 or not spoken(rows[i - 1]):
                E(f"lines[{i}] 的停顿行前面不是台词：一次考你 = 提问的一句 + 停顿行")
    else:
        quiz_idx = [i for i, r in enumerate(rows) if spoken(r) and QUIZ_RE.search(r[3])]
        info.append(f"考你 {len(quiz_idx)} 次（structure.quiz_pause 是 false：没有停顿行、没有「看答案！」）")
        if len(quiz_idx) != nq:
            E(f"考你要 {nq} 次（structure.quiz_count），现在 {len(quiz_idx)} 次"
              f"（没有停顿行时，一次考你 = 一句台词里有「考考」或「考你」，弹幕投票那句也要写）：" + "、".join(at(i) for i in quiz_idx))
        for i in pause_idx:
            E(f"{at(i)} structure.quiz_pause 是 false：不要「停 X 秒」的停顿行（S24：不停顿等答案，画面直接往下演）")
        for i in reveals:
            E(f"{at(i)} structure.quiz_pause 是 false：不要「看答案！」（S24：画面直接往下演）")
    starts = notes.get("level_starts")
    nl = S["levels"]
    n_levels = 0
    if not (isinstance(starts, list) and len(starts) == nl and all(isinstance(x, int) and 0 <= x < len(rows) for x in starts)
            and starts == sorted(starts)):
        E(f"notes.level_starts 要写成{CN_NUM.get(nl, nl)}关各自第一句的下标" + ("，如 [8, 15, 34]" if nl == 3 else f"（structure.levels = {nl}）"))
    else:
        n_levels = nl
        for k, s in enumerate(starts, 1):
            if not re.search(r"关|跟头", rows[s][4]):
                E(f"第 {k} 关的第一句 lines[{s}] 的画面里没有「关」或「跟头」（level_starts 是不是错位了）")
        bounds = starts + [len(rows)]
        before = [i for i in quiz_idx if i < starts[0]]
        want_open = 1 if S["opening_quiz"] else 0
        if len(before) != want_open:
            if want_open:
                E(f"第 1 关之前（开头）要恰好一次考你（二选一），现在 {len(before)} 次")
            else:
                E(f"第 1 关之前（开头）不要考你（structure.opening_quiz 是 false），现在 {len(before)} 次")
        every_level = nq >= nl + want_open      # 考你的次数够每关一次：每关恰好一次；不够：每关最多一次
        for k in range(nl):
            inside = [i for i in quiz_idx if bounds[k] <= i < bounds[k + 1]]
            if every_level and len(inside) != 1:
                E(f"第 {k + 1} 关（lines[{bounds[k]}] 起）要恰好一次考你（F-1），现在 {len(inside)} 次")
            elif len(inside) > 1:
                E(f"第 {k + 1} 关（lines[{bounds[k]}] 起）最多一次考你（F-1），现在 {len(inside)} 次")

    # 5 揭晓要念出答案
    for i in reveals if S["quiz_pause"] else []:
        vis = rows[i][4]
        labels = BTN_RE.findall(vis) if "亮起" in vis else []
        if not labels:
            E(f"{at(i)} 揭晓的画面里要写出亮起的按钮，例如「【不听】亮起」")
            continue
        nxt, j = [], i + 1
        while j < len(rows) and len(nxt) < 2:
            if spoken(rows[j]):
                nxt.append(rows[j])
            j += 1
        heard = "".join(core(r[3]) for r in nxt)
        for lb in labels:
            if core(lb) not in heard:
                E(f"{at(i)} 揭晓后的 1–2 句里没有念出答案「{lb}」（S18：不识字的孩子只听得见声音）")

    # 5b 点题之后要有白话翻译（S18）：点题句之后的 1–2 句里出现金句
    dk = notes.get("dian_key", DIAN_DEFAULT)
    g0 = notes.get("golden")
    dx = [i for i, r in enumerate(rows) if spoken(r) and core(dk) in core(r[3])]
    if not dx:
        E(f"找不到点题那一句（关键词「{dk}」）；每集要用臣光曰点题，关键词写在 notes.dian_key")
    elif g0:
        nxt, j = [], dx[0] + 1
        while j < len(rows) and len(nxt) < 2:
            if spoken(rows[j]):
                nxt.append(rows[j])
            j += 1
        if core(g0) not in "".join(core(r[3]) for r in nxt):
            E(f"{at(dx[0])} 点题之后的 1–2 句里没有白话翻译（金句「{g0}」）（S18：文言点题后要紧跟一句口头翻译）")

    # 6 视角人物每关都在
    pov = notes.get("pov")
    if not pov:
        E("notes.pov（视角人物）没写")
    elif not S["pov_every_level"]:
        if not any(pov in r[3] or pov in r[4] for r in rows):
            E(f"视角人物「{pov}」在整个剧本里一次也没出现（notes.pov 是不是写错了）")
    elif n_levels:
        lk = notes.get("level_end_key")
        if lk:
            end = next((i for i, r in enumerate(rows) if lk in r[3]), None)
            if end is None:
                E(f"notes.level_end_key「{lk}」在剧本台词里找不到")
                end = len(rows)
        else:
            end = next((i for i, r in enumerate(rows) if r[3] == XIE), len(rows))   # 系列固定句之前算最后一关
        bounds = starts + [end]
        for k in range(n_levels):
            seg = rows[bounds[k]:bounds[k + 1]]
            if not any(pov in r[3] or pov in r[4] for r in seg):
                E(f"视角人物「{pov}」在第 {k + 1} 关（lines[{bounds[k]}]–lines[{bounds[k + 1] - 1}]，"
                  f"{rows[bounds[k]][0]:.1f}–{rows[bounds[k + 1] - 1][1]:.1f}s）里台词和画面都没出现（S17）")

    # 7 笑点间隔
    gags = [r[0] for r in rows if "笑点" in r[4]]
    if not gags:
        E("没有标「笑点」的句子")
    else:
        marks = [0.0] + gags + [total]
        worst = max(((b - a), a) for a, b in zip(marks, marks[1:]))
        info.append(f"笑点 {len(gags)} 个，最长间隔 {worst[0]:.1f}s（从 {worst[1]:.1f}s 起）")
        for a, b in zip(marks, marks[1:]):
            if b - a > MAX_GAG_GAP:
                E(f"笑点间隔 {b - a:.1f}s（{a:.1f}s → {b:.1f}s）超过 {MAX_GAG_GAP:g} 秒")

    # 8 单句太长
    for i, r in enumerate(rows):
        if spoken(r) and r[1] - r[0] > LONG_LINE:
            W(f"{at(i)} 单句 {r[1] - r[0]:.1f}s，超过 {LONG_LINE:g} 秒，考虑拆开：{r[3][:24]}")

    # 8b 单句超过 15 字、旁白占比过半（警告）
    for i, r in enumerate(rows):
        if spoken(r) and len(core(r[3])) > LONG_CHARS:
            W(f"{at(i)} 单句 {len(core(r[3]))} 字，超过 {LONG_CHARS} 字，孩子跟不上，考虑拆成短句：{r[3][:24]}")
    said = [r for r in rows if spoken(r)]
    narr = sum(r[2] == "旁白" for r in said)
    if said and narr / len(said) > MAX_NARR_SHARE:
        W(f"旁白 {narr} 句 / 共 {len(said)} 句台词 = {narr / len(said):.0%}，超过一半：这个系列以对话为主，能让人物自己说的改成对话")

    # 9 画面备注残留、道具前面没交代
    for i, r in enumerate(rows):
        m = VER_RE.search(r[4])
        if m:
            E(f"{at(i)} 画面备注里有「{m.group(0)}…」这种某个版本的残留（S11）")
    seen = set()
    for i, r in enumerate(rows):
        vis = r[4]
        for prop in PROPS:
            if prop in vis and prop not in seen:
                if re.search("(?:" + "|".join(HOLD) + r")[^，；。（）]{0,6}" + prop, vis):
                    E(f"{at(i)} 道具「{prop}」第一次出现就已经拿在手里，前面没有交代（S11）")
                seen.add(prop)
        for prop in PROPS:
            if prop in r[3]:
                seen.add(prop)

    # 10 金句、男声、声音、语速、赌注、结尾、半关
    g = notes.get("golden")
    gc, gmax = S["golden_count"], S["golden_max_chars"]
    if not g:
        if gc:
            E("notes.golden（金句）没写")
    else:
        cnt = sum(core(r[3]).count(core(g)) for r in rows if spoken(r))
        info.append(f"金句「{g}」{cnt} 次（{len(core(g))} 字）")
        if cnt != gc or len(core(g)) > gmax:
            E(f"金句要恰好 {gc} 次、≤ {gmax} 字，现在 {cnt} 次、{len(core(g))} 字")
    male = {"司马光"} | {w for w, v in cast.items() if isinstance(v, dict) and v.get("voice") in MALE_VOICES}
    run_ = 0
    for i, r in enumerate(rows):
        who = parts(r[2])      # A+B+C 齐声：每个人都是男声才算一句男声
        if spoken(r) and who and all(w in male for w in who):
            run_ += 1
            if run_ > 2:
                E(f"{at(i)} 起男声连着说了 {run_} 句（儿童动画调研规则 11：每次最多两句，中间插旁白或音效）")
        else:
            run_ = 0
    speakers = {w for r in rows if spoken(r) for w in parts(r[2])}      # A+B+C 齐声：拆开逐个算
    miss = sorted(s for s in speakers if s not in ("旁白", "司马光") and s not in cast)
    if miss:
        E(f"说话人 {miss} 在 episode.json 的 cast 里没有声音")
    by = {}
    for s in speakers:
        if s in cast and isinstance(cast[s], dict):
            by.setdefault(cast[s].get("voice") or cast[s].get("desc"), []).append(s)   # Qwen 的 cast 没有 voice，按声音描述 desc 比
    for v, ws in by.items():
        if len(ws) > 1:
            E(f"同一个声音 {v} 给了 {sorted(ws)}（同一版里有两个角色同声音）")
    if "zh-CN-YunxiNeural" in by:
        E("cast 里的角色用了 YunxiNeural（只给司马光）")
    info.append("说话的角色：" + "、".join(sorted(s for s in speakers if s in cast)))
    if "然后" in "".join(r[3] for r in rows):
        E("台词里有「然后」（转场只用「但是」「所以」）")
    fast = story.checks({"lines": rows})["too_fast"]
    for f in fast:
        E(f"语速超过每秒 {story.MAX_RATE:g} 字：{f}")
    sk = notes.get("stake_line")
    if not sk:
        E("notes.stake_line（赌注那句里的关键词）没写")
    else:
        st = [r for r in rows if sk in r[3]]
        if not st or st[0][1] > STAKE_BY:
            E(f"赌注（「{sk}」）要在第 {STAKE_BY:g} 秒前念完" + (f"，现在 {st[0][0]:.1f}–{st[0][1]:.1f}s" if st else "，剧本里没有"))
    eo = notes.get("ending_order")
    if eo:
        pos = []
        for k in eo:
            ix = [i for i, r in enumerate(rows) if k in r[3]]
            pos.append(ix[0] if ix else -1)
        if -1 in pos or pos != sorted(pos):
            E(f"结尾顺序不对：{list(zip(eo, pos))}")
    hc = notes.get("half_close")
    if hc:
        hs = [r for r in rows if hc in r[3]]
        if not hs:
            E(f"找不到大问题先关一半的那句「{hc}」")
        else:
            pct = hs[0][0] / total
            info.append(f"大问题先关一半「{hc}」在 {hs[0][0]:.1f}s = {pct:.0%}")
            if not 0.40 <= pct <= 0.60:
                E(f"大问题先关一半在 {pct:.0%} 处，要在 40%–60%")
    return errs, warns, info


def main():
    ap = argparse.ArgumentParser(description="剧本结构自查（第 2 步）")
    ap.add_argument("script", help="剧本 JSON（同目录要有 episode.json）")
    ap.add_argument("--timeline", help="voice.py 输出的 timeline.json：所有和时间有关的检查按真实时间线算")
    a = ap.parse_args()
    errs, warns, info = run(a.script, a.timeline)
    for x in info:
        print("  " + x)
    for w in warns:
        print("  ⚠ " + w)
    for e in errs:
        print("  ✗ " + e)
    print(f"script_check：{'通过' if not errs else '有 ' + str(len(errs)) + ' 处错误'}，{len(warns)} 条警告")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
