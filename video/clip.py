"""只渲染一个剧本里的一段（检查动作用）：python video/clip.py <剧本.json> <开始秒> <结束秒> <输出.mp4>"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render
from playwright.sync_api import sync_playwright

scene_path, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
scene = render.load_scene(Path(scene_path))
with sync_playwright() as p:
    browser, page = render.open_page(p, scene)
    ff = subprocess.Popen([render.FFMPEG, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(render.FPS), "-vcodec", "mjpeg",
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], stdin=subprocess.PIPE)
    n = int((t1 - t0) * render.FPS)
    for i in range(n):
        ff.stdin.write(render.grab(page, t0 + i / render.FPS))
    ff.stdin.close()
    ff.wait()
    browser.close()
print(out)
