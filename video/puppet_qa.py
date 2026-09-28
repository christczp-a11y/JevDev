"""纸偶质检：把纸偶单独画在品红底上，把所有「身体内部的描边」和「漏出来的白色」标出来，拼成放大检查图。

为什么要有它（Chris 2026-09-28）：手肘、膝盖、脖子的白缝，闭眼时漏出的一牙眼白，鞋口露出的一截脚脖子——
这些都是纸偶部件「一块一块叠起来」时才会出现的问题，在整帧画面里很小，靠肉眼扫缩略图总是漏。

做法：
- 描边颜色换成青色（scene.qaOutline），这样画面里凡是青色的都是程序画的描边；
- 强制闭眼（window.qaEyesClosed），眼白要是没盖住就会露出白色；
- 只画这一个纸偶（window.soloActor），品红底，离外轮廓超过「描边宽度 + 3 像素」的青色 = 身体内部的描边，标红；
  身体内部接近白色的像素 = 漏出来的白（部件原图自带的白边、眼白），标黄；
- 时刻：每个动作的开始、中点、结束，换视角前后，外加每 0.5 秒一帧。

内部描边不一定是错（近侧手臂压在身子上，手臂外轮廓本来就该有描边），所以检查图要逐张看：
同一条肢体「内部横穿」的红线（手肘、膝盖、脖子、手腕、鞋口）才是错。

用法：python video/puppet_qa.py <剧本.json> [角色 id，默认所有纸偶] [--eyes=0.4]
交付前全闭（默认）和半闭（--eyes=0.4）各跑一次：半闭眼漏过一次（Chris 2026-09-28）
输出：video/out/puppet_qa_<剧本名>/<角色>_XX.png 和 summary.json
"""
import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render
from playwright.sync_api import sync_playwright

BAND = (0, 560, 1080, 1168)


def times_for(a):
    s0, s1 = a.get("show", [a["keys"][0][0], a["keys"][-1][0]])
    ts = {round(t, 2) for t in np.arange(s0 + 0.1, s1, 0.5)}
    for x in a.get("actions", []):
        for u in (0.1, 0.5, 0.9):
            ts.add(round(x[0] + (x[1] - x[0]) * u, 2))
    for t, _ in a.get("views", [])[1:]:
        ts |= {round(t - 0.1, 2), round(t + 0.15, 2), round(t + 0.35, 2)}
    return sorted(t for t in ts if s0 <= t <= s1)


def analyse(im):
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    bg = (r > 140) & (b > 140) & (g < 100)
    body = ~bg
    body[:, :45] = False; body[:, -45:] = False; body[:6] = False   # 画框的纸边不算
    body = ndimage.binary_opening(body, iterations=1)
    if body.sum() < 500:
        return None
    dist = ndimage.distance_transform_edt(body)
    cyan = body & (r < 110) & (g > 140) & (b > 140)
    ring = np.percentile(dist[cyan], 80) if cyan.any() else 4
    inner_line = cyan & (dist > ring + 3)
    white = body & ~cyan & (np.minimum(np.minimum(r, g), b) > 228) & (dist > ring + 3)
    white = ndimage.binary_opening(white, iterations=1)
    return inner_line, white, body


EYES = 1.0


def main():
    global EYES
    args = [a for a in sys.argv[1:] if not a.startswith("--eyes=")]
    for a in sys.argv[1:]:
        if a.startswith("--eyes="):   # --eyes=0.4 查半闭眼（使劲、眨眼中途）；默认 1 = 全闭
            EYES = float(a.split("=")[1])
    sys.argv[1:] = args
    scene_path = Path(sys.argv[1])
    scene = render.load_scene(scene_path)
    scene["qaOutline"] = "#00ffff"
    ids = sys.argv[2:] or [k for k, a in scene["actors"].items() if a.get("rigData")]
    out = render.ROOT / "out" / f"puppet_qa_{scene_path.stem}_eyes{EYES}"
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        page.evaluate(f"window.qaEyesClosed = {EYES}")
        for aid in ids:
            page.evaluate(f"window.soloActor = {json.dumps(aid)}")
            cells, rows = [], []
            for t in times_for(scene["actors"][aid]):
                im = Image.open(BytesIO(render.grab(page, t, "image/png"))).convert("RGB").crop(BAND)
                res = analyse(im)
                if res is None:
                    continue
                inner, white, body = res
                ys, xs = np.nonzero(body)
                box = (max(0, xs.min() - 12), max(0, ys.min() - 12), min(im.width, xs.max() + 12), min(im.height, ys.max() + 12))
                show = np.asarray(im).copy()
                show[inner] = (255, 0, 0)
                show[white] = (255, 220, 0)
                crop = Image.fromarray(show).crop(box)
                k = min(360 / crop.height, 3.0)
                crop = crop.resize((max(1, int(crop.width * k)), 360))
                d = ImageDraw.Draw(crop)
                d.rectangle((0, 0, 150, 18), fill=(255, 255, 255))
                d.text((3, 3), f"{t:.2f}s red {int(inner.sum())} yel {int(white.sum())}", fill=(0, 0, 0))
                cells.append(crop)
                rows.append({"t": t, "inner_outline_px": int(inner.sum()), "white_px": int(white.sum())})
            page.evaluate("window.soloActor = null")
            summary[aid] = rows
            per = 12
            for n in range(0, len(cells), per):
                g = cells[n:n + per]
                cw = max(c.width for c in g)
                sheet = Image.new("RGB", (cw * 6, 370 * ((len(g) + 5) // 6)), (40, 40, 40))
                for i, c in enumerate(g):
                    sheet.paste(c, ((i % 6) * cw, (i // 6) * 370))
                sheet.save(out / f"{aid}_{n // per + 1:02d}.png")
        browser.close()
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for aid, rows in summary.items():
        worst = sorted(rows, key=lambda r: -(r["white_px"]))[:3]
        print(aid, f"{len(rows)} 帧；漏白最多：", [(r["t"], r["white_px"]) for r in worst])
    print(f"检查图：{out}/*.png（必须逐张看：同一条肢体内部横穿的红线、任何黄色都是错）")


if __name__ == "__main__":
    main()
