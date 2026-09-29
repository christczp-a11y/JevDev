"""3D 立体书舞台：整集渲染（第 1 集试做「徙木立信」，剧本沿用 video/scenes/ep01v2/shot*.json 和整集配音）。

用法（仓库根目录）：
  python video/stage3d/build_stage3d.py qa [场号...]        # 先查缺字（video/glyph_check.py），再穿帮质检：每个故事镜头抽 3 帧，把书外面涂成品红，拍到品红就报错
  python video/stage3d/build_stage3d.py frame [场号...]     # 入画质检：说话的人、镜头对准的人在不在画面里；前景人物有没有被切一半
  python video/stage3d/build_stage3d.py stills 场号 秒...    # 截几张静帧看（video/out/stage3d/ep01/still_场号_秒.jpg）
  python video/stage3d/build_stage3d.py render [并行数]      # 渲染整集：切成 20 秒的段，默认 4 段并行（可断点续渲），再拼接、配上整集声音
输出：video/out/stage3d/ep01/ep01_3d.mp4
退出码：0 没问题；1 质检查出了问题（qa、frame）；2 崩溃或环境有问题（字体没加载成功、页面初始化失败、脚本报错），不是质检结果。
环境变量 STAGE3D_SCENES / STAGE3D_OUT：临时换场景 JSON 目录、输出目录（video/tests/ 下的测试用）。

镜头规则（docs/research/纸艺作品-运镜场景叙事.md、docs/画面改版-纸片马里奥风格-给云端.md）：
- 每一页先用书桌机位交代（desk），再切电影镜头：贴地仰拍（low）、斜上方高机位（high）、反应特写（close）、跟拍（follow）、推近（push）；
- 选择题、讲知识点、点题时镜头稳住（wide）；每 2–5 秒换一个机位；
- 结尾拉远回到书桌（pullback）。
"""
import functools
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
import glyph_check  # noqa: E402
import render  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402

# 环境变量 STAGE3D_SCENES / STAGE3D_OUT 可以临时换场景 JSON 目录和输出目录（测试用：video/tests/ 下的脚本；环境变量会传给并行渲染的子进程，命令行参数不会）
SCENES = Path(os.environ["STAGE3D_SCENES"]) if os.environ.get("STAGE3D_SCENES") else ROOT / "video/scenes/ep01v2"
AUDIO = ROOT / "video/out/ep01v2/ep01_full.mp4"
OUT = Path(os.environ["STAGE3D_OUT"]) if os.environ.get("STAGE3D_OUT") else ROOT / "video/out/stage3d/ep01"
TAG_MIN_SECS = 1.5    # 人名牌实际画出来至少这么久，不到就报错（T24）
FPS = 30
W, H = 1080, 1920

