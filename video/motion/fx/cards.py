"""卡片类特效：人名牌、人物卡、游戏卡片（任务 / 失败 / 称号 / MVP）、大字标题。全是「纸做的牌子」：白纸边、柔和纸影、纸纹，弹出时带弹簧过冲。

人名牌（人物第一次出场：竖排大字写名字，下面一行小字写身份，家族颜色；像挂着的木牌一样落下来晃两下）：
  {"type": "name_plate", "name": "智伯", "role": "智家老大", "house": "智家", "pos": [230, 330], "at": {...}}
  name 2–4 个字；role ≤ 8 个字；house 家名（video/series_style.json 里的，决定颜色）或 color: "#rrggbb"；pos 是牌子挂点（牌子顶部中点）；size 大小倍数（默认 1.15）；dur 停留几秒（**默认 2.4：落下 0.42 秒 + 能看清 2.0 秒**；能看清的时间 = dur − 0.42，< 1.5 秒出片前报错，所以 dur ≥ 1.92；想留到镜头结束写一个大数）。
  牌子放在人物旁边、别压脸；位置要在主体安全区里（y 360 以下、左右留 80）。sfx plate_drop。

人物卡（片尾收藏卡，底板 props/card_char.png）：
  {"type": "person_card", "img": "chars/sgm_hi_remote.png", "name": "智伯", "line": "本事最大，好心最少", "no": 1, "pos": [540, 900], "at": {...}}
  img 人物高清半身；name 名字；line 一句话（≤ 24 个字，自动分两行）；no 第几张（可选，写在左上角小三角签上）；stats 可选，最多两行 [{"label": "本事", "stars": 5}]，写了就代替 line；
  w 显示宽度（默认 700，原图 957）；dur。卡片从下面翻着飞进来，落稳以后一道光扫过。sfx person_card。

游戏卡片（纸卡弹出）：card_quest「任务：守住晋阳」、card_fail「任务失败」、card_title「获得称号：最会忍的人」、card_mvp「本集 MVP」
  {"type": "card_quest", "text": "守住晋阳", "pos": [540, 820], "at": {...}}          text 主文字（≤ 10 个字）；sub 上面的小字（默认：任务 / 任务失败 / 获得称号 / 本集 MVP）；dur
  card_mvp 的 text 是获奖人名。sfx 各自固定：card_quest / card_fail / card_title / card_mvp。

大字标题（「第 1 关：忍」「水，倒过来了！」）：
  {"type": "big_title", "text": "第 1 关：忍", "pos": [540, 800], "deco": "rays", "at": {...}}
  text 1–2 行（用 \\n 分行，每行 ≤ 10 个字；超过 6 个字又没分行，就自动在第一个逗号后面分成两行）；color 字色（默认朱红，也可 gold / house 家名）；deco：rays（光芒，默认）/ flame（脚下一排纸剪火焰）/ none；
  size 字号（默认 220）；shake 落地震屏（像素，默认 10）；dur。sfx title_boom。
"""
import math

import cv2

from engine import anim
from engine import consts as C
from engine.sprites import text_image
from fx import FX
from fx import _paper as P
from fx import fx

CARD_C = "props/card_char.png"
CARD_C_LAY = "props/card_char.layout.json"


def _house_or_color(p, default):
    if p.get("house"):
        return P.house_rgb(p["house"])
    return P.rgb(p.get("color"), default)


def _hc_errors(p):
    errs = []
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    if p.get("house"):
        try:
            P.house_rgb(p["house"])
        except ValueError as e:
            errs.append(str(e))
    return errs


# ============================== 人名牌 ==============================
PLATE_FALL, PLATE_DUR, PLATE_MIN_VISIBLE = 0.42, 2.4, 1.5


