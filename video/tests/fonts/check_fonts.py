"""字体测试（工作流第 0 步第 19 项，E1）：字体在仓库里、加载时真的生效、失败会报错、每次截图一样、每一段成片的第一帧字体也对。
用法（仓库根目录）：python video/tests/fonts/check_fonts.py     退出码 0 = 全过。输出在 video/out/tests/fonts/。"""
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/fonts"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["STAGE3D_OUT"] = str(OUT / "stage3d")
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT / "video/stage3d"))
sys.stdout.reconfigure(encoding="utf-8")
import build_stage3d as bs  # noqa: E402
import imgdiff  # noqa: E402
import render  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FONTS = ROOT / "video/vendor/fonts"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'通过' if ok else '不通过'}] {name}" + (f"：{detail}" if detail else ""))


def kicker_metrics(img):
    """卷号胶囊的宽度（第 124 行上底色最左到最右）和里面米色字形的像素数。ZCOOL KuaiLe：宽 338、字形约 2620–2640；备用无衬线字体：宽 356、约 2420
    （用这个函数在参考帧和预热帧上量的；reviewer 09-29 用另一种量法得到 318 / 2770 和 337 / 2610，方向一样：ZCOOL 更窄、字形像素更多）。"""
    a = np.asarray(img.convert("RGB")).astype(int)
    dark = (a[124, :, 0] < 95) & (a[124, :, 1] < 95) & (a[124, :, 2] < 95)   # 胶囊的底色（88% 的 #2a2320 盖在背景上）
    xs = np.nonzero(dark[250:830])[0] + 250
    x0, x1 = int(xs.min()), int(xs.max())
    box = a[92:154, x0:x1 + 1]
    cream = (abs(box[..., 0] - 244) < 24) & (abs(box[..., 1] - 232) < 24) & (abs(box[..., 2] - 208) < 28)
    return x1 - x0 + 1, int(cream.sum())


# 1 文件都在
need = ["NotoSansSC-subset.woff2", "ZCOOLKuaiLe-subset.woff2", "fonts.css", "charset.txt", "subset_fonts.py", "NotoSansSC-OFL.txt", "ZCOOLKuaiLe-OFL.txt"]
missing = [n for n in need if not (FONTS / n).exists()]
sizes = {n: (FONTS / n).stat().st_size for n in need if (FONTS / n).exists()}
check("video/vendor/fonts/ 里字体文件、fonts.css、许可证、子集化脚本都在", not missing, f"缺 {missing}" if missing else "，".join(f"{n} {s / 1024:.0f} KB" for n, s in sizes.items() if n.endswith("woff2")))
css = (FONTS / "fonts.css").read_text(encoding="utf-8")
check("fonts.css 里的 url 指向的文件都存在", all((FONTS / u).exists() for u in __import__("re").findall(r'url\("([^"]+)"\)', css)))
for f in ("video/engine.html", "video/stage3d/stage.html"):
    txt = (ROOT / f).read_text(encoding="utf-8")
    check(f"{f} 不再连 Google Fonts", "fonts.googleapis.com" not in txt and "fonts.gstatic.com" not in txt)

scene_path = ROOT / "video/scenes/ep01v2/shot1.json"
scene = render.load_scene(scene_path)
assets = render.assets_for(scene)
engine_uri = (ROOT / "video/engine.html").as_uri()

