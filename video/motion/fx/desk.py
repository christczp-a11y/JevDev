"""解说台和想象泡泡：司马光坐在书房的解说台后面讲故事（书房后墙 sets/study/wall.png + 书桌 sets/study/desk.png + 纸屏幕 + 司马光高清半身 chars/sgm_hi_remote.png），
按一下遥控器，画面切到故事里（用转场 tv_switch）。想象泡泡是人物头上的思考云，里面放古今对照的小画。书页边是「考你」时司马光从书页后面探出来用的。

  {"type": "screen", "img": "props/screen_cup_before.png", "pos": [540, 700], "w": 860, "at": {...}}      纸屏幕：木框立在书桌上，屏幕里的画「展开」出现；
        后面再写一个 screen（同一个 pos）就是换画面（新画从中间往两边展开盖住旧的）；img 可以不写（空白纸屏）；w 木框显示宽度（默认 860，原图 1278）；dur
        4:3 的画放进去：屏幕纸面是 16:9（约 981×565 像素），画按「完整放进去」缩放，左右留纸边，外面一圈白纸边像贴上去的照片
  {"type": "remote_click", "pos": [700, 900], "at": {...}}                                                  按遥控器：按钮处一圈涟漪 + 几道短线 + 「叮」的一声；pos 是按钮的屏幕位置；color（默认朱红）
  {"type": "bubble", "img": "props/bubble_nickname.png", "pos": [400, 620], "at": {...}}                     想象泡泡（props/bubble_cloud.png）：从人物头旁边的尾巴那一头「鼓」出来；
        img 泡泡里的画（相对 video/assets；缩放到放进云里）；text 不放画、放几个大字（≤ 8 个字）；flip 尾巴放到右下；w 显示宽度（默认 820，原图 1357）；dur
  {"type": "page_edge", "at": {...}}                                                                        书页边（props/page_edge.png）：从画面下面滑上来，盖住司马光的下半截，像他躲在书页后面；
        y 书页上沿的位置（默认 1240）；w 显示宽度（默认 1180，原图 1510）；dur 停留几秒（之后滑下去）；人物写在 actors 里，出场用 slide 或 pop，画在书页边后面
音效：screen → screen_on，remote_click → click，bubble → bubble_pop，page_edge → page_slide。
"""
import json
import math

import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx

FRAME, FRAME_LAY = "props/screen_frame.png", "props/screen_frame.layout.json"
CLOUD, CLOUD_LAY = "props/bubble_cloud.png", "props/bubble_cloud.layout.json"
PAGE = "props/page_edge.png"


def _lay(canvas, path):
    return json.loads(canvas.assets.resolve(path).read_text(encoding="utf-8"))


def _fit(im, w, h):
    s = min(w / im.width, h / im.height)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), P.Image.LANCZOS)


# ============================== 纸屏幕 ==============================
def _scheck(p):
    return P.need_pos(p) if "pos" in p else []


def _sassets(p):
    return [FRAME, FRAME_LAY] + ([p["img"]] if p.get("img") else [])


