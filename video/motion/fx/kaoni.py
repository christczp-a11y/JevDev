"""考你（系列仪式，每集 4 次）：「考你！」按钮弹出 → 选项一个个弹出 → 倒计时圈 3、2、1 → 「看答案！」。整个流程的时间是固定的（音效 kaoni 是按这个时间做的整段音），
每一次都一样，孩子一听就知道「要考我了」。

  {"type": "kaoni", "options": ["给", "不给"], "at": {"line": 1}}                          也可以写在 rituals 里（分镜表顶层）
  {"type": "kaoni", "options": ["给", "不给"], "answer": 1, "at": {...}}                    answer = 正确选项的序号（从 0 数）：「看答案！」的时候正确的那张打勾、别的变暗；不写就只出「看答案！」
时间（从 at 起算，秒）：0 按钮弹出　0.55 起选项弹出（每个晚 0.15）　1.1 倒计时圈出现，3 → 2 → 1 各一秒　4.1「看答案！」弹出　5.8 全部收掉。
参数：options 1–3 个选项（每个 ≤ 6 个字）；y 按钮中心的高度（默认 480，在标题条下面）；sfx 默认 kaoni，写 null 静音；
      end_stamp：≤ 6 个字，倒计时切走前最后一拍（3.75 秒）在计时器上「啪」地盖一个小章（比如「第 2 关揭晓」写不下就写「揭晓」），章和计时器一起缩走、「看答案！」接上，不会像被剪断；盖章那一刻有一声 pop（check 自动排进音效表）。
安全区：按钮 y≈480、选项 y≈760、倒计时圈 y≈1040，都在主体安全区（360–1400）里，左右各留 80 以上。
"""
import math

import cv2

from engine import anim
from fx import _paper as P
from fx import fx
from sfx import timing as T

OPT_COLS = [(45, 91, 154), (208, 138, 46), (47, 125, 91)]           # 选项颜色：蓝、橙黄、青绿（不用红，红是按钮的）


STAMP_T = T.KAONI_ANS - 0.35            # 盖章的时刻：最后一拍（数字 1 出现 0.65 秒后）
VANISH = 0.22                           # 计时器 + 章一起缩走用多久


def _check(p, shot=None):
    errs = []
    o = p.get("options")
    if not (isinstance(o, list) and 1 <= len(o) <= 3 and all(isinstance(x, str) and 1 <= len(x) <= 6 for x in o)):
        errs.append("kaoni 的 options 要写 1–3 个选项，每个 1–6 个字，比如 [\"给\", \"不给\"]")
        return errs
    errs += P.glyph_errors("考你！看答案", *o)
    if "answer" in p and not (isinstance(p["answer"], int) and 0 <= p["answer"] < len(o)):
        errs.append("kaoni 的 answer 要写选项的序号（从 0 数）")
    st = p.get("end_stamp")
    if st is not None:
        if not (isinstance(st, str) and 1 <= len(st) <= 6):
            errs.append("kaoni 的 end_stamp 要写 1–6 个字")
        else:
            errs += P.glyph_errors(st)
            if not errs:
                P.add_sfx(shot, p.get("at"), STAMP_T, "pop")
    return errs


def _stamp(text):
    """小章：奶白的纸章 + 朱红双边框 + 朱红字，带一点印泥的纸纹。"""
    size = 54
    t = P.text_image(text, "title", size, P.RED)
    w, h = max(200, t.width + 84), 126
    card = P.paper_card(w, h, (250, 240, 222), 20, border=P.RED, bw=9, seed=71 + len(text), tex=0.06)
    d = P.ImageDraw.Draw(card)
    d.rounded_rectangle((16, 16, w - 17, h - 17), 12, outline=P.RED + (255,), width=3)
    card.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2 - 2))
    return P.add_shadow(P.edged(card, 7, False), (3, 5), 5, 0.3, 14)


