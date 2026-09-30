"""特效包共用的小工具：纸艺质感（纸纹、白纸边、柔和纸影）、缓动、颜色、往画布上盖形状。
文件名以下划线开头，引擎不当插件加载；特效用 `from fx import _paper as P` 引用。

约定：
- 坐标都是设计坐标（1080×1920）；直接往 canvas.img 上画的时候才 × canvas.S。
- 每个 Sprite 只造一次（按 (key, canvas.S) 缓存在本模块里）。造图只依赖参数，不依赖时间，所以缓存是纯函数缓存，不违反「特效没有隐藏状态」。
- 随机数一律用固定种子（zlib.crc32 出来的整数），同样输入每一帧都一样。
"""
import functools
import json
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from engine import anim
from engine import consts as C
from engine.sprites import (AssetError, load_bgra, missing_glyphs, paper_edge, pil_font, runs_for, sprite_from_pil,
                            text_image)

INK, RED, CREAM, WHITE = C.INK, C.RED, C.CREAM, C.WHITE_EDGE
GOLD = (240, 188, 58)
ORANGE = (232, 128, 42)
GREEN = (47, 125, 91)
BLUE = (45, 91, 154)
SKY = (110, 176, 214)
BROWN = (122, 92, 64)
NAMED = {"ink": INK, "red": RED, "cream": CREAM, "white": (255, 255, 255), "gold": GOLD, "orange": ORANGE, "green": GREEN,
         "blue": BLUE, "sky": SKY, "brown": BROWN}


# ============================== 颜色 ==============================
def rgb(v, default=None):
    """'#rrggbb' / [r,g,b] / 名字（ink red cream white gold orange green blue sky brown）→ (r,g,b)。"""
    if v is None:
        return default
    if isinstance(v, str):
        if v in NAMED:
            return NAMED[v]
        h = v.lstrip("#")
        if len(h) == 6:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        raise ValueError(f"颜色 {v!r} 看不懂：写 #rrggbb、[r,g,b] 或 {sorted(NAMED)} 里的名字")
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return tuple(int(x) for x in v)
    raise ValueError(f"颜色 {v!r} 看不懂")


def bad_color(v):
    if v is None:
        return None
    try:
        rgb(v)
    except ValueError as e:
        return str(e)
    return None


@functools.lru_cache(maxsize=1)
def houses():
    return json.loads(C.SERIES_STYLE.read_text(encoding="utf-8")).get("houses", {})


def house_rgb(name):
    """家名 → 家族颜色（video/series_style.json）。"""
    h = houses()
    if name not in h:
        raise ValueError(f"家名 {name!r} 不在 video/series_style.json 里（有：{sorted(h)}）")
    return rgb(h[name]["color"])


def shade(c, k):
    """颜色乘 k（k<1 变暗，k>1 变亮，封顶 255）。"""
    return tuple(int(max(0, min(255, v * k))) for v in c)


