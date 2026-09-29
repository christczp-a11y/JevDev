"""把剧本渲染成竖屏视频：Playwright 打开 engine.html，逐帧调用 renderFrame(t) 截图 → ffmpeg 合成 → 混入音轨。

逐帧渲染而不是录屏：每一帧的时间是算出来的，和电脑快慢无关，成片一定流畅、每次结果一样。

用法：
  python video/render.py video/scenes/ep01_ximulixin_demo.json               # 出视频（带 video/audio.py 合成的音乐音效）
  python video/render.py video/scenes/ep01_ximulixin_demo.json --still 7.5   # 只出某一秒的单帧 PNG，调画面用
"""
import argparse
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")   # 缺布景等中文报错走 stderr，不设 PYTHONIOENCODING 也能正常显示
FFMPEG = str(next((Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"), None)
             or shutil.which("ffmpeg") or "ffmpeg")   # 本地 Windows（WinGet 装的）/ 云端 Linux（apt install ffmpeg）
CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None   # 云端预装的 Chromium（Playwright 下载被网络策略拦截）；本地为 None，用 Playwright 自带的
FPS = 30


PROPS = ["block", "log", "coin", "scroll", "board"]


def set_missing_message(scene_path, scene, name):
    have = "、".join(sorted(p.stem for p in (ROOT / "sets").glob("*.json"))) or "（一份都没有）"
    return (f"错误：场景 {scene_path}（{scene.get('about', '没写 about')}）要用 2D 布景「{name}」，但找不到 video/sets/{name}.json。\n"
            f"  每个新地点都要有一份 2D 布景（工作流第 0 步第 9a 项）：far、mid、stage、fore 四层。补法：\n"
            f"  1. 第 3 步 Codex 画的分层图放到 video/assets/sets/{name}/；\n"
            f"  2. 照 video/sets/README.md 拼成 video/sets/{name}.json；\n"
            f"  3. 跑 python video/set_check.py {name} 检查（层和引用的图都齐了才算过）。\n"
            f"  现有的布景：{have}。不会悄悄换成别的布景。")


def load_scene(path):
    """读剧本，并把它引用的场景（video/sets/<名字>.json）合进来。
    找不到布景就用中文报清楚：哪个场景、要哪个布景、该放在哪（SystemExit：不打 traceback，退出码 1），不会悄悄用别的布景。"""
    scene = json.loads(Path(path).read_text(encoding="utf-8"))
    name = scene.get("set")
    if not isinstance(name, str) or not name:
        sys.exit(f"错误：场景 {path} 里没有写 set（布景名，对应 video/sets/<名字>.json）。")
    set_path = ROOT / "sets" / f"{name}.json"
    if not set_path.exists():
        sys.exit(set_missing_message(path, scene, name))
    try:
        scene["set"] = json.loads(set_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"错误：布景 {set_path} 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列，{e.msg}。改好以后跑 python video/set_check.py {name}。")
    for a in scene["actors"].values():   # 纸偶角色：每个视角一套部件和关节（video/assets/rig/<文件夹>/rig.json）
        rigs = a.get("rigs") or ({"side": a["rig"]} if a.get("rig") else None)
        if rigs:
            a["rigs"] = rigs
            a["rigData"] = {v: json.loads((ROOT / "assets/rig" / d / "rig.json").read_text(encoding="utf-8")) for v, d in rigs.items()}
    return scene


def assets_for(scene):
    files = {n: ROOT / "assets/chars" / f"{n}.png" for a in scene["actors"].values() for n in a.get("sprites", {}).values()}
    for a in scene["actors"].values():
        for v, d in a.get("rigs", {}).items():
            rd = a["rigData"][v]
            files.update({f"rig:{d}:{n}": ROOT / "assets/rig" / d / f"{n}.png" for n in [*rd["parts"], *(f"{b}_bare" for b in rd.get("bare", []))]})
            files.update({f"rig:{d}:{n}_core": ROOT / "assets/rig" / d / f"{n}_core.png" for n in rd["parts"]
                          if (ROOT / "assets/rig" / d / f"{n}_core.png").exists()})   # 去掉白边的纸芯（strip_border.py）
    files.update({n: ROOT / "assets/props" / f"{n}.png" for n in PROPS})
    # 第 1 集起：姿势时间线里的人物图、纸片道具、纸鸟 —— 按名字在 chars / props 里找
    extra = {n for a in scene["actors"].values() for _t, n in a.get("poses", [])}
    extra |= {p["img"] for p in scene["props"] if p["type"] == "sprite"}
    if any(e["type"] == "birds" for e in scene["events"]):
        extra.add("paper_bird")
    for n in extra:
        files[n] = next(d / f"{n}.png" for d in (ROOT / "assets/chars", ROOT / "assets/props") if (d / f"{n}.png").exists())
    s = scene["set"]
    ground = s["stage"].get("ground")
    names = {s["far"]["img"]} | ({ground["img"]} if ground else set()) | {it[0] for k in ("hills", "mid", "stage", "fore", "frame") for it in s.get(k, {}).get("items", []) + s.get(k, {}).get("behind", [])}
    if s["mid"].get("wallStrip"):
        names.add(s["mid"]["wallStrip"]["img"])
    lost = sorted(n for n in names if not (ROOT / "assets" / s["dir"] / f"{n}.png").exists())
    if lost:
        sys.exit(f"错误：2D 布景（video/assets/{s['dir']}/）缺这些图：{'、'.join(n + '.png' for n in lost)}。"
                 f"补上，或者改布景 JSON 里的引用；改完跑 python video/set_check.py 检查。")
    files.update({n: ROOT / "assets" / s["dir"] / f"{n}.png" for n in names})
    return {n: "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() for n, p in files.items()}


def font_failure(err):
    """Playwright 报的错里带「字体没加载成功」（engine.html / stage.html 的 checkFonts 抛的）时，返回那句中文；不是字体问题返回 None。"""
    msg = str(err)
    i = msg.find("字体没加载成功")
    return msg[i:].splitlines()[0] if i >= 0 else None


def open_page(p, scene, hide_nametags=False):
    """打开 2D 引擎页并初始化。字体没加载成功（检查在 engine.html 的 checkFonts）就打印原因、退出码 2（不是「查到问题」的 1），不往下渲。
    初始化完先空渲一帧（t=0）再交给调用方（第一帧前的预热，和 3D 一致）。
    hide_nametags：2D 质检截图（logic_qa、puppet_qa、selfcheck）用，藏起人名牌，别让它进观察员的图和改前改后对比。"""
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.goto((ROOT / "engine.html").as_uri(), wait_until="networkidle")
    try:
        page.evaluate("([s, a]) => init(s, a)", [scene, assets_for(scene)])
    except PlaywrightError as e:
        browser.close()
        why = font_failure(e)
        if why:
            print(f"错误：{why}", file=sys.stderr)
            sys.exit(2)
        raise
    if hide_nametags:
        page.evaluate("() => { window.hideNametags = true; }")
    page.evaluate("() => { renderFrame(0); }")
    return browser, page


def grab(page, t, fmt="image/jpeg"):
    uri = page.evaluate(f"(t) => {{ renderFrame(t); return document.getElementById('c').toDataURL('{fmt}', 0.93); }}", t)
    return base64.b64decode(uri.split(",", 1)[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--still", type=float)
    ap.add_argument("--out")
    args = ap.parse_args()
    scene_path = Path(args.scene)
    scene = load_scene(scene_path)
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser, page = open_page(p, scene)
        if args.still is not None:
            dst = Path(args.out or out_dir / f"{scene_path.stem}_{args.still:.1f}s.png")
            dst.write_bytes(grab(page, args.still, "image/png"))
            print(dst)
            browser.close()
            return
        silent = out_dir / f"{scene_path.stem}_silent.mp4"
        ff = subprocess.Popen([FFMPEG, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
                               "-vcodec", "mjpeg", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "18", "-preset", "medium", str(silent)], stdin=subprocess.PIPE)
        n = int(scene["duration"] * FPS)
        for i in range(n):
            ff.stdin.write(grab(page, i / FPS))
            if i % 60 == 0:
                print(f"  帧 {i}/{n}", flush=True)
        ff.stdin.close()
        ff.wait()
        scene["_steps"] = page.evaluate("() => footsteps()")   # 纸偶的脚步时刻，给音效用
        browser.close()

    import audio  # video/audio.py
    wav = audio.build(scene, out_dir / f"{scene_path.stem}.wav")
    final = Path(args.out or out_dir / f"{scene_path.stem}.mp4")
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-i", str(silent), "-i", str(wav), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    print(final)


if __name__ == "__main__":
    main()
