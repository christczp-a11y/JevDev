"""转场（写在后一镜里：`"transition": "page_turn"` 或 `{"type": "iris", "dur": 0.5, "pos": [540, 900]}`；接口见 README「特效和转场接口」）。
全是纸的样子：翻书页（卷起来的纸背）、纸片擦过（三条彩色纸片斜着扫过）、墨笔刷（飞白的墨条一条条刷过）、圆圈收拢（纸圈收成一点再放开）、淡到纸色、甩镜（带运动模糊）、
tv_switch（解说台的纸屏幕展开成整个画面，「按一下，画面切到故事里」）。都是进度 p 的函数，没有随机、没有隐藏状态。
  page_turn    dur 0.7  side: right（默认，从右往左翻）/ left
  paper_wipe   dur 0.8  colors: 三条纸片的颜色（默认朱红、金、米白）；dir: right（默认，从左扫到右）/ left
  ink_wipe     dur 0.7  strokes: 笔画条数（默认 4）；dir: right / left
  iris         dur 0.7  pos: [x, y] 圆心（默认画面中心偏上 [540, 900]，可以对准主体）；color: 纸色（默认米白，也可 ink / 家族色）
  fade_paper   dur 0.7  淡到纸色再淡入下一镜（换时间、换场）
  whip         dur 0.28 dir: left（默认，画面往左甩，下一镜从右边进来）/ right / up / down
  tv_switch    dur 0.8  pos: [x, y] 纸屏幕中心（默认 [540, 700]，要和 screen 特效的 pos 一致）；w: 起始屏幕宽（默认 800）
"""
import functools
import math

import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import transition


def _pcheck(allowed_extra=()):
    def check(p):
        errs = []
        for k in ("pos",):
            if k in p and not (isinstance(p[k], (list, tuple)) and len(p[k]) == 2):
                errs.append("pos 要写成 [x, y]")
        if "colors" in p:
            for c in p["colors"]:
                if P.bad_color(c):
                    errs.append(P.bad_color(c))
        if P.bad_color(p.get("color")):
            errs.append(P.bad_color(p.get("color")))
        if p.get("dir", "left") not in ("left", "right", "up", "down"):
            errs.append("dir 只能是 left / right / up / down")
        return errs
    return check


def _smoothstep(x, e0, e1):
    t = np.clip((x - e0) / np.maximum(e1 - e0, 1e-6), 0, 1)
    return t * t * (3 - 2 * t)


@functools.lru_cache(maxsize=8)
def _paper_bg(w, h, base=(238, 228, 208)):
    """整幅纸底：奶白 + 纸纹 + 一点点暗角（BGR uint8）。"""
    t = P.paper_tex(w, h, 77)
    img = np.empty((h, w, 3), np.float32)
    img[:] = (base[2], base[1], base[0])
    img *= (1 + 0.03 * t)[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 1.414
    img *= (1 - 0.10 * np.clip((r - 0.5) / 0.5, 0, 1) ** 2)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def _mix(a, b, m):
    """m: float32 (h, w) 0..1 → a*(1-m) + b*m。"""
    if m.ndim == 2:
        m = m[..., None]
    return (a.astype(np.float32) * (1 - m) + b.astype(np.float32) * m).astype(np.uint8)


def _shadow_from(mask, canvas, dx, dy, blur, strength):
    """从一个遮罩（0..1 float）投出的软阴影（0..strength）。"""
    S = canvas.S
    M = np.float32([[1, 0, dx * S], [0, 1, dy * S]])
    sh = cv2.warpAffine(mask, M, (mask.shape[1], mask.shape[0]))
    return cv2.GaussianBlur(sh, (0, 0), max(0.8, blur * S)) * strength


# ============================== 淡到纸色 ==============================
@transition("fade_paper", dur=0.7, sfx="fade_soft", check=_pcheck())
def fade_paper(a, b, p, params, canvas):
    bg = _paper_bg(canvas.w, canvas.h)
    if p < 0.5:
        k = anim.smooth(p / 0.5)
        return cv2.addWeighted(a, 1 - k, bg, k, 0)
    k = anim.smooth((p - 0.5) / 0.5)
    return cv2.addWeighted(bg, 1 - k, b, k, 0)


# ============================== 圆圈收拢 ==============================
@transition("iris", dur=0.7, sfx="iris", check=_pcheck())
def iris(a, b, p, params, canvas):
    S = canvas.S
    h, w = canvas.h, canvas.w
    cx, cy = params.get("pos", [C.W / 2, 900])
    col = P.rgb(params.get("color"), (238, 228, 208))
    R0 = math.hypot(max(cx, C.W - cx), max(cy, C.H - cy)) * 1.02
    if p < 0.5:
        r = R0 * (1 - anim.smooth(p / 0.5)) ** 1.0
        inner = a
    else:
        r = R0 * anim.smooth((p - 0.5) / 0.5)
        inner = b
    bg = _paper_bg(w, h, tuple(col)) if col != (238, 228, 208) else _paper_bg(w, h)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - cx * S, yy - cy * S)
    rr = r * S
    inside = 1.0 - _smoothstep(d, rr - 1.2, rr + 1.2)                    # 圈里面（抗锯齿）
    ring = (1.0 - _smoothstep(np.abs(d - (rr + 7 * S)), 6 * S, 8 * S)) * (d >= rr - 1)      # 圈外那一圈白纸边
    out = _mix(bg, inner, inside)
    out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), (ring * (1 - inside)).astype(np.float32) * (r > 2))
    return out


