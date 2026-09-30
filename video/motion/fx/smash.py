"""砸字：关键词一个字一个字砸下来，落地挤扁再弹回，带震屏、冲击环和飞出的纸屑。厚纸剪字（ZCOOL KuaiLe），白纸边。

  {"type": "smash", "text": "本事", "pos": [540, 800], "at": {"line": 3, "word": "本事", "dt": -0.14}}
参数：
  text  1–6 个字（不写空格）；pos  整个词的正中心（放在主体安全区 y 360–1400、左右各留 80 之内）；
  size  字号，默认 300（字多了自动缩小，整行不超过 920 宽）；color  字色，默认朱红（"gold" "blue" "#rrggbb"，或 house: "智家" 取家族色）；
  shake 每个字落地的震屏振幅（像素，默认 9；整幅画面平移，总和不超过画面宽度的 1.5%）；写 0 = 不震；
  dur   停留几秒（默认到镜头结束，最后 0.25 秒淡出）；sfx 默认按字数选 slam_1 … slam_6，写 null 静音。
时间：第 k 个字（从 0 数）在 at + 0.14 + 0.17·k 秒落地；要让第一个字正好落在某个字上，at 写 dt: -0.14。
"""
import math

import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx
from sfx import timing as T

SHAKE_DUR = 0.28
EXIT = 0.3


def _color(p):
    if p.get("house"):
        return P.house_rgb(p["house"])
    return P.rgb(p.get("color"), P.RED)


def _check(p):
    errs = P.need_pos(p)
    text = p.get("text")
    if not isinstance(text, str) or not (1 <= len(text) <= T.SLAM_MAX) or any(c.isspace() for c in text):
        errs.append(f"smash 的 text 要写 1–{T.SLAM_MAX} 个字（不写空格）")
        return errs
    errs += P.glyph_errors(text)
    try:
        _color(p)
    except ValueError as e:
        errs.append(str(e))
    P.auto_sfx(p, f"slam_{len(text)}")
    return errs


@fx("smash", params=['text', 'pos', 'size', 'color', 'house', 'shake'], layer="front", sfx="slam_1", check=_check)
def smash(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, EXIT):
        return
    text = params["text"]
    n = len(text)
    col = _color(params)
    size = min(float(params.get("size", 300)), 920.0 / (0.95 * n))
    amp = min(float(params.get("shake", 9.0)), C.SHAKE_AMP_MAX)
    px, py = params["pos"]
    adv = [P.text_width(ch, "title", int(size)) * 0.97 for ch in text]
    x = px - sum(adv) / 2
    xs = []
    for a in adv:
        xs.append(x + a / 2)
        x += a
    rng = np.random.default_rng(P.seed_of("smash", text))
    tilt = rng.uniform(-5, 5, n)
    chips = rng.uniform(0, 1, (n, 9, 4))
    # ---- 震屏：每个字落地时一次，衰减；整幅画面先移，字和纸屑跟着一起移 ----
    dx = dy = 0.0
    for k in range(n):
        a = u - (T.SLAM_FALL + T.SLAM_STAG * k)
        if 0 <= a < SHAKE_DUR:
            env = (1 - a / SHAKE_DUR) ** 2
            ph = 1.7 * k
            dx += amp * env * (0.6 * math.sin(2 * math.pi * 11.0 * a + ph) + 0.4 * math.sin(2 * math.pi * 17.0 * a + 2 * ph))
            dy += amp * env * (0.6 * math.sin(2 * math.pi * 14.0 * a + 1 + ph) + 0.4 * math.sin(2 * math.pi * 9.0 * a + ph))
    lim = C.SHAKE_AMP_MAX
    dx, dy = max(-lim, min(lim, dx)), max(-lim, min(lim, dy))
    P.shift_screen(canvas, dx, dy)
    # 退场：字带着白纸边和纸影一起缩小 0.3 秒，前 40% 不透明度不变（白边在浅色背景上一淡就看不见，所以先缩、后淡），后面一起淡出
    v = 0.0 if dur is None else anim.clamp((u - dur) / EXIT)
    fo = 1.0 - anim.smooth((v - 0.4) / 0.6)
    shrink = 1.0 - 0.45 * anim.in_cubic(v)
    for k in range(n):
        land = T.SLAM_FALL + T.SLAM_STAG * k
        s0 = land - T.SLAM_FALL
        if u < s0:
            continue
        sp = P.sprite(canvas, ("smash", text[k], int(size), col), lambda k=k: P.chunky_text(text[k], int(size), col, seed=3 + k))
        by = py + dy
        if u < land:
            w = (u - s0) / T.SLAM_FALL
            y = by - 760 * (1 - w * w)
            sc = 1.0 + 0.55 * (1 - w * w)
            sx, sy, rot = 1.0 - 0.10 * (1 - w), 1.0 + 0.22 * (1 - w), tilt[k] * (1 - w) * 1.5
        else:
            a = u - land
            q = math.exp(-a * 9.5) * math.cos(2 * math.pi * 2.9 * a)
            y, sc = by, 1.0
            sx, sy, rot = 1.0 + 0.24 * q, 1.0 - 0.30 * q, tilt[k] * 0.5 * math.exp(-a * 5) * math.cos(2 * math.pi * 2.0 * a)
        canvas.blit(sp, xs[k] + dx, y, scale=sc * shrink, sx=sx, sy=sy, rot=rot, alpha=fo, anchor=(0.5, 0.93), depth=0)
        a = u - land
        if 0 <= a < 0.5:
            # 冲击环：变大、变细、变淡
            if a < 0.32:
                rm = P.new_mask(canvas)
                r = size * (0.28 + 0.62 * anim.out_cubic(a / 0.32))
                P.circle(canvas, rm, (xs[k] + dx, by + size * 0.05), r, 255, max(3, size * 0.05 * (1 - a / 0.32)))
                P.blend(canvas, rm, P.CREAM, 0.85 * (1 - a / 0.32) * fo)
            # 纸屑
            cm = P.new_mask(canvas)
            for j in range(9):
                ang = math.radians(-160 + 140 * chips[k, j, 0])
                sp0 = 300 + 380 * chips[k, j, 1]
                cxp = xs[k] + dx + math.cos(ang) * sp0 * a
                cyp = by + dy + size * 0.05 + math.sin(ang) * sp0 * a + 900 * a * a
                sz = 15 + 18 * chips[k, j, 2]
                r0 = chips[k, j, 3] * 6.28 + a * 9
                c0, s0_ = math.cos(r0), math.sin(r0)
                P.fill_poly(canvas, cm, [(cxp + c0 * sz - s0_ * sz * 0.5, cyp + s0_ * sz + c0 * sz * 0.5), (cxp - c0 * sz - s0_ * sz * 0.5, cyp - s0_ * sz + c0 * sz * 0.5),
                                         (cxp - c0 * sz + s0_ * sz * 0.5, cyp - s0_ * sz - c0 * sz * 0.5), (cxp + c0 * sz + s0_ * sz * 0.5, cyp + s0_ * sz - c0 * sz * 0.5)])
            P.blend(canvas, cm, col if k % 2 == 0 else P.GOLD, min(1.0, (0.5 - a) / 0.25) * fo)
