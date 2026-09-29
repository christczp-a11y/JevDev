"""调色和闪白。

调色 / 颜色分段：每一段一个主色调，换段就换色（得意 = 金色，密谋 = 蓝色夜晚，从前 = 旧纸黄 + 颗粒 + 暗角，胜利 = 暖色，紧张 = 稍暗 + 暗角，不用血红）。
  镜头级：分镜表镜头里写 "grade": "gold"（引擎自带，整个镜头一个色调）；
  镜头中间换色：{"type": "tone", "tone": "night", "at": {...}}   新色调从左往右像一道柔和的光扫过去（0.7 秒），扫完保持到镜头结束
     tone：gold / warm / cool / night / memory / tense；ramp 扫过去用多久（默认 0.7，写 0 = 立刻换）；sweep：false = 整幅一起渐变；dur 停留几秒（默认到镜头结束）
  颜色分段对照：得意 gold　密谋 night（cool 是淡一点的蓝）　从前 memory　胜利 warm　紧张 tense

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

TONES = dict(GRADES)
TONES.pop("normal", None)
TONES["night"] = ((36, 56, 116), 0.30, 0.30, 0.0)         # 密谋：蓝色夜晚，比 cool 深


def _tcheck(p):
    if p.get("tone") not in TONES:
        return [f"tone 只能是 {sorted(TONES)}（写成 \"tone\": \"night\"）"]
    return []


_vig = {}


def _vign(w, h):
    key = (w, h)
    if key not in _vig:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 1.414
        _vig[key] = np.clip((r - 0.45) / 0.55, 0, 1) ** 2
    return _vig[key]


@fx("tone", layer="front", sfx="tone_shift", check=_tcheck)
def tone(canvas, t, params, at):
    u = t - at
    dur = params.get("dur")
    if u < 0 or P.gone(u, dur, 0.5):
        return
    tint, a0, vig, grain = TONES[params["tone"]]
    ramp = float(params.get("ramp", 0.7))
    fo = P.fade_out(u, dur, 0.5)
    w, h = canvas.w, canvas.h
    e = 1.0 if ramp <= 0 else anim.smooth(u / ramp)
    if params.get("sweep", True) and ramp > 0 and e < 1.0:
        edge = 0.55                                               # 光扫过的软边宽度（画面宽度的比例）
        pos = -edge + (1 + edge) * e
        x = np.linspace(0, 1, w, dtype=np.float32)
        col = np.clip((pos - x) / edge + 0.0, 0, 1)
        col = col * col * (3 - 2 * col)
        k = np.tile(col[None, :], (h, 1))
    else:
        k = np.full((h, w), e, np.float32)
    k = k * fo
    img = canvas.img.astype(np.float32)
    kk = k[..., None]
    if tint:
        tc = np.array([tint[2], tint[1], tint[0]], np.float32)
        img = img * (1 - kk * a0) + tc * kk * a0
    if vig > 0:
        img = img * (1 - vig * kk * _vign(w, h)[..., None])
    if grain > 0:
        n = canvas.rng.normal(0.0, grain, (h // 2, w // 2, 1)).astype(np.float32)
        n = cv2.resize(n, (w, h), interpolation=cv2.INTER_NEAREST)[..., None]
        img = img + n * kk
    canvas.img[:] = np.clip(img, 0, 255).astype(np.uint8)


@fx("flash", layer="front", sfx="flash", check=lambda p: [])
def flash(canvas, t, params, at):
    u = t - at
    if u < 0 or u >= T.FLASH_DUR:
        return
    a = 0.55 * math.sin(math.pi * u / T.FLASH_DUR)
    canvas.tint((255, 250, 238), a)
