"""清单和属性卡：信息一条一条弹出来（讲本事、理由、功绩、人物属性）。

清单（纸条一条条弹出，带打勾或星星）：
  {"type": "checklist", "items": ["会打仗", "会写文章", "个子高"], "pos": [540, 620], "at": {"line": 4}}
  items 1–6 条（每条最好 ≤ 10 个字）；pos 第一条的正中心（默认 [540, 620]，每条往下 128 像素）；mark = check（绿色打勾，默认）/ star（金星）/ none；
  w 纸条宽（默认 780）；dur 停留几秒（默认到镜头结束）；sfx 默认按条数选 list_1 … list_6。第 k 条比第 k−1 条晚 0.55 秒。

属性卡（游戏属性面板：名字、6 格图标、「本事 ★★★★★」逐条亮起来；底板 props/card_attr.png）：
  {"type": "stat_card", "name": "智伯", "rows": [{"label": "本事", "stars": 5, "icon": "props/icon_look.png"}, {"label": "好心", "stars": 1}], "at": {...}}
  rows 1–6 行，按「先左后右、一行一行」填格子，**有几条画几格**（卡片高度跟着行数裁短，奇数行最后一格空的那一个抹掉）；label ≤ 3 个字；stars 0–5（亮几颗）；icon 可选（格子里的圆形图标，相对 video/assets）；
  pos 卡片正中心（默认 [540, 900]）；w 显示宽度（默认 760，原图 949）；dur 停留几秒；gap 行与行亮起的间隔秒数（默认 0.75，允许 0.15–2.0；行数多、镜头短就写小，比如 6 行写 0.3 只要 2.3 秒）。
  音效：sfx 默认 `stat_open`（卡片滑进来），每行亮起时一声 `stat_row_N`（按行序，调一行比一行高）、每颗星一声 `star_ding`——后两种出片前按 gap 排进镜头的音效表，所以改 gap 音效跟着走。
  每亮一颗星响一声 `star_ding`（一颗一声，出片前自动排进镜头的音效表；写 "star_ding": false 关掉）。
"""
import json
import math

import numpy as np

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


@fx("checklist", params=['items', 'pos', 'mark', 'w'], layer="front", sfx="list_1", check=_lcheck)
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


def _card_pil(canvas, lay, n):
    """底板按行数裁成刚好放得下 n 格的样子：一行 2 格，有几行留几行（把多余的行整段切掉，上下两半接起来；纸是竖向均匀的，接缝看不出来）；
    最后一行只有一格（n 是奇数）时，把没用的那一格（凹槽 + 横条）抹掉，用周围的纸补上。返回 (PIL 图, 裁完的高度)。"""
    import cv2
    im = P.load_pil(canvas, CARD)
    arr = np.array(im)
    R = (n + 1) // 2
    cys = [s["circle"][1] for s in lay["slots"][0::2]]                    # 每一行的中心 y（原图像素）
    bottom_from = int(cys[-1] + 122)                                        # 最后一行下面那条缝：这以下是空白纸 + 底边
    keep_end = int(cys[R - 1] + 122)
    if n % 2 == 1:                                                          # 抹掉最后一行右边没用的格子
        slot = lay["slots"][n]
        cx, cy, r = slot["circle"]
        bx0, by0, bx1, by1 = slot["bar"]
        m = np.zeros(arr.shape[:2], np.uint8)
        cv2.circle(m, (int(cx), int(cy)), int(r) + 14, 255, -1)
        cv2.rectangle(m, (int(bx0) - 8, int(by0) - 8), (int(bx1) + 8, int(by1) + 8), 255, -1)
        rgb = cv2.inpaint(np.ascontiguousarray(arr[..., :3][..., ::-1]), m, 7, cv2.INPAINT_TELEA)[..., ::-1]
        noise = P.paper_tex(arr.shape[1], arr.shape[0], 5).astype(np.float32) * 2.4
        fill = np.clip(rgb.astype(np.float32) + noise[..., None], 0, 255).astype(np.uint8)
        arr[m > 0, :3] = fill[m > 0]
    if R < 3:
        arr = np.concatenate([arr[:keep_end], arr[bottom_from:]], axis=0)
    return P.Image.fromarray(arr, "RGBA"), arr.shape[0]


