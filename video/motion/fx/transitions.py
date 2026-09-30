"""转场（写在后一镜里：`"transition": "page_turn"` 或 `{"type": "iris", "dur": 0.5, "pos": [540, 900]}`；接口见 README「特效和转场接口」）。
全是纸的样子：翻书页（卷起来的纸背）、纸片擦过（三条彩色纸片斜着扫过）、墨笔刷（飞白的墨条一条条刷过）、圆圈收拢（纸圈收成一点再放开）、淡到纸色、甩镜（带运动模糊）、
tv_switch（解说台的纸屏幕展开成整个画面，「按一下，画面切到故事里」）。都是进度 p 的函数，没有随机、没有隐藏状态。
  page_turn    dur 0.7  side: right（默认，从右往左翻）/ left
  paper_wipe   dur 0.8  colors: 三条纸片的颜色（默认朱红、金、米白）；dir: right（默认，从左扫到右）/ left
  ink_wipe     dur 0.7  strokes: 笔画条数（默认 4）；dir: right / left
  iris         dur 0.7  pos: [x, y] 圆心（默认画面中心偏上 [540, 900]，可以对准主体）；color: 纸色（默认米白，也可 ink / 家族色）
  fade_paper   dur 0.7  淡到纸色再淡入下一镜（换时间、换场）
  whip         dur 0.28 dir: left（默认，画面往左甩，下一镜从右边进来）/ right / up / down
  tv_switch    dur 0.8  前一镜要先放好纸屏幕（`screen` 特效）；pos: 纸屏幕**纸面**的中心，w: 纸面的宽（默认 414；纸面 = 木框宽 × 0.765，中心比木框中心偏 (−0.021, −0.040)×框宽）。
               屏幕里的画先叠化成故事的画，再从纸面大小放大到盖满整个画面
"""
import functools

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
    m = np.asarray(m, np.float32)
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
@transition("fade_paper", params=[], dur=0.7, sfx="fade_soft", check=_pcheck())
def fade_paper(a, b, p, params, canvas):
    bg = _paper_bg(canvas.w, canvas.h)
    if p < 0.5:
        k = anim.smooth(p / 0.5)
        return cv2.addWeighted(a, 1 - k, bg, k, 0)
    k = anim.smooth((p - 0.5) / 0.5)
    return cv2.addWeighted(bg, 1 - k, b, k, 0)


# ============================== 圆圈收拢 ==============================
@functools.lru_cache(maxsize=16)
def _iris_dists(cx, cy):
    """屏幕上每个点（粗网格）到圆心的距离，排好序：第 q 分位数 = 「圆里正好装下画面 q 这么多面积」时的半径。"""
    gy, gx = np.mgrid[0:96, 0:54].astype(np.float32)
    d = np.hypot((gx + 0.5) * (C.W / 54) - cx, (gy + 0.5) * (C.H / 96) - cy).ravel()
    return np.sort(d)


def _iris_radius(area, cx, cy):
    """圆里装着画面的面积比例 area（0..1）→ 半径（设计像素）。"""
    d = _iris_dists(round(cx), round(cy))
    if area <= 0:
        return 0.0
    if area >= 1:
        return float(d[-1]) * 1.03
    return float(np.interp(area * (len(d) - 1), np.arange(len(d)), d))


@transition("iris", params=['pos', 'color'], dur=0.7, sfx="iris", check=_pcheck())
def iris(a, b, p, params, canvas):
    """圆圈收拢再放开。缓动按「圈里画面的面积」走，不按半径走：面积随时间 smooth 地变，亮度（旧画面 → 纸色 → 新画面）就不会在两三帧里跳掉大半。"""
    S = canvas.S
    h, w = canvas.h, canvas.w
    cx, cy = params.get("pos", [C.W / 2, 900])
    col = P.rgb(params.get("color"), (238, 228, 208))
    if p < 0.5:
        area, inner = 1.0 - anim.smooth(p / 0.5), a
    else:
        area, inner = anim.smooth((p - 0.5) / 0.5), b
    r = _iris_radius(area, cx, cy)
    bg = _paper_bg(w, h, tuple(col)) if col != (238, 228, 208) else _paper_bg(w, h)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot(xx - cx * S, yy - cy * S)
    rr = r * S
    inside = 1.0 - _smoothstep(d, rr - 1.2, rr + 1.2)                    # 圈里面（抗锯齿）
    ring = (1.0 - _smoothstep(np.abs(d - (rr + 7 * S)), 6 * S, 8 * S)) * (d >= rr - 1)      # 圈外那一圈白纸边
    out = _mix(bg, inner, inside)
    out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), (ring * (1 - inside)).astype(np.float32) * (0 < area < 1))
    return out


