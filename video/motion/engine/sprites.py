"""图和字：素材加载（带缓存）、字体、文字图、纸边贴纸、卡片。

Sprite = 预乘 alpha 的 BGRA 数组 + 设计尺寸（1080×1920 坐标下的宽高）+ 每个设计像素对应多少数组像素（k）。
预览时整个画面缩小一半，Sprite 的数组也跟着按比例缩小，所以图层永远只在「够用的分辨率」上做缩放，不会每帧从原图重采样。
找不到字体、找不到素材一律直接报错，不许退回系统字体（PITFALLS E1）。
"""
import math
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .consts import (ASSETS, CREAM, FONT_BODY, FONT_TITLE, HEADROOM, INK, WHITE_EDGE)


class AssetError(FileNotFoundError):
    pass


# ============================== 字体 ==============================
_FONT_FILES = {"title": FONT_TITLE, "body": FONT_BODY}
_pil_fonts = {}
_cmaps = {}


def font_file(kind):
    if kind not in _FONT_FILES:
        raise AssetError(f"字体只有两种：title（ZCOOL KuaiLe）和 body（Noto Sans SC Bold），没有 {kind!r}")
    p = _FONT_FILES[kind]
    if not p.exists():
        raise AssetError(f"找不到字体 {p}：不许退回系统字体，把字体放进 video/vendor/fonts/（见 README.md）")
    return p


def pil_font(kind, size):
    key = (kind, int(size))
    if key not in _pil_fonts:
        _pil_fonts[key] = ImageFont.truetype(str(font_file(kind)), int(size))
    return _pil_fonts[key]


def _cmap(kind):
    if kind not in _cmaps:
        from fontTools.ttLib import TTFont
        f = TTFont(str(font_file(kind)), lazy=True)
        _cmaps[kind] = set(f.getBestCmap())
        f.close()
    return _cmaps[kind]


def has_glyph(kind, ch):
    return ord(ch) in _cmap(kind)


def missing_glyphs(text):
    """两种字体都没有的字（空白不算）。"""
    return sorted({c for c in text if not c.isspace() and not has_glyph("title", c) and not has_glyph("body", c)})


def runs_for(text, kind):
    """按字体拆成几段：默认用 kind，这个字体没有的字逐字改用另一种（按 cmap 判断，不靠系统字体）。"""
    other = "body" if kind == "title" else "title"
    out = []
    for ch in text:
        k = kind if (ch.isspace() or has_glyph(kind, ch)) else other
        if not ch.isspace() and k == other and not has_glyph(other, ch):
            raise AssetError(f"两种字体里都没有「{ch}」（U+{ord(ch):04X}）：换个字，或者把字体子集补上")
        if out and out[-1][0] == k:
            out[-1][1] += ch
        else:
            out.append([k, ch])
    return out