def mix(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def glyph_errors(*texts):
    """字体里没有的字 → 错误说明列表（check 用）。"""
    try:
        miss = missing_glyphs("".join(t for t in texts if isinstance(t, str)))
    except AssetError as e:
        return [str(e)]
    return [f"这些字两种字体里都没有：{''.join(miss)}"] if miss else []


def auto_sfx(p, name):
    """给「几下」的特效按下数选音效：分镜表没写 sfx 就补上（写了什么都不动，写 null = 静音）。
    check() 在出片前对每个特效调用一次，音效表在那之后才收集，所以这里补的会被用上。"""
    if "sfx" not in p:
        p["sfx"] = name


def need_pos(p, key="pos"):
    return [] if isinstance(p.get(key), (list, tuple)) and len(p[key]) == 2 else [f"缺 {key}: [x, y]"]


# ============================== 缓动和弹性 ==============================
def spring(t, f=2.4, d=6.5):
    """阻尼弹簧：t（秒）从 0 开始，值从 0 冲过 1 再回来、慢慢停在 1（过冲约 15–20%，两三个来回）。用来做「弹出」。"""
    if t <= 0:
        return 0.0
    return 1.0 - math.exp(-d * t) * math.cos(2 * math.pi * f * t)


def pop_xy(t, f=2.4, d=6.5, squash=0.10):
    """弹出时的 (整体缩放, sx, sy)：带一点挤压拉伸（冲过头的时候竖着长一点，回落的时候横着扁一点）。"""
    s = spring(t, f, d)
    e = s - 1.0
    return max(s, 0.0), 1.0 - squash * e, 1.0 + squash * e


def swing(t, amp=9.0, f=1.5, d=3.2):
    """挂着的东西摆动：角度（度），从 amp 开始衰减。"""
    return amp * math.exp(-d * max(t, 0)) * math.cos(2 * math.pi * f * max(t, 0))


def fade_out(t, dur, span=0.25):
    """t 是特效开始以后的秒数，dur 是停留多久（None = 一直在）；返回 0..1 的不透明度，最后 span 秒淡出。"""
    if dur is None:
        return 1.0
    return 1.0 - anim.smooth((t - dur) / span)


def gone(t, dur, span=0.25):
    return dur is not None and t > dur + span


def sstep(a, b, t):
    """t 从 a 到 b 的 smootherstep（0..1）。"""
    return anim.smooth((t - a) / max(b - a, 1e-6))


def seed_of(*parts):
    return anim.seed_of(*parts)


def rng_for(*parts):
    return np.random.default_rng(seed_of(*parts))


# ============================== 纸纹和纸片 ==============================
@functools.lru_cache(maxsize=32)
def paper_tex(w, h, seed=1):
    """纸纹：均值 0、标准差约 1 的 float32 数组（细颗粒 + 粗起伏 + 短纤维）。"""
    rng = np.random.default_rng(seed)
    fine = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 0.9)
    mid = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 5.0) * 4.0
    fib = np.zeros((h, w), np.float32)
    for _ in range(max(20, w * h // 900)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        a, ln = rng.uniform(0, math.pi), rng.uniform(6, 22)
        cv2.line(fib, (x, y), (int(x + ln * math.cos(a)), int(y + ln * math.sin(a))), float(rng.choice([-1.0, 1.0]) * rng.uniform(0.6, 1.4)), 1, cv2.LINE_AA)
    fib = cv2.GaussianBlur(fib, (0, 0), 0.6)
    t = fine * 0.55 + mid * 0.6 + fib * 1.0
    return ((t - t.mean()) / (t.std() + 1e-6)).astype(np.float32)


def shape_mask(w, h, radius=28, ss=2):
    """圆角矩形的抗锯齿遮罩（uint8，0–255），用 2 倍超采样。"""
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius * ss, fill=255)
    return np.array(im.resize((w, h), Image.LANCZOS))


def deckle(mask, amp=5.0, seed=3, scale=9.0):
    """把遮罩的边变成手撕纸的不规则边：距离场加噪声再阈值。"""
    h, w = mask.shape
    d = cv2.distanceTransform((mask > 127).astype(np.uint8), cv2.DIST_L2, 3)
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), scale) * scale * 0.75
    n2 = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 2.0) * 2.0
    a = np.clip((d - (amp + n * amp * 0.5 + n2 * 0.6)) * 1.5 + 0.5, 0, 1)
    return (a * 255).astype(np.uint8)


