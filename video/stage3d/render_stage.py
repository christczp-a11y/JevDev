"""3D 立体书舞台试做：把剧本里的一段（默认第 1 场「搬木头」42–62 秒）用 video/stage3d/stage.html 逐帧渲染成 mp4，配上整集成片里同一段的声音。

用法（仓库根目录）：python video/stage3d/render_stage.py [--w 1080 --h 1920 --t0 42 --t1 62 --frames 0（只渲这几帧，调试用）]
输出：video/out/stage3d/carry.mp4（有声），并打印每秒成片的渲染耗时
"""
import argparse
import functools
import http.server
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
import render  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="video/scenes/ep01v2/shot1.json")
ap.add_argument("--audio", default="video/out/ep01v2/ep01_full.mp4")
ap.add_argument("--w", type=int, default=1080)
ap.add_argument("--h", type=int, default=1920)
ap.add_argument("--t0", type=float, default=42.0)
ap.add_argument("--t1", type=float, default=62.0)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--stills", nargs="*", type=float, help="只截这几个时刻的静帧（检查用），存到 video/out/stage3d/still_*.jpg")
args = ap.parse_args()

# 镜头表：[开始, 结束, 机位, 视角]（机位定义在 stage.html 的 CAMS）
SHOTS = [[42.0, 45.3, "open", 40], [45.3, 47.25, "lowPole", 50], [47.25, 49.3, "lift", 40], [49.3, 53.7, "follow", 42],
         [53.7, 54.9, "top", 40], [54.9, 57.0, "push", 36], [57.0, 59.6, "douzi", 34], [59.6, 62.0, "hold", 40]]
# 纵深：每个角色站在路上的前后位置（越大越靠前）
Z = {"youth": 2.1, "dad": 1.2, "douzi2": 1.65, "douzi": 1.5, "shangyang": 1.0, "shangyang2": 1.1, "auntie0": 1.0, "auntie": 1.0, "host": 1.0}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/video/stage3d/stage.html?w={args.w}&h={args.h}"
out_dir = ROOT / "video/out/stage3d"
out_dir.mkdir(parents=True, exist_ok=True)
scene = render.load_scene(ROOT / args.scene)
assets = render.assets_for(scene)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=render.CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    page = browser.new_page(viewport={"width": args.w, "height": args.h})
    page.on("console", lambda m: m.type == "error" and print("[console]", m.text))
    page.on("pageerror", lambda e: print("[pageerror]", e))
    page.goto(url)
    page.wait_for_function("window.ready === true && document.getElementById('engine').contentWindow.init !== undefined")
    page.evaluate("([s, a, o]) => window.stageInit(s, a, o)", [scene, assets, {"t0": args.t0, "shots": SHOTS, "z": Z}])
    if args.stills:
        for t in args.stills:
            page.evaluate(f"window.renderFrame({t})")
            page.screenshot(path=str(out_dir / f"still_{t:06.2f}.jpg"), type="jpeg", quality=90)
        print("stills ->", out_dir)
        sys.exit(0)
    silent = out_dir / "carry_silent.mp4"
    ff = subprocess.Popen([render.FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(args.fps), "-vcodec", "mjpeg", "-i", "-",
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(silent)], stdin=subprocess.PIPE)
    n = int(round((args.t1 - args.t0) * args.fps))
    start = time.time()
    for i in range(n):
        page.evaluate(f"window.renderFrame({args.t0 + i / args.fps})")
        ff.stdin.write(page.screenshot(type="jpeg", quality=92))
        if i % 60 == 0:
            print(f"{i}/{n}  {time.time() - start:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    browser.close()
el = time.time() - start
print(f"渲染 {n} 帧用了 {el:.0f} 秒：每秒成片 {el / (args.t1 - args.t0):.1f} 秒（{args.w}×{args.h}）")
out = out_dir / "carry.mp4"
subprocess.run([render.FFMPEG, "-y", "-loglevel", "error", "-i", str(silent), "-ss", str(args.t0), "-t", str(args.t1 - args.t0), "-i", str(ROOT / args.audio),
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)], check=True)
srv.shutdown()
print("->", out)
