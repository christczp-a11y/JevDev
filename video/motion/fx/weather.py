"""天气和火：雨、水花、纸剪火焰。

  {"type": "rain", "at": {...}}                                     雨：两层斜着落下的雨丝（远的细淡、近的粗亮），画面稍微压暗压蓝；dim 压暗程度（默认 0.16，0 = 不压）；
                                                                    density（默认 1）、slant（倾斜度数，默认 12）、dur（默认到镜头结束）
  {"type": "splash", "pos": [540, 1350], "at": {...}}                水花：pos 是落水点；水滴像纸剪的小蓝水滴，抛起来划弧线落下，脚下一圈圈涟漪；size 大小（默认 1，0.6–1.6）
  {"type": "flame", "pos": [540, 1300], "w": 640, "at": {...}}        纸剪火焰：一排三层纸剪（橙红、橙、黄）的火苗，轻轻摇；pos 是火苗底边中点，w 是整排宽度（默认 640）；
                                                                    count（火苗数，默认 7）、height（最高的火苗高，默认 360）、dur
音效：rain → rain，splash → splash，flame → whoomp（写 sfx: null 静音）。火焰只画成温暖的橙黄色，不用血红，不发红光；
**火焰不许和人物叠在一起**：出片前 check 会查火苗的框和镜头里每个人物的框，重叠就报错（火放在画面边上，或者只放在 big_title 的字周围）。
"""
import math

import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx


def _check(p):
    errs = []
    if "pos" in p and not (isinstance(p["pos"], (list, tuple)) and len(p["pos"]) == 2):
        errs.append("pos 要写成 [x, y]")
    return errs


# ============================== 雨 ==============================
@fx("rain", params=['dim', 'density', 'slant'], layer="front", sfx="rain", check=_check)
def rain(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.6):
        return
    env = anim.smooth(u / 0.6) * P.fade_out(u, dur, 0.6)
    dens = float(params.get("density", 1.0))
    slant = math.radians(float(params.get("slant", 12)))
    dim = float(params.get("dim", 0.16))
    if dim > 0:
        canvas.tint((58, 74, 96), dim * env)
    sx, sy = math.sin(slant), math.cos(slant)
    for layer, (n, spd, ln, th, alpha) in enumerate(((int(170 * dens), 1500.0, 84.0, 3.6, 0.45), (int(90 * dens), 2300.0, 150.0, 6.0, 0.66))):
        rng = np.random.default_rng(P.seed_of("rain", layer, n))
        x0 = rng.uniform(-300, C.W + 300, n)
        y0 = rng.uniform(0, C.H + 300, n)
        v = spd * rng.uniform(0.9, 1.1, n)
        m = P.new_mask(canvas)
        span = C.H + 400.0
        for i in range(n):
            y = (y0[i] + v[i] * u) % span - 200
            xx = ((x0[i] + (y + 200) * sx / sy) % (C.W + 600)) - 300
            P.draw_line(canvas, m, (xx, y), (xx + ln * sx, y + ln * sy), th)
        P.blend(canvas, m, (226, 238, 250), alpha * env)


