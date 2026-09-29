"""storyboard_jev.py 的测试数据（合成的）：重写 voice/timeline.json 和 storyboard.json。
    python video/motion/tests/jev_case/make_case.py
素材用 check_case 的测试图和测试登记表（test_storyboard_jev.py 会生成）。g = 好镜头，b1 b2 = 主体不对，s1 s2 = 吓人，m1 = 网络烂梗，b3 = 孩子看不懂。"""
import json
from pathlib import Path
D = Path(__file__).resolve().parent
LINES = [
 ("旁白", "宴会上，智伯举着杯子哈哈大笑，当众取笑韩康子。"),
 ("智伯", "韩康子，给我一座城！"),
 ("旁白", "韩康子很为难，抱着地图卷，不想给。"),
 ("旁白", "智伯有五样本事，样样比别人强！"),
 ("旁白", "韩康子低着头，眼泪汪汪，一句话也不敢说。"),
 ("旁白", "智伯被杀了，血流了一地，尸体倒在河边。"),
 ("旁白", "河水冲进营帐，好多士兵掉进水里，被淹死了，再也没有上来。"),
 ("旁白", "智伯这一波，简直是 PUA，太绝绝子了，直接 yyds！"),
 ("司马光", "这就像同桌天天要你的零食，你烦不烦？"),
 ("旁白", "夫才与德异，而世俗莫之能辨，通谓之贤。"),
 ("旁白", "智伯很生气，气得头发都竖起来了！"),
]
t, lines = 0.3, []
for i, (who, text) in enumerate(LINES):
    d = 3.2
    lines.append({"t0": round(t, 3), "t1": round(t + d, 3), "who": who, "text": text, "audio": None, "voiced_end": round(d - 0.4, 3), "i": i})
    t += d + 0.3
(D / "voice" / "timeline.json").write_text(json.dumps({"duration": round(t, 3), "lines": lines, "note": "合成的时间线（storyboard_jev 的测试用，没有音频）"}, ensure_ascii=False, indent=1), encoding="utf-8")

sky = {"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080}
def A(pid, who, pose, x, h, note, flip=False):
    a = {"id": pid, "who": who, "img": f"chars/{pid}_{pose}.png", "pos": [x, 1560], "h": h, "note": note}
    if flip:
        a["flip"] = True
    return a
def stk(line, text, dt=0.6):
    return {"type": "sticker", "text": text, "pos": [840, 700], "at": {"line": line, "dt": dt}, "size": 180}
SHOTS = [
 ("g1", 0, "medium", [A("zb", "智伯", "point", 330, 440, "跪坐，举着酒杯仰头哈哈大笑"), A("hkz", "韩康子", "low", 760, 300, "跪坐，低着头，眼泪汪汪", True)], [stk(0, "哈")], None),
 ("g2", 1, "medium", [A("zb", "智伯", "grab", 330, 440, "跪坐，一手摊开要东西，下巴抬得高高的"), A("hkz", "韩康子", "low", 760, 300, "跪坐，缩着肩膀", True)], [], None),
 ("g3", 2, "close", [A("hkz", "韩康子", "give", 400, 460, "跪坐，抱着地图卷，咬牙为难"), A("zb", "智伯", "point", 850, 240, "站在后面看着", True)], [], None),
 ("b1", 3, "close", [A("zxz", "赵襄子", "kneel", 400, 540, "端坐不动，双手放膝上"), A("hkz", "韩康子", "low", 850, 260, "跪坐在旁边", True)], [], None),
 ("b2", 4, "close", [A("zb", "智伯", "point", 400, 560, "叉腰哈哈大笑"), A("hkz", "韩康子", "low", 850, 240, "缩在角落里", True)], [], None),
 ("s1", 5, "medium", [A("zb", "智伯", "angry", 540, 440, "倒在地上，身下一大摊红色的血")], [], "河边，地上都是血，智伯的眼睛发着红光"),
 ("s2", 6, "wide", [], [], "大水冲垮营帐，水里漂着士兵的尸体，有人在水里挣扎"),
 ("m1", 7, "medium", [A("zb", "智伯", "stand", 540, 470, "叉腰得意大笑")], [stk(7, "躺平"), stk(7, "yyds", 1.2)], None),
 ("g4", 8, "medium", [A("sgm", "司马光", "finger", 400, 520, "举起食指讲道理")], [stk(8, "咚")], None),
 ("b3", 9, "close", [A("sgm", "司马光", "thumb", 540, 480, "翻开一本书")], [], "书上是密密麻麻的文言文"),
 ("g5", 10, "close", [A("zb", "智伯", "angry", 540, 520, "气得头发根根竖起，握拳咬牙（搞笑）")], [stk(10, "怒")], None),
]
shots = []
for sid, line, size, actors, fx, note in SHOTS:
    s = {"id": sid, "from": {"line": line, "dt": -0.3 if line == 0 else 0.0}, "size": size, "bg": [sky], "actors": actors, "fx": fx}
    if note:
        s["note"] = note
    shots.append(s)
sb = {"episode": "tj01", "no": 1, "title": ["最强的智伯，", "为什么输了？"], "voice": "video/motion/tests/jev_case/voice",
      "note": "storyboard_jev 的测试数据：g = 好镜头（一项都不该标）；b1、b2 = 主体不对；s1、s2 = 吓人（血、尸体）；m1 = 网络烂梗；b3 = 孩子看不懂（文言文）。",
      "shots": shots}
lines_out = ["{"]
for k, v in sb.items():
    if k == "shots":
        lines_out.append(' "shots": [')
        lines_out += ["  " + json.dumps(s, ensure_ascii=False) + ("," if i + 1 < len(v) else "") for i, s in enumerate(v)]
        lines_out.append(" ]")
    else:
        lines_out.append(f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},")
lines_out.append("}")
(D / "storyboard.json").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
print("ok", len(shots))