def _rows(p):
    return [r for r in p.get("rows", []) if isinstance(r, dict)]


def _scheck(p, shot=None):
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
    g = p.get("gap", T.STAT_GAP)
    if not isinstance(g, (int, float)) or not 0.15 <= g <= 2.0:
        errs.append(f"stat_card 的 gap（行与行亮起的间隔秒数）要写 0.15–2.0 的数（默认 {T.STAT_GAP}）")
    if not errs and shot is not None:
        # 每行亮起一声 stat_row_N、每颗星亮起一声 star_ding：出片前把每个时刻排进这个镜头的音效表（特效自己只能在 at 那一刻带一个音效）
        at = p.get("at")
        for i, r in enumerate(_rows(p)):
            if p.get("sfx", "x") is not None:
                P.add_sfx(shot, at, 0.45 + g * i + 0.12, f"stat_row_{i + 1}")
            if p.get("star_ding", True) is not False:
                for j in range(int(r.get("stars", 0))):
                    P.add_sfx(shot, at, 0.45 + g * i + 0.22 + 0.11 * j, "star_ding")
    return errs


def _sassets(p):
    out = [CARD, LAYOUT]
    out += [r["icon"] for r in _rows(p) if r.get("icon")]
    return out


@fx("stat_card", params=['name', 'rows', 'pos', 'w', 'max', 'star_ding', 'gap'], layer="front", sfx="stat_open", assets=_sassets, check=_scheck)
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
    nrows = len(_rows(params))
    card_im, CHe = _card_pil(canvas, lay, nrows)
    base = P.sprite(canvas, ("card_attr", W, nrows), lambda: P.add_shadow(P.fit_width(card_im, W), (6, 10), 9, 0.34))
    s, sx, sy = P.pop_xy(u, f=1.8, d=6.2, squash=0.05)
    slide = 260 * (1 - anim.out_cubic(u / 0.45))
    g = P.Group(cx, cy + slide, s, -3.5 * (1 - anim.smooth(u / 0.5)))
    canvas.blit(base, g.cx, g.cy, scale=g.g, sx=sx, sy=sy, rot=g.rot, alpha=min(1.0, u / 0.1) * fo, depth=0)

    def loc(x, y):                                               # 卡片像素坐标 → 卡片中心为原点的设计像素
        return (x - CW / 2) * k, (y - CHe / 2) * k

    name = params.get("name")
    if name and u > 0.25:
        x0, y0, x1, y1 = lay["name_bar"]
        nsp = P.sprite(canvas, ("stat_name", name, W), lambda: P.text_image(name, "title", int(96 * k * 1.25), (255, 255, 255)))
        a = u - 0.25
        ps, psx, psy = P.pop_xy(a, 2.6, 8.0, 0.08)
        lx, ly = loc((x0 + x1) / 2, (y0 + y1) / 2)
        P.draw_group(canvas, nsp, g, lx, ly, sc=ps, sx=psx, sy=psy, alpha=fo)
    gap = float(params.get("gap", T.STAT_GAP))
    n = int(params.get("max", 5))
    ssz = int(STAR * k * 1.4)
    esp = P.sprite(canvas, ("star_off", ssz), lambda: P.star_image(ssz, (222, 202, 168), (200, 176, 140)))
    lsp2 = P.sprite(canvas, ("star_on", ssz), lambda: P.edged(P.star_image(ssz, P.GOLD, (215, 140, 40)), 3, False))
    for i, r in enumerate(_rows(params)):
        a = u - (0.45 + gap * i)
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
