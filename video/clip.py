"""只渲染一个剧本里的一段（检查动作用）：python video/clip.py <剧本.json> <开始秒> <结束秒> <输出.mp4> [--audio 成片.mp4 --offset 秒]

注意：不给 --audio 时是无声的（Chris 2026-09-28 收到过无声片段）。发给 Chris 的片段一律带声音：
--audio 指向带声音的整集成片，--offset 是这个剧本在整集里的开始时间（第 1 场是 0）。成片必须是和剧本同一版时间线渲染出来的。"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render
from playwright.sync_api import sync_playwright

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("scene"); ap.add_argument("t0", type=float); ap.add_argument("t1", type=float); ap.add_argument("out")
ap.add_argument("--audio"); ap.add_argument("--offset", type=float, default=0.0)
args = ap.parse_args()
scene_path, t0, t1, out = args.scene, args.t0, args.t1, args.out
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
if args.audio:   # 把整集成片里同一段的声音配上
    tmp = out + ".v.mp4"
    Path(out).rename(tmp)
    subprocess.run([render.FFMPEG, "-loglevel", "error", "-y", "-i", tmp, "-ss", str(args.offset + t0), "-t", str(t1 - t0), "-i", args.audio,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", out], check=True)
    Path(tmp).unlink()
else:
    print("（无声：没给 --audio）")
print(out)
