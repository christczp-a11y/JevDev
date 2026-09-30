"""贴纸弹出（带弹簧过冲、轻微挤压、停稳后一直微微晃）。也是写新特效的模板：照这个文件的结构抄。

分镜表里：
  {"type": "sticker", "name": "question", "pos": [800, 520], "at": {"line": 1, "word": "给"}}      图片贴纸 = video/motion/stickers/question.png
  {"type": "sticker", "text": "咚", "pos": [300, 700], "at": {...}, "size": 180, "color": "#c8372d"}   文字贴纸（临时的拟声字），ZCOOL KuaiLe 厚纸剪字 + 白纸边
可选：size（图片 = 屏幕高度，文字 = 字号，默认 200）、rot（角度，默认 0）、flip（水平翻转）、dur（停留几秒，默认到镜头结束）、
      depth（视差，默认 1 = 贴在画上跟着镜头走；0 = 钉在屏幕上）、sfx（音效名，默认 pop；写 null 静音）。
挂在人物身上：
  {"type": "sticker", "name": "anger", "follow": "zb", "attach": "head", "at": {...}}
  {"type": "sticker", "name": "sweat", "follow": "zb", "offset": [120, -700], "at": {...}}
  follow  人物的 id（写在这个镜头的 actors 里）：贴纸跟着这个人物动（出场、小弹跳、说话起伏、呼吸、补间、镜头视差都跟），人物被 `flip` 或者翻身（sx 变负）时，贴纸的位置也跟着镜像过去（贴纸图案本身不翻，字不会反）；
  offset  [dx, dy]：贴纸中心离人物**脚底中点**的位置（设计像素，人物原大小时；dy 往上是负数）；人物放大 / 缩小贴纸位置按比例跟；
  attach  不写 offset 时用：`head`（头顶偏朝向那一侧）；
  人物还没出场（透明 / 缩成 0）时贴纸不画。pos 在写了 follow 以后不用写。
撕掉：
  "exit": "tear"（要写 dur）：到 dur 那一刻贴纸从中间撕成两半（撕口是毛边，带纸纤维的白边），两半往两边翻着落下、渐隐（0.6 秒），音效 `tear` 在撕的那一刻响（出片前 check 自动加进镜头的 sfx 表）。
系列贴纸（video/motion/stickers/）：question 问号、question3 三个问号、exclaim 感叹号、bulb 灯泡、sweat 汗滴、anger 怒气、star 闪光星星、
  star_eyes 星星眼、heart 小心心、dong「咚」、pa「啪」、sou「嗖」。
"""
import math

import numpy as np

from engine import anim
from engine.consts import MOTION
from fx import _paper as P
from fx import fx

STICKERS = MOTION / "stickers"
OUT = 0.22
TEAR = 0.6


def names():
    return sorted(f.stem for f in STICKERS.glob("*.png"))


def _assets(p):
    return [STICKERS / f"{p['name']}.png"] if p.get("name") else []


def _check(p, shot=None):
    follow = p.get("follow")
    errs = [] if follow else P.need_pos(p)
    if bool(p.get("name")) == bool(p.get("text")):
        errs.append("sticker 要写 name（图片贴纸）或 text（文字贴纸），二选一")
    if p.get("name") and not (STICKERS / f"{p['name']}.png").exists():
        errs.append(f"没有叫 {p['name']!r} 的贴纸（有：{names()}）")
    errs += P.glyph_errors(p.get("text"))
    if P.bad_color(p.get("color")):
        errs.append(P.bad_color(p.get("color")))
    if follow:
        if shot is not None and follow not in [a.get("id") for a in shot.get("actors", [])]:
            errs.append(f"follow={follow!r}：这个镜头的 actors 里没有 id 是它的人物（有：{[a.get('id') for a in shot.get('actors', [])]}）")
        if "offset" not in p and p.get("attach") != "head":
            errs.append("写了 follow 就要写 offset: [dx, dy]（离人物脚底中点多远）或者 attach: \"head\"")
        if "offset" in p and not (isinstance(p["offset"], (list, tuple)) and len(p["offset"]) == 2):
            errs.append("offset 要写成 [dx, dy]")
    ex = p.get("exit")
    if ex not in (None, "tear"):
        errs.append("exit 目前只有 \"tear\"（撕成两半落下）")
    if ex == "tear":
        if p.get("dur") is None:
            errs.append("exit: \"tear\" 要写 dur（贴纸停留几秒，然后撕掉）")
        elif not errs and p.get("sfx", "x") is not None:
            P.add_sfx(shot, p.get("at"), float(p["dur"]), "tear")
    return errs


def _build_image(canvas, path, size, flip):
    im = P.fit_height(P.load_pil(canvas, path), size)
    if flip:
        im = im.transpose(P.Image.FLIP_LEFT_RIGHT)
    return P.add_shadow(im)