# ============================== 甩镜 ==============================
@transition("whip", dur=0.28, sfx="whip", check=_pcheck())
def whip(a, b, p, params, canvas):
    d = params.get("dir", "left")
    h, w = a.shape[:2]
    e = anim.smooth(p)
    horizontal = d in ("left", "right")
    n = w if horizontal else h
    if d in ("left", "up"):
        strip = np.concatenate([a, b], axis=1 if horizontal else 0)
        off = int(round(n * e))
        out = strip[:, off:off + w] if horizontal else strip[off:off + h]
    else:
        strip = np.concatenate([b, a], axis=1 if horizontal else 0)
        off = int(round(n * (1 - e)))
        out = strip[:, off:off + w] if horizontal else strip[off:off + h]
    dur = float(params.get("dur", 0.28))
    # 瞬时速度（像素 / 帧）：smootherstep 的导数 30 e'(1-e')... 直接数值算
    de = (anim.smooth(min(p + 0.02, 1)) - anim.smooth(max(p - 0.02, 0))) / (min(p + 0.02, 1) - max(p - 0.02, 0) + 1e-9)
    per_frame = n * de / (dur * C.FPS)
    k = int(round(per_frame * 0.9)) | 1
    if k > 2:
        out = cv2.blur(out, (k, 1) if horizontal else (1, k))
    return np.ascontiguousarray(out)


