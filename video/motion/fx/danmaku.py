"""弹幕：一条条纸条从右往左飞过画面（「把你的选择打在弹幕上！」）。每条是一张手撕边的小纸条（米白 / 鹅黄 / 天蓝 / 薄荷 / 粉，白纸边、纸影、纸纹），墨色字，飘着飞：
大小、速度、高度各不一样，行与行错开，飞的时候轻轻上下飘、微微晃。

  {"type": "danmaku", "texts": ["给！", "不给！", "给！", "我选不给"], "at": {"line": 40}, "dur": 3.0, "density": 1.0}
参数：
  texts    纸条上的字（1–16 条，每条 ≤ 10 个字），按顺序循环用；
  dur      弹幕持续放多久（默认 3.0 秒）：纸条在这段时间的前 75% 里陆续从右边飞出来，每条飞完整个画面（约 2–3 秒），所以特效总共持续 dur + 约 3 秒；
  density  密度（默认 1.0 ≈ 10 条，0.3 ≈ 3 条，2.4 ≈ 24 条）；
  area     [x0, y0, x1, y1]：纸条飞的高度范围，默认 [0, 360, 1080, 1380]（x 不限制，整屏飞过）。**y 必须在 340–1400 之内**：标题条在 330 以上、字幕卡从 1420 起，弹幕不压它们；
  avoid    自动避开人物的脸（和氛围粒子一样：出片前按镜头里每个人物的脸框算，纸条飞近脸框会渐隐，不会盖住脸）；avoid: [] 关掉，avoid: [[x0,y0,x1,y1]] 自己指定。
音效：每条纸条从右边飞出来的时刻一声轻快的「嗖」`danmaku_whoosh`（出片前 check 按每条的出场时刻排进镜头的音效表，三档轻重交替）；写 "sfx": null 静音，写别的名字就换成那个声音。
定格配合：freeze 定格中开始的弹幕照常飞（见 freeze.py）。
"""
import functools
import math

import numpy as np

from engine import consts as C
from fx import _paper as P
from fx import fx

DEF_AREA = [0, 360, 1080, 1380]
ROW_H = 112
PAPERS = [(250, 240, 220), (255, 232, 150), (190, 222, 244), (200, 232, 206), (250, 206, 206)]
LIFE = 3.0


def _check(p, shot=None):
    errs = []
    tx = p.get("texts")
    if not (isinstance(tx, list) and 1 <= len(tx) <= 16 and all(isinstance(x, str) and 1 <= len(x) <= 10 for x in tx)):
        return ["danmaku 的 texts 要写 1–16 条文字，每条 1–10 个字，比如 [\"给！\", \"不给！\"]"]
    errs += P.glyph_errors(*tx)
    dens = p.get("density", 1.0)
    if not isinstance(dens, (int, float)) or not 0.2 <= dens <= 2.5:
        errs.append("density 要写 0.2–2.5 的数（默认 1.0 ≈ 10 条）")
    d = p.get("dur", 3.0)
    if not isinstance(d, (int, float)) or not 0.5 <= d <= 10:
        errs.append("danmaku 的 dur 要写 0.5–10 秒（默认 3.0）")
    a = p.get("area", DEF_AREA)
    if not (isinstance(a, (list, tuple)) and len(a) == 4 and all(isinstance(v, (int, float)) for v in a)):
        errs.append("area 要写成 [x0, y0, x1, y1]")
    elif a[1] < 340 or a[3] > 1400 or a[3] - a[1] < ROW_H:
        errs.append(f"danmaku 的 area={list(a)}：弹幕要在 y 340–1400 之内（标题条在 330 以上，字幕卡从 1420 起），而且至少要放得下一行（高 {ROW_H}）")
    if not errs:
        if shot is not None and "avoid" not in p:
            p["_avoid"] = P.face_avoid(shot, pad=30)
        elif "avoid" in p:
            p["_avoid"] = p["avoid"]
        if shot is not None and p.get("sfx", "x") is not None:
            name = p.get("sfx") or "danmaku_whoosh"
            for i, it in enumerate(_items(p)):
                if name == "danmaku_whoosh":
                    _add_whoosh(shot, p.get("at"), it["spawn"], -2.0 - (i % 3) * 1.6)
                else:
                    P.add_sfx(shot, p.get("at"), it["spawn"], name)
    return errs


