"""漫画线：集中线、放射速度线、横向速度线。画在整个画面上（不跟镜头动），都是「尖头细长的纸条」，一直在缓缓流动，不闪。

  {"type": "lines_focus",  "at": {...}, "pos": [540, 900]}                          集中线：细而淡的线，只画在画面边上，往 pos 收拢，中间大片留白（惊讶、揭晓、点题）
  {"type": "lines_radial", "at": {...}, "pos": [540, 900]}                          放射速度线：一条条从 pos 往外飞（「燃」、冲刺、大喊）
  {"type": "lines_speed",  "at": {...}, "dir": "left"}                              横向速度线：横着飞过画面（人物在跑，dir 是线飞的方向：人往右跑就写 left）
共同的可选参数：
  color：ink（默认，集中线）/ cream（默认，放射和横向）/ white / gold / "#rrggbb"；alpha：0–1（集中线 0.30，放射 0.9，横向 0.85）；
  dur：停留几秒（默认到镜头结束），最后 0.2 秒淡出；count：线的数量；sfx：音效名（写 null 静音）。
  lines_focus 另有：
    center：线往哪里收拢（默认 = pos，都不写 = [540, 900]）；
    clear：[x, y, r]——这个圆里**一根线都不画**（圆边 40 像素柔和过渡），用来让开人物的脸和要看的东西；不写 = 以 center 为圆心、半径 380 的圆；写一个数 = 以 center 为圆心的这个半径；
    线只出现在「圆心到画面边」这条路的外半程（离画面边越近越明显），所以再大的画面中间也是干净的，看起来是边上一圈线，不是画面被划花（PITFALLS M2）。
  lines_speed 另有 y0、y1（横线出现的高度范围，默认 380–1330，不进标题条和字幕）。
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
    for k in ("pos", "center"):
        if k in p and not (isinstance(p[k], (list, tuple)) and len(p[k]) == 2):
            errs.append(f"{k} 要写成 [x, y]")
    c = p.get("clear")
    if c is not None and not (isinstance(c, (int, float)) or (isinstance(c, (list, tuple)) and len(c) == 3 and all(isinstance(v, (int, float)) for v in c))):
        errs.append("clear 要写成 [x, y, r]（这个圆里不画线）或者一个半径数字")
    return errs


def _envelope(u, dur):
    """出现（0.14 秒淡入）、停留、淡出（0.2 秒）；返回 0..1，None = 已经结束。"""
    if u < 0 or P.gone(u, dur, FADE_OUT):
        return None
    return anim.smooth(u / FADE_IN) * P.fade_out(u, dur, FADE_OUT)


_ramp_cache = {}


def _edge_ramp(w, h, cx, cy, S):
    """每个像素「离圆心多远 / 圆心沿这个方向到画面边多远」k（0 在圆心、1 在画面边上）→ 线的可见度 smoothstep((k − 0.45) / 0.4)：
    只有外半程可见，往画面边越来越明显。按 (尺寸, 圆心) 缓存。"""
    key = (w, h, round(cx), round(cy))
    if key not in _ramp_cache:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx, dy = xx - cx * S, yy - cy * S
        tx = np.where(dx > 0, (w - cx * S) / np.maximum(dx, 1e-6), np.where(dx < 0, (0 - cx * S) / np.minimum(dx, -1e-6), 1e9))
        ty = np.where(dy > 0, (h - cy * S) / np.maximum(dy, 1e-6), np.where(dy < 0, (0 - cy * S) / np.minimum(dy, -1e-6), 1e9))
        k = 1.0 / np.maximum(np.minimum(tx, ty), 1e-6)              # 这个像素在「圆心 → 画面边」这条射线上走了几分之几（射线走到边时 k = 1）
        k = np.clip(k, 0, 1.5)
        r = np.clip((k - 0.45) / 0.4, 0, 1)
        _ramp_cache[key] = (r * r * (3 - 2 * r)).astype(np.float32)
        if len(_ramp_cache) > 8:
            _ramp_cache.pop(next(iter(_ramp_cache)))
    return _ramp_cache[key]


@fx("lines_focus", params=['pos', 'center', 'clear', 'color', 'alpha', 'count'], layer="front", sfx="focus", check=_check)
def lines_focus(canvas, t, params, at):
    u = t - at
    env = _envelope(u, params.get("dur"))
    if env is None:
        return
    cx, cy = params.get("center", params.get("pos", [C.W / 2, 900]))
    n = int(params.get("count", 84))
    clear = params.get("clear")
    if isinstance(clear, (list, tuple)):
        kx, ky, kr = (float(v) for v in clear)
    else:
        kx, ky, kr = cx, cy, float(clear if clear is not None else 380)
    col = P.rgb(params.get("color"), P.INK)
    alpha = float(params.get("alpha", 0.30)) * env
    rng = np.random.default_rng(P.seed_of("focus", n))
    ang = (np.arange(n) + rng.uniform(-0.35, 0.35, n)) * (2 * math.pi / n) + 0.03 * u          # 慢慢转一点点
    breathe = 1 + 0.06 * np.sin(2 * math.pi * (0.7 * u + rng.uniform(0, 1, n)))
    r_in = 260.0 * rng.uniform(0.6, 1.4, n) * breathe * (1 + 1.4 * (1 - anim.out_cubic(u / 0.22)))   # 刚出现时从远处收拢过来；可见度由外半程的 ramp 管
    half = rng.uniform(0.0022, 0.0055, n) * (1 + 0.2 * np.sin(2 * math.pi * (0.5 * u + rng.uniform(0, 1, n))))    # 细：1000 像素外的线宽约 4–11 像素
    R = 1900.0
    mask = P.new_mask(canvas)
    for i in range(n):
        a = ang[i]
        tip = (cx + r_in[i] * math.cos(a), cy + r_in[i] * math.sin(a))
        pts = [tip, (cx + R * math.cos(a - half[i]), cy + R * math.sin(a - half[i])), (cx + R * math.cos(a + half[i]), cy + R * math.sin(a + half[i]))]
        P.fill_poly(canvas, mask, pts)
    m = mask.astype(np.float32) * _edge_ramp(canvas.w, canvas.h, cx, cy, canvas.S)
    if kr > 0:                                                                                    # clear 圆里不画线（40 像素柔和边）
        yy, xx = np.mgrid[0:canvas.h, 0:canvas.w].astype(np.float32)
        d = np.hypot(xx - kx * canvas.S, yy - ky * canvas.S)
        m *= np.clip((d - kr * canvas.S) / (40 * canvas.S), 0, 1)
    P.blend(canvas, m.astype(np.uint8), col, alpha)


@fx("lines_radial", params=['pos', 'color', 'alpha', 'count'], layer="front", sfx="burst", check=_check)
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


@fx("lines_speed", params=['dir', 'y0', 'y1', 'color', 'alpha', 'count'], layer="front", sfx="whoosh", check=_check)
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