def flat_shape(mask, fill, seed=1, tex=0.05, bevel=True):
    """遮罩 + 颜色 + 纸纹 + 一点点厚度感（上沿亮一线、下沿暗一线）→ PIL RGBA。"""
    h, w = mask.shape
    col = np.empty((h, w, 3), np.float32)
    col[:] = fill
    t = paper_tex(w, h, seed)
    col *= (1.0 + tex * t)[..., None]
    if bevel:
        up = np.roll(mask, 2, axis=0).astype(np.float32)
        hl = np.clip(mask.astype(np.float32) - up, 0, 255) / 255.0        # 上沿一条
        dn = np.roll(mask, -2, axis=0).astype(np.float32)
        sh = np.clip(mask.astype(np.float32) - dn, 0, 255) / 255.0        # 下沿一条
        col += hl[..., None] * 22.0 - sh[..., None] * 26.0
    out = np.dstack([np.clip(col, 0, 255), mask]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def paper_card(w, h, fill=CREAM, radius=28, border=None, bw=5, seed=1, tex=0.045, torn=0.0, stitch=None):
    """一张纸卡（不含外面的白纸边）：圆角矩形，可选撕边、彩色细边、缝线虚线。"""
    mask = shape_mask(w, h, radius)
    if torn:
        mask = deckle(mask, torn, seed + 7)
    im = flat_shape(mask, fill, seed, tex)
    if border is not None:
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((bw // 2, bw // 2, w - 1 - bw // 2, h - 1 - bw // 2), max(radius - bw // 2, 2), outline=tuple(border) + (255,), width=bw)
    if stitch is not None:
        d = ImageDraw.Draw(im)
        inset = (bw if border is not None else 0) + 12
        x0, y0, x1, y1 = inset, inset, w - 1 - inset, h - 1 - inset
        col = tuple(stitch) + (230,)
        for x in range(x0 + radius, x1 - radius, 22):
            d.line((x, y0, x + 11, y0), fill=col, width=3)
            d.line((x, y1, x + 11, y1), fill=col, width=3)
        for y in range(y0 + radius, y1 - radius, 22):
            d.line((x0, y, x0, y + 11), fill=col, width=3)
            d.line((x1, y, x1, y + 11), fill=col, width=3)
    return im


def edged(im, edge=9, shadow=True):
    """白纸边 + 柔和纸影（engine.sprites.paper_edge）。返回大一圈的 PIL 图。"""
    return paper_edge(im, edge, shadow)


def add_shadow(im, off=(5, 8), blur=7, alpha=0.32, pad=22):
    """只加纸影（图自己已经有白纸边时用，比如 Codex 画的贴纸和卡片）。"""
    big = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = np.zeros((big.height, big.width), np.uint8)
    a[pad:pad + im.height, pad:pad + im.width] = np.array(im.split()[3])
    a = np.roll(np.roll(a, off[1], 0), off[0], 1)
    a = cv2.GaussianBlur(a, (0, 0), blur)
    sh = np.zeros((big.height, big.width, 4), np.uint8)
    sh[..., :3] = (70, 52, 36)
    sh[..., 3] = (a * alpha).astype(np.uint8)
    out = Image.fromarray(sh, "RGBA")
    out.alpha_composite(im, (pad, pad))
    return out


def load_pil(canvas, path):
    """读素材成 PIL RGBA（路径相对 video/assets，或绝对路径）。"""
    f = canvas.assets.resolve(path)
    return Image.fromarray(cv2.cvtColor(load_bgra(f), cv2.COLOR_BGRA2RGBA), "RGBA")


def fit_height(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), int(h)), Image.LANCZOS)


def fit_width(im, w):
    return im.resize((int(w), max(1, round(im.height * w / im.width))), Image.LANCZOS)


# ---------- 文字 ----------
def put_text(im, cx, cy, text, kind="body", size=48, fill=INK, stroke=0, stroke_fill=(255, 255, 255), max_w=None):
    """把一行字画到 PIL 图 im 上，(cx, cy) 是字的正中心；max_w 给了就缩字号直到放得下。返回实际字号。"""
    size = int(size)
    while True:
        t = text_image(text, kind, size, fill, stroke, stroke_fill)
        if max_w is None or t.width <= max_w or size <= 16:
            break
        size -= 2
    im.alpha_composite(t, (int(round(cx - t.width / 2)), int(round(cy - t.height / 2))))
    return size


def vtext_image(text, kind="title", size=120, fill=INK, gap=0.06, stroke=0, stroke_fill=(255, 255, 255)):
    """竖排：每个字单独画，从上到下叠起来（居中对齐）。"""
    parts = [text_image(ch, kind, size, fill, stroke, stroke_fill) for ch in text]
    step = int(size * (1 + gap))
    w = max(p.width for p in parts)
    h = step * (len(parts) - 1) + max(p.height for p in parts)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i, p in enumerate(parts):
        im.alpha_composite(p, ((w - p.width) // 2, i * step))
    return im


def text_width(text, kind, size):
    return sum(pil_font(k, size).getlength(s) for k, s in runs_for(text, kind))


# ============================== Sprite 缓存 ==============================
_SPR = {}


def sprite(canvas, key, build):
    """按 (key, 渲染比例) 缓存 Sprite。build() 返回设计像素大小的 PIL RGBA 图。key 要包含所有影响画面的参数。"""
    k = (key, canvas.S)
    if k not in _SPR:
        _SPR[k] = sprite_from_pil(build(), canvas.S)
    return _SPR[k]


# ============================== 画到画布上 ==============================
def new_mask(canvas):
    return np.zeros((canvas.h, canvas.w), np.uint8)


def pts_fx(canvas, pts):
    """设计坐标点列 → cv2 用的定点整数（4 位小数，抗锯齿更准）。"""
    S = canvas.S * 16
    return np.array([[round(x * S), round(y * S)] for x, y in pts], np.int32)


def fill_poly(canvas, mask, pts, val=255):
    cv2.fillPoly(mask, [pts_fx(canvas, pts)], val, cv2.LINE_AA, 4)


def draw_line(canvas, mask, p0, p1, width, val=255):
    S = canvas.S
    cv2.line(mask, (round(p0[0] * S * 16), round(p0[1] * S * 16)), (round(p1[0] * S * 16), round(p1[1] * S * 16)), val, max(1, round(width * S)), cv2.LINE_AA, 4)


def circle(canvas, mask, c, r, val=255, thickness=-1):
    S = canvas.S
    cv2.circle(mask, (round(c[0] * S * 16), round(c[1] * S * 16)), round(r * S * 16), val, thickness if thickness < 0 else max(1, round(thickness * S)), cv2.LINE_AA, 4)


def blend(canvas, mask, color, alpha=1.0, bbox=None):
    """把 color 按 mask（uint8）× alpha 盖到画布上。bbox = (x0, y0, x1, y1) 屏幕像素，只处理这一块（省时间）。"""
    if alpha <= 0:
        return
    img = canvas.img
    if bbox is None:
        x0, y0, x1, y1 = 0, 0, canvas.w, canvas.h
    else:
        x0, y0, x1, y1 = (max(0, bbox[0]), max(0, bbox[1]), min(canvas.w, bbox[2]), min(canvas.h, bbox[3]))
        if x1 <= x0 or y1 <= y0:
            return
    m = mask[y0:y1, x0:x1]
    if alpha < 1.0:
        m = (m.astype(np.float32) * alpha).astype(np.uint8)
    if not m.any():
        return
    col = np.empty((y1 - y0, x1 - x0, 3), np.uint8)
    col[:] = (color[2], color[1], color[0])
    m3 = cv2.merge([m, m, m])
    dst = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = cv2.add(cv2.multiply(dst, cv2.subtract(np.full_like(m3, 255), m3), scale=1 / 255.0), cv2.multiply(col, m3, scale=1 / 255.0))


def shift_screen(canvas, dx, dy):
    """整幅画面平移 (dx, dy) 设计像素（砸字的震屏）。边缘用镜像补，不露底。"""
    if abs(dx) < 0.05 and abs(dy) < 0.05:
        return
    M = np.float32([[1, 0, dx * canvas.S], [0, 1, dy * canvas.S]])
    canvas.img[:] = cv2.warpAffine(canvas.img, M, (canvas.w, canvas.h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def star_pts(cx, cy, r_out, r_in, n=5, rot=-90.0):
    pts = []
    for i in range(2 * n):
        a = math.radians(rot + i * 180.0 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def star_image(size, fill=GOLD, edge_col=None, tex_seed=5):
    """圆角五角星（纸剪），带一点高光；PIL RGBA，边长约 size。"""
    ss = 3
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pts = star_pts(S / 2, S / 2 + S * 0.03, S * 0.48, S * 0.215)
    d = ImageDraw.Draw(im)
    d.polygon(pts, fill=tuple(fill) + (255,))
    # 圆角：先模糊再阈值
    a = np.array(im.split()[3]).astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), S * 0.03)
    a = np.clip((a - 127) * 4 + 127, 0, 255).astype(np.uint8)
    mask = np.array(Image.fromarray(a).resize((size, size), Image.LANCZOS))
    out = flat_shape(mask, fill, tex_seed, 0.05)
    # 高光小圆
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse((size * 0.32, size * 0.24, size * 0.44, size * 0.36), fill=(255, 255, 255, 120))
    out.alpha_composite(hl)
    if edge_col is not None:
        m2 = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=max(1, size // 24))
        ring = np.clip(mask.astype(int) - m2.astype(int), 0, 255).astype(np.uint8)
        arr = np.array(out)
        arr[..., :3] = np.where(ring[..., None] > 0, np.array(edge_col, np.uint8), arr[..., :3])
        out = Image.fromarray(arr, "RGBA")
    return out


def tick_image(size, color=GREEN, bg=CREAM):
    """圆形底 + 打勾（纸剪风）。"""
    ss = 3
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, S - 1, S - 1), fill=tuple(color) + (255,))
    w = max(3, int(S * 0.13))
    p = [(S * 0.26, S * 0.54), (S * 0.43, S * 0.70), (S * 0.75, S * 0.32)]
    d.line(p, fill=(255, 255, 255, 255), width=w, joint="curve")
    for q in (p[0], p[2]):
        d.ellipse((q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2), fill=(255, 255, 255, 255))
    return im.resize((size, size), Image.LANCZOS)


def chunky_text(text, size, fill=RED, kind="title", depth=None, edge=None, shadow=True, seed=2, tex=0.06):
    """厚纸剪字（砸字、大标题、拟声字用）：下面叠一层暗色当纸的厚度，上面一层亮色（带纸纹），外面白纸边和纸影。PIL RGBA。"""
    size = int(size)
    depth = depth if depth is not None else max(4, size // 21)
    edge = edge if edge is not None else max(6, size // 16)
    t = text_image(text, kind, size, (255, 255, 255), pad=2)
    pad = depth + 4
    A = np.zeros((t.height + 2 * pad, t.width + 2 * pad), np.uint8)
    A[pad:pad + t.height, pad:pad + t.width] = np.array(t.split()[3])
    ext = A.copy()
    for k in range(1, depth + 1):
        M = np.float32([[1, 0, k * 0.4], [0, 1, k]])
        ext = np.maximum(ext, cv2.warpAffine(A, M, (A.shape[1], A.shape[0])))
    h, w = A.shape
    col = np.empty((h, w, 3), np.float32)
    col[:] = shade(fill, 0.60)
    top = np.empty((h, w, 3), np.float32)
    top[:] = fill
    top *= (1.0 + tex * paper_tex(w, h, seed))[..., None]
    a3 = (A.astype(np.float32) / 255.0)[..., None]
    col = col * (1 - a3) + top * a3
    out = Image.fromarray(np.dstack([np.clip(col, 0, 255), np.maximum(A, ext)]).astype(np.uint8), "RGBA")
    return paper_edge(out, edge, shadow)


class Group:
    """一组东西一起动（卡片和卡片上的字、图标）：以 (cx, cy) 为中心，缩放 g、顺时针转 rot 度、再平移。
    pt(lx, ly) 把卡片自己坐标系里（原点在卡片中心，单位 = 设计像素）的点变成屏幕设计坐标。"""

    def __init__(self, cx, cy, g=1.0, rot=0.0):
        self.cx, self.cy, self.g, self.rot = cx, cy, g, rot
        a = math.radians(rot)
        self.c, self.s = math.cos(a), math.sin(a)

    def pt(self, lx, ly):
        return self.cx + self.g * (lx * self.c - ly * self.s), self.cy + self.g * (lx * self.s + ly * self.c)


def draw_group(canvas, sp, grp, lx, ly, sc=1.0, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), depth=0.0):
    x, y = grp.pt(lx, ly)
    canvas.blit(sp, x, y, scale=grp.g * sc, sx=sx, sy=sy, rot=grp.rot + rot, alpha=alpha, anchor=anchor, depth=depth)


# ============================== 人物框（check(params, shot) 和氛围避脸用） ==============================
FACE_FRAC = (0.25, 0.75, 0.0, 0.40)        # 脸在人物图里的位置：x0, x1, y0, y1（占图宽 / 图高的比例，同 storyboard_check）


@functools.lru_cache(maxsize=256)
def _img_size(path):
    with Image.open(path) as im:
        return im.size


def actor_boxes(shot):
    """一个镜头里所有人物的框：[{"id", "body": (x0, y0, x1, y1), "face": (...)}]（设计坐标；按分镜表里的 pos / h 和图片宽高比算，不含出场动画）。
    图片找不到（本集专用素材）的人物跳过。shot = 分镜表里的一个镜头字典（check(params, shot) 拿到的就是它）。"""
    out = []
    for a in (shot or {}).get("actors", []):
        try:
            sw, sh = _img_size(str(C.ASSETS / a["img"]))
            x, y = a["pos"]
            H = float(a["h"])
        except (KeyError, TypeError, ValueError, OSError):
            continue
        W = H * sw / sh
        x0, y0 = x - W / 2, y - H
        f = FACE_FRAC
        out.append({"id": a.get("id", a["img"]), "body": (x0, y0, x0 + W, y),
                    "face": (x0 + f[0] * W, y0 + f[2] * H, x0 + f[1] * W, y0 + f[3] * H)})
    return out


def boxes_overlap(a, b, margin=0.0):
    return a[0] < b[2] - margin and b[0] < a[2] - margin and a[1] < b[3] - margin and b[1] < a[3] - margin


def face_avoid(shot, pad=40):
    """氛围粒子要避开的框：每个人物的脸框，四周多留 pad 像素。check 里 params["_avoid"] = face_avoid(shot)。"""
    return [[round(b["face"][0] - pad), round(b["face"][1] - pad), round(b["face"][2] + pad), round(b["face"][3] + pad)] for b in actor_boxes(shot)]


def avoid_alpha(boxes, x, y, soft=70.0):
    """点 (x, y) 离最近的避让框有多远 → 0..1 的不透明度系数：在框里 0，离开 soft 像素以上 1，中间平滑（粒子飘过脸边上会渐隐，不会突然消失）。"""
    k = 1.0
    for x0, y0, x1, y1 in boxes or ():
        dx = max(x0 - x, 0.0, x - x1)
        dy = max(y0 - y, 0.0, y - y1)
        d = math.hypot(dx, dy)
        k = min(k, anim.smooth(d / soft))
    return k


def add_sfx(shot, at, dt, name):
    """往镜头的 sfx 表里加一条：锚点 at（分镜表里这个特效的 at）往后 dt 秒响 name。已经有同样的一条就不重复加（check 在主进程和渲染进程各跑一遍）。"""
    if shot is None:
        return
    a = dict(at) if isinstance(at, dict) else {}
    a["dt"] = round(float(a.get("dt", 0.0)) + dt, 4)
    entry = {"name": name, "at": a}
    lst = shot.setdefault("sfx", [])
    if entry not in lst:
        lst.append(entry)