with sync_playwright() as p:
    # 2 字体文件加载不出来：init 抛「字体没加载成功」，render.font_failure 认得出来
    browser = p.chromium.launch(executable_path=render.CHROMIUM)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.route("**/*.woff2", lambda r: r.abort())
    page.goto(engine_uri, wait_until="networkidle")
    try:
        page.evaluate("([s, a]) => init(s, a)", [scene, assets]); why = None
    except PlaywrightError as e:
        why = render.font_failure(e)
    browser.close()
    check("字体文件加载不出来（woff2 请求被拦掉）：init 报「字体没加载成功」", bool(why), why or "没有报错")

    # 3 字体「加载成功」但其实是备用字体（load 返回的列表不是空的，但画出来和 sans-serif 一样宽：reviewer 说的「返回列表不是空的」拦不住的那种）
    browser = p.chromium.launch(executable_path=render.CHROMIUM)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    fake = css.replace('format("woff2");', 'format("woff2"); unicode-range: U+0020;')   # 字体文件是真的，但只对空格生效：load() 返回的列表不是空的，字形却都是备用字体
    page.route("**/fonts.css", lambda r: r.fulfill(status=200, content_type="text/css", body=fake))
    page.goto(engine_uri, wait_until="networkidle")
    try:
        page.evaluate("([s, a]) => init(s, a)", [scene, assets]); why = None
    except PlaywrightError as e:
        why = render.font_failure(e)
    browser.close()
    check("字体只对空格生效（load 返回的列表不是空的，字形都是备用字体，E1 那种）：init 报「字体没加载成功」", bool(why), why or "没有报错")

    # 3b ZCOOL KuaiLe 里没有的字（tj01 的「絺」）：fonts.css 里用 Noto Sans SC 补，画出来和 Noto 一样（不是系统备用字体）
    b3, pg3 = render.open_page(p, scene)
    res = pg3.evaluate("""async () => {
      await document.fonts.load('400 100px "ZCOOL KuaiLe"', '絺疵');
      const g = document.createElement('canvas').getContext('2d');
      const ink = f => { g.font = f; const m = g.measureText('絺'); return [m.width, m.actualBoundingBoxAscent, m.actualBoundingBoxDescent, m.actualBoundingBoxLeft + m.actualBoundingBoxRight]; };
      return { zc: ink('400 100px "ZCOOL KuaiLe", sans-serif'), noto: ink('500 100px "Noto Sans SC", sans-serif'), sans: ink('400 100px sans-serif') };
    }""")
    b3.close()
    same_noto = all(abs(a - c) < 0.5 for a, c in zip(res["zc"], res["noto"])) and any(abs(a - c) > 0.5 for a, c in zip(res["zc"], res["sans"]))
    check("ZCOOL KuaiLe 里没有的字（絺）：画出来和 Noto Sans SC 一样，不是系统备用字体", same_noto, str(res))

    # 4 正常打开：不报错；截同一个时刻两次（两个新浏览器），带容差对比 + 看是不是逐像素相同
    srv = bs.serve()
    shots = []
    for run in range(2):
        browser, page, _ = bs.open_stage(p, 1, srv)
        page.evaluate("window.renderFrame(20.0)")
        shots.append(Image.open(BytesIO(page.screenshot(type="png"))).convert("RGB"))
        browser.close()
    r = imgdiff.report(np.asarray(shots[0]).astype(np.int16), np.asarray(shots[1]).astype(np.int16))
    check("同一个时刻在两个新浏览器里各截一次：没有变化区域（带容差）", r["same"], imgdiff.describe(r))
    check("……而且逐像素完全相同（字体本地化以后不再有抗锯齿差异）", r["exact"], "不是逐像素相同：容差对比通过，但要在报告里写出来" if not r["exact"] else "")
    m = kicker_metrics(shots[0])
    check("卷号胶囊是 ZCOOL KuaiLe（宽 338、字形像素约 2620–2640，不是备用字体的 356 / 约 2420）", abs(m[0] - 338) <= 4 and abs(m[1] - 2630) <= 80, f"宽 {m[0]}、字形像素 {m[1]}")

    srv.shutdown()

# 5 每一段成片的第一帧：render_seg 每段新开浏览器，第一帧和第二帧的卷号胶囊要一样
seg = OUT / "stage3d" / "shot1_0.mp4"
(OUT / "stage3d").mkdir(parents=True, exist_ok=True)
for f in list((OUT / "stage3d").glob("shot1_0.*")):
    f.unlink()
bs.render_seg((1, 0, 0, 3))
frames = OUT / "seg_frames"; frames.mkdir(exist_ok=True)
for f in frames.glob("*.png"):
    f.unlink()
subprocess.run([render.FFMPEG, "-loglevel", "error", "-y", "-i", str(seg), str(frames / "f%d.png")], check=True)
ms = [kicker_metrics(Image.open(frames / f"f{i}.png")) for i in (1, 2, 3)]
check("render_seg 渲出的一段：第 1、2、3 帧的卷号胶囊都是 ZCOOL KuaiLe（第一帧字体是对的；视频压缩会让宽度差 2 像素、字形像素差几十，备用字体是 356 / 约 2420，差得远）",
      all(abs(m[0] - 338) <= 4 and abs(m[1] - 2630) <= 80 for m in ms), f"（宽, 字形像素）{ms}")

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
