"""漫画线：集中线、放射速度线、横向速度线。画在整个画面上（不跟镜头动），都是「尖头细长的纸条」，一直在缓缓流动，不闪。

  {"type": "lines_focus",  "at": {...}, "pos": [540, 900]}                          集中线：从画面边缘往 pos 收拢，中间留白（惊讶、揭晓、点题）
  {"type": "lines_radial", "at": {...}, "pos": [540, 900]}                          放射速度线：一条条从 pos 往外飞（「燃」、冲刺、大喊）
  {"type": "lines_speed",  "at": {...}, "dir": "left"}                              横向速度线：横着飞过画面（人物在跑，dir 是线飞的方向：人往右跑就写 left）
共同的可选参数：
  color：ink（默认，集中线）/ cream（默认，放射和横向）/ white / gold / "#rrggbb"；alpha：0–1（集中线 0.45，放射 0.9，横向 0.85）；
  dur：停留几秒（默认到镜头结束），最后 0.2 秒淡出；count：线的数量；sfx：音效名（写 null 静音）。
  lines_focus 另有 clear（中间留白的半径，默认 360）；lines_speed 另有 y0、y1（横线出现的高度范围，默认 380–1330，不进标题条和字幕）。
"""
import math

import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx

FADE_IN, FADE_OUT = 0.14, 0.2


def _check(p):
    errs = []
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    if "pos" in p and not (isinstance(p["pos"], (list, tuple)) and len(p["pos"]) == 2):
        errs.append("pos 要写成 [x, y]")
    return errs


def _envelope(u, dur):
    """出现（0.14 秒淡入）、停留、淡出（0.2 秒）；返回 0..1，None = 已经结束。"""
    if u < 0 or P.gone(u, dur, FADE_OUT):
        return None
    return anim.smooth(u / FADE_IN) * P.fade_out(u, dur, FADE_OUT)


@fx("lines_focus", layer="front", sfx="focus", check=_check)
def lines_focus(canvas, t, params, at):
    u = t - at
    env = _envelope(u, params.get("dur"))
    if env is None:
        return
    cx, cy = params.get("pos", [C.W / 2, 900])
    n = int(params.get("count", 72))
    clear = float(params.get("clear", 360))
    col = P.rgb(params.get("color"), P.INK)
    alpha = float(params.get("alpha", 0.45)) * env
    rng = np.random.default_rng(P.seed_of("focus", n))
    ang = (np.arange(n) + rng.uniform(-0.35, 0.35, n)) * (2 * math.pi / n) + 0.05 * u          # 慢慢转一点点
    r_in = clear * rng.uniform(0.85, 1.7, n) * (1 + 0.07 * np.sin(2 * math.pi * (0.8 * u + rng.uniform(0, 1, n))))
    r_in = r_in * (1 + 1.6 * (1 - anim.out_cubic(u / 0.22)))                                   # 刚出现时从远处收拢过来
    half = rng.uniform(0.004, 0.012, n) * (1 + 0.2 * np.sin(2 * math.pi * (0.5 * u + rng.uniform(0, 1, n))))
    R = 1700.0
    mask = P.new_mask(canvas)
    for i in range(n):
        a = ang[i]
        tip = (cx + r_in[i] * math.cos(a), cy + r_in[i] * math.sin(a))
        pts = [tip, (cx + R * math.cos(a - half[i]), cy + R * math.sin(a - half[i])), (cx + R * math.cos(a + half[i]), cy + R * math.sin(a + half[i]))]
        P.fill_poly(canvas, mask, pts)
    P.blend(canvas, mask, col, alpha)


@fx("lines_radial", layer="front", sfx="burst", check=_check)
def lines_radial(canvas, t, params, at):
    u = t - at
    env = _envelope(u, params.get("dur"))
    if env is None:
        return
    cx, cy = params.get("pos", [C.W / 2, 900])
    n = int(params.get("count", 52))
    col = P.rgb(params.get("color"), P.CREAM)
    alpha = float(params.get("alpha", 0.9)) * env
    rng = np.random.default_rng(P.seed_of("radial", n))
    ang = (np.arange(n) + rng.uniform(-0.4, 0.4, n)) * (2 * math.pi / n)
    period = rng.uniform(0.55, 0.95, n)
    phase = rng.uniform(0, 1, n)
    length = rng.uniform(170, 460, n)
    width = rng.uniform(9, 24, n)
    r0, r1 = 210.0, 1350.0
    mask = P.new_mask(canvas)
    for i in range(n):
        s = (u / period[i] + phase[i]) % 1.0
        head = r0 + (r1 - r0) * s ** 1.5
        tail = max(r0, head - length[i] * (0.35 + s))
        w = width[i] * (0.4 + 1.3 * s) * min(1.0, s * 8) * (1 - 0.6 * s ** 4)
        c, sn = math.cos(ang[i]), math.sin(ang[i])
        hx, hy, tx, ty = cx + head * c, cy + head * sn, cx + tail * c, cy + tail * sn
        P.fill_poly(canvas, mask, [(tx, ty), (hx - sn * w / 2, hy + c * w / 2), (hx + sn * w / 2, hy - c * w / 2)])
    P.blend(canvas, mask, col, alpha)


@fx("lines_speed", layer="front", sfx="whoosh", check=_check)
def lines_speed(canvas, t, params, at):
    u = t - at
    env = _envelope(u, params.get("dur"))
    if env is None:
        return
    n = int(params.get("count", 30))
    col = P.rgb(params.get("color"), P.CREAM)
    alpha = float(params.get("alpha", 0.85)) * env
    y0, y1 = float(params.get("y0", 380)), float(params.get("y1", 1330))
    sgn = -1.0 if params.get("dir", "left") == "left" else 1.0
    rng = np.random.default_rng(P.seed_of("speed", n))
    y = rng.uniform(y0, y1, n)
    length = rng.uniform(260, 760, n)
    thick = rng.uniform(8, 20, n)
    speed = rng.uniform(2600, 4400, n)
    off = rng.uniform(0, 1, n)
    mask = P.new_mask(canvas)
    for i in range(n):
        span = C.W + 2 * length[i]
        s = ((u * speed[i] / span) + off[i]) % 1.0
        # 头的位置：sgn<0 从右边进、往左飞
        head = (C.W + length[i] - s * span) if sgn < 0 else (-length[i] + s * span)
        tail = head - sgn * length[i]
        th = thick[i]
        P.fill_poly(canvas, mask, [(tail, y[i]), (head, y[i] - th / 2), (head, y[i] + th / 2)])
    P.blend(canvas, mask, col, alpha)
