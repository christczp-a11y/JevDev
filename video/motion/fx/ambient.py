"""氛围：光芒、闪粉、纸屑彩带、灰尘（雨、水花、纸剪火焰在 weather.py）。都是「纸剪」的小东西，动作全是时间的函数（没有隐藏状态），不闪。

  {"type": "rays", "pos": [540, 820], "at": {...}}                    光芒：一圈半透明的光条从 pos 往外放，慢慢转（画在背景之上、人物之下，人物站在光里）
      color（默认暖金）、alpha（默认 0.7）、count（光条数，默认 14）、radius、dur
  {"type": "sparkle", "at": {...}, "area": [80, 360, 1000, 1400]}       闪粉：一颗颗四角小星星在 area 里轻轻亮起又暗下去（胜利、变身、宝物）
      count（默认 28）、dur；每颗一次亮 0.8–1.5 秒，不快闪
  {"type": "confetti", "at": {...}, "mode": "burst"}                    纸屑彩带：burst = 从画面下面两角喷起来再落下；fall = 从上面一直飘下来
      count（默认 100）、dur（fall 默认到镜头结束，burst 约 2.6 秒落完）
  {"type": "dust", "at": {...}, "mode": "float"}                        灰尘：float = 光里飘着的小尘（旧屋、行军、废墟）；puff = 在 pos 落地扬起一团尘（脚下、落地、撞击）
      float：area、count（默认 40）、dur；puff：pos（脚底）、size（默认 150）：一团柔和的尘雾颗粒（大的很淡很糊、中的、细碎的纸屑）向两边和上面散开，边散边胀大，1 秒左右淡掉
音效：rays → shine，sparkle → twinkle，confetti → party，dust 的 puff → dust_puff（float 不出声）（写 sfx: null 静音）。
"""
import math

import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx

DEF_AREA = [80, 360, 1000, 1400]


def _check(p, shot=None):
    errs = []
    if shot is not None and "avoid" not in p:
        p["_avoid"] = P.face_avoid(shot)                    # 出片前自动记下这个镜头里每个人物的脸框：粒子飘到脸边上会渐隐，不会盖住脸（想关掉写 "avoid": []；想自己指定写 "avoid": [[x0, y0, x1, y1], ...]）
    elif "avoid" in p:
        p["_avoid"] = p["avoid"]
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    for k in ("pos",):
        if k in p and not (isinstance(p[k], (list, tuple)) and len(p[k]) == 2):
            errs.append(f"{k} 要写成 [x, y]")
    if "area" in p and not (isinstance(p["area"], (list, tuple)) and len(p["area"]) == 4):
        errs.append("area 要写成 [x0, y0, x1, y1]")
    return errs


# ============================== 光芒 ==============================
_grad = {}


def _radial(w, h, cx, cy, R, power):
    key = (w, h, round(cx), round(cy), round(R), power)
    if key not in _grad:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot(xx - cx, yy - cy) / R
        _grad[key] = np.clip(1 - r, 0, 1) ** power
    return _grad[key]


@fx("rays", params=['pos', 'color', 'alpha', 'count', 'radius'], layer="back", sfx="shine", check=lambda p: _check(p))
def rays(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.4):
        return
    cx, cy = params.get("pos", [C.W / 2, 820])
    n = int(params.get("count", 14))
    col = P.rgb(params.get("color"), (255, 226, 150))
    R = float(params.get("radius", 1300))
    fo = P.fade_out(u, dur, 0.4) * anim.smooth(u / 0.45)
    k = 0.25                                                       # 低分辨率画，再放大：边缘自带柔和
    lw, lh = max(2, round(canvas.w * k)), max(2, round(canvas.h * k))
    low = np.zeros((lh, lw), np.uint8)
    sc = canvas.S * k * 16
    rot = 0.10 * u + 0.4
    grow = 0.55 + 0.45 * anim.out_cubic(u / 0.6)
    for i in range(n):
        a0 = rot + i * 2 * math.pi / n
        a1 = a0 + math.pi / n * 0.92
        far = R * 1.25 * grow
        pts = [(cx, cy), (cx + far * math.cos(a0), cy + far * math.sin(a0)), (cx + far * math.cos((a0 + a1) / 2), cy + far * math.sin((a0 + a1) / 2)),
               (cx + far * math.cos(a1), cy + far * math.sin(a1))]
        cv2.fillPoly(low, [np.array([[round(x * sc), round(y * sc)] for x, y in pts], np.int32)], 255, cv2.LINE_AA, 4)
    low = cv2.GaussianBlur(low, (0, 0), 1.6).astype(np.float32) / 255.0
    fall = _radial(lw, lh, cx * canvas.S * k, cy * canvas.S * k, R * canvas.S * k * grow, 0.8)
    glow = _radial(lw, lh, cx * canvas.S * k, cy * canvas.S * k, 380 * canvas.S * k, 1.5)
    m = np.clip(low * fall * 1.25 + glow * 0.8, 0, 1)
    mask = cv2.resize((m * 255).astype(np.uint8), (canvas.w, canvas.h), interpolation=cv2.INTER_LINEAR)
    P.blend(canvas, mask, col, float(params.get("alpha", 0.7)) * fo)


