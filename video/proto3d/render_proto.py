"""把 video/proto3d/popup.html 逐帧渲染成 mp4（Playwright 截图 → ffmpeg）。

用法（仓库根目录）：python video/proto3d/render_proto.py [--w 540 --h 960 --fps 30 --dur 6]
输出：video/out/proto3d_popup.mp4
"""
import argparse
import functools
import http.server
import subprocess
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video"))
from render import CHROMIUM, FFMPEG  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--w", type=int, default=540)
ap.add_argument("--h", type=int, default=960)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--dur", type=float, default=6.0)
args = ap.parse_args()

# 纹理不能从 file:// 读进 WebGL，所以起一个本地静态服务器
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


handler = functools.partial(Quiet, directory=str(ROOT))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/video/proto3d/popup.html?w={args.w}&h={args.h}"

out = ROOT / "video/out/proto3d_popup.mp4"
out.parent.mkdir(parents=True, exist_ok=True)
ff = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(args.fps), "-i", "-",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)], stdin=subprocess.PIPE)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    page = browser.new_page(viewport={"width": args.w, "height": args.h})
    page.goto(url)
    page.wait_for_function("window.ready !== undefined")
    page.evaluate("window.ready")
    n = int(args.dur * args.fps)
    for i in range(n):
        page.evaluate(f"window.renderFrame({i / args.fps})")
        ff.stdin.write(page.locator("canvas").screenshot(type="png"))
        if i % 30 == 0:
            print(f"{i}/{n}", flush=True)
    browser.close()
ff.stdin.close()
ff.wait()
srv.shutdown()
print("->", out)