# 每场：2D 世界坐标 x0 对应书页中线；纵深 z（越大越靠前）；镜头表 [开始, 结束, 类型, 参数]
SHOTS = {
    1: {"set": "qin_gate", "x0": 1100,
        "z": {"youth": 2.1, "dad": 1.2, "douzi2": 1.65, "douzi": 1.5, "shangyang": 1.0, "shangyang2": 1.1, "auntie0": 0.9, "auntie": 1.0, "host": 1.3,
              "prop:big_book": 0.6},
        "cams": [   # fit = 自动构图：ids 里的人（道具）整个落在安全区里；elev 机位高低；follow 跟拍；zoom 推近；pole 把立着的木杆也框进来
            [0.0, 0.9, "desk", {"x": -2.0}],                                             # 书页弹起，司马光从书里跳出来
            [0.9, 2.6, "fit", {"ids": ["host"], "pad": 1.15}],                           # 「考考你！」
            [2.6, 5.0, "fit", {"ids": ["host"], "pole": True, "elev": "low"}],           # 木杆「咚」地竖起：仰拍，司马光也在画面里
            [5.0, 8.0, "fit", {"ids": ["host", "shangyang"], "pole": True}],             # 选择题：稳住
            [8.0, 12.2, "fit", {"ids": ["shangyang", "douzi", "auntie0"], "pole": True, "elev": "high"}],   # 没一个人敢搬：高机位看人群
            [12.2, 15.9, "fit", {"ids": ["shangyang"], "pole": True, "elev": "low"}],    # 一根木头，怎么让一个国家开始相信？
            [15.9, 22.8, "fit", {"ids": ["shangyang", "prop:medal", "prop:token"]}],    # 商鞅讲新法（知识点：稳住）
            [22.8, 26.5, "fit", {"ids": ["douzi"], "pad": 1.12}],                        # 小豆子：十金！
            [26.5, 31.0, "fit", {"ids": ["dad"]}],                                       # 爹一把拎住
            [31.0, 38.0, "fit", {"ids": ["shangyang", "dad"], "pole": True}],   # 选择题 + 告示「十」翻成「五十」
            [38.0, 42.4, "fit", {"ids": ["dad"], "pad": 1.12}],                          # 爹捂眼：给得越多越不像真的
            [42.4, 45.3, "fit", {"ids": ["youth", "shangyang"]}],                        # 小伙：我来！
            [45.3, 47.25, "fit", {"ids": ["youth"], "pole": True, "elev": "low"}],       # 伸手前停一下：仰拍木杆
            [47.25, 49.3, "fit", {"ids": ["youth"], "az": -20}],                         # 起杆
            [49.3, 53.7, "fit", {"ids": ["youth"], "follow": True, "az": 18}],           # 搬运：跟拍
            [53.7, 54.9, "fit", {"ids": ["youth", "shangyang2"], "elev": "high"}],       # 放下木杆
            [54.9, 57.0, "fit", {"ids": ["youth", "shangyang2"], "zoom": [1.35, 1.0]}],  # 推近领赏
            [57.0, 61.5, "fit", {"ids": ["douzi2", "youth"], "pad": 1.1}],                       # 小豆子：真给了！
            [61.5, 74.9, "fit", {"ids": ["douzi2", "youth", "shangyang2"]}],             # 为什么是木头（知识点：稳住）
            [74.9, 79.19, "fit", {"ids": ["youth", "shangyang2", "auntie"], "elev": "high"}],   # 纸鸟满城飞、过关
        ]},
    2: {"set": "qin_gate", "x0": 967,
        "z": {"crowd1": 0.8, "crowd2": 1.3, "douzi": 1.7, "shangyang": 1.2, "teachers": 0.3},
        "cams": [
            [0.0, 5.0, "desk", {"x": 3.0}],
            [5.0, 7.6, "fit", {"ids": ["prop:prince_hat", "crowd1", "crowd2", "douzi"], "elev": "high"}],                                                # 城门里露出太子帽
            [7.6, 12.3, "fit", {"ids": ["douzi", "crowd1", "crowd2"]}],                   # 选择题
            [12.3, 16.0, "fit", {"ids": ["shangyang"], "az": -30}],   # 从左前方仰拍：右边的松树、灌木不挡住他                   # 商鞅拍案：仰拍
            [16.0, 20.2, "fit", {"ids": ["teachers", "crowd2"]}],                                   # 两位老师：啊？我们？
            [20.2, 23.0, "fit", {"ids": ["douzi"], "pad": 1.12}],                         # 连太子的老师都罚了！
            [23.0, 28.59, "fit", {"ids": ["crowd1", "crowd2", "douzi", "shangyang"]}],    # 金句：稳住
        ]},
    3: {"set": "qin_gate", "x0": 710,
        "z": {"teen": 1.5, "dad": 1.0, "prop:bundle": 1.9},
        "cams": [
            [0.0, 2.8, "desk", {"x": -1.0}],                                               # 很多年：四季翻过
            [2.8, 6.3, "fit", {"ids": ["teen"], "follow": True, "az": 15}],
            [6.3, 10.6, "fit", {"ids": ["teen", "prop:bundle"]}],                         # 选择题：拿不拿
            [10.6, 15.9, "fit", {"ids": ["teen"], "follow": True, "az": 15}],
            [15.9, 18.41, "fit", {"ids": ["dad", "teen"]}],                          # 我信了
        ]},
    4: {"set": "qin_gate", "x0": 850,
        "z": {"sima": 1.4, "prop:big_book": 0.4, "prop:sgm_pillow": 1.9},
        "cams": [
            [0.0, 4.1, "wide", {"x": 0.0, "d": 11.5}],                                     # 写书的人，来了——
            [4.1, 9.0, "fit", {"ids": ["sima", "prop:sgm_pillow"], "pad": 1.12}],         # 警枕滚落惊醒 → 我是司马光
            [9.0, 12.0, "fit", {"ids": ["sima", "prop:big_book"]}],                       # 书页上的原文：稳住
            [12.0, 14.04, "pullback", {"x": 0.0}],                                          # 拉远：原来是书桌上的一本书
        ]},
    5: {"set": "classroom", "x0": 550,
        "z": {"kid": 1.2, "desk": 1.2, "prop:school_desk": 0.9},
        "cams": [
            [0.0, 3.5, "fit", {"ids": ["kid", "desk", "prop:school_desk"]}],
            [3.5, 6.0, "fit", {"ids": ["kid"], "pad": 1.12}],
            [6.0, 11.6, "fit", {"ids": ["kid", "desk", "prop:school_desk"]}],             # 金句：稳住
        ]},
    6: {"set": "qin_gate", "x0": 700, "z": {},
        "cams": [[0.0, 6.54, "wide", {"x": 0.0, "d": 12.0}]]},
}
STORY = {"wide", "low", "high", "close", "follow", "push", "lift", "fit"}   # 故事镜头：不许拍到书外面（desk / pullback 本来就要拍到书桌）


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def open_stage(p, k, srv, tries=3):
    """打开第 k 场的 3D 舞台页并初始化。
    字体没加载成功（stage.html / engine.html 的 checkFonts 抛的）：打印原因，退出码 2，不往下渲；
    初始化偶发失败（reviewer 遇到过 `Page.evaluate: Event`）：换一个新浏览器重试，最多 tries 次，还不行就把错误抛出去（main 会按崩溃退出码 2）。
    初始化完先空渲一帧（t=0）再交给调用方：第一帧之前的预热。"""
    scene = render.load_scene(SCENES / f"shot{k}.json")
    cfg = SHOTS[k]
    flip = scene.get("flip", [True, True])
    args = [scene, render.assets_for(scene), {"set": cfg["set"], "x0": cfg["x0"], "z": cfg["z"], "shots": cfg["cams"], "flip": [True, True] if flip else flip}]
    for attempt in range(1, tries + 1):
        browser = p.chromium.launch(executable_path=render.CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        try:
            page = browser.new_page(viewport={"width": W, "height": H})
            page.on("pageerror", lambda e: print(f"[shot{k} pageerror]", e, flush=True))
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/video/stage3d/stage.html?w={W}&h={H}")
            page.wait_for_function("window.ready === true && document.getElementById('engine').contentWindow.init !== undefined")
            page.evaluate("([s, a, o]) => window.stageInit(s, a, o)", args)
            page.evaluate("window.renderFrame(0)")
            return browser, page, scene
        except PlaywrightError as e:
            browser.close()
            why = render.font_failure(e)
            if why:
                print(f"错误：{why}", file=sys.stderr)
                sys.exit(2)
            print(f"[第 {k} 场] 舞台初始化失败（第 {attempt}/{tries} 次）：{str(e).splitlines()[0][:200]}", flush=True)
            if attempt == tries:
                raise


SEG = 20.0   # 每段最多 20 秒成片：长场次切成几段并行渲染（原来按场次分，最长的第 1 场拖了整集一半时间）


REUSE = {1, 3, 4, 5, 6}   # 这几场沿用上一版整场渲好的文件（shotK_0.mp4 = 整场）；只改了哪场就只重渲哪场


def segments():
    """整集切成段：[(场号, 段号, 开始帧, 结束帧), ...]"""
    out = []
    for k in SHOTS:
        if k in REUSE and (OUT / f"shot{k}_0.done").exists():
            out.append((k, 0, 0, 0))
            continue
        n = int(round(json.loads((SCENES / f"shot{k}.json").read_text(encoding="utf-8"))["duration"] * FPS))
        step = int(SEG * FPS)
        for j, f0 in enumerate(range(0, n, step)):
            out.append((k, j, f0, min(n, f0 + step)))
    return out


def render_seg(job):
    k, j, f0, f1 = job
    from playwright.sync_api import sync_playwright
    out, done, tmp = OUT / f"shot{k}_{j}.mp4", OUT / f"shot{k}_{j}.done", OUT / f"shot{k}_{j}.part.mp4"
    if done.exists() and out.exists():   # 断点续渲：已经渲完的段跳过（云端 worker 可能被重启）
        return job, 0.0
    srv = serve()
    with sync_playwright() as p:
        browser, page, scene = open_stage(p, k, srv)
        ff = subprocess.Popen([render.FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(tmp)], stdin=subprocess.PIPE)
        t0 = time.time()
        for i in range(f0, f1):
            page.evaluate(f"window.renderFrame({i / FPS})")
            ff.stdin.write(page.screenshot(type="jpeg", quality=92))
        ff.stdin.close()
        ff.wait()
        browser.close()
    srv.shutdown()
    tmp.replace(out)
    done.write_text(str(f1 - f0))
    return job, time.time() - t0


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


def tag_errors(k, page):
    """人名牌：实际画出来的时间够不够、摆不摆得开（没配名单的场是空列表）。返回和 frame_qa 的 errs 同样格式的元组。"""
    errs = [(k, float(st["t0"] if st["ts"] is None else st["ts"]), float(st["t1"] if st["te"] is None else st["te"]),
             f"人名牌只画出 {st['secs']:.1f} 秒，要 ≥ {TAG_MIN_SECS} 秒（从这个人第一次入画、脚在安全区里算起 2 秒）", f"「{st['name']}」", None)
            for st in page.evaluate("window.nametagStats()") if st["secs"] < TAG_MIN_SECS]
    names = {st["id"]: st["name"] for st in page.evaluate("window.nametagStats()")}
    errs += [(k, float(c["t0"]), float(c["t1"]), "人名牌摆不开，互相重叠（安全区里放不下：改镜头，或者让这几个人错开出场）", "、".join(f"「{names[i]}」" for i in c["ids"]), None)
             for c in page.evaluate("window.nametagClashes()")]
    return errs


def frame_qa(shots, step=0.5):
    """入画质检（Chris 2026-09-29：有些人物跑出画面了）：每 0.5 秒查一次
    1. 正在说话的人，必须至少 75% 在画面里，而且不能被前面的东西挡住 30% 以上；
    2. 特写、跟拍、推近镜头对准的人，必须至少 85% 在画面里；
    3. 其他人：占画面高度 25% 以上（在前景、很显眼）却只有 20%–70% 在画面里 = 被画框切了一半，也算错；
    4. 人名牌（场景 JSON 里有 nametags 的场）：每张牌实际画出来的时间要 ≥ TAG_MIN_SECS（1.5 秒）。牌子从这个人第一次入画（脚在安全区里）开始计 2 秒，
       没入画、入画太晚、中途退场都会不够；stage.html 的 nametagStats() 给出每张牌的窗口和实际画了多少帧（T24）。
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
                    elif (sh[3].get("id") == id_ or id_ in sh[3].get("ids", [])) and vis < 0.85:
                        found.add(("镜头对准的人出画", id_, sh[2]))
                    elif h > 0.25 * 1920 and 0.2 < vis < 0.7:
                        found.add(("前景人物被切一半", id_, sh[2]))
                    # 遮挡：说话的人、镜头对准的人被前面的树、房子、别人挡住超过 30%（Chris 2026-09-29 之后补：商鞅被松树挡住）
                    if ((sub and speakers.get(sub[2]) == id_) or id_ in sh[3].get("ids", [])) and vis > 0.5:
                        if page.evaluate(f"window.visibleFraction({json.dumps(id_)})") < 0.7:
                            found.add(("被前面的东西挡住", id_, sh[2]))
                for key in found:
                    open_.setdefault(key, [t, t])[1] = t
                for key in list(open_):
                    if key not in found:
                        t0, t1 = open_.pop(key)
                        errs.append((k, t0, t1, *key))
                t = round(t + step, 2)
            errs += [(k, v[0], v[1], *key) for key, v in open_.items()]
            errs += tag_errors(k, page)
            browser.close()
    srv.shutdown()
    for k, t0, t1, kind, who, cam in sorted(errs, key=lambda e: e[:5]):
        print(f"  第 {k} 场 {t0:.1f}–{t1:.1f}s [{kind}] {who}" + (f"（{cam} 镜头）" if cam else ""))
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


def glyph_gate(shots):
    """渲染前先查每场要上画面的字有没有缺在字体子集外面（video/glyph_check.py）：缺字就报出来、退出码 1，不往下渲。"""
    issues = glyph_check.check_files([SCENES / f"shot{k}.json" for k in shots])
    if issues:
        glyph_check.print_report(issues)
        sys.exit(1)


def _main():
    cmd, rest = sys.argv[1], sys.argv[2:]
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "qa":
        shots = [int(x) for x in rest] or list(SHOTS)
        glyph_gate(shots)   # 缺字也算 qa 不过（退出码 1），先查它：快
        sys.exit(1 if qa(shots) else 0)
    if cmd == "frame":
        sys.exit(1 if frame_qa([int(x) for x in rest] or list(SHOTS)) else 0)
    if cmd == "stills":
        stills(int(rest[0]), [float(x) for x in rest[1:]])
        return
    glyph_gate(list(SHOTS))   # 渲染前先查缺字
    jobs = segments()
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=int(rest[0]) if rest else 4) as ex:   # 4 核：4 段并行
        for (k, j, f0, f1), el in ex.map(render_seg, jobs):
            print(f"第 {k} 场第 {j + 1} 段（{f1 - f0} 帧）：" + (f"{el:.0f} 秒" if el else "已渲过，跳过") + f"　累计 {time.time() - t0:.0f} 秒", flush=True)
    (OUT / "list.txt").write_text("".join(f"file 'shot{k}_{j}.mp4'\n" for k, j, _, _ in jobs), encoding="utf-8")
    subprocess.run([render.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "list.txt"), "-c", "copy", str(OUT / "silent.mp4")], check=True)
    subprocess.run([render.FFMPEG, "-y", "-loglevel", "error", "-i", str(OUT / "silent.mp4"), "-i", str(AUDIO), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT / "ep01_3d.mp4")], check=True)
    print(f"整集 → {OUT / 'ep01_3d.mp4'}（总共 {time.time() - t0:.0f} 秒）")


def main():
    """退出码：0 = 没问题；1 = 质检查出了问题（qa、frame 的结果）；2 = 崩溃或环境有问题（字体没加载成功、页面初始化失败、脚本报错），不是质检结果，要先修好再重跑。"""
    try:
        _main()
    except SystemExit:
        raise
    except Exception:   # noqa: BLE001 —— 崩溃不能和「查到问题」的退出码 1 混在一起
        traceback.print_exc()
        print("build_stage3d.py 崩溃了（不是质检查出的问题）：退出码 2", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