@fx("screen", layer="front", sfx="screen_on", assets=_sassets, check=_scheck)
def screen(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lay = _lay(canvas, FRAME_LAY)
    W = float(params.get("w", 860))
    px, py = params.get("pos", [C.W / 2, 700])
    FW, FH = 1278, 882
    k = W / FW
    fo = P.fade_out(u, dur, 0.3)
    frame = P.sprite(canvas, ("screenf", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, FRAME), W), (6, 10), 9, 0.34))
    # 木框只在第一次出现时弹一下；之后换画面的 screen 也会重画框，但框已经在那里了，弹动只发生在 u < 0.5 而且只有没有 img 或 img 是第一张时才明显
    s, sx, sy = P.pop_xy(u, 2.0, 6.5, 0.05) if not params.get("img") else (1.0, 1.0, 1.0)
    canvas.blit(frame, px, py, scale=s, sx=sx, sy=sy, alpha=min(1.0, u / 0.06) * fo, depth=0)
    if not params.get("img"):
        return
    x0, y0, x1, y1 = lay["screen"]
    sw, sh = (x1 - x0) * k, (y1 - y0) * k
    ccx, ccy = px + ((x0 + x1) / 2 - FW / 2) * k, py + ((y0 + y1) / 2 - FH / 2) * k
    img = params["img"]

    def build():
        pic = _fit(P.load_pil(canvas, img), sw * 0.94, sh * 0.94)
        pic = P.add_shadow(P.edged(pic, max(5, int(sh * 0.016)), False), (3, 5), 5, 0.3, 14)
        return pic
    sp = P.sprite(canvas, ("screenc", img, W), build)
    # 展开：从中间往两边（横向遮罩），0.4 秒，展开时中间一道亮线
    e = anim.smooth(u / 0.4)
    if e >= 1.0:
        canvas.blit(sp, ccx, ccy, alpha=min(1.0, u / 0.1) * fo, depth=0)
        return
    S = canvas.S
    tmp = canvas.img.copy()                                              # 图先画在一份拷贝上，再按「从中间往两边」的遮罩贴回来
    tc, canvas.img = canvas.img, tmp
    canvas.blit(sp, ccx, ccy, alpha=min(1.0, u / 0.1) * fo, depth=0)
    canvas.img = tc
    half = sw * 0.5 * (0.02 + 0.98 * e)
    m = np.zeros((canvas.h, canvas.w), np.uint8)
    y_a, y_b = int(round((ccy - sh / 2 - 30) * S)), int(round((ccy + sh / 2 + 30) * S))
    x_a, x_b = int(round((ccx - half) * S)), int(round((ccx + half) * S))
    m[max(0, y_a):min(canvas.h, y_b), max(0, x_a):min(canvas.w, x_b)] = 255
    m = cv2.GaussianBlur(m, (0, 0), max(0.8, 6 * S)).astype(np.float32)[..., None] / 255.0
    canvas.img[:] = (tc.astype(np.float32) * (1 - m) + tmp.astype(np.float32) * m).astype(np.uint8)
    lm = P.new_mask(canvas)
    P.draw_line(canvas, lm, (ccx, ccy - sh / 2), (ccx, ccy + sh / 2), 8 * (1 - u / 0.35) + 2 if u < 0.35 else 2)
    if u < 0.35:
        P.blend(canvas, lm, (255, 250, 232), 0.85 * (1 - u / 0.35) * fo)


# ============================== 按遥控器 ==============================
@fx("remote_click", layer="front", sfx="click", check=lambda p: P.need_pos(p) + ([P.bad_color(p.get("color"))] if P.bad_color(p.get("color")) else []))
def remote_click(canvas, t, params, at):
    u = t - at
    if u < 0 or u > 0.7:
        return
    px, py = params["pos"]
    col = P.rgb(params.get("color"), P.RED)
    # 涟漪：两圈，由小变大变淡
    for i, delay in enumerate((0.0, 0.12)):
        a = u - delay
        if 0 <= a < 0.5:
            m = P.new_mask(canvas)
            e = anim.out_cubic(a / 0.5)
            P.circle(canvas, m, (px, py), 26 + 120 * e, 255, max(3, 12 * (1 - e)))
            P.blend(canvas, m, col if i == 0 else P.CREAM, 0.9 * (1 - e))
    # 按钮被按下去：一个小圆先压扁再弹起
    press = 1.0 - 0.28 * math.sin(math.pi * min(u / 0.16, 1.0)) if u < 0.16 else 1.0 + 0.10 * math.exp(-(u - 0.16) * 12) * math.cos(2 * math.pi * 3 * (u - 0.16))
    m = P.new_mask(canvas)
    P.circle(canvas, m, (px, py), 22 * press)
    P.blend(canvas, m, P.WHITE, 0.9 * (1 - anim.smooth((u - 0.3) / 0.3)))
    # 八道短线，往外一蹦
    a = u
    if a < 0.4:
        lm = P.new_mask(canvas)
        e = anim.out_cubic(a / 0.4)
        for i in range(8):
            ang = 2 * math.pi * i / 8 + 0.2
            r0, r1 = 60 + 80 * e, 96 + 110 * e
            P.draw_line(canvas, lm, (px + r0 * math.cos(ang), py + r0 * math.sin(ang)), (px + r1 * math.cos(ang), py + r1 * math.sin(ang)), 9 * (1 - e) + 3)
        P.blend(canvas, lm, col, 1.0 - e)