# ============================== 闪粉 ==============================
def _star4(size, col):
    ss = 4
    S = size * ss
    im = P.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S / 2
    pts = []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        r = S * 0.5 if i % 2 == 0 else S * 0.13
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    P.ImageDraw.Draw(im).polygon(pts, fill=tuple(col) + (255,))
    a = np.array(im.split()[3]).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), ss * 0.9)
    a = np.clip((a - 100) * 2.2 + 100, 0, 255).astype(np.uint8)
    im.putalpha(P.Image.fromarray(a))
    core = P.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    P.ImageDraw.Draw(core).ellipse((S * 0.42, S * 0.42, S * 0.58, S * 0.58), fill=(255, 255, 255, 230))
    im.alpha_composite(core)
    return im.resize((size, size), P.Image.LANCZOS)


SPARK_COLS = [(255, 236, 170), (255, 255, 255), (255, 208, 96), (196, 230, 255)]


@fx("sparkle", params=['area', 'count', 'avoid'], layer="front", sfx="twinkle", check=_check)
def sparkle(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.4):
        return
    x0, y0, x1, y1 = params.get("area", DEF_AREA)
    n = int(params.get("count", 28))
    fo = P.fade_out(u, dur, 0.4)
    rng = np.random.default_rng(P.seed_of("sparkle", n, x0, y0, x1, y1))
    px, py = rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)
    period = rng.uniform(0.8, 1.5, n)
    phase = rng.uniform(0, 1, n)
    size = rng.uniform(48, 112, n)
    ci = rng.integers(0, len(SPARK_COLS), n)
    rot0 = rng.uniform(-20, 20, n)
    for i in range(n):
        s = (u / period[i] + phase[i]) % 1.0
        cyc = int(u / period[i] + phase[i])
        # 每一轮换一个位置（用轮数当种子的一部分，仍然是 t 的函数）
        jx = math.sin(cyc * 12.9898 + i * 78.233) * 43758.5453
        jy = math.sin(cyc * 39.346 + i * 11.135) * 24634.6345
        ox, oy = (jx - math.floor(jx) - 0.5) * (x1 - x0) * 0.5, (jy - math.floor(jy) - 0.5) * (y1 - y0) * 0.5
        env = math.sin(math.pi * s) ** 1.6
        if env < 0.02:
            continue
        sz = int(round(size[i] / 8)) * 8
        sp = P.sprite(canvas, ("star4", sz, int(ci[i])), lambda sz=sz, c=int(ci[i]): _star4(sz, SPARK_COLS[c]))
        x = min(max(px[i] + ox, x0), x1)
        y = min(max(py[i] + oy, y0), y1) - 28 * s
        canvas.blit(sp, x, y, scale=env, rot=rot0[i] + 40 * s, alpha=min(1.0, env * 1.3) * fo * P.avoid_alpha(params.get("_avoid"), x, y), depth=1.0)


# ============================== 纸屑彩带 ==============================
CONF = [(226, 76, 60), (248, 190, 60), (70, 150, 210), (86, 176, 120), (240, 130, 170), (250, 240, 220), (150, 110, 200)]


def _piece(col, w, h):
    im = P.Image.new("RGBA", (w + 4, h + 4), (0, 0, 0, 0))
    P.ImageDraw.Draw(im).rectangle((2, 2, w + 1, h + 1), fill=tuple(col) + (255,))
    a = np.array(im).astype(np.int16)
    a[..., :3] = np.where(a[..., 3:4] > 0, np.clip(a[..., :3] + np.array([12, 12, 12]), 0, 255), a[..., :3])
    return P.Image.fromarray(a.astype(np.uint8), "RGBA")