# ============================== 纸片擦过 ==============================
@transition("paper_wipe", dur=0.8, sfx="paper_swipe", check=_pcheck())
def paper_wipe(a, b, p, params, canvas):
    S = canvas.S
    h, w = canvas.h, canvas.w
    cols = [P.rgb(c) for c in params.get("colors", ["red", "gold", "cream"])]
    right = params.get("dir", "right") == "right"
    tilt = 0.20
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    x = xx if right else (w - 1 - xx)
    s = x + tilt * (yy - h / 2)                                              # 斜着扫
    # 纸边不是直的：每一行有一点点手撕的起伏
    n1 = np.sin(yy / (37.0 * S) + 1.3) * 3 + np.sin(yy / (11.0 * S)) * 1.5
    s = s + n1 * S
    widths = [c * S for c in (330, 210, 130)]
    total = sum(widths)
    smin, smax = -tilt * h / 2 - 4 * S, w + tilt * h / 2 + 4 * S
    e = 0.7 * p + 0.3 * anim.smooth(p)                                        # 大半匀速、两头带一点缓动：最快时约画面宽度的 10% / 帧
    f = smin + (smax - smin + total) * e                                   # 最前面一条的前缘
    out = np.where((s > f)[..., None], a, b)                                    # 前缘右边是旧的，后面是新的（下面再盖纸片）
    edges = []
    cur = f
    for wd in widths[:len(cols)]:
        edges.append((cur - wd, cur))
        cur -= wd
    # 从后往前画：最后一条最先画（最靠下）
    ink = _paper_tex_cache(w, h)
    for (lo, hi), col in reversed(list(zip(edges, cols))):
        m = _smoothstep(s, lo - 1.0, lo + 1.0) * (1 - _smoothstep(s, hi - 1.0, hi + 1.0))
        # 纸下面的软阴影（投在前缘右边的内容上）
        shadow = _smoothstep(s, hi, hi + 1) * (1 - _smoothstep(s, hi + 22 * S, hi + 46 * S)) * 0.3
        out = (out.astype(np.float32) * (1 - shadow[..., None])).astype(np.uint8)
        edge = (1 - _smoothstep(hi - s, 5 * S, 7 * S)) * (s <= hi + 0.5)                                  # 前缘的白纸边
        band = np.empty((h, w, 3), np.float32)
        band[:] = (col[2], col[1], col[0])
        band *= (1 + 0.05 * ink)[..., None]
        out = _mix(out, np.clip(band, 0, 255).astype(np.uint8), m.astype(np.float32))
        out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), (edge * (m > 0.02)).astype(np.float32) * 0.95)
    return out


@functools.lru_cache(maxsize=8)
def _paper_tex_cache(w, h):
    return P.paper_tex(w, h, 88)


# ============================== 墨笔刷 ==============================
@functools.lru_cache(maxsize=8)
def _bristles(h, seed=5):
    rng = np.random.default_rng(seed)
    n = rng.standard_normal(h).astype(np.float32)
    n = cv2.GaussianBlur(n[None, :], (0, 0), 2.2)[0] * 3.2 + cv2.GaussianBlur(rng.standard_normal(h).astype(np.float32)[None, :], (0, 0), 9)[0] * 5.5
    return np.clip(n / (n.std() + 1e-6), -2.5, 2.5)


@functools.lru_cache(maxsize=8)
def _jitter_x(w, seed=9):
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.standard_normal(w).astype(np.float32)[None, :], (0, 0), 7)[0]
    n2 = cv2.GaussianBlur(rng.standard_normal(w).astype(np.float32)[None, :], (0, 0), 1.6)[0]
    return np.clip((n * 4.0 + n2 * 1.2) / 2.0, -2.5, 2.5)


@transition("ink_wipe", dur=0.7, sfx="brush", check=_pcheck())
def ink_wipe(a, b, p, params, canvas):
    """几条粗笔画的墨从左刷到右：笔头钝钝的（一排毛刷的参差），尾巴是飞白；墨条上下互相叠着，刷过的地方露出新画面。"""
    S = canvas.S
    h, w = canvas.h, canvas.w
    n = int(params.get("strokes", 4))
    right = params.get("dir", "right") == "right"
    bris = _bristles(h)
    yy = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]
    if not right:
        X = (w - 1) - X
    jx = _jitter_x(w)[None, :]
    band_h = h / n
    Lw = 0.55 * w
    stag = 0.08
    ink_m = np.zeros((h, w), np.float32)
    b_m = np.zeros((h, w), np.float32)
    for i in range(n):
        q = np.clip((p - i * stag) / (1 - (n - 1) * stag), 0, 1)
        f = -40 * S + (w + Lw + 80 * S) * anim.smooth(q)
        y0 = (i - 0.30) * band_h + jx * 9 * S                                      # 每一笔上下沿参差不齐，互相叠着盖满
        y1 = (i + 1.30) * band_h + jx[:, ::-1] * 9 * S
        vert = _smoothstep(yy, y0 - 1.5, y0 + 1.5) * (1 - _smoothstep(yy, y1 - 1.5, y1 + 1.5))
        xf = f + bris[:, None] * 7 * S                                              # 笔头：钝，毛刷参差
        xt = f - Lw * (0.70 + 0.11 * bris[:, None])                                # 尾巴：飞白
        ink_i = _smoothstep(X, xt - 1.0, xt + 1.0) * (1 - _smoothstep(X, xf - 1.0, xf + 1.0)) * vert
        b_i = (1 - _smoothstep(X, xt - 1.0, xt + 1.0)) * vert
        ink_m = np.maximum(ink_m, ink_i)
        b_m = np.maximum(b_m, b_i)
    out = _mix(a, b, b_m)
    tex = _paper_tex_cache(w, h)
    ink = np.empty((h, w, 3), np.float32)
    ink[:] = (C.INK[2], C.INK[1], C.INK[0])
    ink = ink * (1 + 0.16 * tex[..., None]) + 8
    return _mix(out, np.clip(ink, 0, 255).astype(np.uint8), ink_m)


