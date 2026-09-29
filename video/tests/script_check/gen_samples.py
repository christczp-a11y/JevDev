"""生成 script_check 的测试样例（改了要重新生成：python video/tests/script_check/gen_samples.py）。
ok.json 是一版迷你的合格剧本（三关、四次考你、视角人物段规在每一关都出现）；bad_*.json 每份只坏一处（个别会连带别的错，测试只认它该报的那一条）；warn_*.json 只应该有警告；
*_timeline.json 是配套的真实时间线（voice.py 输出的格式的最小子集）。episode.json 提供 cast 和 banned。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
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
    ("旁白", "冲过来！智伯气坏了。", "三面旗子围上来；智伯气得鬓发竖起（笑点）；段规站在韩康子身后", 0),                               # 21
    ("旁白", "答案先揭一半：他以为大家都怕他！", "大问题横幅翻开一半", 0),                                    # 22
    ("旁白", "好心是队长。", "（金句 2/3）", 0),                                                           # 23
    ("旁白", "第 3 关，最难：反！", "第 3 关；段规站在韩康子身后", 0),                                       # 24
    ("智伯", "哈哈！水能灭国！", "智伯站在战车上大笑", 0),                                                  # 25
    ("动作", "", "魏桓子碰了一下韩康子的胳膊肘（笑点）", 1.5),                                              # 26
    ("司马光", "考你：他俩说什么？", "（考你 4/4）【咱们也怕】", 0),                                        # 27
    ("动作", "", "停 1.8 秒：倒计时转圈、滴答声；不揭晓", 1.8),                                             # 28
    ("司马光", "看答案！", "【咱们也怕】亮起", 0),                                                          # 29
    ("旁白", "他俩想的是：咱们也怕！", "两人身后各浮出一座城", 0),                                           # 30
    ("旁白", "段规说过：等着变。这个变，来了！", "段规微微点头（艺术化演绎）", 0),                             # 31
    ("动作", "", "大水冲垮营帐；智伯鬓发湿成一团（笑点）", 2.0),                                             # 32
    ("旁白", "智伯大败，智家没了！", "智伯的旗子倒在水里", 0),                                              # 33
    ("旁白", "五十年后，周王把韩、赵、魏三家的后代封为诸侯。", "周王宫；三面旗子", 0),                        # 34
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
    (HERE / name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


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


def main():
    (HERE / "episode.json").write_text(json.dumps(EP, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = mk("ok.json")
    w("ok_timeline.json", timeline(ok))
    # 剧本估算没问题，真实时间线里第 3 句（大问题）起后移，让它 7.3 秒才念完
    w("bad_timeline_bigq_timeline.json", timeline(ok, 3, round(7.3 - ok["lines"][3][1], 2)))
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
    mk("bad_ending_order.json", {34: ("旁白", "下集预告：一个下雨天的约会。", ROWS[34][2], 0), 39: ("旁白", "五十年后，周王把韩、赵、魏三家的后代封为诸侯。", ROWS[39][2], 0)})
    # ---- 只应该有警告（退出码 0）
    mk("warn_long_line.json", {4: ("旁白", "智伯本事大，可对人不好，智家会没！他到处要地。", ROWS[4][2], 9.0)})


if __name__ == "__main__":
    main()
