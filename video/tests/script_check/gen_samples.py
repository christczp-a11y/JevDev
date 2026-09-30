"""生成 script_check 的测试样例（改了要重新生成：python video/tests/script_check/gen_samples.py）。
ok.json 是一版迷你的合格剧本（三关、四次考你、视角人物段规在每一关都出现）；bad_*.json 每份只坏一处（个别会连带别的错，测试只认它该报的那一条）；warn_*.json 只应该有警告；
*_timeline.json 是配套的真实时间线（voice.py 输出的格式的最小子集）。episode.json 提供 cast 和 banned。
structure/<目录>/ 是用了 episode.json 的 structure 字段的样例（每个目录一份 episode.json = 一种结构设置，目录里的剧本共用它）：
  vote/ 是 tj01 新结构（开头不考你、只有一次弹幕投票、不停顿、金句一次、大问题晚一点）；no_ceremony/、golden_max4/、two_levels/、pov_any/、pause_two/ 各改一个键；
  bad_keys/ 是写错的 structure；partial/ 只写了一个键（别的用默认值）。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KAO = "考考你！"
EP = {"core_question": "测试",
      "cast": {"智伯": {"voice": "zh-CN-YunjianNeural"}, "段规": {"voice": "zh-CN-YunxiaNeural"}, "赵襄子": {"voice": "zh-CN-YunyangNeural"}},
      "banned": {"知伯": "异名，通鉴写智伯", "豫让": "暴力情节整段跳过"}}

# (谁, 台词, 画面, 秒数)；秒数写 0 表示按字数估（每字 0.3 秒 + 0.5）。下标要和 V 里的常量对上。
ROWS = [
    ("司马光", "考考你！", "司马光弹出来（笑点：青蛙「呱」）", 1.2),                                        # 0
    ("旁白", "给不给？", "屏幕弹出大字「有人要地」和【给】【不给】", 1.0),                                     # 1
    ("动作", "", "停 1 秒（考你 1/4）：倒计时转圈、滴答声；不揭晓", 1.0),                                     # 2
    ("旁白", "最强的智伯，为什么输了？", "大问题横幅", 2.0),                                                  # 3
    ("旁白", "智伯本事大，可对人不好，智家会没！", "五个图标亮起", 0),                                       # 4
    ("旁白", "他的意思就是：好心是队长。", "（金句 1/3）", 0),                                              # 5
    ("旁白", "宴会上，智伯取笑韩康子。", "第 1 关：忍。横幅「第 1 关」；段规攥着袖子", 0),                     # 6
    ("动作", "", "智伯把自己的杯子碰倒了（笑点）", 1.5),                                                   # 7
    ("司马光", "考你：智伯听不听劝？", "（考你 2/4）【听】【不听】", 0),                                     # 8
    ("动作", "", "停 1.2 秒：倒计时转圈、滴答声；不揭晓", 1.2),                                             # 9
    ("司马光", "看答案！", "【不听】亮起", 0),                                                             # 10
    ("智伯", "不听！我不惹事！", "一只蚂蚁爬上他的鞋（笑点）", 0),                                           # 11
    ("旁白", "第 2 关：要地。", "第 2 关：给。段规拉住韩康子", 0),                                          # 12
    ("段规", "给他！", "段规凑到韩康子耳边", 0),                                                           # 13
    ("赵襄子", "不给。", "赵襄子端坐不动", 0),                                                             # 14
    ("动作", "", "全场一静，只有青蛙「呱」了一声（笑点）", 1.0),                                             # 15
    ("司马光", "看答案！", "【给】亮起；接着【不给】亮起", 0),                                               # 16
    ("旁白", "给的，是韩、魏；不给的，是赵襄子。", "「计」字纸牌翻开", 0),                                    # 17
    ("司马光", "考你：智伯会怎么办？", "（考你 3/4）【算了】【冲过来】", 0),                                 # 18
    ("动作", "", "停 1.2 秒：倒计时转圈、滴答声；不揭晓", 1.2),                                             # 19
    ("司马光", "看答案！", "【冲过来】亮起", 0),                                                           # 20
    ("智伯", "冲过来！气死我了！", "三面旗子围上来；智伯气得鬓发竖起（笑点）；段规站在韩康子身后", 0),                               # 21
    ("旁白", "答案先揭一半：他以为大家都怕他！", "大问题横幅翻开一半", 0),                                    # 22
    ("旁白", "好心是队长。", "（金句 2/3）", 0),                                                           # 23
    ("旁白", "第 3 关，最难：反！", "第 3 关；段规站在韩康子身后", 0),                                       # 24
    ("智伯", "哈哈！水能灭国！", "智伯站在战车上大笑", 0),                                                  # 25
    ("动作", "", "魏桓子碰了一下韩康子的胳膊肘（笑点）", 1.5),                                              # 26
    ("司马光", "考你：他俩说什么？", "（考你 4/4）【咱们也怕】", 0),                                        # 27
    ("动作", "", "停 1.8 秒：倒计时转圈、滴答声；不揭晓", 1.8),                                             # 28
    ("司马光", "看答案！", "【咱们也怕】亮起", 0),                                                          # 29
    ("段规", "咱们也怕！", "两人身后各浮出一座城", 0),                                           # 30
    ("旁白", "段规说过：等着变。这个变，来了！", "段规微微点头（艺术化演绎）", 0),                             # 31
    ("动作", "", "大水冲垮营帐；智伯鬓发湿成一团（笑点）", 2.0),                                             # 32
    ("智伯", "我败了！智家没了！", "智伯的旗子倒在水里", 0),                                              # 33
    ("旁白", "五十年后，三家的后代封为诸侯。", "周王宫；三面旗子", 0),                        # 34
    ("旁白", "写书的人，来了——", "画面压暗", 0),                                                           # 35
    ("司马光", "才者，德之资也；德者，才之帅也。", "司马光手指点在书页上", 0),                                 # 36
    ("旁白", "意思就是：好心是队长。", "（金句 3/3）", 0),                                                   # 37
    ("动作", "", "一只青蛙跳上书页（笑点）", 1.5),                                                          # 38
    ("旁白", "下集预告：一个下雨天的约会。", "问号纸牌翻出：雨点", 0),                                       # 39
]
NOTES = {"pov": "段规", "big_question": "最强的智伯，为什么输了？", "golden": "好心是队长。", "half_close": "答案先揭一半",
         "stake_line": "智家会没", "level_starts": [6, 12, 24],
         "ending_order": ["封为诸侯", "写书的人，来了", "德者，才之帅也", "下集"]}


def build(rows, notes=None):
    """秒数：写了就用，没写（0）按字数估；开头留白 0.3，句间 0.3。"""
    t, lines = 0.3, []
    for who, text, vis, d in rows:
        n = len("".join(c for c in text if c.isalnum()))
        d = d or round(0.5 + 0.3 * n, 2)
        lines.append([round(t, 2), round(t + d, 2), who, text, vis])
        t += d + 0.3
    nt = dict(NOTES)
    nt.update(notes or {})
    return {"id": "T", "name": "测试", "title": ["测试"], "notes": nt, "lines": lines}


def timeline(d, shift_from=None, shift=0.0):
    """配套的真实时间线：每句和剧本一样，可以从第 shift_from 句起整体后移 shift 秒。"""
    out = []
    for i, (t0, t1, who, text, vis) in enumerate(d["lines"]):
        s = shift if (shift_from is not None and i >= shift_from) else 0.0
        out.append({"i": i, "t0": round(t0 + s, 2), "t1": round(t1 + s, 2), "who": who, "text": text, "visual": vis})
    return {"duration": round(out[-1]["t1"] + 0.5, 2), "lines": out}


def w(name, d):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def mk(name, edits=None, notes=None, drop_level_starts=False):
    """edits：{下标: (谁, 台词, 画面, 秒数)}，只改这几句；再在 notes 里覆盖备注。"""
    rows = [list(r) for r in ROWS]
    for i, r in (edits or {}).items():
        rows[i] = list(r)
    d = build(rows, notes)
    if drop_level_starts:
        d["notes"].pop("level_starts")
    w(name, d)
    return d


# ---- structure 样例：从 ROWS 改出来的新结构剧本
# 新结构（tj01 的新剧本）：开头不考你（第一句是钩子）、一集只有一次弹幕投票（第 2 关）、不停顿、没有「看答案！」、金句只说一次（点题之后的白话翻译）、大问题晚一点念完。
# 下标是 ROWS 的下标：值 None = 删掉这一句；元组 = 换成这一句。
VOTE_EDIT = {
    0: ("司马光", "最强的智伯，被浇成了落汤鸡！", "智伯被大水浇成落汤鸡（笑点）", 2.5),
    1: ("旁白", "两千四百年前，晋国最强的人，就是他。", "日历飞速倒翻", 3.8),
    2: None,                                                                          # 开头的停顿
    3: ("旁白", "最强的智伯，为什么输了？", "大问题横幅", 2.2),                                    # 大问题晚一点念完（9.4 秒）：默认的 7.3 秒过不了，structure.bigq_by = 10 才过
    5: ("司马光", "可是他对人不好。", "（铺垫）", 0),                                   # 金句只留最后一次
    8: ("段规", "主公，听我一句！", "段规拉了拉智伯的袖子", 0),                         # 第 1 关的「考你」换成对话
    9: None, 10: None, 16: None,                                                       # 停顿、看答案
    18: ("司马光", "智伯怒了，要动手了！", "司马光探头", 0),
    19: None, 20: None,
    23: ("司马光", "他以为自己最大！", "（铺垫）", 0),
    27: ("司马光", "他俩心里，也慌了！", "司马光探头", 0),
    28: None, 29: None,
}
VOTE_INSERT = {15: [("司马光", "考考你：给还是不给？弹幕告诉我！", "司马光举牌定格，弹幕飘过", 4.0)]}   # 全集唯一一次考你（弹幕投票）
S_VOTE = {"opening_quiz": False, "quiz_count": 1, "quiz_pause": False, "golden_count": 1, "golden_max_chars": 12,
          "bigq_by": 10, "levels": 3, "pov_every_level": True}


def derive(plan, ins=None, notes=None):
    """plan / ins 见 VOTE_EDIT / VOTE_INSERT；level_starts 自动按画面里的「第 N 关」找。"""
    rows = []
    for i, r in enumerate(ROWS):
        r = plan.get(i, r)
        if r is not None:
            rows.append(list(r))
        rows.extend(list(x) for x in (ins or {}).get(i, []))
    nt = {"level_starts": [next(k for k, r in enumerate(rows) if f"第 {n} 关" in r[2]) for n in (1, 2, 3)]}
    nt.update(notes or {})
    return build(rows, nt)


def vote(edit=None, insert=None, notes=None):
    return derive({**VOTE_EDIT, **(edit or {})}, {**VOTE_INSERT, **(insert or {})}, notes)


def sdir(name, structure):
    """structure/<name>/episode.json：和 EP 一样，再加一个 structure 字段。"""
    w(f"structure/{name}/episode.json", {**EP, "structure": structure})
    return f"structure/{name}/"


def main():
    (HERE / "episode.json").write_text(json.dumps(EP, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = mk("ok.json")
    w("ok_timeline.json", timeline(ok))
    # 剧本估算没问题；真实时间线里第 3 句（大问题）起后移：7.5 秒才念完 = 超过 7.0 + 容差 0.3；7.3 秒正好在容差边上，算过
    w("bad_timeline_bigq_timeline.json", timeline(ok, 3, round(7.5 - ok["lines"][3][1], 2)))
    w("ok_timeline_edge_timeline.json", timeline(ok, 3, round(7.3 - ok["lines"][3][1], 2)))
    # ---- 每份只坏一处
    mk("bad_bigq_late.json", {1: ("旁白", "有人跟你要地，你给不给，你再想想？", ROWS[1][2], 3.6)})
    mk("bad_pov_missing.json", {24: ("旁白", "第 3 关，最难：反！", "第 3 关；城头一片水", 0), 31: ("旁白", "说过：等着变。这个变，来了！", "两人点头（艺术化演绎）", 0)})
    mk("bad_level_two_asks.json", {12: ("司马光", "考你：他会笑吗？", "（考你 2/4）第 2 关：给。【会】【不会】", 0), 13: ("动作", "", "停 1.2 秒：倒计时转圈、滴答声；不揭晓", 1.2)})
    mk("bad_level_no_ask.json", {18: ("旁白", "智伯想了想。", "智伯低头", 0), 19: ("动作", "", "智伯抬起头", 1.2), 20: ("旁白", "他冲过来！", "三面旗子围上来", 0)})
    mk("bad_reveal_no_answer.json", {11: ("智伯", "我不惹事！", "一只蚂蚁爬上他的鞋（笑点）", 0)})
    mk("bad_reveal_no_label.json", {10: ("司马光", "看答案！", "亮起的是第二个按钮", 0)})
    mk("bad_reveal_open_second.json", {17: ("旁白", "给的，是韩、魏；赵襄子躲进晋阳。", "「计」字纸牌翻开", 0)})
    mk("bad_gag_gap.json", {7: ("动作", "", "智伯把杯子碰倒了", 1.5), 11: ("智伯", "不听！我不惹事！", "他哈哈大笑", 0), 15: ("动作", "", "全场一静", 1.0),
                            21: ("旁白", ROWS[21][1], "三面旗子围上来；段规站在韩康子身后", 0), 26: ("动作", "", "魏桓子碰了一下韩康子的胳膊肘", 1.5), 32: ("动作", "", "大水冲垮营帐", 2.0)})
    mk("bad_version_residual.json", {36: ("司马光", ROWS[36][1], "司马光接住毛笔（警枕版：捧着书）", 0)})
    mk("bad_prop_first.json", {36: ("司马光", ROWS[36][1], "司马光接住毛笔，手指点在书页上", 0)})
    mk("ok_prop_introduced.json", {34: ("旁白", ROWS[34][1], "周王宫；一支毛笔「咻」地飞出来", 0), 36: ("司马光", ROWS[36][1], "司马光接住毛笔，手指点在书页上", 0)})
    mk("bad_pauses.json", {28: ("动作", "", "停 2.5 秒：倒计时转圈、滴答声；不揭晓", 2.5)})
    mk("bad_male_run.json", {12: ("智伯", "第 2 关：要地。", ROWS[12][2], 0)})
    mk("bad_golden_count.json", {23: ("旁白", "好心很重要。", "（金句 2/3）", 0)})
    mk("bad_ceremony_first.json", {0: ("旁白", "考考你！", ROWS[0][2], 1.2)})
    mk("bad_xie_embedded.json", {35: ("旁白", "这个故事，写在通鉴里。写书的人，来了——", ROWS[35][2], 0)})
    # 赌注按「念完」算：开口 < 20 秒但念完 > 20 秒也不行
    mk("bad_stake_end_late.json", {4: ("旁白", ROWS[4][1], ROWS[4][2], 16.0)})
    mk("bad_no_stake_note.json", notes={"stake_line": ""})
    # 点题（德者，才之帅也）之后 1–2 句里没有金句 = 没有白话翻译
    mk("bad_dian_no_translation.json", {37: ("旁白", "他的意思很深。", ROWS[37][2], 0)})
    mk("bad_no_dian_line.json", {36: ("司马光", "才者，德之资也。", ROWS[36][2], 0)})
    mk("ok_dian_key_custom.json", {36: ("司马光", "君子挟才以为善。", ROWS[36][2], 0)}, notes={"dian_key": "挟才以为善", "ending_order": ["封为诸侯", "写书的人，来了", "挟才以为善", "下集"]})
    # 第 3 关的终点：默认到「写书的人，来了——」之前；notes.level_end_key 可以指定别的句子（这里「五十年后」那一句）
    late_pov = {24: ("旁白", ROWS[24][1], "第 3 关；城头一片水", 0), 31: ("旁白", "他说过：等着变。这个变，来了！", "两人点头（艺术化演绎）", 0)}
    late_pov[34] = ("旁白", ROWS[34][1], "周王宫；三面旗子；段规在旁边看着", 0)
    mk("ok_level_end_default.json", late_pov)
    mk("bad_level_end_key.json", late_pov, notes={"level_end_key": "五十年后"})
    mk("bad_stake_late.json", {4: ("旁白", "智伯本事大，可对人不好，他很麻烦！", ROWS[4][2], 0), 12: ("旁白", "第 2 关：要地。智家会没！", ROWS[12][2], 0)},
       notes={"stake_line": "智家会没"})
    mk("bad_banned.json", {11: ("智伯", "不听！知伯不惹事！", ROWS[11][2], 0)})
    mk("bad_no_level_starts.json", drop_level_starts=True)
    mk("bad_levelstarts_shifted.json", notes={"level_starts": [7, 12, 24]})
    mk("bad_no_pov_note.json", notes={"pov": ""})
    mk("bad_half_close_pos.json", {22: ("旁白", "他以为大家都怕他！", ROWS[22][2], 0), 37: ("旁白", "答案先揭一半：意思就是：好心是队长。", ROWS[37][2], 0)})
    mk("bad_speaker_no_voice.json", {13: ("魏桓子", "给他！", ROWS[13][2], 0)})
    mk("bad_fast.json", {1: ("旁白", "给不给给不给给不给给不给给不给？", ROWS[1][2], 1.0)})
    mk("bad_then.json", {4: ("旁白", "然后智伯本事大，可对人不好，智家会没！", ROWS[4][2], 0)})
    mk("bad_ending_order.json", {34: ("旁白", "下集预告：一个下雨天的约会。", ROWS[34][2], 0), 39: ("旁白", ROWS[34][1], ROWS[39][2], 0)})
    # ---- 只应该有警告（退出码 0）
    # 单句超过 15 字（去掉标点）：16 字警告；15 字不警告
    mk("warn_long_chars.json", {5: ("旁白", "他的意思其实就是这个啊：好心是队长。", ROWS[5][2], 0)})
    mk("ok_edge_15chars.json", {5: ("旁白", "他的意思其实就是这个：好心是队长。", ROWS[5][2], 0)})
    # 旁白句数占全部台词的一半以上：把三句角色台词改回旁白（15 → 18 句 / 31 句 = 58%）
    mk("warn_narration_heavy.json", {13: ("旁白", ROWS[13][1], ROWS[13][2], 0), 14: ("旁白", ROWS[14][1], ROWS[14][2], 0), 25: ("旁白", ROWS[25][1], ROWS[25][2], 0)})
    # Qwen 的 cast 没有 voice 字段、只有 desc（声音描述）：三个角色 desc 不同 = 合格；两个角色 desc 一样 = 同一个声音
    qdir = HERE / "qwen"
    qdir.mkdir(exist_ok=True)
    qep = {"core_question": "测试", "banned": EP["banned"],
           "cast": {"智伯": {"desc": "四十多岁的男性贵族，嗓音洪亮，自信傲慢"}, "段规": {"desc": "三十多岁的男性谋士，嗓音偏细，克制隐忍"},
                    "赵襄子": {"desc": "三十多岁的男性诸侯，嗓音沉稳，平静从容"}}}
    (qdir / "episode.json").write_text(json.dumps(qep, ensure_ascii=False, indent=1), encoding="utf-8")
    (qdir / "ok_qwen.json").write_text(json.dumps(build([list(r) for r in ROWS]), ensure_ascii=False, indent=1), encoding="utf-8")
    qep["cast"]["赵襄子"] = dict(qep["cast"]["智伯"])
    (qdir / "bad_same_desc").mkdir(exist_ok=True)
    (qdir / "bad_same_desc" / "episode.json").write_text(json.dumps(qep, ensure_ascii=False, indent=1), encoding="utf-8")
    (qdir / "bad_same_desc" / "bad_same_desc.json").write_text(json.dumps(build([list(r) for r in ROWS]), ensure_ascii=False, indent=1), encoding="utf-8")
    mk("warn_long_line.json", {4: ("旁白", "智伯本事大，可对人不好，智家会没！", ROWS[4][2], 9.0)})
    # ---- 说话人写成 A+B+C（几个人齐声）：逐个查声音；全是男声才算一句男声
    mk("ok_chorus.json", {30: ("段规+赵襄子", ROWS[30][1], ROWS[30][2], 0)})
    mk("bad_chorus_no_voice.json", {30: ("段规+魏桓子", ROWS[30][1], ROWS[30][2], 0)})
    mk("bad_chorus_male_run.json", {12: ("智伯+段规", ROWS[12][1], ROWS[12][2], 0)})
    # ---- 用了 episode.json 的 structure
    d = sdir("vote", S_VOTE)
    ok_vote = vote()
    w(d + "ok_vote.json", ok_vote)
    w(d + "ok_vote_timeline.json", timeline(ok_vote))
    # 真实时间线里大问题（第 bi 句）起后移：10.5 秒才念完 = 超过 10 + 容差 0.3；10.3 秒正好在容差边上，算过
    bi = next(i for i, r in enumerate(ok_vote["lines"]) if r[3] == NOTES["big_question"])
    w(d + "bad_bigq_timeline.json", timeline(ok_vote, bi, round(10.5 - ok_vote["lines"][bi][1], 2)))
    w(d + "ok_bigq_edge_timeline.json", timeline(ok_vote, bi, round(10.3 - ok_vote["lines"][bi][1], 2)))
    quiz8 = ("司马光", "考你：智伯听不听劝？", "（考你）【听】【不听】", 0)
    quiz27 = ("司马光", "考你：他俩说什么？", "（考你）【咱们也怕】", 0)
    w(d + "bad_three_quizzes.json", vote({8: quiz8, 27: quiz27}))
    w(d + "bad_pause_and_reveal.json", vote({9: ("动作", "", "停 1.2 秒：倒计时转圈、滴答声；不揭晓", 1.2), 10: ("司马光", "看答案！", "【不听】亮起", 0)}))
    w(d + "bad_opening_quiz.json", vote({0: ("司马光", KAO, "司马光弹出来（笑点）", 1.2)}))
    w(d + "bad_bigq_late.json", vote({1: (*VOTE_EDIT[1][:3], 5.5)}))
    w(d + "bad_golden_twice.json", vote({23: ("旁白", "好心是队长。", "（金句）", 0)}))
    # 结尾没有「写书的人，来了——」：默认要报错；ending_ceremony 为 false 就不查
    no_xie = vote({35: None}, notes={"ending_order": ["封为诸侯", "德者，才之帅也", "下集"]})
    w(d + "bad_no_ceremony.json", no_xie)
    d = sdir("no_ceremony", {**S_VOTE, "ending_ceremony": False})
    w(d + "ok_no_ceremony.json", no_xie)
    d = sdir("golden_max4", {**S_VOTE, "golden_max_chars": 4})
    w(d + "bad_golden_long.json", ok_vote)
    d = sdir("two_levels", {**S_VOTE, "levels": 2})
    starts = ok_vote["notes"]["level_starts"]
    w(d + "ok_two_levels.json", vote(notes={"level_starts": starts[:2]}))
    w(d + "bad_levels_mismatch.json", ok_vote)
    d = sdir("pov_any", {**S_VOTE, "pov_every_level": False})
    w(d + "ok_pov_not_every.json", vote({24: ("旁白", ROWS[24][1], "第 3 关；城头一片水", 0), 31: ("旁白", "说过：等着变。这个变，来了！", "两人点头（艺术化演绎）", 0)}))
    w(d + "bad_pov_nowhere.json", vote(notes={"pov": "张孟谈"}))
    d = sdir("pause_two", {"quiz_count": 2})
    drop = {8: None, 9: None, 10: None, 27: None, 28: None, 29: None}            # 留下开头一次和第 2 关一次
    w(d + "ok_pause_two.json", derive(drop))
    w(d + "bad_pause_count.json", build([list(r) for r in ROWS]))
    w(d + "bad_pause_range.json", derive({**drop, 19: ("动作", "", "停 2.5 秒：倒计时转圈、滴答声；不揭晓", 2.5)}))
    d = sdir("bad_keys", {"quiz_cnt": 1, "quiz_count": "1", "quiz_pause": 0, "bigq_by": -3, "levels": 0})
    w(d + "bad_keys.json", build([list(r) for r in ROWS]))
    d = sdir("partial", {"golden_count": 1})
    w(d + "bad_partial.json", build([list(r) for r in ROWS]))


if __name__ == "__main__":
    main()