# ============================== 翻书页 ==============================
@transition("page_turn", dur=0.7, sfx="page_flip", check=_pcheck())
def page_turn(a, b, p, params, canvas):
    """一页纸从右往左卷起来撕下去：左边是还没翻的旧画面，中间一卷带圆柱明暗的纸背（浅浅透出旧画面的镜像），右边露出新画面；卷得过去的地方有软阴影。"""
    S = canvas.S
    h, w = canvas.h, canvas.w
    left = params.get("side", "right") == "left"
    if left:
        a, b = a[:, ::-1], b[:, ::-1]
    R = 150.0 * S
    tilt = 0.10
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    s = xx + tilt * (yy - h * 0.5)
    smin, smax = -tilt * h * 0.5, w + tilt * h * 0.5
    f0, f1 = smax + 4, smin - R - 4
    f = f0 + (f1 - f0) * anim.smooth(p)
    # 三块：s < f 旧画面；f <= s <= f+R 纸卷（背面）；s > f+R 新画面
    flat = 1 - _smoothstep(s, f - 1.0, f + 1.0)
    roll = _smoothstep(s, f - 1.0, f + 1.0) * (1 - _smoothstep(s, f + R - 1.0, f + R + 1.0))
    out = _mix(b, a, flat.astype(np.float32))
    # 阴影：纸卷投在新画面上（右边宽而软）、投在旧画面上（左边窄）
    sh_r = _smoothstep(s, f + R - 4, f + R) * (1 - _smoothstep(s, f + R + 6 * S, f + R + 70 * S)) * 0.33
    sh_l = (1 - _smoothstep(s, f - 30 * S, f)) * _smoothstep(s, f - 34 * S, f - 26 * S) * 0.16
    out = (out.astype(np.float32) * (1 - (sh_r + sh_l)[..., None])).astype(np.uint8)
    # 纸卷本身：φ 从 π（在 s=f）到 π/2（在 s=f+R）；亮度按圆柱的角度
    tt = np.clip((s - f) / R, 0, 1)                                          # 0..1 = sin(φ2 的补角)
    phi = np.pi - np.arcsin(tt)                                              # 背面那一层的角度 π..π/2
    shade = 0.62 + 0.38 * np.cos(np.pi - phi + 0.55) ** 1                    # 卷起来的地方偏暗，圆顶上偏亮
    shade = np.clip(shade + 0.18 * (1 - tt), 0.55, 1.0)
    src_u = f + R * phi                                                      # 这一点对应旧画面里的哪个位置（s 坐标）
    mx = (src_u - tilt * (yy - h * 0.5)).astype(np.float32)
    ghost = cv2.remap(a, mx, yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    back = np.empty((h, w, 3), np.float32)
    back[:] = (196, 214, 236)                                                # 纸背（BGR）：米色
    back *= (1 + 0.03 * _paper_tex_cache(w, h))[..., None]
    back = back * 0.82 + ghost.astype(np.float32) * 0.18
    back *= shade[..., None]
    back = np.clip(back, 0, 255).astype(np.uint8)
    out = _mix(out, back, roll.astype(np.float32))
    # 纸卷顶上一条白纸边（卷起的边亮一线）
    rim = (1 - _smoothstep(np.abs(s - (f + R * 0.985)), 1.0 * S, 3.5 * S)) * roll
    out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), rim.astype(np.float32) * 0.85)
    return np.ascontiguousarray(out[:, ::-1] if left else out)


