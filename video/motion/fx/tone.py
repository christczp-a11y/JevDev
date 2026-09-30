"""调色和闪白。

调色 / 颜色分段：每一段一个主色调（得意 = 金色，密谋 = 蓝色夜晚，从前 = 旧纸黄 + 颗粒，胜利 = 暖色，紧张 = 稍暗 + 暗角，不用血红）。
  镜头级：分镜表镜头里写 "grade": "gold"（引擎自带，整个镜头一个色调）；
  镜头中间换色：{"type": "tone", "tone": "night", "from": "gold", "delay": 1.0, "ramp": 0.9, "at": {...}}
     tone：目标色调 gold / warm / cool / night / memory / tense；
     from：换色以前是什么色调（写了就在 at 到 at+delay 这段先保持 from，然后被新色调扫掉——**镜头本身不要再写 grade**，grade 是盖在特效上面的，会和 tone 叠出灰雾）；
     delay：从 at 起先等几秒再开始换（默认 0）；ramp：新色调从左往右像一道柔和的光扫过去用几秒（默认 0.7，写 0 = 立刻换）；sweep：false = 整幅一起渐变；
     dur：停留几秒（默认到镜头结束）。
  night 是用乘法调的（红绿压暗、蓝保留 + 阴影里补一点蓝），出来是清楚的深蓝夜晚，不是加一层灰蓝雾。

柔和闪白：{"type": "flash", "at": {...}}   0.1 秒（3 帧）的柔和白光，最亮盖 55%（不超过 60%）。重大揭晓才用，一集最多 3–4 次，两次之间隔开 1 秒以上
"""
import math

import cv2
import numpy as np

from engine import anim
from engine.scene import GRADES
from fx import _paper as P
from fx import fx
from sfx import timing as T

# 名字 → (叠色 RGB, 叠色强度, 暗角, 颗粒, 三通道增益 RGB, 三通道补光 RGB)：先乘增益、加补光、再叠色（tint）、再暗角、再颗粒
TONES = {n: (*v, (1.0, 1.0, 1.0), (0, 0, 0)) for n, v in GRADES.items() if n != "normal"}
TONES["night"] = (None, 0.0, 0.30, 0.0, (0.34, 0.50, 0.82), (6, 14, 46))       # 密谋：蓝色夜晚


def _tcheck(p):
    errs = []
    for k in ("tone", "from"):
        if k in p and p[k] not in TONES:
            errs.append(f"{k} 只能是 {sorted(TONES)}（写成 \"{k}\": \"night\"）")
    if "tone" not in p:
        errs.append("tone 要写目标色调，比如 \"tone\": \"night\"")
    return errs


_vig = {}


def _vign(w, h):
    key = (w, h)
    if key not in _vig:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 1.414
        _vig[key] = np.clip((r - 0.45) / 0.55, 0, 1) ** 2
    return _vig[key]


def _apply(img, name, canvas, k=1.0):
    """把色调 name 以强度 k（float 或 (h, w) 数组，0..1）用到 img（float32 BGR）上。"""
    tint, a0, vig, grain, gain, add = TONES[name]
    kk = k if np.ndim(k) == 0 else k[..., None]
    out = img
    if gain != (1.0, 1.0, 1.0) or any(add):
        g = np.array([gain[2], gain[1], gain[0]], np.float32)
        ad = np.array([add[2], add[1], add[0]], np.float32)
        out = out * (1 + (g - 1) * kk) + ad * kk
    if tint:
        tc = np.array([tint[2], tint[1], tint[0]], np.float32)
        out = out * (1 - kk * a0) + tc * kk * a0
    if vig > 0:
        v = _vign(canvas.w, canvas.h)[..., None]
        out = out * (1 - vig * kk * v)
    if grain > 0:
        n = canvas.rng.normal(0.0, grain, (canvas.h // 2, canvas.w // 2, 1)).astype(np.float32)
        n = cv2.resize(n, (canvas.w, canvas.h), interpolation=cv2.INTER_NEAREST)[..., None]
        out = out + n * kk
    return out


@fx("tone", params=['tone', 'from', 'delay', 'ramp', 'sweep'], layer="front", sfx="tone_shift", check=_tcheck)
def tone(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.5):
        return
    to, frm = params["tone"], params.get("from")
    delay, ramp = float(params.get("delay", 0.0)), float(params.get("ramp", 0.7))
    fo = P.fade_out(u, dur, 0.5)
    w, h = canvas.w, canvas.h
    e = 1.0 if ramp <= 0 else anim.smooth((u - delay) / ramp)
    if e >= 1.0:
        k = 1.0
    elif e <= 0.0:
        k = 0.0
    elif params.get("sweep", True):
        edge = 0.55                                               # 光扫过的软边宽度（画面宽度的比例）
        pos = -0.02 + (1.02 + edge) * e                           # 起点在画面左边缘、终点在右边外面一个软边：最后一帧整幅都是 1，没有跳
        x = np.linspace(0, 1, w, dtype=np.float32)
        col = np.clip((pos - x) / edge, 0, 1)
        col = col * col * (3 - 2 * col)
        k = np.tile(col[None, :], (h, 1))
    else:
        k = e
    img = canvas.img.astype(np.float32)
    if frm:                                                       # 换色以前的样子：整幅 from → 被 to 扫掉
        kk = k if np.ndim(k) == 0 else k[..., None]
        img = _apply(img, frm, canvas, 1.0) * (1 - kk) + _apply(img, to, canvas, 1.0) * kk
        if fo < 1.0:
            img = canvas.img.astype(np.float32) * (1 - fo) + img * fo
    else:
        img = _apply(img, to, canvas, k * fo)
    canvas.img[:] = np.clip(img, 0, 255).astype(np.uint8)


@fx("flash", params=[], layer="front", sfx="flash", check=lambda p: [])
def flash(canvas, t, params, at):
    u = t - at
    if u < 0 or u >= T.FLASH_DUR:
        return
    a = 0.55 * math.sin(math.pi * u / T.FLASH_DUR)
    canvas.tint((255, 250, 238), a)