def _tear_pieces(im, seed):
    """把贴纸图沿一条毛边的竖线撕成左右两半：返回 [(PIL 图（裁到自己的外框）, 外框中心离原图中心的偏移 (dx, dy))]。撕口两边各有一圈纸纤维的白边。"""
    import cv2
    arr = np.array(im.convert("RGBA"))
    h, w = arr.shape[:2]
    rng = np.random.default_rng(seed)
    n1 = cv2.GaussianBlur(rng.standard_normal(h).astype(np.float32)[None, :], (0, 0), max(h / 14.0, 2.0))[0]
    n2 = cv2.GaussianBlur(rng.standard_normal(h).astype(np.float32)[None, :], (0, 0), 1.6)[0]
    cut = w * 0.5 + w * 0.06 * n1 / (n1.std() + 1e-6) + 2.2 * n2 / (n2.std() + 1e-6)
    xs = np.arange(w, dtype=np.float32)[None, :]
    left = xs < cut[:, None]
    dist = np.abs(xs - cut[:, None])
    out = []
    for side in (left, ~left):
        a = arr.copy()
        a[..., 3] = np.where(side, a[..., 3], 0)
        fringe = (dist < 5.0) & side & (arr[..., 3] > 60)
        a[..., :3] = np.where(fringe[..., None], np.array([250, 246, 232], np.uint8), a[..., :3])
        ys, xs_ = np.nonzero(a[..., 3] > 8)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs_.min(), xs_.max() + 1
        piece = P.Image.fromarray(a[y0:y1, x0:x1], "RGBA")
        out.append((piece, ((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2)))
    return out


@fx("sticker", params=['name', 'text', 'pos', 'size', 'rot', 'flip', 'color', 'depth', 'follow', 'offset', 'attach', 'exit'], layer="front", sfx="pop", assets=_assets, check=_check)
def sticker(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    tear = params.get("exit") == "tear"
    span = TEAR + 0.05 if tear else OUT
    if u < 0 or P.gone(u, dur, span):
        return
    size = float(params.get("size", 200))
    flip = bool(params.get("flip", False))
    if params.get("name"):
        path = STICKERS / f"{params['name']}.png"
        key = ("sticker", str(path), size, flip)
        build = lambda: _build_image(canvas, path, size, flip)                       # noqa: E731
    else:
        col = P.rgb(params.get("color"), P.RED)
        key = ("stext", params["text"], size, col)
        build = lambda: P.chunky_text(params["text"], size, col)                     # noqa: E731
    depth = float(params.get("depth", 1.0))
    # ---- 位置：自己的 pos，或者跟着人物 ----
    alpha_f, extra_rot, scale_f = 1.0, 0.0, 1.0
    if params.get("follow"):
        st = canvas.actor_state.get(params["follow"])
        if st is None or st["alpha"] <= 0.01 or st["scale"] <= 0.01:
            return
        if "offset" in params:
            dx, dy = (float(v) for v in params["offset"])
        else:
            dx, dy = 0.22 * st["wd"], -0.98 * st["hd"]                                # attach: head
        mir = (-1.0 if st["flip"] else 1.0) * (1.0 if st["sx"] >= 0 else -1.0)         # 人物翻身（flip / sx 变负）：贴纸的位置跟着镜像
        lx, ly = mir * dx * st["scale"] * abs(st["sx"]), dy * st["scale"] * abs(st["sy"])
        a = math.radians(st["rot"])
        x = st["x"] + lx * math.cos(a) - ly * math.sin(a)
        y = st["y"] + lx * math.sin(a) + ly * math.cos(a)
        depth, alpha_f, extra_rot, scale_f = st["depth"], st["alpha"], st["rot"], st["scale"]
    else:
        x, y = params["pos"]
    base_rot = float(params.get("rot", 0)) + extra_rot
    # ---- 撕掉：两半落下 ----
    if tear and dur is not None and u > dur:
        te = u - dur
        for i, (piece, (ox, oy)) in enumerate(_tear_cached(canvas, key, build)):
            sgn = -1.0 if i == 0 else 1.0
            sp = P.sprite(canvas, ("tearpiece", i) + key, lambda piece=piece: piece)
            px = x + ox + sgn * (55.0 * te + 40.0 * te * te)
            py = y + oy + 750.0 * te * te
            rot = base_rot + sgn * (30.0 * te + 70.0 * te * te)
            al = alpha_f * (1.0 - anim.smooth((te - 0.25) / 0.35))
            canvas.blit(sp, px, py, scale=scale_f, rot=rot, alpha=al, depth=depth)
        return
    sp = P.sprite(canvas, key, build)
    s, sx, sy = P.pop_xy(u)
    a = P.fade_out(u, dur, OUT) if not tear else 1.0
    if dur is not None and u > dur and not tear:
        s *= a
    wob = 2.2 * P.sstep(0.4, 0.8, u) * math.sin(2 * math.pi * u / 1.7)
    canvas.blit(sp, x, y, scale=s * scale_f, sx=sx, sy=sy, rot=base_rot + wob, alpha=min(1.0, a) * alpha_f, depth=depth)


_tear_memo = {}


def _tear_cached(canvas, key, build):
    k = key + (canvas.S,)
    if k not in _tear_memo:
        _tear_memo[k] = _tear_pieces(build(), P.seed_of("tear", *[str(x) for x in key[:3]]))
    return _tear_memo[k]
