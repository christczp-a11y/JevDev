"""第 1 集《一根木头，怎么让秦国人开始相信？》整集：按配音时间线排出 7 场戏 → 逐场渲染 → 拼接 → 混音（配音 + 背景音乐 + 音效）。

先跑配音：python video/voice.py video/stories/ep01/N5_最终.json video/out/ep01_voice 14=2.0 15=6.5
再跑本脚本：python video/build_ep01.py [--only 场号,...] [--no-render]
  --no-render 只写出每场的剧本（video/scenes/ep01/*.json），不渲染；--only 2,3 只渲染这几场（其余沿用已渲染的片段）

每场戏是一个独立剧本（自己的时间从 0 开始），场与场之间整条画面像纸片一样翻过去。
小伙用纸偶关节动画（和测试片段同一套动作，整体平移到这一集的时间）；其他角色是 Codex 画的整身姿势图，
靠弹出、换姿势时的挤压回弹、说话时的起伏、摇头点头来表演。
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
VOICE = ROOT / "out/ep01_voice"
OUT = ROOT / "out/ep01"
SCENES = ROOT / "scenes/ep01"
BGM = Path.home() / "MoneyPrinterTurbo/resource/songs/output009.mp3"   # MPT 自带曲库（来源不明，仅内部预览，发布前必须换）
TITLE = {"kicker": "资治通鉴 · 第 1 集", "lines": ["一根木头，怎么让", "秦国人开始[[相信]]？"]}
FOOTER = "徙木立信 · 出自《资治通鉴》卷二"
LABEL = {"农夫": "爹"}   # 字幕上显示的说话人

TL = json.loads((VOICE / "timeline.json").read_text(encoding="utf-8"))
L = TL["lines"]
T0 = lambda i: L[i]["t0"]
T1 = lambda i: L[i]["t1"]
mid = lambda i, j: round((T1(i) + T0(j)) / 2, 2)
# 场次边界：教室 | 第 1 关（集市） | 第 2 关（太子） | 第 3 关（十年） | 司马光 | 回教室 | 下集预告
B = [0, mid(1, 2), mid(21, 22), mid(26, 27), mid(29, 30), mid(31, 32), mid(32, 33), TL["duration"]]


def actor(x, pose, show, flip=1, px=0.42, speaker=None, native=1, phase=0.0, **kw):
    a = {"keys": [[0, x, "", flip]], "poses": [[0, pose]], "show": show, "px": px, "native": native, "phase": phase}
    if speaker:
        a["speaker"] = speaker
    a.update(kw)
    return a


def sprite(img, x, y, h, show, **kw):
    return {"type": "sprite", "img": img, "x": x, "y": y, "h": h, "show": show, **kw}


def subs(k):
    s0, s1 = B[k], B[k + 1]
    return [[round(x["t0"] - s0, 2), round(x["t1"] - s0, 2), LABEL.get(x["who"], x["who"]), x["text"]]
            for x in L if x["audio"] and s0 <= x["t0"] < s1]


def base(k, set_name, camera, hud, actors, props=(), events=()):
    d = round(B[k + 1] - B[k], 2)
    return {"about": f"第 1 集 · 第 {k + 1} 场", "duration": d, "title": TITLE, "footer": FOOTER, "set": set_name,
            "flip": [k > 0, k < len(B) - 2], "camera": camera, "hud": hud, "actors": actors,
            "props": list(props), "events": list(events), "subtitles": subs(k)}


def shot1():   # 现代教室：忘了带漫画书，同桌不信了
    S, r = B[0], lambda g: round(g - B[0], 2)
    end = B[1] - S
    return base(0, "classroom", [[0, 0], [end, 0]],
                {"label": "信用值", "hearts": 1, "credit": [[0, 1]], "crack": [[r(T1(1) - 1.0), 1e9]]},
                {"kid": actor(330, "kid_bag", [0.4, 99], px=0.6, speaker="小孩", phase=0.3),
                 # 同桌说「我可不信了」时整个人翻过去、背对小孩（扭头不理他）
                 "desk": actor(760, "desk_wait", [0.9, 99], flip=-1, native=-1, px=0.6, speaker="同桌", phase=1.1,
                               keys=[[0, 760, "", -1], [r(T0(1)), 760, "", 1]],
                               poses=[[0, "desk_wait"], [r(T0(1)), "desk_angry"]])},
                [sprite("school_desk", 545, 506, 175, [0.2, 99])],
                [{"type": "shake", "t": r(T1(1) - 1.0), "amp": 6}])


def youth(off):
    """纸偶小伙：测试片段 test_puppet_youth 的整套动作，整体平移 off 秒。"""
    sh = lambda v: round(v + off, 2)
    return {"speaker": "小伙", "phase": 0.3, "seed": 11, "rigs": {"side": "youth", "q": "youth_q"},
            "keys": [[sh(0), 60, "", 1], [sh(2.4), 560, "", 1], [sh(9.0), 560, "", 1], [sh(12.4), 1480, "", 1], [sh(40), 1480, "", 1]],
            "views": [[0, "side"], [sh(2.55), "q"], [sh(6.05), "side"], [sh(14.55), "q"]], "jumps": [],
            "actions": [[sh(2.6), sh(5.9), "talk"], [sh(5.1), sh(6.0), "fist"], [sh(6.1), sh(7.6), "reach", {"target": [632, 370], "stop": 0.8}],
                        [sh(6.3), sh(8.0), "look"], [sh(8.0), sh(8.9), "lift"], [sh(8.9), sh(12.7), "carry"], [sh(12.7), sh(13.8), "drop"],
                        [sh(13.55), sh(14.5), "lookup"], [sh(14.55), sh(15.2), "catch"], [sh(15.15), sh(18.6), "hug", {"hops": [[0.05, 1]]}],
                        [sh(18.45), sh(40), "hold"]]}   # 金子一直捧在怀里，直到这场戏结束


def shot2():   # 第 1 关：南门立木
    S = B[1]
    r = lambda g: round(g - S, 2)
    end = round(B[2] - S, 2)
    off = r(T0(13)) - 1.45           # 小伙在「我来」之前 1.45 秒开始走进画面
    lift = off + 8.0
    # 木杆 460 约 2.3 个人高（原先 740 约 4 个人高，Chris 说太长）；gB 后手握点按比例外移，两手间距不变
    # 站位规则：画框左边那棵大松树挡住画面左侧约 260 像素，人物和道具都要站在它右边
    sy_icons = [sprite("medal", 505, 300, 105, [r(T0(3)) + 2.2, r(T0(5))], sfx="pop", gray=r(T0(4)) + 1.8, text=[["奖", 0, 14, 44, "#c8372d"]]),
                sprite("token", 385, 300, 62, [r(T0(3)) + 3.4, r(T0(5))], sfx="pop", gray=r(T0(4)) + 3.6, text=[["罚", 0, 2, 44, "#c8372d"]]),
                sprite("bulb", 440, 250, 78, [r(T0(5)) - 0.1, r(T0(5)) + 1.9], sfx="pop")]
    return base(1, "qin_gate",
                [[0, -120], [r(T0(3)), 0], [r(T0(6)), 0], [r(T0(6)) + 2.0, 170], [lift + 1.0, 170], [lift + 5.0, 1060], [end, 1060]],
                {"label": "秦国信用值", "hearts": 3, "credit": [[0, 0], [off + 16.8, 1]],
                 "coins": [[0, None], [r(T0(7)) + 0.4, 10], [r(T0(11)) + 2.2, 50]]},
                {"shangyang": actor(440, "sy_scroll", [r(T0(3)), lift - 1.0], speaker="商鞅", phase=0.7,
                                    poses=[[0, "sy_scroll"], [r(T0(4)), "sy_worry"], [r(T0(5)), "sy_idea"], [r(T0(7)), "shangyang_point"]],
                                    shakes=[[r(T0(4)), r(T0(4)) + 1.2, 6]]),
                 "shangyang2": actor(1700, "shangyang_point", [off + 13.9, end], flip=-1, speaker="商鞅", phase=0.7,
                                     poses=[[0, "shangyang_point"], [r(T0(21)), "sy_raise"]]),
                 "douzi": actor(960, "douzi_gold", [r(T0(8)), r(T0(9))], flip=-1, px=0.25, speaker="小豆子", phase=0.2,
                                jumps=[[r(T0(8)) + 0.3, r(T0(8)) + 0.7, 26]]),
                 "dad": actor(1000, "dad_grab", [r(T0(9)), end], flip=-1, speaker="爹", phase=1.4,
                              poses=[[0, "dad_grab"], [r(T0(12)), "dad_cover"], [lift + 2.4, "dad_doubt"]]),
                 # 小伙抱着木杆从爹面前经过以后，小豆子才挣脱、跟在后面跑
                 "douzi2": {"keys": [[lift + 2.5, 960, "", 1], [lift + 5.0, 1360, "", 1], [end, 1360, "", 1]], "px": 0.25, "native": 1, "phase": 0.2,
                            "poses": [[0, "douzi_run"], [lift + 5.1, "douzi_gold"], [r(T0(17)), "douzi_puzzled"]],
                            "show": [lift + 2.4, end], "speaker": "小豆子",
                            "bubbles": [[r(T0(17)) + 0.6, r(T1(17)), "？"]]},
                 "auntie": actor(1920, "auntie_gossip", [r(T0(20)), end], flip=-1, px=0.38, speaker="大婶", phase=0.5),
                 "youth": {**youth(off), "show": [off - 0.1, end]}},
                [{"type": "pole", "x": 632, "height": 460, "thick": 18, "gB": [0.065, 0.12], "appear": r(T0(6)) + 2.1, "lift": [lift, lift + 0.9],
                  "drop": [lift + 4.7, lift + 5.8], "by": "youth"},
                 {"type": "board", "x": 810, "height": 170, "show": [r(T0(7)) + 0.3, end],
                  "texts": [[0, ["谁把木杆", "搬到北门", "!赏 十金"]], [r(T0(11)) + 2.2, ["谁把木杆", "搬到北门", "!赏 五十金"]]]},
                 sprite("crow", 830, 332, 58, [r(T0(10)), end], enter="fly", from_=None, say=[[r(T0(10)) + 0.7, r(T1(10)) + 0.3, "嘎——"]]),
                 *sy_icons],
                [{"type": "banner", "t": r(T0(6)) + 0.2, "d": 2.3, "text": "第 1 关：一根木杆"},   # 灯泡先亮，「有了！」说完横幅才落下
                 {"type": "shake", "t": r(T0(6)) + 2.3, "amp": 9},
                 {"type": "gold", "t": off + 14.4, "n": 5, "by": "youth", "seed": 4, "gap": 0.38},
                 {"type": "badges", "t0": r(T0(18)), "t1": r(T1(19)) + 0.3,
                  "items": [[r(T0(19)) + 0.1, "小事"], [r(T0(19)) + 2.35, "看得见"], [r(T0(19)) + 4.7, "当场给"]]},
                 {"type": "birds", "t": r(T0(20)) + 0.6, "n": 7, "text": "真给了！"},
                 {"type": "stamp", "t": r(T0(21)) + 1.1, "x": 540, "y": 200, "text": "过关！"}])


def shot3():   # 第 2 关：太子犯法（BOSS）
    S = B[2]
    r = lambda g: round(g - S, 2)
    end = round(B[3] - S, 2)
    cam = 1060
    gate_x = 1010 + cam * 0.45       # 中景视差 0.55：让太子帽正好在门洞里（换算成跟着镜头走的坐标）
    return base(2, "qin_gate", [[0, cam], [end, cam]],
                {"label": "秦国信用值", "hearts": 3, "credit": [[0, 1], [r(T0(26)) + 0.7, 2]]},
                {"crowd1": actor(1360, "auntie_hands", [r(T0(23)), end], px=0.38, enter="rise", y=150, phase=0.4),
                 "crowd2": actor(1500, "dad_doubt", [r(T0(23)) + 0.25, end], enter="rise", y=160, phase=1.0),
                 "douzi": actor(1760, "douzi_puzzled", [r(T0(23)) - 0.2, end], flip=-1, px=0.25, speaker="小豆子", phase=0.2,
                                poses=[[0, "douzi_puzzled"], [r(T0(26)), "douzi_shock"]]),
                 "shangyang": actor(1930, "sy_slam", [r(T0(24)), end], flip=-1, speaker="商鞅", phase=0.7,
                                    poses=[[0, "sy_slam"], [r(T1(24)) + 0.4, "shangyang_stand"]]),
                 "teachers": {"keys": [[0, gate_x, "", -1], [r(T0(25)) + 1.0, gate_x, "", -1], [r(T1(25)) + 1.5, 900, "", -1]],
                              "poses": [[0, "teachers"]], "px": 0.4, "native": 1, "phase": 0.9, "bob": 5,
                              "show": [r(T0(25)) + 0.6, end],
                              "bubbles": [[r(T0(25)) + 2.0, r(T0(25)) + 4.2, "啊？我们？"]]}},
                [sprite("prince_hat", gate_x, 486, 44, [r(T0(22)) + 4.0, end], layer="mid", enter="rise", bob=2)],
                [{"type": "banner", "t": 0.4, "d": 2.3, "text": "第 2 关：太子犯法"},
                 {"type": "boss", "t0": r(T0(22)) + 4.2, "t1": end, "hp": [[r(T0(22)) + 4.2, 1], [r(T0(25)) + 3.2, 1], [r(T0(25)) + 3.6, 0.12]]},
                 {"type": "shake", "t": r(T0(24)) + 0.35, "amp": 12}])


def shot4():   # 第 3 关：坚持十年
    S = B[3]
    r = lambda g: round(g - S, 2)
    end = round(B[4] - S, 2)
    return base(3, "qin_gate", [[0, 80], [end, 260]],
                {"label": "秦国信用值", "hearts": 3, "credit": [[0, 2], [r(T1(28)) - 0.3, 3]]},
                {"teen": {"keys": [[r(T0(28)) - 0.2, 250, "", 1], [r(T1(28)), 980, "", 1], [end, 980, "", 1]], "poses": [[0, "douzi_teen"]],
                          "px": 0.36, "native": 1, "phase": 0.3, "bob": 6, "show": [r(T0(28)) - 0.3, end]},
                 "dad": actor(1110, "dad_old", [r(T0(29)) - 0.3, end], flip=-1, speaker="爹", phase=1.2, nods=[[r(T0(29)), r(T1(29))]])},
                [sprite("bundle", 640, 512, 56, [r(T0(28)) - 0.4, end], enter="drop")],
                [{"type": "banner", "t": 0.3, "d": 2.2, "text": "第 3 关：坚持十年"},
                 {"type": "seasons", "t0": 2.5, "t1": r(T1(27)), "loops": 1}])


def shot5():   # 一千多年后：司马光从书里跳出来
    S = B[4]
    r = lambda g: round(g - S, 2)
    end = round(B[5] - S, 2)
    cam = 150
    # 书在司马光身后（人物后面那一层，用跟着镜头走的坐标）
    book = [sprite("big_book", 540 + cam, 560, 250, [r(T0(30)) + 2.2, end], sfx="pop"),
            sprite("big_book", 540 + cam, 560, 250, [r(T0(31)) + 3.4, end], enter="fade",
                   text=[["信者，", -96, -44, 42, "#2a2320"], ["人君之", -96, 2, 36, "#2a2320"], ["大宝也", -96, 46, 36, "#c8372d"]])]   # 字只写在左半页（右半页站着司马光和破缸）
    return base(4, "qin_gate", [[0, cam], [end, cam]],
                {"label": "秦国信用值", "hearts": 3, "credit": [[0, 3]]},
                {"sima": actor(610 + cam, "simaguang", [r(T0(31)), end], px=0.34, y=-70, speaker="司马光", phase=0.6,
                               jumps=[[r(T0(31)), r(T0(31)) + 0.55, 90]])},
                book,
                [{"type": "tint", "t0": -1, "t1": end + 1, "color": "#2a1f18", "a": 0.55, "under": True},
                 {"type": "shake", "t": r(T0(30)) + 2.3, "amp": 6}])


def shot6():   # 回到教室：说到做到
    S = B[5]
    r = lambda g: round(g - S, 2)
    end = round(B[6] - S, 2)
    return base(5, "classroom", [[0, 0], [end, 0]],
                {"label": "信用值", "hearts": 1, "credit": [[0, 1]], "crack": [[-1, r(T1(32)) - 0.8]]},
                {"kid": actor(360, "kid_give", [0.2, 99], px=0.6, speaker="小孩", phase=0.3),
                 "desk": actor(740, "desk_happy", [0.3, 99], flip=-1, native=-1, px=0.6, speaker="同桌", phase=1.1,
                               poses=[[0, "desk_wait"], [r(T1(32)) - 1.2, "desk_happy"]])},
                [sprite("school_desk", 545, 506, 175, [0.1, 99])])


def shot7():   # 下集预告
    S = B[6]
    r = lambda g: round(g - S, 2)
    end = round(B[7] - S, 2)
    return base(6, "qin_gate", [[0, 150], [end, 190]], None, {},
                [sprite("door", 540, 560, 330, [0.6, end + 1], layer="overlay", enter="fade")],
                [{"type": "tint", "t0": -1, "t1": end + 1, "color": "#140d0a", "a": 0.7},
                 {"type": "banner", "t": 0.3, "d": 2.4, "text": "下集预告", "color": "#3a2f2a"},
                 {"type": "eyes", "t0": r(T0(33)) + 3.6, "t1": end + 1, "x": 540, "y": 380, "slit": True}])


SHOTS = [shot1, shot2, shot3, shot4, shot5, shot6, shot7]


def fix_fly(scene):
    """乌鸦从右上方飞进来（from 是相对落点的位移）。"""
    for p in scene["props"]:
        if p.get("type") == "sprite" and p.get("enter") == "fly" and not p.get("from"):
            p["from"] = [420, -260]
        p.pop("from_", None)
    return scene


def render_shot(path, out_mp4):
    import render
    from playwright.sync_api import sync_playwright
    scene = render.load_scene(path)
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        ff = subprocess.Popen([render.FFMPEG, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(render.FPS), "-vcodec", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(out_mp4)],
                              stdin=subprocess.PIPE)
        n = int(round(scene["duration"] * render.FPS))
        for i in range(n):
            ff.stdin.write(render.grab(page, i / render.FPS))
        ff.stdin.close()
        ff.wait()
        steps = page.evaluate("() => footsteps()")
        browser.close()
    return n, steps


def decode(path, sr):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def mix(frames_per_shot, steps_per_shot, out_wav):
    import audio
    sr = audio.SR
    total = sum(frames_per_shot) / 30
    n = int(sr * total)
    voice = np.zeros(n)
    for x in L:
        if x["audio"]:
            clip = decode(VOICE / x["audio"], sr)
            i = int(x["t0"] * sr)
            voice[i:i + len(clip)] += clip[: n - i]
    # 背景音乐：有人说话时压低（0.15 秒渐变），开头淡入、结尾淡出
    bgm = decode(BGM, sr) if BGM.exists() else np.zeros(n)
    bgm = np.tile(bgm, int(np.ceil(n / max(len(bgm), 1))))[:n]
    env = np.full(n, 0.20)
    for x in L:
        if x["audio"]:
            env[int(x["t0"] * sr): int(x["t1"] * sr)] = 0.07
    k = int(0.15 * sr)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    env[: sr] *= np.linspace(0, 1, sr)
    env[-2 * sr:] *= np.linspace(1, 0, 2 * sr)
    sfx = np.zeros(n)
    start = 0
    for s, (frames, steps) in enumerate(zip(frames_per_shot, steps_per_shot)):
        scene = json.loads((SCENES / f"shot{s + 1}.json").read_text(encoding="utf-8"))
        scene["_steps"] = steps
        m = int(sr * frames / 30)
        part = audio.sfx(scene, m)
        i = int(start / 30 * sr)
        sfx[i:i + m] += part[: n - i]
        start += frames
    out = voice * 1.0 + bgm * env + sfx * 0.45
    out = out / max(1e-6, np.abs(out).max()) * 0.92
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    SCENES.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for k, fn in enumerate(SHOTS, 1):
        (SCENES / f"shot{k}.json").write_text(json.dumps(fix_fly(fn()), ensure_ascii=False, indent=1), encoding="utf-8")
    print("场次边界：", [round(b, 2) for b in B])
    if args.no_render:
        return
    only = {int(x) for x in args.only.split(",")} if args.only else set(range(1, len(SHOTS) + 1))
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for k in range(1, len(SHOTS) + 1):
        if k in only or str(k) not in meta:
            print(f"渲染第 {k} 场…", flush=True)
            frames, steps = render_shot(SCENES / f"shot{k}.json", OUT / f"shot{k}.mp4")
            meta[str(k)] = {"frames": frames, "steps": steps}
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
    frames = [meta[str(k)]["frames"] for k in range(1, len(SHOTS) + 1)]
    steps = [meta[str(k)]["steps"] for k in range(1, len(SHOTS) + 1)]
    (OUT / "list.txt").write_text("".join(f"file 'shot{k}.mp4'\n" for k in range(1, len(SHOTS) + 1)), encoding="utf-8")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"), "-c", "copy",
                    str(OUT / "silent.mp4")], check=True)
    mix(frames, steps, OUT / "mix.wav")
    final = OUT / "ep01_full.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(OUT / "silent.mp4"), "-i", str(OUT / "mix.wav"), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    print(final)


if __name__ == "__main__":
    main()
