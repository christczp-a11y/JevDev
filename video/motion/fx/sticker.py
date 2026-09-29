"""示例特效：贴纸弹出（带过冲）。也是写新特效的模板：照这个文件的结构抄。

分镜表里：
  {"type": "sticker", "name": "question", "pos": [800, 520], "at": {"line": 1, "word": "给"}}      图片贴纸 = video/motion/stickers/question.png
  {"type": "sticker", "text": "咚", "pos": [300, 700], "at": {...}, "size": 180, "color": "#c8372d"}   文字贴纸（拟声字、砸字），ZCOOL KuaiLe + 白纸边
可选：size（图片 = 屏幕高度，文字 = 字号，默认 200）、rot（角度，默认 0）、dur（停留几秒，默认到镜头结束）、
      depth（视差，默认 1 = 贴在画上跟着镜头走；0 = 钉在屏幕上）、sfx（音效名，默认 pop；写 null 静音）。
"""
import math

from engine import anim
from engine.consts import MOTION, RED
from fx import fx

STICKERS = MOTION / "stickers"
POP_IN, POP_OUT = 0.35, 0.20


def _color(v):
    if v is None:
        return RED
    v = v.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _assets(p):
    return [STICKERS / f"{p['name']}.png"] if p.get("name") else []


def _check(p):
    errs = []
    if bool(p.get("name")) == bool(p.get("text")):
        errs.append("sticker 要写 name（图片贴纸）或 text（文字贴纸），二选一")
    if not (isinstance(p.get("pos"), list) and len(p["pos"]) == 2):
        errs.append("sticker 缺 pos: [x, y]")
    return errs


@fx("sticker", layer="front", sfx="pop", assets=_assets, check=_check)
def sticker(canvas, t, params, at):
    u = t - at                                   # 特效开始以后过了几秒
    if u < 0:
        return
    dur = params.get("dur")
    if dur is not None and u > dur + POP_OUT:
        return
    size = float(params.get("size", 200))
    if params.get("name"):
        sp = canvas.assets.sticker(STICKERS / f"{params['name']}.png", size)
    else:
        sp = canvas.assets.text(params["text"], "title", int(size), _color(params.get("color")), edge=max(6, int(size * 0.06)))
    scale = anim.back_out(u / POP_IN)            # 0 → 1，冲过头再回来
    if dur is not None and u > dur:
        scale *= 1 - anim.in_cubic((u - dur) / POP_OUT)
    wobble = 2.5 * anim.smooth((u - POP_IN) / 0.3) * math.sin(2 * math.pi * u / 1.6)
    x, y = params["pos"]
    canvas.blit(sp, x, y, scale=scale, rot=float(params.get("rot", 0)) + wobble, depth=float(params.get("depth", 1.0)))