def text_image(text, kind, size, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0), pad=0):
    """一行字画成 RGBA 的 PIL 图（设计像素，紧贴字的外框 + pad）。"""
    runs = runs_for(text, kind)
    base = pil_font(kind, size)
    asc, desc = base.getmetrics()
    fonts = [(pil_font(k, size), s) for k, s in runs]
    widths = [f.getlength(s) for f, s in fonts]
    w = int(math.ceil(sum(widths))) + 2 * (pad + stroke) + 2
    h = asc + desc + 2 * (pad + stroke)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad + stroke + 1
    for (f, s), wd in zip(fonts, widths):
        d.text((x, pad + stroke + asc), s, font=f, fill=tuple(fill) + (255,), anchor="ls",
               stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
        x += wd
    return im


# ============================== Sprite ==============================
class Sprite:
    __slots__ = ("arr", "wd", "hd", "k", "opaque")

    def __init__(self, arr, wd, hd, k):
        self.arr, self.wd, self.hd, self.k = arr, float(wd), float(hd), float(k)
        self.opaque = bool(arr[..., 3].min() == 255)


def _premultiply(bgra):
    a = bgra[..., 3:4]
    if a.min() == 255:
        return bgra
    a3 = cv2.merge([bgra[..., 3]] * 3)
    out = bgra.copy()
    out[..., :3] = cv2.multiply(bgra[..., :3], a3, scale=1 / 255.0)
    return out


def load_bgra(path):
    """读图成 8 位 BGRA（straight alpha）。cv2.imread 读不了中文路径，所以走 fromfile + imdecode。"""
    data = np.fromfile(str(path), np.uint8)
    im = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise AssetError(f"读不出图片 {path}")
    if im.dtype == np.uint16:
        im = (im >> 8).astype(np.uint8)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    elif im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    return im


def sprite_from_pil(im, S):
    """PIL RGBA 图（设计像素）→ Sprite；预览时按 S 缩小。"""
    arr = cv2.cvtColor(np.array(im.convert("RGBA")), cv2.COLOR_RGBA2BGRA)
    return sprite_from_bgra(arr, im.width, im.height, S)


def sprite_from_bgra(bgra, wd, hd, S):
    arr = _premultiply(bgra)
    if abs(S - 1.0) > 1e-6:
        arr = cv2.resize(arr, (max(1, round(wd * S)), max(1, round(hd * S))), interpolation=cv2.INTER_AREA)
    return Sprite(np.ascontiguousarray(arr), wd, hd, arr.shape[1] / wd)


def paper_edge(im, width=10, shadow=True):
    """给一张 RGBA 图加粗白纸边和柔和的纸片投影（贴纸、砸字用）。返回大一圈的 PIL RGBA 图。"""
    m = width + (16 if shadow else 0) + 2
    big = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m), (0, 0, 0, 0))
    big.alpha_composite(im.convert("RGBA"), (m, m))
    arr = np.array(big)
    alpha = arr[..., 3]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * width + 1, 2 * width + 1))
    edge = cv2.dilate(alpha, k)
    out = np.zeros_like(arr)
    if shadow:
        sh = cv2.GaussianBlur(cv2.dilate(alpha, k), (0, 0), 5)
        sh = np.roll(np.roll(sh, 7, axis=0), 5, axis=1)
        out[..., :3] = (80, 60, 40)
        out[..., 3] = (sh * 0.30).astype(np.uint8)
    white = np.zeros_like(arr)
    white[..., :3] = WHITE_EDGE
    white[..., 3] = edge
    out = _over(out, white)
    out = _over(out, arr)
    return Image.fromarray(out, "RGBA")


def _over(dst, src):
    """straight-alpha RGBA uint8 的 src over dst。"""
    sa = src[..., 3:4].astype(np.float32) / 255
    da = dst[..., 3:4].astype(np.float32) / 255
    oa = sa + da * (1 - sa)
    rgb = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / np.maximum(oa, 1e-6)
    return np.concatenate([rgb, oa * 255], axis=2).round().clip(0, 255).astype(np.uint8)


# ============================== 卡片（字幕、标题条、人名牌通用） ==============================
def rounded_rect(w, h, fill, r=28, border=None, bw=5):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=tuple(fill) + (255,),
                                         outline=tuple(border) + (255,) if border else None, width=bw if border else 0)
    return im


