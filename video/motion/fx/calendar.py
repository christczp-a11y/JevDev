"""翻日历转场：一本纸日历（皇历）从上面落下来，压暗的旧画面后面，一张张纸页飞快地往前倒翻（干支一个接一个往回退、日子往回数），最后停在「两千四百多年前 · 战国」这样的一页，
停一会儿，日历放大淡出，露出下一镜。写在后一镜里：

  "transition": {"type": "calendar_flip", "stop_text": "两千四百多年前 · 战国"}
参数：
  stop_text  最后停住的那页上的字（默认「两千四百多年前 · 战国」）。用「 · 」分成两行：前半小字（墨色）、后半大字（朱红）；不写「·」就一行大字。每行 ≤ 10 个字；
  pos        日历的中心（默认 [540, 880]，日历高约 1000，在主体安全区 y 360–1400 里）；
  dur        默认 1.2 秒。p 0–0.10 日历落下；0.05 起 7 张纸页从快到慢翻完（约 0.3 秒翻 7 张，每张翻 4–5 帧）；翻停以后有约 0.55 秒能看清 stop_text；0.92 以后放大淡出。dur 写大一点停得更久（翻页声按 1.2 秒做）。
音效 calendar_flip（「刷刷刷」翻页声，翻 7 张，翻停那一下「嗒」）：按翻页开始的时刻响（登记 sfx_dt，比切点早约半秒）。
切点（p = 0.5）在日历遮住的时候悄悄把背景从旧画面换成新画面（0.44–0.56 之间叠化），所以旧画面的最后半秒和新画面的头半秒都被日历盖着。
"""
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import transition
from sfx import timing as T

PW, PH = 760, 860                       # 一页纸的大小
M = 40                                  # 图四周留给阴影的边
GANZHI = ["甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉", "甲戌", "乙亥"]
HEADER = "皇历"
DEFAULT_STOP = "两千四百多年前 · 战国"
IN_END, OUT_START = 0.10, 0.92


def _lines(stop_text):
    parts = [x.strip() for x in stop_text.split("·") if x.strip()]
    return parts if len(parts) == 2 else [stop_text.strip()]


def _check(p):
    errs = []
    st = p.get("stop_text", DEFAULT_STOP)
    if not isinstance(st, str) or not st.strip():
        return ["calendar_flip 的 stop_text 要写一句话，比如 \"两千四百多年前 · 战国\""]
    lines = _lines(st)
    if len(lines) > 2 or any(len(x) > 10 for x in lines):
        errs.append("stop_text 用「 · 」分成最多两行，每行 ≤ 10 个字")
    errs += P.glyph_errors(st.replace("·", ""), HEADER, "".join(GANZHI), "年", "0123456789")
    if "pos" in p and not (isinstance(p["pos"], (list, tuple)) and len(p["pos"]) == 2):
        errs.append("pos 要写成 [x, y]")
    return errs


def _page_bg(tint):
    card = P.paper_card(PW, PH, tint, 26, border=(196, 160, 120), bw=5, seed=41 + sum(tint) % 17, tex=0.05)
    return card