# ============================== 甩镜 ==============================
@transition("whip", params=['dir'], dur=0.28, sfx="whip", check=_pcheck())
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
@transition("paper_wipe", params=['colors', 'dir'], dur=0.8, sfx="paper_swipe", check=_pcheck())
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
def _brush_rows(h, n, seed=5):
    """每一笔的「毛刷」：每一行（y）一个 0..1 的数 s（大的 = 这一缕毛刷带的墨多、飞白拖得长），相邻几行差不多（缕宽 6–12 像素），整体在 0..1 里均匀分布。"""
    out = []
    for i in range(n):
        rng = np.random.default_rng(seed * 31 + i)
        z = cv2.GaussianBlur(rng.standard_normal(h).astype(np.float32)[None, :], (0, 0), 3.0)[0] + 0.5 * cv2.GaussianBlur(rng.standard_normal(h).astype(np.float32)[None, :], (0, 0), 1.2)[0]
        rank = np.argsort(np.argsort(z)).astype(np.float32) / max(h - 1, 1)
        out.append(rank)
    return out


@functools.lru_cache(maxsize=8)
def _smooth_noise(n, sigma, seed):
    rng = np.random.default_rng(seed)
    z = cv2.GaussianBlur(rng.standard_normal(n).astype(np.float32)[None, :], (0, 0), sigma)[0]
    return z / (z.std() + 1e-6)


@transition("ink_wipe", params=['strokes', 'dir'], dur=0.7, sfx="brush", check=_pcheck())
def ink_wipe(a, b, p, params, canvas):
    """毛笔刷过去：一两道粗墨笔从左往右一笔扫过。笔头是圆的、边缘有一点不规则（但平滑）；笔肚一整块浓墨，刷过的地方露出新画面；
    笔尾是「飞白」：一缕一缕拖长短不一的墨丝，毛刷的纹路里露着新画面。墨里有纸纤维的纹理，上下两笔边缘微微起伏并且叠着盖满。
    strokes：笔数（默认 2）；dir：right（默认）/ left。"""
    S = canvas.S
    h, w = canvas.h, canvas.w
    n = max(1, min(int(params.get("strokes", 2)), 4))
    right = params.get("dir", "right") == "right"
    yy = np.arange(h, dtype=np.float32)[:, None]
    X = np.arange(w, dtype=np.float32)[None, :]
    if not right:
        X = (w - 1) - X
    rows = _brush_rows(h, n)
    band = h / n
    core_len = 0.20 * w
    tail_len = 0.46 * w
    lead_r = 0.16 * band
    f_start, f_end = -0.10 * w, w + core_len + tail_len + 0.10 * w
    stag = 0.18 if n > 1 else 0.0
    ink_m = np.zeros((h, w), np.float32)
    b_m = np.zeros((h, w), np.float32)
    xs = np.arange(w, dtype=np.float32)
    for i in range(n):
        q = np.clip((p - i * stag) / (1 - (n - 1) * stag), 0, 1)
        f = f_start + (f_end - f_start) * (0.75 * anim.smooth(q) + 0.25 * q)              # 中段快、两头慢，一笔下去的手感
        # 这一笔占的行：[y0, y1]，上下都多出一截，和相邻一笔叠着
        tilt = 0.05 * h * (xs / w - 0.5) * (1 if i % 2 == 0 else -1)
        w0 = np.clip(_smooth_noise(w, 110.0, 11 + i)[:w], -2, 2) * 0.05 * band                   # 上下沿的起伏（平滑，最多 ±0.1 笔宽）
        w1 = np.clip(_smooth_noise(w, 110.0, 21 + i)[:w], -2, 2) * 0.05 * band
        y0 = (i - 0.45) * band + w0 + tilt if i == 0 else (i - 0.20) * band + w0 + tilt              # 第一笔的上沿、最后一笔的下沿在画面外面；相邻两笔各叠 0.2 笔宽，起伏也漏不出缝
        y1 = (i + 1.45) * band + w1 + tilt if i == n - 1 else (i + 1.20) * band + w1 + tilt
        vert = _smoothstep(yy, y0[None, :] - 2.5 * S, y0[None, :] + 2.5 * S) * (1 - _smoothstep(yy, y1[None, :] - 2.5 * S, y1[None, :] + 2.5 * S))
        yc = ((i + 0.5) * band)
        u = np.clip((yy[:, 0] - yc) / (0.60 * band), -1, 1)                                  # 行相对笔中心的位置 -1..1
        wob = 9.0 * S * _smooth_noise(h, 12.0, 31 + i)                                       # 笔头边缘的不规则，平滑的
        xf = f - lead_r * u ** 2 * 2.2 + wob                                                # 笔头：圆的（中间冲得最远）
        s = rows[i]
        xm = xf - core_len * (0.75 + 0.25 * s)                                              # 浓墨笔肚的尾端（也是新画面露出来的边界）
        ls = tail_len * s ** 1.6                                                             # 这一行飞白拖多长
        XF, XM, LS = xf[:, None], xm[:, None], ls[:, None]
        core = _smoothstep(X, XM - 1.2, XM + 1.2) * (1 - _smoothstep(X, XF - 1.2, XF + 1.2))
        strand = (1 - _smoothstep(XM - X, 0.0, np.maximum(LS, 1.0))) * (X <= XM + 1.0) * (LS > 6.0)       # 飞白：从笔肚往回一缕一缕淡出
        strand = strand * (0.55 + 0.45 * _smoothstep(s[:, None], 0.25, 0.6))
        ink_i = np.maximum(core, strand * 0.92) * vert
        b_i = (1 - _smoothstep(X, XM - 1.2, XM + 1.2)) * vert
        ink_m = np.maximum(ink_m, ink_i)
        b_m = np.maximum(b_m, b_i)
    out = _mix(a, b, b_m)
    tex = _paper_tex_cache(w, h)
    ink = np.empty((h, w, 3), np.float32)
    ink[:] = (C.INK[2], C.INK[1], C.INK[0])
    ink = ink * (1 + 0.14 * tex[..., None]) + 6
    # 墨条的边缘比中间浓一点点（墨在纸上聚边）
    edge_dark = np.clip(1.0 - ink_m, 0, 1) * ink_m * 4.0
    ink = ink * (1 - 0.18 * edge_dark[..., None])
    return _mix(out, np.clip(ink, 0, 255).astype(np.uint8), ink_m)


