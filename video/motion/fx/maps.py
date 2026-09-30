"""地图：纸地图展开、城标一个个弹出、虚线箭头一点点画出来（讲地理、行军、谁要谁的地）。三个特效，各写各的时刻，可以一个一个卡在台词上。
坐标都是屏幕设计坐标（1080×1920）；地图、城、箭头要对得上位置，先写 map 再照它的位置摆城和箭头。

  {"type": "map", "pos": [540, 900], "w": 940, "at": {...}}                                    纸地图（props/map_paper.png）从折痕处展开；dim 把背景压暗一点（默认 0.25，0 = 不压）；dur 停留几秒
  {"type": "map_city", "pos": [400, 700], "name": "晋阳", "house": "赵家", "at": {...}}          城标从上面掉下来盖在地图上，名字牌跟着弹出；house 取家族颜色（或 color: "#rrggbb"）；
                                                                                             icon: "props/city_han.png" 用现成的圆形城图标；size 城标大小（默认 130）；dur 停留几秒
  {"type": "map_arrow", "pts": [[400, 700], [560, 820], [700, 1100]], "house": "智家", "at": {...}}   虚线箭头：0.8 秒把路径一点点画出来，画完箭头头弹一下；
                                                                                             pts 至少 2 个点（3 个以上会拐弯，平滑连起来）；color / house 颜色（默认朱红）；width 线粗（默认 16）；dur 停留几秒
音效：map → paper_unfold，map_city → city_pop，map_arrow → draw（0.8 秒画线 + 收尾一声，和画线时间对齐）。
"""
import math

import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx

MAP = "props/map_paper.png"
DRAW = 0.8            # 箭头画出来用多久（sfx/synth.py 的 draw 音效按这个长度做）
DASH, GAP = 40.0, 24.0


def _color(p, default=P.RED):
    if p.get("house"):
        return P.house_rgb(p["house"])
    return P.rgb(p.get("color"), default)


def _ccheck(p):
    errs = []
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    if p.get("house"):
        try:
            P.house_rgb(p["house"])
        except ValueError as e:
            errs.append(str(e))
    return errs


# ============================== 纸地图 ==============================
def _mcheck(p):
    return P.need_pos(p) if "pos" in p else []


@fx("map", params=['pos', 'w', 'dim'], layer="front", sfx="paper_unfold", assets=lambda p: [MAP], check=_mcheck)
def map_(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    W = float(params.get("w", 940))
    cx, cy = params.get("pos", [C.W / 2, 900])
    fo = P.fade_out(u, dur, 0.3)
    dim = float(params.get("dim", 0.25))
    if dim > 0:
        canvas.tint((20, 16, 12), dim * min(1.0, anim.smooth(u / 0.3)) * fo)
    sp = P.sprite(canvas, ("map", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, MAP), W), (7, 12), 10, 0.36))
    # 从中间折痕处「展开」：竖向先压扁再弹开（带过冲），同时轻轻转正
    e = P.spring(u / 0.7 * 0.7, f=1.7, d=6.0)
    sy = max(0.04, min(e, 1.15))
    sx = 0.90 + 0.10 * anim.smooth(u / 0.4)
    canvas.blit(sp, cx, cy, sx=sx, sy=sy, rot=-4.0 * (1 - anim.smooth(u / 0.6)), alpha=min(1.0, u / 0.08) * fo, depth=0)


# ============================== 城标 ==============================
def _c2check(p):
    errs = _ccheck(p) + P.need_pos(p)
    if p.get("name"):
        errs += P.glyph_errors(p["name"])
    return errs


def _cassets(p):
    return [p["icon"]] if p.get("icon") else []