def _add_whoosh(shot, at, dt, gain):
    """同 P.add_sfx，带增益（dB）。"""
    a = dict(at) if isinstance(at, dict) else {}
    a["dt"] = round(float(a.get("dt", 0.0)) + dt, 4)
    entry = {"name": "danmaku_whoosh", "at": a, "gain": gain}
    lst = shot.setdefault("sfx", [])
    if entry not in lst:
        lst.append(entry)


def _items(p):
    """这个弹幕的全部纸条（按出场时间排）：[{text, size, y, speed, spawn, w, color, rot, phase}]。只依赖参数（固定种子），draw 和 check 用同一份。"""
    return _items_cached(tuple(p["texts"]), float(p.get("dur", 3.0)), float(p.get("density", 1.0)), tuple(float(v) for v in p.get("area", DEF_AREA)))


@functools.lru_cache(maxsize=64)
def _items_cached(texts, dur, dens, area):
    x0, y0, x1, y1 = area
    n = max(3, min(24, int(round(10 * dens))))
    rng = np.random.default_rng(P.seed_of("danmaku", "|".join(texts), n, y0, y1))
    rows = max(1, int((y1 - y0) // ROW_H))
    order = rng.permutation(rows)
    free_at = [0.0] * rows
    out = []
    for i in range(n):
        size = int(rng.choice([44, 50, 58, 66, 76], p=[0.25, 0.25, 0.22, 0.18, 0.10]))
        text = texts[i % len(texts)]
        w = P.text_width(text, "title", size) + 2 * 30
        row = int(order[i % rows])
        speed = float(rng.uniform(430, 780))
        spawn = max(dur * 0.75 * i / n + float(rng.uniform(0.0, 0.12)), free_at[row])
        free_at[row] = spawn + (w + 160) / speed                                # 同一行：前一条飞出去一段以后下一条才出来，不重叠
        y = y0 + ROW_H * (row + 0.5) + float(rng.uniform(-8, 8))
        out.append(dict(text=text, size=size, y=y, speed=speed, spawn=spawn, w=w, color=int(rng.integers(0, len(PAPERS))), rot=float(rng.uniform(-2.2, 2.2)),
                        phase=float(rng.uniform(0, 1))))
    out.sort(key=lambda d: d["spawn"])
    return out


def _slip(text, size, color):
    """一张手撕边的小纸条：纸色 + 纸纹、墨色字、白纸边、纸影。"""
    tw = P.text_image(text, "title", size, C.INK)
    w, h = tw.width + 60, int(size * 1.55)
    card = P.paper_card(w, h, PAPERS[color], 14, seed=17 + len(text) * 3 + color, tex=0.05, torn=2.5)
    card.alpha_composite(tw, ((w - tw.width) // 2, (h - tw.height) // 2 - 1))
    return P.add_shadow(P.edged(card, 6, False), (3, 6), 6, 0.3, 14)


@fx("danmaku", params=["texts", "density", "area", "avoid"], layer="front", sfx=None, check=_check)
def danmaku(canvas, t, params, at):
    u = t - at
    if u < 0:
        return
    items = _items(params)
    if u > items[-1]["spawn"] + (C.W + items[-1]["w"]) / min(it["speed"] for it in items) + 0.3:
        return
    boxes = params.get("_avoid") or []
    for it in items:
        ui = u - it["spawn"]
        if ui < 0:
            continue
        x = C.W + it["w"] / 2 - it["speed"] * ui
        if x < -it["w"]:
            continue
        y = it["y"] + 5.0 * math.sin(2 * math.pi * (0.9 * ui + it["phase"]))
        h = it["size"] * 1.55
        k = 1.0
        for bx0, by0, bx1, by1 in boxes:                                        # 纸条整条（不只是中心）离脸框近了就渐隐
            k = min(k, P.avoid_alpha([[bx0 - it["w"] / 2, by0 - h / 2, bx1 + it["w"] / 2, by1 + h / 2]], x, y, soft=90.0))
        if k <= 0.01:
            continue
        sp = P.sprite(canvas, ("danmaku", it["text"], it["size"], it["color"]), lambda it=it: _slip(it["text"], it["size"], it["color"]))
        rot = it["rot"] + 1.6 * math.sin(2 * math.pi * (0.7 * ui + it["phase"]))
        canvas.blit(sp, x, y, rot=rot, alpha=k, depth=0)