def _header(card, text):
    d = P.ImageDraw.Draw(card)
    d.rounded_rectangle((10, 10, PW - 11, 150), 22, fill=P.RED + (255,))
    d.rectangle((10, 120, PW - 11, 150), fill=P.RED + (255,))
    t = P.text_image(text, "title", 88, (255, 252, 244))
    card.alpha_composite(t, ((PW - t.width) // 2, 80 - t.height // 2))
    return card


def _wrap_sprite(card):
    """整页放进一张带边距的图里，纸边 + 投影；返回 PIL 图（尺寸 PW+2M × PH+2M，页面顶边在 y = M 处）。"""
    big = P.Image.new("RGBA", (PW + 2 * M, PH + 2 * M), (0, 0, 0, 0))
    e = P.edged(card, 8, False)
    big.alpha_composite(e, (M - 8, M - 8))
    return big


def _front(i):
    tint = [(250, 242, 224), (252, 238, 214), (248, 244, 228)][i % 3]
    card = _header(_page_bg(tint), f"{GANZHI[i % len(GANZHI)]}年")
    num = str(31 - (i * 4) % 31)
    t = P.text_image(num, "title", 430, P.INK)
    card.alpha_composite(t, ((PW - t.width) // 2, 150 + (PH - 150 - t.height) // 2 - 30))
    return _wrap_sprite(card)


def _stop(stop_text):
    card = _header(_page_bg((252, 244, 226)), HEADER)
    lines = _lines(stop_text)
    if len(lines) == 2:
        t1 = P.text_image(lines[0], "title", 92 if len(lines[0]) <= 7 else 76, P.INK)
        size = 190 if len(lines[1]) <= 3 else 150 if len(lines[1]) <= 5 else 110
        t2 = P.text_image(lines[1], "title", size, P.RED)
        gap = 40
        total = t1.height + gap + t2.height
        y = 150 + (PH - 150 - total) // 2
        card.alpha_composite(t1, ((PW - t1.width) // 2, y))
        card.alpha_composite(t2, ((PW - t2.width) // 2, y + t1.height + gap))
    else:
        size = 130 if len(lines[0]) <= 6 else 100
        t = P.text_image(lines[0], "title", size, P.RED)
        card.alpha_composite(t, ((PW - t.width) // 2, 150 + (PH - 150 - t.height) // 2))
    return _wrap_sprite(card)


def _back():
    card = _page_bg((226, 212, 184))
    return _wrap_sprite(card)


def _pad():
    """日历底座：朱红硬纸背板（比纸页大一圈）、顶上的装订条和两个铁环、下面露出的几层纸边。"""
    W, H = PW + 70, PH + 120
    big = P.Image.new("RGBA", (W + 2 * M, H + 2 * M), (0, 0, 0, 0))
    back = P.paper_card(W, H, (178, 52, 44), 30, seed=53, tex=0.05)
    d = P.ImageDraw.Draw(back)
    for k in range(1, 4):                                                       # 下沿露出的纸页层
        d.rounded_rectangle((36 + 4 * k, H - 70 + 7 * k - 30, W - 36 - 4 * k, H - 30 + 7 * k), 10, fill=(250 - 6 * k, 242 - 6 * k, 224 - 6 * k, 255), outline=(200, 170, 130, 255), width=2)
    for cx in (W // 2 - 150, W // 2 + 150):
        d.ellipse((cx - 22, 18, cx + 22, 62), outline=(120, 120, 130, 255), width=8)
        d.ellipse((cx - 11, 29, cx + 11, 51), fill=(70, 50, 40, 255))
    big.alpha_composite(P.edged(back, 9, True), (M - 9, M - 9))
    return big


@transition("calendar_flip", params=["stop_text", "pos"], dur=T.CAL_DUR, sfx="calendar_flip", sfx_dt=T.CAL_START * T.CAL_DUR - 0.5 * T.CAL_DUR, check=_check)
def calendar_flip(a, b, p, params, canvas):
    stop = params.get("stop_text", DEFAULT_STOP)
    cx, cy = params.get("pos", [C.W / 2, 880])
    n = T.CAL_N
    # ---- 背景：旧画面，切点前后悄悄换成新画面；日历在的时候压暗一点 ----
    k = float(np.clip((p - 0.44) / 0.12, 0, 1))
    k = k * k * (3 - 2 * k)
    base = (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k)
    intro = anim.smooth(p / IN_END)
    outro = anim.smooth((p - OUT_START) / (1 - OUT_START))
    dim = 0.26 * intro * (1 - outro)
    canvas.img[:] = np.clip(base * (1 - dim), 0, 255).astype(np.uint8)
    # ---- 日历整体：落下来（带过冲）、结束放大淡出 ----
    if p < IN_END:
        g = 0.55 + 0.45 * anim.back_out(p / IN_END)
        dy = -160 * (1 - anim.out_cubic(p / IN_END))
        al = anim.smooth(p / 0.06)
    else:
        g, dy, al = 1.0, 0.0, 1.0
    if p > OUT_START:
        g = 1.0 + 0.22 * anim.out_cubic(outro)
        dy = -60 * outro
        al = 1.0 - anim.smooth((p - OUT_START) / (1 - OUT_START) * 1.25)
    if al <= 0:
        return canvas.img.copy()
    top = cy - PH / 2
    hinge = cy + (top - cy) * g + dy                                            # 合页（页面顶边）在屏幕上的 y
    pad = P.sprite(canvas, ("cal_pad",), _pad)
    canvas.blit(pad, cx, hinge - 18 * g, scale=g, alpha=al, anchor=(0.5, (M + 12) / pad.hd), depth=0)
    starts = T.cal_starts(n)
    ths = [180.0 * anim.smooth(float(np.clip((p - starts[i]) / T.cal_flip_dur(i, n), 0, 1))) for i in range(n)]
    anch_f = M / (PH + 2 * M)
    flipping = [i for i in range(n) if 0.0 < ths[i] < 180.0 - 1e-6]                 # 正在翻的（可能好几张同时在翻）
    done = sum(1 for i in range(n) if ths[i] >= 180.0 - 1e-6 and all(ths[j] >= 180.0 - 1e-6 for j in range(i)))   # 已经翻完的张数（从第 0 张连续数）
    top_static = (max(flipping) + 1) if flipping else done                          # 最下面露着不动的那一页
    _draw_page(canvas, min(top_static, n), stop, cx, hinge, g, al, anch_f)
    # 正在翻的，从下往上画：编号大的在下
    for i in sorted(flipping, reverse=True):
        th = ths[i]
        if th <= 90.0:
            sy = max(float(np.cos(np.radians(th))), 0.02)
            sp = P.sprite(canvas, ("cal_front", i % 12), lambda i=i: _front(i))
            canvas.blit(sp, cx, hinge, scale=g, sy=sy, alpha=al, anchor=(0.5, anch_f), depth=0)
            m = P.new_mask(canvas)                                                 # 翻起来的页压在下面那页上的软阴影
            S = canvas.S
            y0, y1 = int(hinge * S), int((hinge + PH * g * sy) * S)
            m[max(y0, 0):max(y1, 0), int((cx - PW * g / 2) * S):int((cx + PW * g / 2) * S)] = 255
            P.blend(canvas, m, (40, 28, 20), 0.22 * float(np.sin(np.radians(th))) * al)
        else:
            sy = max(abs(float(np.cos(np.radians(th)))), 0.02)
            back = P.sprite(canvas, ("cal_back",), _back)
            fade = 1.0 - anim.smooth((th - 120.0) / 60.0)
            canvas.blit(back, cx, hinge, scale=g, sy=sy, alpha=al * fade, anchor=(0.5, 1.0 - anch_f), depth=0)
    return canvas.img.copy()


def _draw_page(canvas, idx, stop, cx, hinge, g, al, anch_f):
    if idx >= T.CAL_N:
        sp = P.sprite(canvas, ("cal_stop", stop), lambda: _stop(stop))
    else:
        sp = P.sprite(canvas, ("cal_front", idx % 12), lambda: _front(idx))
    canvas.blit(sp, cx, hinge, scale=g, alpha=al, anchor=(0.5, anch_f), depth=0)
