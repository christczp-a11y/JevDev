"""贴纸弹出（带弹簧过冲、轻微挤压、停稳后一直微微晃）。也是写新特效的模板：照这个文件的结构抄。

分镜表里：
  {"type": "sticker", "name": "question", "pos": [800, 520], "at": {"line": 1, "word": "给"}}      图片贴纸 = video/motion/stickers/question.png
  {"type": "sticker", "text": "咚", "pos": [300, 700], "at": {...}, "size": 180, "color": "#c8372d"}   文字贴纸（临时的拟声字），ZCOOL KuaiLe 厚纸剪字 + 白纸边
可选：size（图片 = 屏幕高度，文字 = 字号，默认 200）、rot（角度，默认 0）、flip（水平翻转）、dur（停留几秒，默认到镜头结束）、
      depth（视差，默认 1 = 贴在画上跟着镜头走；0 = 钉在屏幕上）、sfx（音效名，默认 pop；写 null 静音）。
系列贴纸（video/motion/stickers/）：question 问号、question3 三个问号、exclaim 感叹号、bulb 灯泡、sweat 汗滴、anger 怒气、star 闪光星星、
  star_eyes 星星眼、heart 小心心、dong「咚」、pa「啪」、sou「嗖」。
"""
import math

from engine.consts import MOTION
from fx import _paper as P
from fx import fx

STICKERS = MOTION / "stickers"
OUT = 0.22


def names():
    return sorted(f.stem for f in STICKERS.glob("*.png"))


def _assets(p):
    return [STICKERS / f"{p['name']}.png"] if p.get("name") else []


def _check(p):
    errs = P.need_pos(p)
    if bool(p.get("name")) == bool(p.get("text")):
        errs.append("sticker 要写 name（图片贴纸）或 text（文字贴纸），二选一")
    if p.get("name") and not (STICKERS / f"{p['name']}.png").exists():
        errs.append(f"没有叫 {p['name']!r} 的贴纸（有：{names()}）")
    errs += P.glyph_errors(p.get("text"))
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    return errs


def _build_image(canvas, path, size, flip):
    im = P.fit_height(P.load_pil(canvas, path), size)
    if flip:
        im = im.transpose(P.Image.FLIP_LEFT_RIGHT)
    return P.add_shadow(im)


@fx("sticker", layer="front", sfx="pop", assets=_assets, check=_check)
def sticker(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, OUT):
        return
    size = float(params.get("size", 200))
    flip = bool(params.get("flip", False))
    if params.get("name"):
        path = STICKERS / f"{params['name']}.png"
        sp = P.sprite(canvas, ("sticker", str(path), size, flip), lambda: _build_image(canvas, path, size, flip))
    else:
        col = P.rgb(params.get("color"), P.RED)
        sp = P.sprite(canvas, ("stext", params["text"], size, col), lambda: P.chunky_text(params["text"], size, col))
    s, sx, sy = P.pop_xy(u)
    a = P.fade_out(u, dur, OUT)
    if dur is not None and u > dur:
        s *= a
    wob = 2.2 * P.sstep(0.4, 0.8, u) * math.sin(2 * math.pi * u / 1.7)
    x, y = params["pos"]
    canvas.blit(sp, x, y, scale=s, sx=sx, sy=sy, rot=float(params.get("rot", 0)) + wob, alpha=min(1.0, a), depth=float(params.get("depth", 1.0)))