def _button(text, w, h, fill, size):
    im = P.edged(P.paper_card(w, h, fill, h // 2, seed=31 + len(text), tex=0.04), 10)
    m = (im.width - w) // 2
    hl = P.Image.new("RGBA", im.size, (0, 0, 0, 0))                      # 上半截一层浅浅的亮，像纸压出来的弧面
    P.ImageDraw.Draw(hl).rounded_rectangle((m + 14, m + 8, m + w - 14, m + h * 0.46), h // 3, fill=(255, 255, 255, 34))
    im.alpha_composite(hl)
    t = P.text_image(text, "title", size, (255, 255, 255), stroke=5, stroke_fill=P.shade(fill, 0.55))
    im.alpha_composite(t, ((im.width - t.width) // 2, (im.height - t.height) // 2 - 4))
    return im


def _option(text, col, w=400, h=170):
    im = P.edged(P.paper_card(w, h, col, 36, seed=41 + len(text), tex=0.045), 9)
    t = P.text_image(text, "title", 84 if len(text) <= 3 else 60, (255, 255, 255), stroke=4, stroke_fill=P.shade(col, 0.55))
    im.alpha_composite(t, ((im.width - t.width) // 2, (im.height - t.height) // 2 - 3))
    return im


def _ring_base(r):
    """倒计时圈的底：奶白圆盘 + 白纸边 + 一圈浅灰凹槽。"""
    S = int(r * 2 + 8)
    disc = P.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(disc)
    d.ellipse((4, 4, S - 5, S - 5), fill=P.CREAM + (255,))
    d.ellipse((4 + r * 0.16, 4 + r * 0.16, S - 5 - r * 0.16, S - 5 - r * 0.16), outline=P.shade(P.CREAM, 0.86) + (255,), width=int(r * 0.2))
    return P.edged(disc, 10)


@fx("kaoni", params=['options', 'answer', 'y', 'end_stamp'], layer="front", sfx="kaoni", check=_check)
def kaoni(canvas, t, params, at):
    u = t - at
    if u < 0 or u > T.KAONI_END + 0.35:
        return
    fo = 1.0 - anim.smooth((u - T.KAONI_END) / 0.3)
    y0 = float(params.get("y", 480))
    opts = params["options"]
    n = len(opts)
    # ---- 「考你！」按钮 ----
    btn = P.sprite(canvas, ("kaoni_btn",), lambda: _button("考你！", 560, 190, P.RED, 118))
    s, sx, sy = P.pop_xy(u - T.KAONI_BTN, 2.2, 6.0, 0.12)
    pulse = 1.0 + 0.025 * math.sin(2 * math.pi * 1.2 * u) * anim.smooth((u - 0.6) / 0.4)
    canvas.blit(btn, 540, y0, scale=s * pulse, sx=sx, sy=sy, rot=-2.0 * math.exp(-4 * u) * math.cos(2 * math.pi * 2 * u), alpha=min(1.0, u / 0.06) * fo, depth=0)
    # ---- 选项 ----
    gap = 24
    ow = 400 if n < 3 else 300
    total = n * ow + (n - 1) * gap
    ans = params.get("answer")
    revealed = u - T.KAONI_ANS
    for i, o in enumerate(opts):
        a = u - (T.KAONI_OPT + 0.15 * i)
        if a < 0:
            continue
        sp = P.sprite(canvas, ("kaoni_opt", o, i, ow), lambda o=o, i=i: _option(o, OPT_COLS[i], ow))
        x = 540 - total / 2 + ow / 2 + i * (ow + gap)
        s, sx, sy = P.pop_xy(a, 2.3, 6.5, 0.12)
        dim = 1.0
        dy = 0.0
        if ans is not None and revealed >= 0:
            dim = 1.0 if i == ans else 1.0 - 0.55 * anim.smooth(revealed / 0.25)
            if i == ans:
                dy = -14 * math.sin(math.pi * min(revealed / 0.4, 1.0)) * math.exp(-0.5 * revealed)
                s *= 1.0 + 0.06 * anim.smooth(revealed / 0.2)
        canvas.blit(sp, x, y0 + 280 + dy, scale=s, sx=sx, sy=sy, rot=(-1.5 if i % 2 == 0 else 1.5) * math.exp(-3 * a), alpha=min(1.0, a / 0.06) * fo * dim, depth=0)
        if ans is not None and i == ans and revealed >= 0.1:
            mk = P.sprite(canvas, ("kaoni_tick",), lambda: P.edged(P.tick_image(92, P.GREEN), 6))
            ms, msx, msy = P.pop_xy(revealed - 0.1, 3.0, 8.0, 0.1)
            canvas.blit(mk, x + ow / 2 - 26, y0 + 280 - 70, scale=ms * (1 + 0.6 * math.exp(-(revealed - 0.1) * 12)), sx=msx, sy=msy, alpha=fo, depth=0)
    # ---- 倒计时圈：3、2、1 ----
    cy = y0 + 560
    r = 112
    a = u - T.KAONI_RING
    if a >= 0 and u < T.KAONI_ANS + VANISH:
        left = T.KAONI_COUNT - a                                              # 还剩几秒（3 → 0）
        base = P.sprite(canvas, ("kaoni_ring", r), lambda: _ring_base(r))
        vanish = 1.0 - anim.smooth((u - T.KAONI_ANS) / VANISH)
        s, sx, sy = P.pop_xy(a, 2.4, 7.0, 0.1)
        s *= vanish
        canvas.blit(base, 540, cy, scale=s, sx=sx, sy=sy, alpha=min(1.0, a / 0.05) * fo, depth=0)
        if s > 0.3 and left > 0:
            m = P.new_mask(canvas)
            S = canvas.S
            frac = left / T.KAONI_COUNT
            cv2.ellipse(m, (round(540 * S * 16), round(cy * S * 16)), (round(r * 0.72 * S * 16),) * 2, 0, -90, -90 + 360 * frac, 255, max(1, round(r * 0.22 * s * S)), cv2.LINE_AA, 4)
            P.blend(canvas, m, P.RED, fo)
            num = str(min(T.KAONI_COUNT, int(math.ceil(left))))
            k = (a % 1.0) if a < T.KAONI_COUNT else 0.99
            ns = P.sprite(canvas, ("kaoni_num", num), lambda: P.text_image(num, "title", 136, P.INK))
            ps = 1.0 + 0.28 * math.exp(-k * 9) * math.cos(2 * math.pi * 2.6 * k)
            canvas.blit(ns, 540, cy + 4, scale=ps * s, alpha=fo, depth=0)
    # ---- 收尾的小章：最后一拍盖在计时器上，和计时器一起缩走 ----
    st = params.get("end_stamp")
    b = u - STAMP_T
    if st and 0 <= b and u < T.KAONI_ANS + VANISH:
        sp = P.sprite(canvas, ("kaoni_stamp", st), lambda: _stamp(st))
        s = (1.0 + 1.6 * (1 - anim.out_cubic(b / 0.10)) if b < 0.10 else 1.0 + 0.10 * math.exp(-(b - 0.10) * 10) * math.cos(2 * math.pi * 3.0 * (b - 0.10)))
        s *= 1.0 - anim.smooth((u - T.KAONI_ANS) / VANISH)
        canvas.blit(sp, 540, cy + 8, scale=s, rot=-11.0 + 5.0 * (1 - anim.out_cubic(b / 0.12)), alpha=min(1.0, b / 0.03) * fo, depth=0)
    # ---- 「看答案！」 ----
    b = u - T.KAONI_ANS
    if b >= 0:
        btn2 = P.sprite(canvas, ("kaoni_ans",), lambda: _button("看答案！", 600, 170, P.GOLD, 96))
        s, sx, sy = P.pop_xy(b, 2.2, 6.0, 0.12)
        canvas.blit(btn2, 540, cy, scale=s, sx=sx, sy=sy, rot=2.0 * math.exp(-4 * b) * math.cos(2 * math.pi * 2 * b), alpha=min(1.0, b / 0.05) * fo, depth=0)
