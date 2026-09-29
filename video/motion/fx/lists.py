"""清单和属性卡：信息一条一条弹出来（讲本事、理由、功绩、人物属性）。

清单（纸条一条条弹出，带打勾或星星）：
  {"type": "checklist", "items": ["会打仗", "会写文章", "个子高"], "pos": [540, 620], "at": {"line": 4}}
  items 1–6 条（每条最好 ≤ 10 个字）；pos 第一条的正中心（默认 [540, 620]，每条往下 128 像素）；mark = check（绿色打勾，默认）/ star（金星）/ none；
  w 纸条宽（默认 780）；dur 停留几秒（默认到镜头结束）；sfx 默认按条数选 list_1 … list_6。第 k 条比第 k−1 条晚 0.55 秒。

属性卡（游戏属性面板：名字、6 格图标、「本事 ★★★★★」逐条亮起来；底板 props/card_attr.png）：
  {"type": "stat_card", "name": "智伯", "rows": [{"label": "本事", "stars": 5, "icon": "props/icon_look.png"}, {"label": "好心", "stars": 1}], "at": {...}}
  rows 1–6 行，按「先左后右、一行一行」填格子；label ≤ 3 个字；stars 0–5（亮几颗）；icon 可选（格子里的圆形图标，相对 video/assets）；
  pos 卡片正中心（默认 [540, 900]）；w 显示宽度（默认 760，原图 949）；dur 停留几秒；sfx 默认按行数选 stat_1 … stat_6。第 k 行比第 k−1 行晚 0.75 秒亮起。
"""
import json
import math

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx
from sfx import timing as T

ROW = 128


# ============================== 清单 ==============================
def _items(p):
    out = []
    for it in p.get("items", []):
        out.append(it if isinstance(it, str) else str(it.get("text", "")))
    return out


def _lcheck(p):
    errs = []
    its = _items(p)
    if not 1 <= len(its) <= T.LIST_MAX or not all(its):
        errs.append(f"checklist 的 items 要写 1–{T.LIST_MAX} 条文字")
        return errs
    if p.get("mark", "check") not in ("check", "star", "none"):
        errs.append("checklist 的 mark 只能是 check / star / none")
    errs += P.glyph_errors(*its)
    P.auto_sfx(p, f"list_{len(its)}")
    return errs


