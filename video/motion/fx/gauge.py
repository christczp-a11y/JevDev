"""进度物：本集的概念物（水位刻度这类），变化的时候整体弹一下。每集一个。

  {"type": "progress", "pos": [960, 900], "title": "水位", "from": 0.2, "to": 0.55, "at": {...}}
参数：
  pos       刻度板正中心（默认 [740, 900]，靠右，别压主体；右边 140 是平台遮挡区，带刻度名的板子约 310 宽，所以中心要 ≤ 780）；
  title     板子上面的小标签（≤ 4 个字，默认不写）；labels  从下往上每一格的名字（比如 ["", "一版", "二版", "三版"]，写几个就分几格；不写 = 5 格没有字）；
  from / to 起点和终点（0–1，水位在板子里的高度）。不写 from = 不动，直接停在 to；
  pop_in    true（默认）= 刻度板从下面弹出来，0.7 秒以后水位才开始动；false = 一开始就在（跨镜头接着用，水位从 from 立刻开始动）；
  color     水的颜色（默认蓝，kind: "water"）；kind  water（默认，带波浪）/ fill（纯色填充，比如「信用值」）；size 大小倍数（默认 1）；dur 停留几秒。
水位动一次用 0.9 秒（平滑，最后带一点过冲），停下来的一刻整块板子弹一下（音效 gauge_pop 就在这一刻响）。同一个镜头里水位分几次涨，写几个 progress（后一个 pop_in: false，from = 前一个的 to）。
音效：gauge_pop（弹出 + 水位变化时一声「咕」；音效在 at 响，水位开始动比 at 晚 0.7 秒，所以要卡「涨到了」，at 提早 0.7 秒或写 pop_in: false）。
"""
import functools
import math

from engine import anim
from fx import _paper as P
from fx import fx

BW, BH = 150, 560        # 刻度板尺寸（设计像素）
MOVE = 0.9


def _check(p):
    errs = P.need_pos(p) if "pos" in p else []
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    for k in ("from", "to"):
        if k in p and not (isinstance(p[k], (int, float)) and 0 <= p[k] <= 1):
            errs.append(f"{k} 要写 0–1 的数")
    if "to" not in p:
        errs.append("progress 要写 to（0–1）")
    if p.get("kind", "water") not in ("water", "fill"):
        errs.append("kind 只能是 water / fill")
    errs += P.glyph_errors(p.get("title", ""), *p.get("labels", []))
    return errs