# ============================== 想象泡泡 ==============================
def _bcheck(p):
    errs = P.need_pos(p) if "pos" in p else []
    if p.get("text") is not None:
        if not isinstance(p["text"], str) or not 1 <= len(p["text"]) <= 8:
            errs.append("bubble 的 text 要写 1–8 个字")
        else:
            errs += P.glyph_errors(p["text"])
    return errs


def _bassets(p):
    return [CLOUD, CLOUD_LAY] + ([p["img"]] if p.get("img") else [])


@fx("bubble", layer="front", sfx="bubble_pop", assets=_bassets, check=_bcheck)
def bubble(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lay = _lay(canvas, CLOUD_LAY)
    W = float(params.get("w", 820))
    flip = bool(params.get("flip", False))
    px, py = params.get("pos", [C.W / 2, 620])
    k = W / 1357
    fo = P.fade_out(u, dur, 0.3)
    x0, y0, x1, y1 = lay["content"]
    cw, ch = (x1 - x0) * k, (y1 - y0) * k

    def build():
        base = P.fit_width(P.load_pil(canvas, CLOUD), W)
        if params.get("img"):
            pic = _fit(P.load_pil(canvas, params["img"]), cw * 0.96, ch * 0.96)
            base.alpha_composite(pic, (int(round((x0 + x1) / 2 * k - pic.width / 2)), int(round((y0 + y1) / 2 * k - pic.height / 2))))
        elif params.get("text"):
            t_ = P.text_image(params["text"], "title", int(min(ch * 0.7, cw / len(params["text"]) * 0.9)), P.INK)
            base.alpha_composite(t_, (int(round((x0 + x1) / 2 * k - t_.width / 2)), int(round((y0 + y1) / 2 * k - t_.height / 2))))
        if flip:
            base = base.transpose(P.Image.FLIP_LEFT_RIGHT)
        return P.add_shadow(base, (-6 if flip else 6, 10), 9, 0.32)
    sp = P.sprite(canvas, ("bubble", params.get("img"), params.get("text"), W, flip), build)
    s, sx, sy = P.pop_xy(u, 2.0, 6.0, 0.08)
    ax = 0.96 if flip else 0.04                                                # 从尾巴那一头鼓出来
    canvas.blit(sp, px, py, scale=max(s, 0.0), sx=sx, sy=sy, rot=(-2.0 if not flip else 2.0) * math.exp(-4 * u) * math.cos(2 * math.pi * 2.2 * u),
                alpha=min(1.0, u / 0.06) * fo, anchor=(ax, 0.92), depth=0)


# ============================== 书页边 ==============================
@fx("page_edge", layer="front", sfx="page_slide", assets=lambda p: [PAGE], check=lambda p: [])
def page_edge(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.45):
        return
    W = float(params.get("w", 1180))
    y_top = float(params.get("y", 1240))
    sp = P.sprite(canvas, ("pageedge", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, PAGE), W), (0, -6), 10, 0.3, 24))
    H = sp.hd
    y_final = y_top + H / 2
    up = P.spring(u, 1.7, 6.0) if u < 1.5 else 1.0
    y = y_final + (C.H + 100 - y_final) * (1 - min(up, 1.12))
    if dur is not None and u > dur:
        y = y_final + (C.H + 200 - y_final) * anim.in_cubic((u - dur) / 0.45)
    canvas.blit(sp, C.W / 2, y, alpha=min(1.0, u / 0.05), depth=0)
    # 书页下面接一块纸色，一直铺到画面底边（书页图本身只有上半截）
    y_bot = y + sp.hd / 2 - 36
    if y_bot < C.H:
        h_, w_ = sp.arr.shape[:2]
        band = sp.arr[int(h_ * 0.60):int(h_ * 0.72), int(w_ * 0.25):int(w_ * 0.75)].reshape(-1, 4)
        band = band[band[:, 3] > 250]
        col = np.median(band[:, :3], axis=0) if len(band) else np.array([190, 215, 240])
        m = P.new_mask(canvas)
        m[int(round(y_bot * canvas.S)):, :] = 255
        P.blend(canvas, m, (int(col[2]), int(col[1]), int(col[0])), min(1.0, u / 0.05))