def _strip(text, w, mark):
    h = 108
    im = P.edged(P.paper_card(w, h, P.CREAM, 30, seed=11 + len(text)), 9)
    m = im.width - w
    d = P.ImageDraw.Draw(im)
    if mark != "none":
        cx, cy = m // 2 + 66, m // 2 + h // 2
        d.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=P.shade(P.CREAM, 0.90) + (255,))
    size = 58
    t = P.text_image(text, "title", size, P.INK)
    while t.width > (w - (150 if mark != "none" else 70)) and size > 24:
        size -= 2
        t = P.text_image(text, "title", size, P.INK)
    x0 = m // 2 + (124 if mark != "none" else 44)
    im.alpha_composite(t, (x0, m // 2 + (h - t.height) // 2))
    return im


@fx("checklist", layer="front", sfx="list_1", check=_lcheck)
def checklist(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur):
        return
    its = _items(params)
    mark = params.get("mark", "check")
    w = int(params.get("w", 780))
    px, py = params.get("pos", [C.W / 2, 620])
    fo = P.fade_out(u, dur)
    rng = P.rng_for("list", tuple(its))
    rots = rng.uniform(-1.4, 1.4, len(its))
    for k, text in enumerate(its):
        a = u - T.LIST_GAP * k
        if a < 0:
            continue
        sp = P.sprite(canvas, ("strip", text, w, mark), lambda text=text: _strip(text, w, mark))
        s, sx, sy = P.pop_xy(a, f=2.0, d=7.5, squash=0.06)
        slide = 200 * (1 - anim.out_cubic(a / 0.28))
        y = py + ROW * k
        canvas.blit(sp, px - slide, y, scale=s, sx=sx, sy=sy, rot=rots[k] * min(1.0, s), alpha=min(1.0, a / 0.08) * fo, depth=0)
        b = a - 0.16                                                            # 0.16 秒以后盖章：打勾 / 星星
        if mark != "none" and b >= 0:
            mk = P.sprite(canvas, ("mark", mark), lambda: P.edged(P.tick_image(64, P.GREEN) if mark == "check" else P.star_image(72, P.GOLD, (215, 140, 40)), 5))
            if b < 0.12:
                pop = 1.0 + 1.3 * (1 - anim.out_cubic(b / 0.12))                # 从大到小「盖」下去
            else:
                c = b - 0.12
                pop = 1.0 + 0.16 * math.exp(-c * 8) * math.sin(2 * math.pi * 3.0 * c)
            cx = px - w / 2 + 66
            canvas.blit(mk, cx, y, scale=pop, rot=rots[k] * 0.6 - (10 if mark == "star" else 0) * (1 - anim.smooth(b / 0.3)), alpha=min(1.0, b / 0.05) * fo, depth=0)


# ============================== 属性卡 ==============================
CARD = "props/card_attr.png"
LAYOUT = "props/card_attr.layout.json"
CW, CH = 949, 1228
STAR = 40


def _layout(canvas):
    return json.loads(canvas.assets.resolve(LAYOUT).read_text(encoding="utf-8"))


def _rows(p):
    return [r for r in p.get("rows", []) if isinstance(r, dict)]


def _scheck(p):
    errs = []
    rows = _rows(p)
    if not 1 <= len(rows) <= T.STAT_MAX:
        errs.append(f"stat_card 的 rows 要写 1–{T.STAT_MAX} 行，每行 {{\"label\": \"本事\", \"stars\": 5}}")
        return errs
    for i, r in enumerate(rows):
        if not r.get("label") or len(r["label"]) > 3:
            errs.append(f"rows[{i}].label 要写 1–3 个字")
        if not isinstance(r.get("stars", 0), int) or not 0 <= r.get("stars", 0) <= int(p.get("max", 5)):
            errs.append(f"rows[{i}].stars 要写 0–{int(p.get('max', 5))} 的整数")
    if p.get("name"):
        errs += P.glyph_errors(p["name"])
    errs += P.glyph_errors(*[r.get("label", "") for r in rows])
    P.auto_sfx(p, f"stat_{len(rows)}")
    return errs


def _sassets(p):
    out = [CARD, LAYOUT]
    out += [r["icon"] for r in _rows(p) if r.get("icon")]
    return out


@fx("stat_card", layer="front", sfx="stat_1", assets=_sassets, check=_scheck)
def stat_card(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lay = _layout(canvas)
    W = float(params.get("w", 760))
    k = W / CW                                                   # 卡片像素 → 设计像素
    cx, cy = params.get("pos", [C.W / 2, 900])
    fo = P.fade_out(u, dur, 0.3)
    base = P.sprite(canvas, ("card_attr", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, CARD), W), (6, 10), 9, 0.34))
    s, sx, sy = P.pop_xy(u, f=1.8, d=6.2, squash=0.05)
    slide = 260 * (1 - anim.out_cubic(u / 0.45))
    g = P.Group(cx, cy + slide, s, -3.5 * (1 - anim.smooth(u / 0.5)))
    canvas.blit(base, g.cx, g.cy, scale=g.g, sx=sx, sy=sy, rot=g.rot, alpha=min(1.0, u / 0.1) * fo, depth=0)

    def loc(x, y):                                               # 卡片像素坐标 → 卡片中心为原点的设计像素
        return (x - CW / 2) * k, (y - CH / 2) * k

    name = params.get("name")
    if name and u > 0.25:
        x0, y0, x1, y1 = lay["name_bar"]
        nsp = P.sprite(canvas, ("stat_name", name, W), lambda: P.text_image(name, "title", int(96 * k * 1.25), (255, 255, 255)))
        a = u - 0.25
        ps, psx, psy = P.pop_xy(a, 2.6, 8.0, 0.08)
        lx, ly = loc((x0 + x1) / 2, (y0 + y1) / 2)
        P.draw_group(canvas, nsp, g, lx, ly, sc=ps, sx=psx, sy=psy, alpha=fo)
    n = int(params.get("max", 5))
    ssz = int(STAR * k * 1.4)
    esp = P.sprite(canvas, ("star_off", ssz), lambda: P.star_image(ssz, (222, 202, 168), (200, 176, 140)))
    lsp2 = P.sprite(canvas, ("star_on", ssz), lambda: P.edged(P.star_image(ssz, P.GOLD, (215, 140, 40)), 3, False))
    for i, r in enumerate(_rows(params)):
        a = u - (0.45 + T.STAT_GAP * i)
        if a < 0:
            continue
        slot = lay["slots"][i]
        ccx, ccy, cr = slot["circle"]
        bx0, by0, bx1, by1 = slot["bar"]
        if r.get("icon"):
            isp = P.sprite(canvas, ("stat_icon", r["icon"], W), lambda r=r: P.fit_height(P.load_pil(canvas, r["icon"]), 2 * cr * k * 1.02))
            ps, psx, psy = P.pop_xy(a, 2.2, 7.0, 0.1)
            lx, ly = loc(ccx, ccy)
            P.draw_group(canvas, isp, g, lx, ly, sc=ps, sx=psx, sy=psy, alpha=fo)
        lsp = P.sprite(canvas, ("stat_label", r["label"], W), lambda r=r: P.text_image(r["label"], "title", int(58 * k * 1.3), P.INK, 0))
        la = anim.smooth((a - 0.08) / 0.2)
        lx, ly = loc((bx0 + bx1) / 2, (by0 + by1) / 2)
        P.draw_group(canvas, lsp, g, lx, ly + 10 * (1 - la), alpha=la * fo)
        stars = int(r.get("stars", 0))
        step = (bx1 - bx0) / n
        for j in range(n):
            lx, ly = loc(bx0 + step * (j + 0.5), by1 + 36)
            P.draw_group(canvas, esp, g, lx, ly, alpha=min(1.0, a / 0.15) * fo)
            b = a - (0.22 + 0.11 * j)
            if j < stars and b >= 0:
                ps, psx, psy = P.pop_xy(b, 3.0, 9.0, 0.12)
                P.draw_group(canvas, lsp2, g, lx, ly, sc=ps * (1 + 0.7 * math.exp(-b * 14)), sx=psx, sy=psy, alpha=min(1.0, b / 0.04) * fo)