# ============================== 解说台切到故事 ==============================
@transition("tv_switch", dur=0.8, sfx="tv_click", check=_pcheck())
def tv_switch(a, b, p, params, canvas):
    S = canvas.S
    h, w = canvas.h, canvas.w
    cx, cy = params.get("pos", [C.W / 2, 700])
    w0 = float(params.get("w", 800))
    h0 = w0 * 0.58
    g = anim.smooth(min(p / 0.25, 1.0))                                       # 前 25%：小画面从屏幕位置「亮」出来（0 → 屏幕大小）
    e = anim.smooth(max(p - 0.25, 0.0) / 0.75)                                 # 后 75%：从屏幕大小放大到盖满画面
    x0f, y0f = cx - w0 / 2 * g, cy - h0 / 2 * g
    left_, top_ = x0f * (1 - e), y0f * (1 - e)
    right_, bot_ = cx + w0 / 2 * g + (C.W - (cx + w0 / 2 * g)) * e, cy + h0 / 2 * g + (C.H - (cy + h0 / 2 * g)) * e
    zoom = 1.0 + 0.10 * e
    A = cv2.resize(a, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)
    ox, oy = int((A.shape[1] - w) * (cx * S / w)), int((A.shape[0] - h) * (cy * S / h))
    A = A[oy:oy + h, ox:ox + w]
    if A.shape[:2] != (h, w):
        A = cv2.resize(A, (w, h))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rx0, ry0, rx1, ry1 = left_ * S, top_ * S, right_ * S, bot_ * S
    r = max(0.0, min(44 * S * (1 - e), (rx1 - rx0) / 2 - 1, (ry1 - ry0) / 2 - 1))
    # 圆角矩形距离场
    qx = np.abs(xx - (rx0 + rx1) / 2) - ((rx1 - rx0) / 2 - r)
    qy = np.abs(yy - (ry0 + ry1) / 2) - ((ry1 - ry0) / 2 - r)
    dist = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    inside = 1 - _smoothstep(dist, -1.0, 1.0)
    # 新画面按矩形的大小缩放着放进去（从「屏幕里的小画」长大）
    sc = max((rx1 - rx0) / w, (ry1 - ry0) / h, 0.05)
    Bs = cv2.resize(b, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc < 1 else cv2.INTER_LINEAR) if sc < 0.999 else b
    canvas_b = np.zeros_like(b)
    if sc < 0.999:
        ox_, oy_ = int(round(rx0)), int(round(ry0))
        x_a, y_a = max(0, ox_), max(0, oy_)
        sx_a, sy_a = x_a - ox_, y_a - oy_
        hh, ww = min(Bs.shape[0] - sy_a, h - y_a), min(Bs.shape[1] - sx_a, w - x_a)
        if hh > 0 and ww > 0:
            canvas_b[y_a:y_a + hh, x_a:x_a + ww] = Bs[sy_a:sy_a + hh, sx_a:sx_a + ww]
    else:
        canvas_b = b
    shadow = (1 - _smoothstep(dist, 0, 40 * S)) * (1 - inside) * 0.30 * (1 - e)
    out = (A.astype(np.float32) * (1 - shadow[..., None])).astype(np.uint8)
    frame_w = 22 * S * (1 - e)
    frame = (1 - _smoothstep(np.abs(dist - frame_w / 2), frame_w / 2 - 1, frame_w / 2 + 1)) * (dist > -1) * (frame_w > 1.0)
    out = _mix(out, np.full_like(out, (60, 80, 110)), frame.astype(np.float32))
    edge = (1 - _smoothstep(np.abs(dist - frame_w - 5 * S), 4 * S, 5.5 * S)) * (dist > frame_w) * (frame_w > 1.0)
    out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), (edge * (1 - inside)).astype(np.float32) * 0.9)
    return _mix(out, canvas_b, inside.astype(np.float32))