# ============================== 翻书页 ==============================
@transition("page_turn", params=['side'], dur=0.7, sfx="page_flip", check=_pcheck())
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
@transition("tv_switch", params=['pos', 'w'], dur=0.8, sfx="tv_click", check=_pcheck())
def tv_switch(a, b, p, params, canvas):
    S = canvas.S
    h, w = canvas.h, canvas.w
    cx, cy = params.get("pos", [C.W / 2, 700])
    w0 = float(params.get("w", 414))
    h0 = w0 * 0.576                                                            # 纸屏幕的纸面是 16:9（props/screen_frame.png）
    e = anim.smooth(p)                                                         # 整个转场：纸面大小的矩形放大到盖满整个画面
    alpha_in = anim.smooth(p / 0.2)                                            # 前 20%：屏幕里的画换成故事里的画（叠化），再开始放大
    x0f, y0f = cx - w0 / 2, cy - h0 / 2
    left_, top_ = x0f * (1 - e), y0f * (1 - e)
    right_, bot_ = x0f + w0 + (C.W - (x0f + w0)) * e, y0f + h0 + (C.H - (y0f + h0)) * e
    zoom = 1.0 + 0.10 * e
    A = cv2.resize(a, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)
    ox, oy = int((A.shape[1] - w) * (cx * S / w)), int((A.shape[0] - h) * (cy * S / h))
    A = A[oy:oy + h, ox:ox + w]
    if A.shape[:2] != (h, w):
        A = cv2.resize(A, (w, h))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rx0, ry0, rx1, ry1 = left_ * S, top_ * S, right_ * S, bot_ * S
    r = max(0.0, min(8 * S * (1 - e), (rx1 - rx0) / 2 - 1, (ry1 - ry0) / 2 - 1))
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
    grow = min(1.0, e * 8.0)                                                   # 刚开始矩形就是纸面本身（外面已经是解说台的木框），边框和阴影随着放大才出现
    shadow = (1 - _smoothstep(dist, 0, 40 * S)) * (1 - inside) * 0.30 * (1 - e) * grow
    out = (A.astype(np.float32) * (1 - shadow[..., None])).astype(np.uint8)
    edge = (1 - _smoothstep(np.abs(dist - 4 * S), 2.5 * S, 5 * S)) * (dist > 0) * grow
    out = _mix(out, np.full_like(out, (P.WHITE[2], P.WHITE[1], P.WHITE[0])), (edge * (1 - inside)).astype(np.float32) * 0.9)
    return _mix(out, _mix(A, canvas_b, alpha_in), inside.astype(np.float32))