def _ccheck(p, shot=None):
    errs = _check(p, shot)
    if p.get("mode", "burst") not in ("burst", "fall"):
        errs.append("confetti 的 mode 只能是 burst / fall")
    return errs


@fx("confetti", params=['mode', 'count', 'avoid'], layer="front", sfx="party", check=_ccheck)
def confetti(canvas, t, params, at):
    u = t - at
    mode = params.get("mode", "burst")
    dur = params.get("dur", 2.8 if mode == "burst" else None)
    if u < 0 or P.gone(u, dur, 0.5):
        return
    n = int(params.get("count", 100))
    fo = P.fade_out(u, dur, 0.5)
    rng = np.random.default_rng(P.seed_of("confetti", mode, n))
    ci = rng.integers(0, len(CONF), n)
    spin = rng.uniform(4, 11, n) * rng.choice([-1, 1], n)
    ph = rng.uniform(0, 6.28, n)
    rot0 = rng.uniform(0, 360, n)
    szw = rng.integers(14, 26, n)
    szh = szw * rng.uniform(1.4, 2.2, n)
    if mode == "fall":
        x0 = rng.uniform(-40, C.W + 40, n)
        vy = rng.uniform(300, 560, n)
        y0 = rng.uniform(0, C.H + 300, n)
        sway = rng.uniform(20, 70, n)
        fr = rng.uniform(0.5, 1.1, n)
        loop = (C.H + 300) / vy
    else:
        side = rng.integers(0, 2, n)
        ang = np.where(side == 0, rng.uniform(-75, -40, n), rng.uniform(-140, -105, n))   # 度：从左下往右上、从右下往左上
        v = rng.uniform(1400, 2800, n)
        x0 = np.where(side == 0, -20.0, C.W + 20.0)
        y0 = np.full(n, C.H - 60.0)
        vx, vyb = v * np.cos(np.radians(ang)), v * np.sin(np.radians(ang))
    for i in range(n):
        if mode == "fall":
            s = (u + y0[i] / vy[i]) % loop[i]
            x = x0[i] + sway[i] * math.sin(2 * math.pi * fr[i] * u + ph[i]) + 30 * s
            y = -150 + vy[i] * s
        else:
            k, g = 1.35, 1500.0
            e = (1 - math.exp(-k * u)) / k
            x = x0[i] + vx[i] * e
            y = y0[i] + (vyb[i] + g / k) * e - g * u / k
        if y < -60 or y > C.H + 60 or x < -60 or x > C.W + 60:
            continue
        sp = P.sprite(canvas, ("piece", int(ci[i]), int(szw[i]), int(szh[i])), lambda i=i: _piece(CONF[int(ci[i])], int(szw[i]), int(szh[i])))
        flip = math.cos(spin[i] * u + ph[i])
        canvas.blit(sp, x, y, sx=flip if abs(flip) > 0.08 else 0.08, rot=rot0[i] + spin[i] * 20 * u, alpha=fo * P.avoid_alpha(params.get("_avoid"), x, y), depth=0)


# ============================== 灰尘 ==============================
def _dcheck(p, shot=None):
    errs = _check(p, shot)
    if p.get("mode", "float") not in ("float", "puff"):
        errs.append("dust 的 mode 只能是 float / puff")
    if p.get("mode") == "puff" and "pos" not in p:
        errs.append("dust puff 要写 pos: [x, y]")
    P.auto_sfx(p, "dust_puff" if p.get("mode") == "puff" else None)          # 飘着的灰尘不出声，扬起一团才「噗」
    return errs