def card_image(lines, kind, size, fg, bg, border=None, padx=46, pady=26, r=30, gap=18, edge=True):
    """多行居中文字的卡片（外面一圈白纸边）。lines 每一项是 str 或 (str, 颜色)。"""
    ts = [text_image(t if isinstance(t, str) else t[0], kind, size, fg if isinstance(t, str) else t[1]) for t in lines]
    w = max(t.width for t in ts) + 2 * padx
    h = sum(t.height for t in ts) + (len(ts) - 1) * gap + 2 * pady
    im = rounded_rect(w, h, bg, r, border, 6)
    y = pady
    for t in ts:
        im.alpha_composite(t, ((w - t.width) // 2, y))
        y += t.height + gap
    if not edge:
        return im
    e = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    ImageDraw.Draw(e).rounded_rectangle((0, 0, w + 15, h + 15), r + 8, fill=WHITE_EDGE + (255,))
    e.alpha_composite(im, (8, 8))
    return e


def subtitle_image(who, text_lines, tag_color, body_size, tag_size=34):
    """字幕卡 + 上方的说话人标签。返回 (PIL 图, 卡片正文中心的 y)。"""
    body = card_image(text_lines, "body", body_size, INK, CREAM, (90, 70, 55), padx=40, pady=24, gap=6)
    tag = card_image([who], "body", tag_size, (255, 255, 255), tag_color, None, padx=22, pady=10, r=18)
    ov = tag.height - 14
    im = Image.new("RGBA", (max(body.width, tag.width + 40), body.height + ov), (0, 0, 0, 0))
    im.alpha_composite(body, ((im.width - body.width) // 2, ov))
    im.alpha_composite(tag, (30, 0))
    return im, ov + body.height / 2


# ============================== 素材仓库 ==============================
class AssetStore:
    """一个进程一份：按（文件、大小、翻转……、预览比例）缓存 Sprite。roots 是找素材的目录（先找系列的，再找分镜表旁边的）。"""

    def __init__(self, scale, roots=None):
        self.S = scale
        self.roots = [ASSETS] + [Path(r) for r in (roots or [])]
        self._cache = {}

    def resolve(self, p):
        p = Path(p)
        if p.is_absolute():
            if p.exists():
                return p
            raise AssetError(f"找不到素材 {p}")
        for r in self.roots:
            if (r / p).exists():
                return r / p
        raise AssetError(f"找不到素材 {p}（找过 {', '.join(str(r) for r in self.roots)}）")

    def image(self, path, w=None, h=None, scale=None, flip=False, blur=0.0, tile_x=1):
        f = self.resolve(path)
        st = f.stat()
        key = (str(f), st.st_mtime_ns, st.st_size, w, h, scale, bool(flip), float(blur), int(tile_x), self.S)
        if key in self._cache:
            return self._cache[key]
        src = load_bgra(f)
        sh, sw = src.shape[:2]
        if w is not None:
            wd = float(w)
        elif h is not None:
            wd = sw * float(h) / sh
        else:
            wd = sw * float(scale if scale is not None else 1.0)
        hd = sh * wd / sw
        k = min(self.S * HEADROOM, sw / wd)
        tw, th = max(1, round(wd * k)), max(1, round(hd * k))
        arr = _premultiply(src)
        if (tw, th) != (sw, sh):
            arr = cv2.resize(arr, (tw, th), interpolation=cv2.INTER_AREA)
        if flip:
            arr = cv2.flip(arr, 1)
        if blur > 0:
            arr = cv2.GaussianBlur(arr, (0, 0), float(blur) * k)
        if tile_x > 1:
            arr = np.tile(arr, (1, int(tile_x), 1))
            wd *= tile_x
        sp = Sprite(np.ascontiguousarray(arr), wd, hd, arr.shape[1] / wd)
        self._cache[key] = sp
        return sp

    def from_pil(self, im):
        return sprite_from_pil(im, self.S)

    def text(self, text, kind="title", size=64, fill=(255, 255, 255), stroke=0, stroke_fill=(0, 0, 0), edge=0, shadow=True):
        """文字 Sprite；edge > 0 加白纸边（贴纸字、砸字的样子）。"""
        key = ("text", text, kind, size, tuple(fill), stroke, tuple(stroke_fill), edge, shadow, self.S)
        if key not in self._cache:
            im = text_image(text, kind, size, fill, stroke, stroke_fill, pad=2)
            if edge > 0:
                im = paper_edge(im, edge, shadow)
            self._cache[key] = self.from_pil(im)
        return self._cache[key]

    def sticker(self, path, height, edge=10, shadow=True):
        """图片贴纸：按屏幕高度缩放，加白纸边和投影。"""
        f = self.resolve(path)
        key = ("sticker", str(f), f.stat().st_mtime_ns, height, edge, shadow, self.S)
        if key not in self._cache:
            src = load_bgra(f)
            wd = src.shape[1] * height / src.shape[0]
            im = Image.fromarray(cv2.cvtColor(cv2.resize(src, (max(1, round(wd)), round(height)), interpolation=cv2.INTER_AREA),
                                              cv2.COLOR_BGRA2RGBA), "RGBA")
            self._cache[key] = self.from_pil(paper_edge(im, edge, shadow) if edge > 0 else im)
        return self._cache[key]


_SAFE = re.compile(r"[^\w\-.]+")


def safe_name(s):
    return _SAFE.sub("_", str(s))
