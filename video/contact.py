"""把一段剧本的多个时刻渲染成一张「联系表」（只截中间的闯关画面），用来检查动作和给质检看连续动作。

用法：python video/contact.py <剧本.json> <输出.png> <开始秒> <结束秒> [每秒几帧=4] [--cols 4] [--zoom x0,y0,x1,y1] [--follow 角色]
--zoom：只截闯关画面里的这一块（画面坐标，1080×608），比如只看人物
--follow：镜头跟着这个角色截（以他为中心、宽 --half×2），看连续动作用
"""
import argparse
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import render  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("out")
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("fps", type=float, nargs="?", default=4)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--zoom")
    ap.add_argument("--width", type=int, default=540, help="每格宽度")
    ap.add_argument("--follow")
    ap.add_argument("--half", type=int, default=230)
    args = ap.parse_args()
    sheet(args.scene, args.out, args.t0, args.t1, args.fps, args.cols, args.width, args.zoom, args.follow, args.half)


def sheet(scene_path, out, t0, t1, fps=4, cols=4, width=540, zoom=None, follow=None, half=230, top=110):
    scene = render.load_scene(scene_path)
    box = (0, 560, 1080, 1168)
    if zoom:
        x0, y0, x1, y1 = map(int, zoom.split(","))
        box = (x0, 560 + y0, x1, 560 + y1)
    n = int(round((t1 - t0) * fps)) + 1
    times = [t0 + i / fps for i in range(n)]
    tiles = []
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        for t in times:
            im = Image.open(BytesIO(render.grab(page, t, "image/png"))).convert("RGB")
            if follow:
                cx = page.evaluate("([id, t]) => actorScreenX(id, t)", [follow, t])
                cx = max(30 + half, min(1050 - half, cx))
                box = (int(cx - half), 560 + top, int(cx + half), 560 + 608)
            tiles.append(im.crop(box))
        browser.close()
    w = width
    h = int(tiles[0].height * w / tiles[0].width)
    rows = (len(tiles) + cols - 1) // cols
    sh = Image.new("RGB", (cols * w, rows * (h + 22)), "white")
    dr = ImageDraw.Draw(sh)
    for i, (t, im) in enumerate(zip(times, tiles)):
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        sh.paste(im.resize((w, h), Image.LANCZOS), (x, y + 22))
        dr.text((x + 6, y + 4), f"{t:.2f}s", fill=(0, 0, 0))
    sh.save(out)
    print(out, sh.size)
    return out


if __name__ == "__main__":
    main()
