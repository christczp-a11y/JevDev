"""解说台和想象泡泡：司马光坐在书房的解说台后面讲故事（书房后墙 sets/study/wall.png + 书桌 sets/study/desk.png + 纸屏幕 + 司马光高清半身 chars/sgm_hi_remote.png），
按一下遥控器，画面切到故事里（用转场 tv_switch）。想象泡泡是人物头上的思考云，里面放古今对照的小画。书页边是「考你」时司马光从书页后面探出来用的。

  {"type": "screen", "img": "props/screen_cup_before.png", "pos": [540, 700], "w": 860, "at": {...}}      纸屏幕：木框立在书桌上，屏幕里的画「展开」出现；
        后面再写一个 screen（同一个 pos）就是换画面（新画从中间往两边展开盖住旧的）；img 可以不写（空白纸屏）；w 木框显示宽度（默认 860，原图 1278）；dur
        屏幕纸面的位置和大小、木框原图尺寸都读 props/screen_frame.layout.json（"size"、"screen"）：换框图只改那个 json，代码不用动；
        放进去的画一律「铺满裁边」（cover）：按纸面的长宽比放大到刚好盖满、居中裁掉多出来的，四周不露到框外、也不留空边（不管画是 4:3、1.42 还是别的比例）
  {"type": "remote_click", "pos": [700, 900], "at": {...}}                                                  按遥控器：按钮处一圈涟漪 + 几道短线 + 「叮」的一声；pos 是按钮的屏幕位置；color（默认朱红）
  {"type": "bubble", "img": "props/bubble_nickname.png", "pos": [330, 1040], "at": {...}}                    想象泡泡（props/bubble_cloud.png）：**pos 是尾巴尖，要点在说话人的头顶旁边**，泡泡从那里往上、往另一边「鼓」出来；
        泡泡会自动缩小、夹进安全区（y 360–1400、x 80–1000，尾巴尖不动）；放不下（宽 < 460）出片前报错；
        crop [x0,y0,x1,y1]（泡泡里那张画的像素）：只框这一块放进云里（放大看一部分）；crop_to + crop_t（泡泡出来后几秒开始）+ crop_dur（摇多久）：框从 crop 慢慢摇到 crop_to（泡泡里的镜头摇）；
        labels [{"text": "才能", "xy": [ix, iy], "size": 56, "color": "red", "dt": 0.4}]：贴在泡泡里那张画上的字（xy 是画的像素坐标、size 是画的像素字号，跟着泡泡 / 框一起动；字里写 \n 分行）——比如写在画里空白铭牌上；
        img 泡泡里的画（相对 video/assets；缩放到放进云里）；text 不放画、放几个大字（≤ 8 个字）；flip 尾巴放到右下；w 显示宽度的上限（默认 820，原图 1357）；inner_sway 里面的画和泡泡的晃动幅度（默认 1；0 = 不动。泡泡本身轻轻呼吸，里面的画上下浮动 + 轻轻鼓动，不许冻住）；dur
  {"type": "page_edge", "at": {...}}                                                                        书页边（props/page_edge.png）：从画面下面滑上来，盖住司马光的下半截，像他躲在书页后面；
        y 书页上沿的位置（默认 1240）；w 显示宽度（默认 1180，原图 1510）；dur 停留几秒（之后滑下去）；
        peek 探出来的人物半身图（相对 video/assets，如 chars/sgm_hi_remote.png）、peek_h 人高（860）、peek_x 中心 x（540）：人物从书页后面升起来、落下去以前先缩回去，**半身像平切的下沿一直藏在书页后面**；
        不写 peek 就只有书页（人物写在 actors 里的话，要自己保证它的下沿不露出来：出场用画外、书页盖住它）
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


def _cover(im, w, h):
    """铺满裁边：放大到刚好盖满 w×h，居中裁掉多出来的。输出正好 w×h。"""
    w, h = max(1, round(w)), max(1, round(h))
    s = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), P.Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


# ============================== 纸屏幕 ==============================
def _scheck(p):
    return P.need_pos(p) if "pos" in p else []


def _sassets(p):
    return [FRAME, FRAME_LAY] + ([p["img"]] if p.get("img") else [])


@fx("screen", params=['img', 'pos', 'w'], layer="front", sfx="screen_on", assets=_sassets, check=_scheck)
def screen(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lay = _lay(canvas, FRAME_LAY)
    W = float(params.get("w", 860))
    px, py = params.get("pos", [C.W / 2, 700])
    FW, FH = lay["size"]                                                   # 框图原尺寸（layout.json 里读，不写死）
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
        return _cover(P.load_pil(canvas, img), sw, sh)                     # 铺满纸面，不加白边、不留空边
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
@fx("remote_click", params=['pos', 'color'], layer="front", sfx="click", check=lambda p: P.need_pos(p) + ([P.bad_color(p.get("color"))] if P.bad_color(p.get("color")) else []))
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
BUB_AR = 920 / 1357                       # 泡泡图的高 / 宽
BUB_MIN_W = 460                            # 缩到比这还小就不像泡泡了（放不下 → 报错，让人换位置）
SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1 = 80.0, 1000.0, 360.0, 1400.0


def bubble_width(W, px, py, flip):
    """泡泡自动夹进安全区（y 360–1400、x 80–1000）：尾巴尖 (px, py) 固定不动（它要指着说话人的头），泡泡的宽度按能放下的最大值缩小。
    尾巴在左下（flip 时在右下），泡泡从尾巴尖往上、往另一边长出来：尾巴尖离左边（右边）多远、离上边多远，泡泡就最宽多宽。"""
    ax, ay = (0.96 if flip else 0.04), 0.92
    lim = [W, (py - SAFE_Y0) / (ay * BUB_AR), (SAFE_Y1 - py) / ((1 - ay) * BUB_AR)]
    if flip:
        lim += [(px - SAFE_X0) / ax, (SAFE_X1 - px) / (1 - ax)]
    else:
        lim += [(SAFE_X1 - px) / (1 - ax), (px - SAFE_X0) / ax]
    return max(min(lim), 0.0)


def _bcheck(p):
    errs = P.need_pos(p) if "pos" in p else []
    if "pos" in p and not errs:
        w = bubble_width(float(p.get("w", 820)), p["pos"][0], p["pos"][1], bool(p.get("flip", False)))
        if w < BUB_MIN_W:
            errs.append(f"bubble 的尾巴尖 pos={p['pos']} 太靠边 / 太靠上，安全区（y 360–1400、x 80–1000）里最多放下宽 {w:.0f} 的泡泡（要 ≥ {BUB_MIN_W}）："
                        f"pos 往下或往中间挪，或者写 flip 把尾巴换到另一边")
    if p.get("text") is not None:
        if not isinstance(p["text"], str) or not 1 <= len(p["text"]) <= 8:
            errs.append("bubble 的 text 要写 1–8 个字")
        else:
            errs += P.glyph_errors(p["text"])
    return errs


def _bassets(p):
    return [CLOUD, CLOUD_LAY] + ([p["img"]] if p.get("img") else [])


_NP = {}


def _load_np(canvas, path):
    f = canvas.assets.resolve(path)
    k = (str(f), f.stat().st_mtime_ns)
    if k not in _NP:
        from engine.sprites import load_bgra
        _NP[k] = load_bgra(f)
    return _NP[k]


def _crop_rect(params, u):
    c0 = params.get("crop")
    if not c0:
        return None
    c1 = params.get("crop_to")
    if not c1:
        return [float(v) for v in c0]
    e = anim.smooth(anim.clamp((u - float(params.get("crop_t", 0.0))) / max(float(params.get("crop_dur", 1.0)), 1e-3)))
    return [float(a) + (float(b) - float(a)) * e for a, b in zip(c0, c1)]


def _crop_inner(canvas, params, rect, cw, ch):
    """框住的那一块缩放到刚好放进云的内容框：返回 (Sprite, 缩放比 s（画的像素 → 设计像素）, 框中心 (cx, cy)（画的像素）)。"""
    src = _load_np(canvas, params["img"])
    H0, W0 = src.shape[:2]
    x0, y0 = max(int(round(rect[0])), 0), max(int(round(rect[1])), 0)
    x1, y1 = min(int(round(rect[2])), W0), min(int(round(rect[3])), H0)
    rw, rh = max(x1 - x0, 1), max(y1 - y0, 1)
    s = min(cw * 0.96 / rw, ch * 0.96 / rh)
    tw, th = max(1, round(rw * s)), max(1, round(rh * s))
    from engine.sprites import sprite_from_bgra
    px = cv2.resize(src[y0:y1, x0:x1], (tw, th), interpolation=cv2.INTER_AREA)
    # 方方正正的画四个角会戳出云的外面：用一个圆角（超椭圆）软边遮罩收掉四个角（本来就是椭圆的画不受影响）
    yy, xx = np.mgrid[0:th, 0:tw].astype(np.float32)
    r = (np.abs((xx + 0.5 - tw / 2) / (tw / 2)) ** 2.8 + np.abs((yy + 0.5 - th / 2) / (th / 2)) ** 2.8) ** (1 / 2.8)
    edge = np.clip((1.0 - r) * (min(tw, th) / 2) / 3.0, 0.0, 1.0)
    px = px.copy()
    px[..., 3] = (px[..., 3].astype(np.float32) * edge).astype(np.uint8)
    return sprite_from_bgra(px, tw, th, canvas.S), s, ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _bubble_check(p):
    errs = _bcheck(p)
    for k in ("crop", "crop_to"):
        v = p.get(k)
        if v is not None and not (isinstance(v, (list, tuple)) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v) and v[2] > v[0] and v[3] > v[1]):
            errs.append(f"bubble 的 {k} 要写 [x0, y0, x1, y1]（泡泡里那张画的像素，x1 > x0、y1 > y0）")
    if p.get("crop_to") is not None and not p.get("crop"):
        errs.append("写了 crop_to 就要写 crop（起点）")
    if (p.get("crop") or p.get("labels")) and not p.get("img"):
        errs.append("crop / labels 要配 img（泡泡里的画）")
    for lb in p.get("labels") or []:
        if not (isinstance(lb, dict) and isinstance(lb.get("text"), str) and lb["text"].strip() and isinstance(lb.get("xy"), (list, tuple)) and len(lb["xy"]) == 2):
            errs.append("bubble 的 labels 每项要写 {\"text\": ..., \"at\": [x, y], \"size\": 画的像素字号}")
            break
        bad = set(lb) - {"text", "xy", "size", "color", "dt"}
        if bad:
            errs.append(f"labels 里不认识的字段 {sorted(bad)}")
        errs += P.glyph_errors(lb["text"].replace("\n", ""))
        if P.bad_color(lb.get("color")):
            errs.append(P.bad_color(lb.get("color")))
    return errs


@fx("bubble", params=['img', 'text', 'pos', 'w', 'flip', 'inner_sway', 'crop', 'crop_to', 'crop_t', 'crop_dur', 'labels'], layer="front", sfx="bubble_pop", assets=_bassets, check=_bubble_check)
def bubble(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.3):
        return
    lay = _lay(canvas, CLOUD_LAY)
    flip = bool(params.get("flip", False))
    px, py = params.get("pos", [C.W / 2, 620])
    W = float(int(bubble_width(float(params.get("w", 820)), px, py, flip)))          # 自动缩进安全区里；尾巴尖 = pos 不动
    k = W / 1357
    fo = P.fade_out(u, dur, 0.3)
    x0, y0, x1, y1 = lay["content"]
    cw, ch = (x1 - x0) * k, (y1 - y0) * k

    def build_cloud():
        base = P.fit_width(P.load_pil(canvas, CLOUD), W)
        if flip:
            base = base.transpose(P.Image.FLIP_LEFT_RIGHT)
        return P.add_shadow(base, (-6 if flip else 6, 10), 9, 0.32)

    def build_inner():
        if params.get("img"):
            return _fit(P.load_pil(canvas, params["img"]), cw * 0.96, ch * 0.96)
        if params.get("text"):
            return P.text_image(params["text"], "title", int(min(ch * 0.7, cw / len(params["text"]) * 0.9)), P.INK)
        return None
    cloud = P.sprite(canvas, ("bubble_cloud", W, flip), build_cloud)
    rect = _crop_rect(params, u)
    inner_im = None if rect is not None else (build_inner() if (params.get("img") or params.get("text")) else None)
    s, sx, sy = P.pop_xy(u, 2.0, 6.0, 0.08)
    ax = 0.96 if flip else 0.04                                                # 从尾巴那一头鼓出来
    sway = float(params.get("inner_sway", 1.0))                                # 0 = 不动；1 = 默认；泡泡本身轻轻呼吸，里面的画上下浮动 + 轻轻鼓动（不许冻住）
    breath = 1.0 + 0.014 * sway * math.sin(2 * math.pi * u / 2.8)
    rot = (-2.0 if not flip else 2.0) * math.exp(-4 * u) * math.cos(2 * math.pi * 2.2 * u) + 0.8 * sway * math.sin(2 * math.pi * u / 3.4 + 1.0)
    al = min(1.0, u / 0.06) * fo
    canvas.blit(cloud, px, py, scale=max(s, 0.0) * breath, sx=sx, sy=sy, rot=rot, alpha=al, anchor=(ax, 0.92), depth=0)
    if inner_im is None and rect is None:
        return
    pad = 22.0
    cx_in = (x0 + x1) / 2 * k
    if flip:
        cx_in = W - cx_in
    off = (pad + cx_in - ax * cloud.wd, pad + (y0 + y1) / 2 * k - 0.92 * cloud.hd)          # 画的中心离尾巴尖（云的支点）多远，设计像素
    bob = 8.0 * sway * math.sin(2 * math.pi * u / 2.2 + 0.8)
    pulse = 1.0 + 0.022 * sway * math.sin(2 * math.pi * u / 1.9)
    rin = 1.6 * sway * math.sin(2 * math.pi * u / 2.6)
    g = P.Group(px, py, max(s, 0.0) * breath, rot)
    gx, gy = g.pt(off[0] * sx, (off[1] + bob) * sy)
    if rect is not None:
        sp_in, sfit, (rcx, rcy) = _crop_inner(canvas, params, rect, cw, ch)
    else:
        sp_in = P.sprite(canvas, ("bubble_inner", params.get("img"), params.get("text"), W), lambda: inner_im)
        sfit, rcx, rcy = 1.0, 0.0, 0.0
    canvas.blit(sp_in, gx, gy, scale=max(s, 0.0) * breath * pulse, rot=rot + rin, alpha=al, depth=0)
    # 贴在画上的字（铭牌上的字）：位置按画的像素坐标算，跟着泡泡 / 框 / 里面的画一起动
    for lb in params.get("labels") or []:
        d0 = float(lb.get("dt", 0.0))
        if rect is None or u < d0:
            continue
        pop = anim.back_out(anim.clamp((u - d0) / 0.25))
        size = float(lb.get("size", 56)) * sfit
        col = P.rgb(lb.get("color"), P.RED)
        lines = lb["text"].split("\n")
        for li, line in enumerate(lines):
            spl = P.sprite(canvas, ("bubble_label", line, round(size), col), lambda line=line: P.chunky_text(line, max(8, round(size)), col))
            lx = (float(lb["xy"][0]) - rcx) * sfit
            ly = (float(lb["xy"][1]) - rcy) * sfit + (li - (len(lines) - 1) / 2.0) * size * 1.02
            a_ = math.radians(rin)
            rx, ry = lx * math.cos(a_) - ly * math.sin(a_), lx * math.sin(a_) + ly * math.cos(a_)
            lx_, ly_ = g.pt((off[0] + rx * pulse) * sx, (off[1] + bob + ry * pulse) * sy)
            canvas.blit(spl, lx_, ly_, scale=max(s, 0.0) * breath * pulse * max(pop, 0.0), rot=rot + rin, alpha=al, depth=0)


# ============================== 书页边 ==============================
def _pgcheck(p):
    errs = []
    if p.get("peek") and not (isinstance(p["peek"], str) and p["peek"].endswith(".png")):
        errs.append("page_edge 的 peek 要写探出来的人物半身图路径（.png，相对 video/assets）")
    return errs


@fx("page_edge", params=['y', 'w', 'peek', 'peek_h', 'peek_x'], layer="front", sfx="page_slide", assets=lambda p: [PAGE] + ([p["peek"]] if p.get("peek") else []), check=_pgcheck)
def page_edge(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    OUT_DELAY, OUT_DUR = 0.2, 0.45
    if u < 0 or P.gone(u, dur, OUT_DELAY + OUT_DUR + 0.05):
        return
    W = float(params.get("w", 1180))
    y_top = float(params.get("y", 1240))
    sp = P.sprite(canvas, ("pageedge", W), lambda: P.add_shadow(P.fit_width(P.load_pil(canvas, PAGE), W), (0, -6), 10, 0.3, 24))
    H = sp.hd
    y_final = y_top + H / 2
    up = P.spring(u, 1.7, 6.0) if u < 1.5 else 1.0
    y = y_final + (C.H + 100 - y_final) * (1 - min(up, 1.12))
    x_out = 0.0 if dur is None else max(u - dur - OUT_DELAY, 0.0)
    if dur is not None and u > dur + OUT_DELAY:
        y = y_final + (C.H + 200 - y_final) * anim.in_cubic(x_out / OUT_DUR)
    page_top = y - H / 2 + 24                                                   # 书页图的上沿（去掉一圈投影的边）；纸面的上沿是一道弧，比它低 55–79 像素，半身像的下沿在 page_top + 120，比弧最低处还低 40 像素
    # 探出来的人物：先画（在书页后面）。半身像的下沿永远藏在书页下面 120 像素：书页升起来以后人才慢慢升起来，落下去以前人先缩回去，
    # 所以半身像平切的下沿从头到尾不会露出来
    if params.get("peek"):
        ph = float(params.get("peek_h", 860))
        px = float(params.get("peek_x", C.W / 2))
        img = params["peek"]
        bust = P.sprite(canvas, ("peek", img, ph), lambda: P.add_shadow(P.fit_height(P.load_pil(canvas, img), ph), (3, 5), 7, 0.28, 16))
        rise = P.spring(u - 0.3, 2.0, 6.5) if u > 0.3 else 0.0
        rise = min(rise, 1.08)
        if dur is not None and u > dur:
            rise = min(rise, 1.0) * (1 - anim.in_cubic((u - dur) / 0.3))
        bottom = page_top + 120 + (ph + 20) * (1 - rise)
        canvas.blit(bust, px, bottom, anchor=(0.5, 1.0), alpha=max(0.0, min(1.0, (u - 0.06) / 0.05)), depth=0)      # 书页完全不透明以后半身像才画（书页淡入的头几帧盖不住它）
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
