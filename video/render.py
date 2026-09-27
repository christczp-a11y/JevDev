"""把剧本渲染成竖屏视频：Playwright 打开 engine.html，逐帧调用 renderFrame(t) 截图 → ffmpeg 合成 → 混入音轨。

逐帧渲染而不是录屏：每一帧的时间是算出来的，和电脑快慢无关，成片一定流畅、每次结果一样。

用法：
  python video/render.py video/scenes/ep01_ximulixin_demo.json               # 出视频（带 video/audio.py 合成的音乐音效）
  python video/render.py video/scenes/ep01_ximulixin_demo.json --still 7.5   # 只出某一秒的单帧 PNG，调画面用
"""
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
FFMPEG = str(next((Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob("Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe")))
FPS = 30


PROPS = ["block", "log", "coin", "scroll", "board"]


def load_scene(path):
    """读剧本，并把它引用的场景（video/sets/<名字>.json）合进来。"""
    scene = json.loads(Path(path).read_text(encoding="utf-8"))
    scene["set"] = json.loads((ROOT / "sets" / f"{scene['set']}.json").read_text(encoding="utf-8"))
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
            files.update({f"rig:{d}:{n}": ROOT / "assets/rig" / d / f"{n}.png" for n in a["rigData"][v]["parts"]})
    files.update({n: ROOT / "assets/props" / f"{n}.png" for n in PROPS})
    s = scene["set"]
    names = {s["far"]["img"], s["stage"]["ground"]["img"]} | {it[0] for k in ("hills", "mid", "stage", "fore", "frame") for it in s.get(k, {}).get("items", [])}
    if s["mid"].get("wallStrip"):
        names.add(s["mid"]["wallStrip"]["img"])
    files.update({n: ROOT / "assets" / s["dir"] / f"{n}.png" for n in names})
    return {n: "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() for n, p in files.items()}


def open_page(p, scene):
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.goto((ROOT / "engine.html").as_uri(), wait_until="networkidle")
    page.evaluate("([s, a]) => init(s, a)", [scene, assets_for(scene)])
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