def _castle(size, col):
    """默认城标：家族色圆盘 + 白纸边 + 一座小城楼（夯土墙、平缓屋顶，不是翘角）。"""
    ss = 3
    S = size * ss
    im = P.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    d.ellipse((0, 0, S - 1, S - 1), fill=tuple(col) + (255,))
    ink = P.shade(col, 0.55) + (255,)
    cream = P.CREAM + (255,)
    wall = (S * 0.2, S * 0.5, S * 0.8, S * 0.78)
    d.rectangle(wall, fill=cream)
    for i in range(4):                                             # 城垛
        x = wall[0] + i * (wall[2] - wall[0]) / 4
        d.rectangle((x + S * 0.012, S * 0.44, x + (wall[2] - wall[0]) / 4 - S * 0.012, S * 0.5), fill=cream)
    d.rectangle((S * 0.4, S * 0.32, S * 0.6, S * 0.5), fill=cream)  # 门楼
    d.polygon([(S * 0.36, S * 0.34), (S * 0.5, S * 0.24), (S * 0.64, S * 0.34)], fill=ink)   # 平缓屋顶
    d.rectangle((S * 0.44, S * 0.6, S * 0.56, S * 0.78), fill=ink)                              # 方门洞
    im = im.resize((size, size), P.Image.LANCZOS)
    return P.edged(im, 8)


@fx("map_city", params=['pos', 'name', 'house', 'color', 'icon', 'size'], layer="front", sfx="city_pop", assets=_cassets, check=_c2check)
def map_city(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur):
        return
    px, py = params["pos"]
    size = int(params.get("size", 130))
    col = _color(params, P.BROWN)
    fo = P.fade_out(u, dur)
    if params.get("icon"):
        ic = params["icon"]
        icon = P.sprite(canvas, ("cityicon", ic, size), lambda: P.add_shadow(P.fit_height(P.load_pil(canvas, ic), size * 1.15), (4, 7), 6, 0.35))
    else:
        icon = P.sprite(canvas, ("castle", size, col), lambda: P.add_shadow(_castle(size, col), (4, 7), 6, 0.35))
    land = 0.16
    if u < land:
        w = u / land
        y = py - 150 * (1 - w * w)
        sc, sx, sy = 1.0 + 0.25 * (1 - w), 0.95, 1.08
    else:
        a = u - land
        q = math.exp(-a * 9) * math.cos(2 * math.pi * 3.0 * a)
        y, sc, sx, sy = py, 1.0, 1.0 + 0.2 * q, 1.0 - 0.26 * q
    canvas.blit(icon, px, y, scale=sc, sx=sx, sy=sy, alpha=fo, anchor=(0.5, 0.85), depth=0)
    a = u - land
    if 0 <= a < 0.35:                                             # 落地时一圈涟漪
        m = P.new_mask(canvas)
        P.circle(canvas, m, (px, py), size * (0.3 + 0.55 * anim.out_cubic(a / 0.35)), 255, max(3, 8 * (1 - a / 0.35)))
        P.blend(canvas, m, P.CREAM, 0.7 * (1 - a / 0.35) * fo)
    name = params.get("name")
    if name and a > 0.05:
        nsp = P.sprite(canvas, ("cityname", name, col), lambda: _name_tag(name, col))
        s, sx, sy = P.pop_xy(a - 0.05, 2.4, 7.5, 0.08)
        canvas.blit(nsp, px, py + size * 0.32, scale=s, sx=sx, sy=sy, alpha=fo, depth=0)


def _name_tag(name, col):
    t = P.text_image(name, "title", 46, P.INK)
    w, h = t.width + 46, t.height + 14
    im = P.edged(P.paper_card(w, h, P.CREAM, h // 2, seed=5 + len(name)), 7)
    im.alpha_composite(t, ((im.width - t.width) // 2, (im.height - t.height) // 2))
    return im


# ============================== 虚线箭头 ==============================
def _acheck(p):
    errs = _ccheck(p)
    pts = p.get("pts")
    if not (isinstance(pts, list) and len(pts) >= 2 and all(isinstance(q, (list, tuple)) and len(q) == 2 for q in pts)):
        errs.append("map_arrow 要写 pts: [[x, y], [x, y], ...]（至少 2 个点）")
    return errs


def _path(pts, step=5.0):
    """点列 → Catmull-Rom 平滑折线（每 ~step 像素一个点）；返回 (N,2) 数组和累计长度。"""
    P0 = np.array(pts, np.float64)
    if len(P0) == 2:
        n = max(2, int(np.hypot(*(P0[1] - P0[0])) / step))
        line = P0[0] + (P0[1] - P0[0]) * np.linspace(0, 1, n)[:, None]
    else:
        ext = np.vstack([2 * P0[0] - P0[1], P0, 2 * P0[-1] - P0[-2]])
        seg = []
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            m = max(3, int(np.hypot(*(p2 - p1)) / step))
            for s in np.linspace(0, 1, m, endpoint=False):
                seg.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (-p0 + 3 * p1 - 3 * p2 + p3) * s ** 3))
        seg.append(P0[-1])
        line = np.array(seg)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(line, axis=0).T))]
    return line, d