@fx("dust", params=['mode', 'area', 'count', 'pos', 'size', 'color', 'avoid'], layer="front", sfx="dust_puff", check=_dcheck)
def dust(canvas, t, params, at):
    u = t - at
    mode = params.get("mode", "float")
    dur = params.get("dur", 1.0 if mode == "puff" else None)
    if u < 0 or P.gone(u, dur, 0.4):
        return
    col = P.rgb(params.get("color"), (238, 222, 190))
    fo = P.fade_out(u, dur, 0.4)
    if mode == "float":
        x0, y0, x1, y1 = params.get("area", [0, 300, C.W, 1500])
        n = int(params.get("count", 40))
        rng = np.random.default_rng(P.seed_of("dust", n))
        px, py = rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)
        r = rng.uniform(3, 8, n)
        ph = rng.uniform(0, 6.28, n)
        sp_ = rng.uniform(10, 30, n)
        m = P.new_mask(canvas)
        for i in range(n):
            x = px[i] + 40 * math.sin(0.5 * u + ph[i]) + 8 * u
            y = py[i] + 25 * math.sin(0.7 * u + ph[i] * 1.3) - sp_[i] * u * 0.5
            x = x0 + (x - x0) % (x1 - x0)
            y = y0 + (y - y0) % (y1 - y0)
            tw = 0.5 + 0.5 * math.sin(1.3 * u + ph[i] * 2)
            P.circle(canvas, m, (x, y), r[i] * (0.8 + 0.4 * tw), int((120 + 110 * tw) * P.avoid_alpha(params.get("_avoid"), x, y)))
        m = cv2.GaussianBlur(m, (0, 0), max(0.6, 0.9 * canvas.S))
        P.blend(canvas, m, col, 0.7 * min(1.0, u / 0.6) * fo)
        return
    # puff：从脚下扬起来的一团尘：一大堆柔和的尘雾颗粒（大的很淡很糊、中的、细的碎纸屑），向两边和上面散开，边散边胀大，然后一起淡掉
    px, py = params["pos"]
    k = float(params.get("size", 150)) / 150.0
    rng = np.random.default_rng(P.seed_of("puff", round(px), round(py)))
    S = canvas.S
    cols = [(232, 216, 186), (200, 176, 142), (170, 148, 120)]                         # 米白、浅土黄、暖灰
    groups = [P.new_mask(canvas) for _ in range(6)]                                    # 3 种颜色 × (雾、粒)
    ph = 0.0
    n = 104
    for i in range(n):
        kind = 0 if i < 16 else (1 if i < 84 else 2)                                   # 0 大雾 1 颗粒 2 碎纸屑
        delay = rng.uniform(0.0, 0.12)
        life = rng.uniform(0.75, 1.25)
        te = u - delay
        if te < 0 or te > life:
            continue
        ang = math.radians(rng.uniform(-172, -8))
        v = rng.uniform(140, 420) * k * (0.6 if kind == 0 else 1.0)
        c = 3.0
        run = (1 - math.exp(-c * te)) / c
        x = px + rng.uniform(-0.3, 0.3) * 150 * k + math.cos(ang) * v * run * 1.25
        y = py - 6 * k + math.sin(ang) * v * run * 0.8 - 26 * k * te                   # 往上飘一点
        r0 = (rng.uniform(34, 58) if kind == 0 else rng.uniform(3, 9) if kind == 1 else rng.uniform(4, 8)) * k
        r = r0 * (1 + 1.5 * (1 - math.exp(-2.5 * te)))
        f = te / life
        al = (0.42 if kind == 0 else 0.75 if kind == 1 else 0.95) * anim.smooth(te / 0.07) * (1 - anim.smooth((f - 0.30) / 0.70))
        if al <= 0.01:
            continue
        ci = int(rng.integers(0, 3))
        m = groups[ci * 2 + (0 if kind == 0 else 1)]
        val = int(255 * al)
        if kind == 2:                                                                    # 碎纸屑：小的斜方片，转着
            a0 = rng.uniform(0, 6.28) + rng.uniform(-6, 6) * te
            cs, sn = math.cos(a0), math.sin(a0)
            w_, h_ = r * 1.6, r * 0.9
            P.fill_poly(canvas, m, [(x + cs * w_ - sn * h_, y + sn * w_ + cs * h_), (x - cs * w_ - sn * h_, y - sn * w_ + cs * h_),
                                    (x - cs * w_ + sn * h_, y - sn * w_ - cs * h_), (x + cs * w_ + sn * h_, y + sn * w_ - cs * h_)], val)
        else:
            tmp = P.new_mask(canvas)
            P.circle(canvas, tmp, (x, y), r, val)
            np.maximum(m, tmp, out=m)
    for ci in range(3):
        haze, grain = groups[ci * 2], groups[ci * 2 + 1]
        if haze.any():
            P.blend(canvas, cv2.GaussianBlur(haze, (0, 0), max(1.0, 16 * k * S)), cols[ci], fo)
        if grain.any():
            P.blend(canvas, cv2.GaussianBlur(grain, (0, 0), max(0.6, 2.4 * k * S)), cols[ci], fo)
