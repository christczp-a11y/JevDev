"""交付前自检：这次改动让画面上哪些地方变了？（Chris 2026-09-28：改了又错——城门打通以后，门洞里露出一棵悬空的树）

只检查「改的那个东西对不对」是不够的：改动常常让别的地方跟着变（新露出来的东西、被挤开的东西）。
做法：把「上一个交付版本」（git 提交）和「现在的工作区」在同样的时刻各渲染一遍——每秒一帧，外加合理性复查的关键时刻；
每个时刻截两张：带人物的画面、藏起人物的纯背景。逐像素比较，圈出所有变化的区域，把每个区域的「改前 | 改后」放大拼成检查图。
检查图必须逐张看完（Claude 用 Read 打开），并在 memory/log 里写一句结论，才能把视频交给 Chris。
Jev 可用时，再跑 video/logic_qa.py。

用法：python video/selfcheck.py <剧本.json> [--base 提交，默认 HEAD]
说明：拿第 0 步第 19 项（字体本地化）之前的提交当 --base 时，文字区域（卷号、标签、字幕）都会被标成变化——改前是备用字体，改后是 ZCOOL KuaiLe / Noto Sans SC，这是字体修好的正常结果，不是新问题。
输出：video/out/selfcheck_<剧本名>/sheet_XX.png（检查图）和 summary.json
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent
BAND = (0, 560, 1080, 1168)   # 中间的闯关画面


def dump(root, scene_rel, times, out):
    """用 root 里的那份代码渲染 times 这些时刻（子进程里跑，改前、改后的代码互不干扰）。"""
    sys.path.insert(0, str(Path(root) / "video"))
    import render
    from playwright.sync_api import sync_playwright
    scene = render.load_scene(Path(root) / scene_rel)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # 人名牌不进对比图。改前（--base 的老提交）的 render.open_page 没有 hide_nametags 参数，老版本也没有人名牌：只有支持这个参数时才传，
        # 不支持就直接设 window.hideNametags（老的 engine.html 里没人读它，无害）
        import inspect
        if "hide_nametags" in inspect.signature(render.open_page).parameters:
            browser, page = render.open_page(p, scene, hide_nametags=True)
        else:
            browser, page = render.open_page(p, scene)
            page.evaluate("() => { window.hideNametags = true; }")
        for hide in (False, True):
            page.evaluate(f"window.hideActors = {'true' if hide else 'false'}")
            for t in times:
                im = Image.open(BytesIO(render.grab(page, t, "image/png"))).convert("RGB").crop(BAND)
                im.save(out / f"{'bg' if hide else 'full'}_{t:06.2f}.png")
        browser.close()


def moments(scene_path):
    """每秒一帧 + 合理性复查的关键时刻（拿不到时只用每秒一帧）。"""
    scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    ts = {round(t + 0.5, 2) for t in range(int(scene["duration"]))}
    try:
        import types
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT.parent))
        sys.modules.setdefault("jevdev.jev", types.ModuleType("jevdev.jev"))   # 只借用抽帧逻辑，不调用 Jev
        import logic_qa
        import render
        ts |= {round(m[0], 2) for m in logic_qa.moments(render.load_scene(Path(scene_path)))}
    except Exception as exc:   # noqa: BLE001
        print(f"  （没拿到关键时刻，只按每秒一帧：{type(exc).__name__}）")
    return sorted(t for t in ts if t < scene["duration"])


def regions(a, b):
    """两张图里变了的区域（合并相邻的变化，外扩 30 像素），返回 [(x0, y0, x1, y1), ...]。"""
    d = np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).max(-1) > 24
    d = ndimage.binary_opening(d, iterations=1)
    if not d.any():
        return []
    lab, _ = ndimage.label(ndimage.binary_dilation(d, iterations=30))
    out = []
    for sl in ndimage.find_objects(lab):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        out.append((x0, y0, x1, y1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--dump", nargs=3, metavar=("ROOT", "TIMES_JSON", "OUT"), help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.dump:
        dump(args.dump[0], args.scene, json.loads(args.dump[1]), args.dump[2])
        return

    repo = ROOT.parent
    scene_rel = str(Path(args.scene).resolve().relative_to(repo))
    out = ROOT / "out" / f"selfcheck_{Path(args.scene).stem}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    times = moments(args.scene)
    print(f"{len(times)} 个时刻，改前 = {args.base}，改后 = 工作区")
    py = sys.executable
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "--detach", str(base), args.base], check=True)
        try:
            for root, tag in ((base, "before"), (repo, "after")):
                subprocess.run([py, __file__, scene_rel, "--dump", str(root), json.dumps(times), str(out / tag)], check=True, cwd=repo)
        finally:
            subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(base)], check=True)

    # 逐帧比较：同一个区域在相邻时刻反复出现时只留一次（看最早的那一帧），避免检查图重复
    items, seen = [], []
    for kind in ("bg", "full"):
        for t in times:
            a = Image.open(out / "before" / f"{kind}_{t:06.2f}.png")
            b = Image.open(out / "after" / f"{kind}_{t:06.2f}.png")
            for box in regions(a, b):
                key = (kind, tuple(v // 60 for v in box))
                if key in seen:
                    continue
                seen.append(key)
                items.append((kind, t, box, a.crop(box), b.crop(box)))
    summary = {"times": times, "changes": [{"kind": k, "t": t, "box": list(bx)} for k, t, bx, _, _ in items]}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    if not items:
        print("没有任何画面变化")
        return
    # 检查图：每行一个变化区域「改前 | 改后」，放大到宽 480；每张最多 6 行
    rows = []
    for kind, t, box, a, b in items:
        k = min(2.0, 480 / max(a.width, 1))
        a2, b2 = (im.resize((max(1, int(im.width * k)), max(1, int(im.height * k)))) for im in (a, b))
        row = Image.new("RGB", (a2.width * 2 + 30, a2.height + 26), "white")
        row.paste(a2, (0, 26))
        row.paste(b2, (a2.width + 30, 26))
        ImageDraw.Draw(row).text((4, 6), f"{'纯背景' if kind == 'bg' else '带人物'} {t:.2f}s  区域 {box}   左=改前  右=改后", fill="black")
        rows.append(row)
    sheets = [rows[i:i + 6] for i in range(0, len(rows), 6)]
    for n, group in enumerate(sheets, 1):
        W, H = max(r.width for r in group), sum(r.height + 12 for r in group)
        sheet = Image.new("RGB", (W, H), (230, 230, 230))
        y = 0
        for r in group:
            sheet.paste(r, (0, y))
            y += r.height + 12
        sheet.save(out / f"sheet_{n:02d}.png")
    print(f"{len(items)} 处变化 → {len(sheets)} 张检查图：{out}/sheet_*.png（必须逐张看完）")


if __name__ == "__main__":
    main()