def _head(size, col):
    """箭头头（指向 +x，尖在右边中心）：圆角三角 + 白纸边。"""
    ss = 3
    w, h = int(size * 1.0) * ss, int(size * 1.2) * ss
    im = P.Image.new("RGBA", (w, h), (0, 0, 0, 0))
    P.ImageDraw.Draw(im).polygon([(0, 0), (w, h / 2), (0, h)], fill=tuple(col) + (255,))
    a = np.array(im.split()[3]).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), ss * 3.0)
    a = np.clip((a - 127) * 5 + 127, 0, 255).astype(np.uint8)
    im.putalpha(P.Image.fromarray(a))
    im = im.resize((w // ss, h // ss), P.Image.LANCZOS)
    return P.add_shadow(P.edged(im, 6, False), (3, 5), 5, 0.3)


@fx("map_arrow", params=['pts', 'house', 'color', 'width'], layer="front", sfx="draw", check=_acheck)
def map_arrow(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur):
        return
    col = _color(params)
    width = float(params.get("width", 16))
    fo = P.fade_out(u, dur)
    line, d = _path(params["pts"])
    total = d[-1]
    head_len = width * 3.4
    body_end = max(total - head_len * 0.7, 1.0)
    shown = body_end * anim.smooth(u / DRAW) if u < DRAW else body_end
    ink = P.new_mask(canvas)
    edge = P.new_mask(canvas)
    sh = P.new_mask(canvas)
    S = canvas.S
    k = 0
    s0 = 0.0
    while s0 < shown:
        s1 = min(s0 + DASH, shown)
        idx = np.nonzero((d >= s0) & (d <= s1))[0]
        if len(idx) >= 2:
            seg = line[idx]
            pl = np.round(seg * S * 16).astype(np.int32).reshape(-1, 1, 2)
            for m, wd, off in ((sh, width + 10, (4, 6)), (edge, width + 10, (0, 0)), (ink, width, (0, 0))):
                o = np.round(np.array(off) * S * 16).astype(np.int32)
                cv2.polylines(m, [pl + o], False, 255, max(1, round(wd * S)), cv2.LINE_AA, 4)
                for e in (0, -1):
                    cv2.circle(m, tuple((pl[e, 0] + o).tolist()), round(wd * S * 8), 255, -1, cv2.LINE_AA, 4)
        s0 += DASH + GAP
        k += 1
    P.blend(canvas, sh, (60, 44, 30), 0.28 * fo)
    P.blend(canvas, edge, P.WHITE, fo)
    P.blend(canvas, ink, col, fo)
    if u >= DRAW:
        a = u - DRAW
        hs = P.sprite(canvas, ("ahead", int(width * 3.4), col), lambda: _head(int(width * 3.4), col))
        end, prev = line[-1], line[max(0, len(line) - 12)]
        ang = math.degrees(math.atan2(end[1] - prev[1], end[0] - prev[0]))
        s, sx, sy = P.pop_xy(a, 2.8, 7.5, 0.1)
        canvas.blit(hs, end[0], end[1], scale=s, sx=sx, sy=sy, rot=ang, alpha=fo, anchor=(0.92, 0.5), depth=0)
