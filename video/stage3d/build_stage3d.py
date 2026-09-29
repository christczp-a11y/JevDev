"""3D 立体书舞台：整集渲染（第 1 集试做「徙木立信」，剧本沿用 video/scenes/ep01v2/shot*.json 和整集配音）。

用法（仓库根目录）：
  python video/stage3d/build_stage3d.py qa [场号...]        # 穿帮质检：每个故事镜头抽 3 帧，把书外面涂成品红，拍到品红就报错
  python video/stage3d/build_stage3d.py frame [场号...]     # 入画质检：说话的人、镜头对准的人在不在画面里；前景人物有没有被切一半
  python video/stage3d/build_stage3d.py stills 场号 秒...    # 截几张静帧看（video/out/stage3d/ep01/still_场号_秒.jpg）
  python video/stage3d/build_stage3d.py render [场号...]     # 渲染（默认全部 6 场，2 场并行），再拼接、配上整集声音
输出：video/out/stage3d/ep01/ep01_3d.mp4

镜头规则（docs/research/纸艺作品-运镜场景叙事.md、docs/画面改版-纸片马里奥风格-给云端.md）：
- 每一页先用书桌机位交代（desk），再切电影镜头：贴地仰拍（low）、斜上方高机位（high）、反应特写（close）、跟拍（follow）、推近（push）；
- 选择题、讲知识点、点题时镜头稳住（wide）；每 2–5 秒换一个机位；
- 结尾拉远回到书桌（pullback）。
"""
import functools
import http.server
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
import render  # noqa: E402

SCENES = ROOT / "video/scenes/ep01v2"
AUDIO = ROOT / "video/out/ep01v2/ep01_full.mp4"
OUT = ROOT / "video/out/stage3d/ep01"
FPS = 30
W, H = 1080, 1920