def _pcheck(p):
    errs = _hc_errors(p) + P.need_pos(p)
    n, r = p.get("name"), p.get("role", "")
    if not isinstance(n, str) or not 1 <= len(n) <= 4:
        errs.append("name_plate 的 name 要写 1–4 个字")
        return errs
    if len(r) > 8:
        errs.append("name_plate 的 role（身份）不要超过 8 个字")
    if not p.get("house") and not p.get("color"):
        errs.append("name_plate 要写 house（家名）或 color")
    dur = p.get("dur", PLATE_DUR)
    if not isinstance(dur, (int, float)) or dur - PLATE_FALL < PLATE_MIN_VISIBLE:
        errs.append(f"name_plate 的 dur={dur!r}：牌子落下要 {PLATE_FALL} 秒，之后能看清的时间（不算淡入淡出）要 ≥ {PLATE_MIN_VISIBLE} 秒，所以 dur ≥ {PLATE_FALL + PLATE_MIN_VISIBLE:.2f}（不写 = {PLATE_DUR}）")
    return errs + P.glyph_errors(n, r)


def _plate(name, role, col):
    n = len(name)
    size = 118
    step = int(size * 1.02)
    bw, bh = 190, n * step + 70 + (44 if role else 0)
    board = P.paper_card(bw, bh, P.CREAM, 24, border=col, bw=7, seed=51 + n, tex=0.05)
    im = P.edged(board, 10)
    m = (im.width - bw) // 2
    txt = P.vtext_image(name, "title", size, col, 0.02)
    im.alpha_composite(txt, ((im.width - txt.width) // 2, m + 26))
    if role:
        t = P.text_image(role, "body", 30, (255, 255, 255))
        pw, ph = max(t.width + 40, 120), t.height + 16
        pill = P.edged(P.paper_card(pw, ph, col, ph // 2, seed=61, tex=0.04), 6)
        pill.alpha_composite(t, ((pill.width - t.width) // 2, (pill.height - t.height) // 2))
        big = P.Image.new("RGBA", (max(im.width, pill.width), im.height + pill.height // 2), (0, 0, 0, 0))
        big.alpha_composite(im, ((big.width - im.width) // 2, 0))
        big.alpha_composite(pill, ((big.width - pill.width) // 2, im.height - pill.height // 2 - 8))
        im = big
    # 上面的挂绳：两股麻绳收到一个小铁钉
    top = 74
    out = P.Image.new("RGBA", (im.width, im.height + top), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(out)
    cx = im.width // 2
    for dx in (-52, 52):
        d.line((cx + dx, top + 16, cx, 8), fill=(150, 112, 70, 255), width=6)
    out.alpha_composite(im, (0, top))
    d.ellipse((cx - 10, 0, cx + 10, 20), fill=(96, 78, 60, 255), outline=(240, 232, 214, 255), width=3)
    return out


@fx("name_plate", params=['name', 'role', 'house', 'color', 'pos', 'size'], layer="front", sfx="plate_drop", check=_pcheck)
def name_plate(canvas, t, params, at):
    u = t - at
    dur = params.get("dur", PLATE_DUR)
    if u < 0 or P.gone(u, dur):
        return
    col = _house_or_color(params, P.INK)
    name, role = params["name"], params.get("role", "")
    k = float(params.get("size", 1.15))
    sp = P.sprite(canvas, ("plate", name, role, col), lambda: _plate(name, role, col))
    px, py = params["pos"]
    fo = P.fade_out(u, dur)
    fall = PLATE_FALL
    if u < fall:
        y = py - 560 * (1 - anim.bounce_out(u / fall))
        ang = 0.0
    else:
        y = py
        ang = P.swing(u - fall, 8.0, 1.3, 2.6)
    canvas.blit(sp, px, y, scale=k * (1.0 if u >= 0.05 else u / 0.05), rot=ang, alpha=fo, anchor=(0.5, 0.0), depth=0)


# ============================== 人物卡 ==============================
def _cscheck(p):
    errs = P.need_pos(p) if "pos" in p else []
    if not p.get("img") or not p.get("name"):
        errs.append("person_card 要写 img（人物半身）和 name")
        return errs
    errs += P.glyph_errors(p["name"], p.get("line", ""), *[s.get("label", "") for s in p.get("stats", [])])
    if len(p.get("line", "")) > 24:
        errs.append("person_card 的 line 不要超过 24 个字")
    if len(p.get("stats", [])) > 2:
        errs.append("person_card 的 stats 最多 2 行")
    return errs


def _cassets(p):
    return [CARD_C, CARD_C_LAY, p["img"]] if p.get("img") else [CARD_C, CARD_C_LAY]


def _cover(im, w, h):
    """图按「铺满」缩放，居中裁成 w×h。"""
    s = max(w / im.width, h / im.height)
    r = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), P.Image.LANCZOS)
    x, y = (r.width - w) // 2, max(0, int((r.height - h) * 0.12))            # 半身像往上靠一点，别切掉脸
    return r.crop((x, y, x + w, y + h))


def _wrap2(s, per=10):
    """一句话分两行：优先在标点后面断（靠近中间的那个），没有标点就从中间断，行首不放标点。"""
    if len(s) <= per:
        return [s]
    mid = (len(s) + 1) // 2
    cands = [i for i in range(2, len(s) - 1) if s[i - 1] in "，、；。！？"]
    cut = min(cands, key=lambda i: abs(i - mid)) if cands and min(abs(i - mid) for i in cands) <= 4 else mid
    return [s[:cut], s[cut:]]


@fx("person_card", params=['img', 'name', 'line', 'no', 'stats', 'w', 'pos'], layer="front", sfx="person_card", assets=_cassets, check=_cscheck)
def person_card(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    import json
    lay = json.loads(canvas.assets.resolve(CARD_C_LAY).read_text(encoding="utf-8"))
    W = float(params.get("w", 700))
    CW, CH = 957, 1347
    k = W / CW
    px, py = params.get("pos", [C.W / 2, 900])
    fo = P.fade_out(u, dur, 0.3)
    base = P.sprite(canvas, ("cardc", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, CARD_C), W), (7, 12), 10, 0.36))
    # 入场：从下面翻着飞进来（先竖着压扁再转开，同时往上飞），落下时弹一下
    fly = 0.55
    e = anim.out_cubic(u / fly)
    sx = math.cos(math.pi * (1 - e) * 1.5) if u < fly else 1.0                # 翻面：1.5 个半圈
    sx = abs(sx) if u < fly else 1.0
    b0 = max(u - fly, 0.0)
    s = 1.0 + 0.07 * math.exp(-8 * b0) * math.cos(2 * math.pi * 3.0 * b0)              # 落地的一弹：先大一点，再回到 1
    ssy = 1.0 - 0.05 * math.exp(-9 * b0) * math.cos(2 * math.pi * 3.0 * b0)
    y = py + 700 * (1 - e)
    g = P.Group(px, y, 1.0 if u < fly else s, -6 * (1 - e))
    x0, y0, x1, y1 = lay["window"]
    ww, wh = int((x1 - x0) * k), int((y1 - y0) * k)

    def loc(x, y_):
        return (x - CW / 2) * k, (y_ - CH / 2) * k

    def gblit(sp, lx, ly, **kw):
        kw.setdefault("sx", 1.0)
        x, y_ = g.pt(lx, ly)
        canvas.blit(sp, x, y_, scale=g.g * kw.pop("sc", 1.0), sx=sx * kw.pop("sx"), sy=kw.pop("sy", 1.0), rot=g.rot + kw.pop("rot", 0.0), alpha=fo * kw.pop("alpha", 1.0), depth=0, **kw)

    # 人物半身（在画框后面，先画）
    av = params["img"]
    asp = P.sprite(canvas, ("cardc_av", av, ww, wh), lambda: _cover(P.load_pil(canvas, av), ww, wh))
    if u >= fly * 0.5:
        wx, wy = loc((x0 + x1) / 2, (y0 + y1) / 2)
        gblit(asp, wx, wy, alpha=min(1.0, (u - fly * 0.5) / 0.2))
    gblit(base, 0, 0, sy=ssy if u >= fly else 1.0)
    if u < fly:
        return
    a = u - fly
    # 名字（名字横条上，白色 ZCOOL）
    nb = lay["name_bar"]
    nsp = P.sprite(canvas, ("cardc_name", params["name"], W), lambda: text_image(params["name"], "title", int(104 * k * 1.1), (255, 255, 255), 3, (120, 30, 24)))
    ps, psx, psy = P.pop_xy(a - 0.1, 2.4, 7.5, 0.08)
    if a > 0.1:
        nx, ny = loc((nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2)
        gblit(nsp, nx, ny, sc=ps, sx=psx, sy=psy)
    # 评语或属性（两条横线上面）
    ly = lay["lines_y"]
    lx0, lx1 = lay["lines_x"]
    if a > 0.3:
        la = anim.smooth((a - 0.3) / 0.25)
        if params.get("stats"):
            for i, st in enumerate(params["stats"][:2]):
                tsp = P.sprite(canvas, ("cardc_stat", st["label"], W), lambda st=st: text_image(st["label"], "title", int(50 * k * 1.15), P.INK))
                tx, ty = loc(lx0 + 60, ly[i] - 46)
                gblit(tsp, tx + tsp.wd / 2, ty, alpha=la)
                ssz = int(44 * k * 1.1)
                on = P.sprite(canvas, ("cardc_on", ssz), lambda: P.star_image(ssz, P.GOLD, (215, 140, 40)))
                off = P.sprite(canvas, ("cardc_off", ssz), lambda: P.star_image(ssz, (222, 202, 168), (200, 176, 140)))
                for j in range(5):
                    sxp, syp = loc(lx1 - 30 - (4 - j) * 60, ly[i] - 46)
                    gblit(on if j < st.get("stars", 0) else off, sxp, syp, alpha=la)
        elif params.get("line"):
            rows = _wrap2(params["line"])
            for i, rowt in enumerate(rows):
                tsp = P.sprite(canvas, ("cardc_line", rowt, W), lambda rowt=rowt: text_image(rowt, "body", int(52 * k * 1.1), P.INK))
                tx, ty = loc((lx0 + lx1) / 2, ly[i] - 46)
                gblit(tsp, tx, ty + 6 * (1 - la), alpha=la)
    # 左上角小三角签：第 N 张
    if params.get("no") and a > 0.2:
        tag = lay["tag"]
        txt = f"第{params['no']}张"
        tsp = P.sprite(canvas, ("cardc_tag", txt, W), lambda: text_image(txt, "body", int(34 * k * 1.2), (255, 255, 255)).rotate(28, expand=True, resample=P.Image.BICUBIC))
        tx, ty = loc(tag[0] + (tag[2] - tag[0]) * 0.46, tag[1] + (tag[3] - tag[1]) * 0.5)
        ts, tsx, tsy = P.pop_xy(a - 0.2, 2.6, 8.0, 0.08)
        gblit(tsp, tx, ty, sc=ts)
    # 一道光扫过（落稳以后 0.5 秒开始，0.7 秒扫完）
    b = a - 0.5
    if 0 <= b < 0.7:
        m = P.new_mask(canvas)
        hw, hh = W / 2, W * CH / CW / 2
        xs = -hw + (2 * hw + 260) * anim.smooth(b / 0.7)
        band = [(xs - 90, -hh - 40), (xs + 10, -hh - 40), (xs - 150, hh + 40), (xs - 250, hh + 40)]
        pts = [g.pt(x_, y_) for x_, y_ in band]
        P.fill_poly(canvas, m, pts)
        m = cv2.GaussianBlur(m, (0, 0), max(1.0, 14 * canvas.S))
        # 只留在卡片范围里：用卡片的圆角矩形遮罩
        box = P.new_mask(canvas)
        P.fill_poly(canvas, box, [g.pt(-hw + 30 * k, -hh + 30 * k), g.pt(hw - 30 * k, -hh + 30 * k), g.pt(hw - 30 * k, hh - 30 * k), g.pt(-hw + 30 * k, hh - 30 * k)])
        m = cv2.min(m, box)
        P.blend(canvas, m, (255, 252, 240), 0.55 * fo)


# ============================== 游戏卡片 ==============================
def _tape(w=120, h=44, ang=-12):
    im = P.Image.new("RGBA", (w + 30, h + 30), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    x0, y0 = 15, 15
    pts = [(x0, y0)]
    for i in range(0, h, 8):
        pts += [(x0 + (5 if (i // 8) % 2 else 0), y0 + i)]
    pts += [(x0, y0 + h)]
    pts += [(x0 + w, y0 + h)] + [(x0 + w - (5 if (i // 8) % 2 else 0), y0 + i) for i in range(h, -1, -8)] + [(x0 + w, y0)]
    d.polygon(pts, fill=(255, 232, 150, 205))
    return P.edged(im.rotate(ang, expand=True, resample=P.Image.BICUBIC), 3, False)


def _gcheck(kind):
    def check(p):
        errs = P.need_pos(p) if "pos" in p else []
        tx = p.get("text")
        if not isinstance(tx, str) or not 1 <= len(tx) <= 10:
            errs.append(f"{kind} 的 text 要写 1–10 个字")
            return errs
        return errs + P.glyph_errors(tx, p.get("sub", ""))
    return check


def _quest_img(text, sub):
    w, h = 820, 330
    card = P.paper_card(w, h, P.CREAM, 30, seed=71, tex=0.05, torn=0.0, stitch=(196, 160, 120))
    im = P.edged(card, 11)
    m = (im.width - w) // 2
    for (tx, ty, ang) in ((m + 10, m + 6, -32), (m + w - 120, m + 4, 30)):          # 胶带先贴，红签压在上面（签上的字不被胶带盖住）
        im.alpha_composite(_tape(110, 40, ang), (tx - 20, ty - 34))
    t = text_image(sub, "title", 52, (255, 255, 255))
    ban = P.edged(P.paper_card(max(300, t.width + 70), 84, P.RED, 26, seed=72), 6)       # 签的宽度跟着字走（6 个字 312 像素，原来 300 会切掉头尾）
    ban.alpha_composite(t, ((ban.width - t.width) // 2, (ban.height - t.height) // 2 - 2))
    im.alpha_composite(ban, (m + 40, m - 30))
    size = 128 if len(text) <= 5 else int(660 / len(text) * 1.0)
    t = text_image(text, "title", min(size, 150), P.INK)
    while t.width > w - 120:
        size -= 6
        t = text_image(text, "title", size, P.INK)
    im.alpha_composite(t, ((im.width - t.width) // 2, m + 110))
    return im


def _fail_img(text, sub):
    w, h = 820, 330
    grey = (188, 194, 200)
    card = P.paper_card(w, h, grey, 30, seed=81, tex=0.05)
    im = P.edged(card, 11)
    m = (im.width - w) // 2
    ban = P.edged(P.paper_card(340, 84, (108, 118, 132), 26, seed=82), 6)
    t = text_image(sub, "title", 52, (255, 255, 255))
    ban.alpha_composite(t, ((ban.width - t.width) // 2, (ban.height - t.height) // 2 - 2))
    im.alpha_composite(ban, (m + 40, m - 30))
    size = 128 if len(text) <= 5 else int(660 / len(text))
    t = text_image(text, "title", min(size, 150), (72, 78, 90))
    while t.width > w - 120:
        size -= 6
        t = text_image(text, "title", size, (72, 78, 90))
    im.alpha_composite(t, ((im.width - t.width) // 2, m + 110))
    # 大大的淡墨色「×」章，压在右下角
    st = P.Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = P.ImageDraw.Draw(st)
    cx, cy, r = im.width - m - 110, im.height - m - 70, 62
    for a in (45, -45):
        dx, dy = r * math.cos(math.radians(a)), r * math.sin(math.radians(a))
        d.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=(72, 78, 90, 150), width=26)
        d.ellipse((cx - dx - 13, cy - dy - 13, cx - dx + 13, cy - dy + 13), fill=(72, 78, 90, 150))
        d.ellipse((cx + dx - 13, cy + dy - 13, cx + dx + 13, cy + dy + 13), fill=(72, 78, 90, 150))
    im.alpha_composite(st)
    return im


def _ribbon(text, sub, col):
    """称号：金色缎带（两头燕尾），上面一条小红签写「获得称号」。"""
    w, h = 900, 190
    tail_h = int(h * 0.2)
    base = P.Image.new("RGBA", (w, h + tail_h), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(base)
    dark = P.shade(col, 0.72)
    for x0, x1, notch in ((0, 250, 1), (w - 250, w, -1)):
        pts = [(x0, tail_h), (x1, tail_h), (x1, h + tail_h), (x0, h + tail_h), (x0 + (60 if notch > 0 else 0) + (0 if notch > 0 else 0), tail_h + h / 2)]
        pts = [(x0, tail_h), (x1, tail_h), (x1, h + tail_h), (x0, h + tail_h), ((x0 + 70) if notch > 0 else (x1 - 70), tail_h + h / 2)]
        d.polygon(pts, fill=dark + (255,))
    band = P.paper_card(w - 220, h, col, 12, seed=91, tex=0.05)
    base.alpha_composite(band, (110, 0))
    im = P.edged(base, 9)
    m = (im.width - w) // 2
    ban = P.edged(P.paper_card(300, 76, P.RED, 24, seed=92), 6)
    t = text_image(sub, "title", 48, (255, 255, 255))
    ban.alpha_composite(t, ((ban.width - t.width) // 2, (ban.height - t.height) // 2 - 2))
    im.alpha_composite(ban, ((im.width - ban.width) // 2, m - 34))
    size = 104
    t = text_image(text, "title", size, P.INK)
    while t.width > w - 320:
        size -= 6
        t = text_image(text, "title", size, P.INK)
    im.alpha_composite(t, ((im.width - t.width) // 2, m + 56))
    return im


def _medal(text, sub):
    """MVP：金色圆形奖章（16 个圆齿）+ 星星 + 两条红飘带，下面一条名字缎带。"""
    S = 340
    ss = 2
    im = P.Image.new("RGBA", (S * ss + 40, int(S * 1.5) * ss), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    cx, cy = im.width / 2, S * ss * 0.52
    for sgn in (-1, 1):
        x = cx + sgn * S * ss * 0.16
        d.polygon([(x - 46 * ss, cy + 40 * ss), (x + 46 * ss, cy + 40 * ss), (x + 46 * ss + sgn * 20 * ss, cy + 330 * ss * 0.55), (x, cy + 300 * ss * 0.55), (x - 46 * ss + sgn * 20 * ss, cy + 330 * ss * 0.55)],
                  fill=(206, 62, 50, 255) if sgn < 0 else (176, 48, 40, 255))
    pts = []
    for i in range(160):
        a = 2 * math.pi * i / 160
        r = S * ss * 0.5 * (1 + 0.045 * math.cos(16 * a))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=P.GOLD + (255,))
    d.ellipse((cx - S * ss * 0.40, cy - S * ss * 0.40, cx + S * ss * 0.40, cy + S * ss * 0.40), fill=(250, 214, 110, 255), outline=(214, 150, 40, 255), width=6 * ss)
    im = im.resize((im.width // ss, im.height // ss), P.Image.LANCZOS)
    st = P.star_image(int(S * 0.5), (255, 250, 232), (222, 168, 60))
    im.alpha_composite(st, (int(im.width / 2 - st.width / 2), int(S * 0.52 - st.height / 2)))
    tt = text_image("MVP", "title", 84, (176, 100, 24), 0)
    im.alpha_composite(tt, (int(im.width / 2 - tt.width / 2), int(S * 0.52 + S * 0.16)))
    im = P.edged(im, 9)
    # 名字缎带
    rb = P.edged(P.paper_card(560, 104, P.RED, 20, seed=97, stitch=(255, 220, 190)), 7)
    t = text_image(text, "title", 72, (255, 255, 255), 3, (120, 30, 24))
    rb.alpha_composite(t, ((rb.width - t.width) // 2, (rb.height - t.height) // 2 - 3))
    out = P.Image.new("RGBA", (max(im.width, rb.width), im.height + 60), (0, 0, 0, 0))
    out.alpha_composite(im, ((out.width - im.width) // 2, 0))
    out.alpha_composite(rb, ((out.width - rb.width) // 2, int(S * 0.52 + S * 0.52)))
    return out


def _mvp_check(p):
    errs = P.need_pos(p) if "pos" in p else []
    if not isinstance(p.get("text"), str) or not 1 <= len(p["text"]) <= 6:
        errs.append("card_mvp 的 text 写获奖人名（1–6 个字）")
        return errs
    return errs + P.glyph_errors(p["text"])


def _game(kind, sfx, default_sub, builder, anim_kind):
    def draw(canvas, t, params, at):
        u = t - at
        dur = params.get("dur")
        if u < 0 or P.gone(u, dur):
            return
        text, sub = params["text"], params.get("sub", default_sub)
        sp = P.sprite(canvas, (kind, text, sub), lambda: builder(text, sub))
        px, py = params.get("pos", [C.W / 2, 820])
        fo = P.fade_out(u, dur)
        if anim_kind == "drop":                       # 任务：像挂牌一样从上面掉下来，落稳后轻晃
            fall = 0.4
            y = py - 800 * (1 - anim.bounce_out(u / fall)) if u < fall else py
            ang = P.swing(u - fall, 4.0, 1.4, 3.0) if u >= fall else 0.0
            sc, sx, sy = 1.0, 1.0, 1.0
        elif anim_kind == "thud":                     # 失败：沉沉地砸下来，歪一下，慢慢垂下去
            fall = 0.28
            y = py - 700 * (1 - anim.in_cubic(u / fall)) if u < fall else py
            q = math.exp(-max(u - fall, 0) * 7) * math.cos(2 * math.pi * 2.2 * max(u - fall, 0)) if u >= fall else 0.0
            sc, sx, sy = 1.0, 1.0 + 0.10 * q, 1.0 - 0.14 * q
            ang = 3.0 * anim.smooth((u - fall) / 0.6) - 1.0 * (u < fall)
        elif anim_kind == "unfurl":                   # 称号：缎带从中间往两边展开，带过冲
            e = P.spring(u, 2.1, 6.2)
            sc, sx, sy = 1.0, max(0.02, min(e, 1.12)), 0.9 + 0.1 * min(e, 1.0)
            y, ang = py, 0.0
        else:                                         # MVP：奖章旋转着弹出
            e = P.spring(u, 2.0, 6.0)
            sc = max(e, 0.0)
            sx = math.cos(2 * math.pi * 2.0 * min(u, 0.5) * 0.9) if u < 0.5 else 1.0
            sx = 0.15 if abs(sx) < 0.15 else abs(sx)
            sy, y, ang = 1.0, py, 0.0
        canvas.blit(sp, px, y, scale=sc, sx=sx, sy=sy, rot=ang, alpha=min(1.0, u / 0.05) * fo, depth=0)
        if anim_kind in ("unfurl", "mvp") and 0.3 <= u < 1.4:               # 亮一下的小星星
            SP = FX.get("sparkle")
            if SP is not None:
                SP.fn(canvas, t, {"area": [px - 380, py - 260, px + 380, py + 200], "count": 10, "dur": 1.1}, at + 0.3)
    fx(kind, params=["text", "sub", "pos"], layer="front", sfx=sfx, check=_mvp_check if kind == "card_mvp" else _gcheck(kind))(draw)
    return draw


card_quest = _game("card_quest", "card_quest", "任务", _quest_img, "drop")
card_fail = _game("card_fail", "card_fail", "任务失败", _fail_img, "thud")
card_title = _game("card_title", "card_title", "获得称号", lambda text, sub: _ribbon(text, sub, P.GOLD), "unfurl")
card_mvp = _game("card_mvp", "card_mvp", "本集 MVP", _medal, "mvp")


# ============================== 大字标题 ==============================
def _tcheck(p):
    errs = _hc_errors(p) + (P.need_pos(p) if "pos" in p else [])
    tx = p.get("text")
    if not isinstance(tx, str) or not tx or any(len(x) > 10 for x in tx.split("\n")) or len(tx.split("\n")) > 2:
        errs.append("big_title 的 text 写 1–2 行（用 \\n 分行），每行 ≤ 10 个字")
        return errs
    if p.get("deco", "rays") not in ("rays", "flame", "none"):
        errs.append("big_title 的 deco 只能是 rays / flame / none")
    return errs + P.glyph_errors(tx.replace("\n", ""))


def _split(text):
    """字多（> 6 个字，空格不算）又没写换行：在第一个逗号 / 冒号后面分成两行，没有标点就从中间分（字更大，更像标题）。"""
    nl = chr(10)
    if nl in text or len(text.replace(" ", "")) <= 6:
        return text.split(nl)
    for i, ch in enumerate(text[:-1]):
        if ch in "，、：；" and 1 <= i < len(text) - 2:
            return [text[:i + 1], text[i + 1:]]
    return [text[:len(text) // 2], text[len(text) // 2:]]


@fx("big_title", params=['text', 'pos', 'deco', 'color', 'house', 'size', 'shake'], layer="front", sfx="title_boom", check=_tcheck)
def big_title(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lines = _split(params["text"])
    col = _house_or_color(params, P.RED) if (params.get("house") or params.get("color")) else P.RED
    px, py = params.get("pos", [C.W / 2, 800])
    n = max(len(x.replace(" ", "")) + 0.35 * x.count(" ") for x in lines)
    size = min(float(params.get("size", 220)), 940.0 / (0.95 * n))
    fo = P.fade_out(u, dur, 0.3)
    deco = params.get("deco", "rays")
    if deco == "rays" and FX.get("rays"):
        FX["rays"].fn(canvas, t, {"pos": [px, py], "alpha": 0.6, "radius": 1100, "dur": dur}, at)
    if deco == "flame" and FX.get("flame"):                                        # 火苗在字后面，从字的下沿烧上来
        FX["flame"].fn(canvas, t, {"pos": [px, py + (len(lines) - 1) / 2 * size * 1.18 + size * 0.55], "w": min(980, n * size * 1.1), "height": size * 1.5,
                                   "count": max(6, n + 2), "dur": dur}, at + 0.15)
    amp = min(float(params.get("shake", 10.0)), C.SHAKE_AMP_MAX)
    land = 0.16
    if u < 0.5 and amp > 0:
        a = u - land
        if 0 <= a < 0.3:
            env = (1 - a / 0.3) ** 2
            P.shift_screen(canvas, amp * env * math.sin(2 * math.pi * 12 * a), amp * env * math.sin(2 * math.pi * 15 * a + 1))
    for li, txt in enumerate(lines):
        sp = P.sprite(canvas, ("btitle", txt, int(size), col), lambda txt=txt: P.chunky_text(txt, int(size), col, seed=4 + li))
        y = py + (li - (len(lines) - 1) / 2) * size * 1.18
        a = u - 0.06 * li
        if a < 0:
            continue
        if a < land:
            w = a / land
            sc, sx, sy = 1.0 + 1.5 * (1 - w * w), 1.0, 1.0
        else:
            b = a - land
            q = math.exp(-b * 9) * math.cos(2 * math.pi * 2.8 * b)
            sc, sx, sy = 1.0, 1.0 + 0.16 * q, 1.0 - 0.22 * q
        canvas.blit(sp, px, y, scale=sc * (1 if dur is None else max(fo, 0.01)), sx=sx, sy=sy, alpha=min(1.0, a / 0.05) * fo, depth=0)