# ============================== 水花 ==============================
def _drop(size):
    ss = 3
    w, h = int(size * 0.72) * ss, int(size) * ss
    im = P.Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    d.ellipse((0, h - w, w - 1, h - 1), fill=(96, 172, 216, 255))
    d.polygon([(w / 2, 0), (w * 0.06, h - w * 0.55), (w * 0.94, h - w * 0.55)], fill=(96, 172, 216, 255))
    d.ellipse((w * 0.2, h - w * 0.78, w * 0.4, h - w * 0.5), fill=(255, 255, 255, 140))
    a = np.array(im.split()[3]).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), ss * 2.0)
    im.putalpha(P.Image.fromarray(np.clip((a - 127) * 4 + 127, 0, 255).astype(np.uint8)))
    im = im.resize((w // ss, h // ss), P.Image.LANCZOS)
    return P.edged(im, 4)


@fx("splash", params=['pos', 'size'], layer="front", sfx="splash", check=lambda p: P.need_pos(p))
def splash(canvas, t, params, at):
    u = t - at
    if u < 0 or u > 1.9:
        return
    px, py = params["pos"]
    k = float(params.get("size", 1.0))
    rng = np.random.default_rng(P.seed_of("splash", round(px), round(py)))
    n = 18
    ang = np.radians(rng.uniform(-158, -22, n))
    spd = rng.uniform(520, 1150, n) * k
    sizes = rng.uniform(46, 88, n) * k
    big = np.arange(n) < 5                                           # 前 5 颗竖着往上蹿（水冠）
    ang = np.where(big, np.radians(rng.uniform(-105, -75, n)), ang)
    spd = np.where(big, rng.uniform(900, 1250, n) * k, spd)
    sizes = np.where(big, sizes * 1.25, sizes)
    # 水面：一摊蓝纸慢慢扩开又变淡，再加两圈涟漪
    a = min(1.0, u / 1.1)
    pud = P.new_mask(canvas)
    S = canvas.S
    axes = (round(220 * k * anim.out_cubic(a) * S * 16), round(56 * k * anim.out_cubic(a) * S * 16))
    cv2.ellipse(pud, (round(px * S * 16), round((py + 8) * S * 16)), axes, 0, 0, 360, 255, -1, cv2.LINE_AA, 4)
    edge = cv2.dilate(pud, np.ones((max(3, round(9 * S)),) * 2, np.uint8))
    fade = (1 - a) ** 0.6 if a > 0.5 else 1.0
    P.blend(canvas, edge, P.WHITE, 0.9 * fade * min(1.0, u / 0.08))
    P.blend(canvas, pud, (110, 178, 218), 0.7 * fade * min(1.0, u / 0.08))
    for ring, delay in enumerate((0.0, 0.16)):
        r_ = u - delay
        if 0 <= r_ < 0.9:
            m = P.new_mask(canvas)
            rr = anim.out_cubic(r_ / 0.9)
            cv2.ellipse(m, (round(px * S * 16), round((py + 8) * S * 16)), (round((70 + 260 * rr) * k * S * 16), round((20 + 76 * rr) * k * S * 16)), 0, 0, 360, 255,
                        max(1, round(8 * (1 - rr) * S)) + 1, cv2.LINE_AA, 4)
            P.blend(canvas, m, (236, 248, 255), 0.85 * (1 - rr))
    g = 2300.0 * k
    for i in range(n):
        vx, vy = spd[i] * math.cos(ang[i]), spd[i] * math.sin(ang[i])
        x = px + vx * u
        y = py + vy * u + 0.5 * g * u * u
        if y > py + 30 and u > 0.3:
            continue                                                 # 落回水面就不画了
        rot = math.degrees(math.atan2(vx, -(vy + g * u)))
        sz = int(sizes[i] / 6) * 6
        sp = P.sprite(canvas, ("drop", sz), lambda sz=sz: P.add_shadow(_drop(sz), (2, 3), 3, 0.25, 8))
        canvas.blit(sp, x, y, scale=min(1.0, u / 0.05), rot=rot, alpha=min(1.0, (1.9 - u) / 0.3), depth=0)


# ============================== 纸剪火焰 ==============================
FLAME_COLS = [(232, 92, 46), (247, 152, 56), (255, 216, 100)]        # 外层橙红、中层橙、内层黄（不用血红）


def _catmull(pts, closed=True, m=14):
    P0 = np.array(pts, np.float64)
    n = len(P0)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = P0[(i - 1) % n], P0[i], P0[(i + 1) % n], P0[(i + 2) % n]
        for s in np.linspace(0, 1, m, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
    return np.array(out)


def _flame(w, h, skew, layer_edge=True):
    """三层纸剪火苗（朝上）：每层是一块颜色不同的纸，越往里越小、越黄；外面一圈细白纸边和纸影。"""
    ss = 3
    W, H = w * ss, h * ss
    base = [(0.50, 0.99), (0.12, 0.93), (0.02, 0.70), (0.16, 0.46), (0.30, 0.30 + 0.05 * skew), (0.40 + 0.10 * skew, 0.10), (0.52 + 0.14 * skew, 0.0),
            (0.60 + 0.06 * skew, 0.24), (0.76, 0.40), (0.95, 0.66), (0.90, 0.92)]
    outline = _catmull(base)
    im = P.Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    for li, (col, sc) in enumerate(zip(FLAME_COLS, (1.0, 0.68, 0.38))):
        pts = [(W / 2 + (x * W - W / 2) * sc, H * 0.99 + (y * H - H * 0.99) * sc) for x, y in outline]
        d.polygon(pts, fill=tuple(col) + (255,))
    im = im.resize((w, h), P.Image.LANCZOS)
    a = np.array(im).astype(np.float32)
    t = P.paper_tex(w, h, 21)
    a[..., :3] = np.clip(a[..., :3] * (1 + 0.04 * t[..., None]), 0, 255)
    return P.edged(P.Image.fromarray(a.astype(np.uint8), "RGBA"), 5)


def flame_box(p):
    """一排火苗占的框（设计坐标）：底边中点 pos，宽 w（两头各多出半朵火苗），高 height。"""
    px, py = p["pos"]
    W, Hm = float(p.get("w", 640)), float(p.get("height", 360))
    return (px - W / 2 - 0.25 * Hm, py - Hm, px + W / 2 + 0.25 * Hm, py + 0.03 * Hm)


def _fcheck(p, shot=None):
    """火焰不许和人物叠在一起（儿童安全：不能像人站在火里）：火苗的框和镜头里任何一个人物的框有重叠就报错。火只放在大字标题周围或画面边上。"""
    errs = _check(p)
    if errs or "pos" not in p:
        return errs + ([] if "pos" in p else ["flame 缺 pos: [x, y]（火苗底边中点）"])
    fb = flame_box(p)
    for a in P.actor_boxes(shot):
        if P.boxes_overlap(fb, a["body"], margin=8.0):
            errs.append(f"flame 和人物 {a['id']} 重叠（火苗框 {[round(x) for x in fb]}，人物框 {[round(x) for x in a['body']]}）：火焰不许挡在人物身上，"
                        f"挪到画面边上（pos / w 改一下）或者只放在大字标题（big_title 的 deco: flame）周围")
    return errs


@fx("flame", params=['pos', 'w', 'height', 'count'], layer="front", sfx="whoomp", check=_fcheck)
def flame(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.4):
        return
    px, py = params["pos"]
    W = float(params.get("w", 640))
    n = int(params.get("count", 7))
    Hm = float(params.get("height", 360))
    fo = P.fade_out(u, dur, 0.4)
    rng = np.random.default_rng(P.seed_of("flame", n))
    order = np.argsort(rng.uniform(0, 1, n))
    for j in range(n):
        i = int(order[j])
        fx_ = (i + 0.5) / n
        x = px - W / 2 + W * fx_
        prof = 0.55 + 0.45 * math.sin(math.pi * fx_)                    # 中间高、两边矮
        h = Hm * prof * (0.8 + 0.2 * ((i * 37) % 5) / 4)
        w = h * 0.62
        variant = i % 3
        hh, ww = int(round(h / 10)) * 10, int(round(w / 10)) * 10
        sp = P.sprite(canvas, ("flame", ww, hh, variant), lambda ww=ww, hh=hh, variant=variant: _flame(ww, hh, (-1, 0, 1)[variant]))
        a = u - 0.05 * j
        if a < 0:
            continue
        grow = P.spring(a / 0.45 * 0.45, 2.0, 6.5)
        ph = i * 1.7
        sy = grow * (1 + 0.07 * math.sin(2 * math.pi * 1.6 * u + ph) + 0.04 * math.sin(2 * math.pi * 2.9 * u + ph * 2))
        sx = (1 - 0.04 * (grow - 1)) * (1 + 0.05 * math.sin(2 * math.pi * 1.3 * u + ph))
        rot = 3.6 * math.sin(2 * math.pi * 0.9 * u + ph)
        canvas.blit(sp, x, py, sx=sx, sy=max(sy, 0.01), rot=rot, alpha=fo * min(1.0, a / 0.08), anchor=(0.5, 0.97), depth=0)