@functools.lru_cache(maxsize=16)
def _board(title, labels):
    """刻度板：纸卡 + 玻璃槽 + 刻度线 + 旁边的刻度名 + 上面的标签。返回 (PIL 图, 槽在图里的位置 [x0,y0,x1,y1])。"""
    n = len(labels) if labels else 5
    lab_w = 118 if labels else 0
    tag_h = 78 if title else 0
    W, H = BW + lab_w + 40, BH + tag_h + 40
    im = P.Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card = P.edged(P.paper_card(BW, BH, P.CREAM, 34, border=(196, 160, 120), bw=6, seed=101), 10)
    off = (20, tag_h + 20)
    im.alpha_composite(card, (off[0] - 10, off[1] - 10 + 0))
    x0, y0, x1, y1 = off[0] + 44, off[1] + 34, off[0] + BW - 44, off[1] + BH - 34
    d = P.ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x1, y1), 18, fill=(250, 246, 236, 255), outline=(150, 118, 84, 255), width=5)
    for i in range(n + 1):
        y = y1 - (y1 - y0) * i / n
        d.line((x0 - 22, y, x0 - 4, y), fill=(120, 92, 64, 255), width=5)
        d.line((x1 + 4, y, x1 + 22, y), fill=(120, 92, 64, 255), width=5)
    for i, lb in enumerate(labels or []):
        if not lb:
            continue
        y = y1 - (y1 - y0) * i / n
        t = P.text_image(lb, "title", 42, P.INK)
        pill = P.edged(P.paper_card(t.width + 26, t.height + 8, P.CREAM, (t.height + 8) // 2, seed=103), 5)
        pill.alpha_composite(t, ((pill.width - t.width) // 2, (pill.height - t.height) // 2))
        im.alpha_composite(pill, (x1 + 30, int(y - pill.height / 2)))
    if title:
        t = P.text_image(title, "title", 46, (255, 255, 255))
        pw = max(t.width + 44, 120)
        tag = P.edged(P.paper_card(pw, t.height + 12, P.BLUE, (t.height + 12) // 2, seed=105), 7)
        tag.alpha_composite(t, ((tag.width - t.width) // 2, (tag.height - t.height) // 2))
        im.alpha_composite(tag, (off[0] + BW // 2 - tag.width // 2, 6))
    return im, (x0, y0, x1, y1)


@fx("progress", params=['pos', 'title', 'labels', 'from', 'to', 'pop_in', 'color', 'kind', 'size'], layer="front", sfx="gauge_pop", check=_check)
def progress(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur):
        return
    title, labels = params.get("title", ""), params.get("labels", [])
    k = float(params.get("size", 1.0))
    to = float(params["to"])
    fr = float(params.get("from", to))
    pop_in = params.get("pop_in", True)
    t_move = 0.7 if pop_in else 0.0
    fo = P.fade_out(u, dur)
    px, py = params.get("pos", [740, 900])
    board = P.sprite(canvas, ("gauge", title, tuple(labels)), lambda: _board(title, tuple(labels))[0])
    x0, y0, x1, y1 = _board(title, tuple(labels))[1]
    bimg_w = BW + (118 if labels else 0) + 40
    bimg_h = BH + (78 if title else 0) + 40
    # 整体的弹：出现时弹簧弹出；水位到达的那一刻再弹一下
    if pop_in:
        s0, sx0, sy0 = P.pop_xy(u, 2.2, 6.5, 0.08)
    else:
        s0, sx0, sy0 = 1.0, 1.0, 1.0
    a = u - t_move
    e = 0.0 if a <= 0 else (anim.smooth(a / MOVE) if a < MOVE else 1.0)
    over = 0.06 * math.sin(math.pi * min(a / MOVE, 1.0)) if 0 < a < MOVE else 0.0
    level = fr + (to - fr) * e + (to - fr) * over
    hit = a - MOVE
    bump = 1.0 + (0.09 * math.exp(-hit * 7) * math.sin(2 * math.pi * 3.0 * hit) if hit >= 0 and fr != to else 0.0)
    g = P.Group(px, py, k * s0 * bump, 0.0)
    cx, cy = bimg_w / 2, bimg_h / 2
    canvas.blit(board, px, py, scale=k * s0 * bump, sx=sx0, sy=sy0, alpha=min(1.0, u / 0.06) * fo, depth=0)
    # 水：多边形（顶面是两层正弦波），画在槽里
    m = P.new_mask(canvas)
    lvl = max(0.0, min(1.0, level))
    top = y1 - (y1 - y0) * lvl
    pts = [(x0 + 3, y1 - 3)]
    wave_amp = 5.0 if params.get("kind", "water") == "water" else 0.0
    for i in range(0, 17):
        x = x0 + 3 + (x1 - x0 - 6) * i / 16
        w = wave_amp * math.sin(2 * math.pi * (i / 8.0 + 0.6 * u)) + wave_amp * 0.5 * math.sin(2 * math.pi * (i / 5.0 - 0.9 * u))
        pts.append((x, max(y0 + 3, min(y1 - 3, top + w))))
    pts.append((x1 - 3, y1 - 3))
    scr = [g.pt((x - cx) * sx0, (y - cy) * sy0) for x, y in pts]
    if lvl > 0.005:
        P.fill_poly(canvas, m, scr)
        col = P.rgb(params.get("color"), (82, 158, 208))
        P.blend(canvas, m, col, 0.95 * min(1.0, u / 0.06) * fo)
        # 水面上一条浅色的高光线
        hl = P.new_mask(canvas)
        for (xa, ya), (xb, yb) in zip(scr[1:-2], scr[2:-1]):
            P.draw_line(canvas, hl, (xa, ya), (xb, yb), 5 * k)
        P.blend(canvas, hl, P.mix(col, (255, 255, 255), 0.6), 0.85 * min(1.0, u / 0.06) * fo)