# 每场：2D 世界坐标 x0 对应书页中线；纵深 z（越大越靠前）；镜头表 [开始, 结束, 类型, 参数]
SHOTS = {
    1: {"set": "qin_gate", "x0": 1100,
        "z": {"youth": 2.1, "dad": 1.2, "douzi2": 1.65, "douzi": 1.5, "shangyang": 1.0, "shangyang2": 1.1, "auntie0": 0.9, "auntie": 1.0, "host": 1.3,
              "prop:big_book": 0.6},
        "cams": [
            [0.0, 0.9, "desk", {"x": -2.0}],                              # 书页弹起，司马光从书里跳出来
            [0.9, 2.6, "close", {"id": "host"}],                          # 「考考你！」
            [2.6, 5.0, "low", {"x": -6.2, "tx": -4.4, "ty": 2.0, "tz": 0.8, "d": 5.8}],         # 木杆「咚」地竖起，贴地仰拍
            [5.0, 8.0, "wide", {"x": -3.2, "d": 12.5}],                    # 选择题：稳住
            [8.0, 12.2, "high", {"x": -2.0}],                              # 整个集市没一个人敢搬：高机位看人群往后缩
            [12.2, 15.9, "low", {"x": -3.0, "tx": -4.7, "ty": 2.0, "d": 6.2}],       # 一根木头，怎么让一个国家开始相信？
            [15.9, 22.8, "wide", {"x": -5.4, "d": 9.5}],                   # 商鞅讲新法（知识点：稳住）
            [22.8, 26.5, "close", {"id": "douzi"}],                       # 小豆子：十金！
            [26.5, 31.0, "wide", {"x": -1.4, "d": 8.0}],                   # 爹一把拎住
            [31.0, 38.0, "wide", {"x": -3.6, "d": 12.5}],                  # 选择题 + 告示「十」翻成「五十」
            [38.0, 42.4, "close", {"id": "dad"}],                         # 爹捂眼：给得越多越不像真的
            [42.4, 45.3, "wide", {"x": -5.2, "d": 10.0}],                  # 小伙：我来！
            [45.3, 47.25, "low", {"x": -2.9, "tx": -4.9, "ty": 2.0, "tz": 1.6}],   # 伸手前停一下：仰拍木杆
            [47.25, 49.3, "lift", {}],                                     # 起杆
            [49.3, 53.7, "follow", {"id": "youth"}],                       # 搬运
            [53.7, 54.9, "high", {"x": 3.4}],                              # 放下木杆
            [54.9, 57.0, "push", {"id": "youth"}],                         # 推近领赏
            [57.0, 61.5, "close", {"id": "douzi2"}],                       # 小豆子：真给了！
            [61.5, 74.9, "wide", {"x": 4.3, "d": 12.6}],                   # 为什么是木头（知识点：稳住）
            [74.9, 79.19, "high", {"x": 4.4}],                             # 纸鸟满城飞、过关
        ]},
    2: {"set": "qin_gate", "x0": 967,
        "z": {"crowd1": 0.8, "crowd2": 1.3, "douzi": 1.7, "shangyang": 1.2, "teachers": 0.3},
        "cams": [
            [0.0, 5.0, "desk", {"x": 3.0}],
            [5.0, 7.6, "low", {"x": 5.6, "tx": 5.2, "ty": 1.8, "tz": -3.0}],   # 从围观的人右边看过去：门洞不被挡住   # 城门里露出太子帽
            [7.6, 12.3, "wide", {"x": 6.0, "d": 13.0}],                         # 选择题
            [12.3, 16.0, "low", {"x": 7.4, "tx": 9.6, "ty": 1.5, "d": 5.6}],     # 商鞅拍案：仰拍
            [16.0, 20.2, "close", {"id": "teachers", "d": 5.2}],                # 两位老师：啊？我们？
            [20.2, 23.0, "close", {"id": "douzi"}],                            # 连太子的老师都罚了！
            [23.0, 28.59, "wide", {"x": 6.2, "d": 12.5}],                       # 金句：稳住
        ]},
    3: {"set": "qin_gate", "x0": 710,
        "z": {"teen": 1.5, "dad": 1.0, "prop:bundle": 1.9},
        "cams": [
            [0.0, 2.8, "desk", {"x": -1.0}],                                   # 很多年：四季翻过
            [2.8, 6.3, "follow", {"id": "teen", "dx": 2.6, "d": 6.8}],
            [6.3, 10.6, "wide", {"x": -1.2, "d": 9.0}],                         # 选择题：拿不拿
            [10.6, 15.9, "follow", {"id": "teen", "dx": 2.6, "d": 6.8}],
            [15.9, 18.41, "close", {"id": "dad", "d": 5.0}],                   # 我信了
        ]},
    4: {"set": "qin_gate", "x0": 850,
        "z": {"sima": 1.4, "prop:big_book": 0.4, "prop:sgm_pillow": 1.9},
        "cams": [
            [0.0, 4.1, "wide", {"x": 0.0, "d": 11.5}],                          # 写书的人，来了——
            [4.1, 9.0, "close", {"id": "sima", "d": 6.2}],                     # 警枕滚落惊醒 → 我是司马光
            [9.0, 12.0, "wide", {"x": -1.9, "d": 11.0, "y": 2.2, "ly": 1.5, "fov": 58}],   # 书页上的原文和司马光都在画面里                         # 书页上的原文：稳住
            [12.0, 14.04, "pullback", {"x": 0.0}],                              # 拉远：原来是书桌上的一本书
        ]},
    5: {"set": "classroom", "x0": 550,
        "z": {"kid": 1.2, "desk": 1.2, "prop:school_desk": 0.9},
        "cams": [
            [0.0, 3.5, "wide", {"x": 0.0, "d": 13.0, "y": 3.0}],
            [3.5, 6.0, "close", {"id": "kid", "d": 5.5}],
            [6.0, 11.6, "wide", {"x": 0.0, "d": 13.0, "y": 3.0}],               # 金句：稳住
        ]},
    6: {"set": "qin_gate", "x0": 700, "z": {},
        "cams": [[0.0, 6.54, "wide", {"x": 0.0, "d": 12.0}]]},
}
STORY = {"wide", "low", "high", "close", "follow", "push", "lift"}   # 故事镜头：不许拍到书外面（desk / pullback 本来就要拍到书桌）


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def open_stage(p, k, srv):
    scene = render.load_scene(SCENES / f"shot{k}.json")
    cfg = SHOTS[k]
    browser = p.chromium.launch(executable_path=render.CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    page = browser.new_page(viewport={"width": W, "height": H})
    page.on("pageerror", lambda e: print(f"[shot{k} pageerror]", e, flush=True))
    page.goto(f"http://127.0.0.1:{srv.server_address[1]}/video/stage3d/stage.html?w={W}&h={H}")
    page.wait_for_function("window.ready === true && document.getElementById('engine').contentWindow.init !== undefined")
    flip = scene.get("flip", [True, True])
    page.evaluate("([s, a, o]) => window.stageInit(s, a, o)",
                  [scene, render.assets_for(scene), {"set": cfg["set"], "x0": cfg["x0"], "z": cfg["z"], "shots": cfg["cams"], "flip": [True, True] if flip else flip}])
    return browser, page, scene


def render_shot(k):
    from playwright.sync_api import sync_playwright
    srv = serve()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"shot{k}.mp4"
    done = OUT / f"shot{k}.done"
    if done.exists() and out.exists():   # 断点续渲：已经渲完的场次跳过（云端 worker 可能被重启）
        return k, 0, 0.0
    tmp = OUT / f"shot{k}.part.mp4"
    with sync_playwright() as p:
        browser, page, scene = open_stage(p, k, srv)
        n = int(round(scene["duration"] * FPS))
        ff = subprocess.Popen([render.FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(tmp)], stdin=subprocess.PIPE)
        t0 = time.time()
        for i in range(n):
            page.evaluate(f"window.renderFrame({i / FPS})")
            ff.stdin.write(page.screenshot(type="jpeg", quality=92))
            if i % 150 == 0:
                print(f"shot{k} {i}/{n} {time.time() - t0:.0f}s", flush=True)
        ff.stdin.close()
        ff.wait()
        browser.close()
    srv.shutdown()
    tmp.replace(out)
    done.write_text(str(n))
    return k, n, time.time() - t0


def qa(shots):
    """穿帮质检：故事镜头里拍到书外面（品红）就报错。每个镜头抽开头、中间、结尾 3 帧。"""
    import numpy as np
    from PIL import Image
    from playwright.sync_api import sync_playwright
    srv = serve()
    bad = []
    with sync_playwright() as p:
        for k in shots:
            browser, page, scene = open_stage(p, k, srv)
            page.evaluate("window.qaLeak(true)")
            for t0, t1, kind, _ in SHOTS[k]["cams"]:
                if kind not in STORY:
                    continue
                for t in (max(t0 + 0.05, 0.9), (t0 + t1) / 2, min(t1 - 0.05, scene["duration"] - 0.5)):   # 开头 0.9 秒书页正在弹起、最后 0.45 秒正在折倒，本来就会露出书外面
                    page.evaluate(f"window.renderFrame({t}, {{noUI: true}})")
                    a = np.asarray(Image.open(BytesIO(page.screenshot(type="png"))).convert("RGB")).astype(int)
                    frac = ((a[..., 0] > 200) & (a[..., 1] < 70) & (a[..., 2] > 200)).mean()
                    if frac > 0.002:
                        bad.append((k, round(t, 2), kind, round(frac * 100, 2)))
                        Image.fromarray(a.astype("uint8")).resize((270, 480)).save(OUT / f"leak_{k}_{t:06.2f}.png")
            browser.close()
    srv.shutdown()
    for b in bad:
        print(f"  穿帮：第 {b[0]} 场 {b[1]}s（{b[2]} 镜头）拍到书外面 {b[3]}% 画面")
    print("穿帮质检：" + ("没有问题" if not bad else f"{len(bad)} 处"))
    return bad


def frame_qa(shots, step=0.5):
    """入画质检（Chris 2026-09-29：有些人物跑出画面了）：每 0.5 秒查一次
    1. 正在说话的人，必须至少 75% 在画面里；
    2. 特写、跟拍、推近镜头对准的人，必须至少 85% 在画面里；
    3. 其他人：占画面高度 25% 以上（在前景、很显眼）却只有 20%–70% 在画面里 = 被画框切了一半，也算错。
    同一个问题连续出现只报一次（报第一次出现的时刻和持续多久）。"""
    from playwright.sync_api import sync_playwright
    srv = serve()
    errs = []
    with sync_playwright() as p:
        for k in shots:
            browser, page, scene = open_stage(p, k, srv)
            speakers = {a.get("speaker"): id_ for id_, a in scene["actors"].items() if a.get("speaker")}
            open_ = {}
            t = 0.9
            while t < scene["duration"] - 0.5:
                page.evaluate(f"window.renderFrame({t}, {{noUI: true}})")
                boxes = {b["id"]: b for b in page.evaluate("window.frameBoxes()")}
                sh = next((c for c in SHOTS[k]["cams"] if c[0] <= t < c[1]), SHOTS[k]["cams"][-1])
                sub = next((x for x in scene["subtitles"] if x[0] <= t <= x[1]), None)
                found = set()
                for id_, b in boxes.items():
                    w, h = max(1, b["x1"] - b["x0"]), max(1, b["y1"] - b["y0"])
                    vis = max(0, min(b["x1"], 1080) - max(b["x0"], 0)) / w * max(0, min(b["y1"], 1920) - max(b["y0"], 0)) / h
                    if sub and speakers.get(sub[2]) == id_ and vis < 0.75:
                        found.add(("说话的人出画", id_, sh[2]))
                    elif sh[3].get("id") == id_ and vis < 0.85:
                        found.add(("镜头对准的人出画", id_, sh[2]))
                    elif h > 0.25 * 1920 and 0.2 < vis < 0.7:
                        found.add(("前景人物被切一半", id_, sh[2]))
                for key in found:
                    open_.setdefault(key, [t, t])[1] = t
                for key in list(open_):
                    if key not in found:
                        t0, t1 = open_.pop(key)
                        errs.append((k, t0, t1, *key))
                t = round(t + step, 2)
            errs += [(k, v[0], v[1], *key) for key, v in open_.items()]
            browser.close()
    srv.shutdown()
    for k, t0, t1, kind, who, cam in sorted(errs):
        print(f"  第 {k} 场 {t0:.1f}–{t1:.1f}s [{kind}] {who}（{cam} 镜头）")
    print("入画质检：" + ("没有问题" if not errs else f"{len(errs)} 处"))
    return errs


def stills(k, ts):
    from playwright.sync_api import sync_playwright
    srv = serve()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, page, _ = open_stage(p, k, srv)
        for t in ts:
            page.evaluate(f"window.renderFrame({t})")
            page.screenshot(path=str(OUT / f"still_{k}_{t:06.2f}.jpg"), type="jpeg", quality=88)
        browser.close()
    srv.shutdown()


def main():
    cmd, rest = sys.argv[1], sys.argv[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "qa":
        sys.exit(1 if qa([int(x) for x in rest] or list(SHOTS)) else 0)
    if cmd == "frame":
        sys.exit(1 if frame_qa([int(x) for x in rest] or list(SHOTS)) else 0)
    if cmd == "stills":
        stills(int(rest[0]), [float(x) for x in rest[1:]])
        return
    shots = [int(x) for x in rest] or list(SHOTS)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=2) as ex:
        for k, n, el in ex.map(render_shot, shots):
            print(f"第 {k} 场：{n} 帧，{el:.0f} 秒" + (f"（每秒成片 {el / (n / FPS):.0f} 秒）" if n else "（已渲过，跳过）"), flush=True)
    (OUT / "list.txt").write_text("".join(f"file 'shot{k}.mp4'\n" for k in SHOTS), encoding="utf-8")
    subprocess.run([render.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"), "-c", "copy", str(OUT / "silent.mp4")], check=True)
    subprocess.run([render.FFMPEG, "-y", "-loglevel", "error", "-i", str(OUT / "silent.mp4"), "-i", str(AUDIO), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT / "ep01_3d.mp4")], check=True)
    print(f"整集 → {OUT / 'ep01_3d.mp4'}（总共 {time.time() - t0:.0f} 秒）")


if __name__ == "__main__":
    main()
