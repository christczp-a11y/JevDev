"""一个镜头的画面：把分镜表里的一个 shot 变成「给一个时刻，画出一帧」。
只画场景（背景 → 背景层特效 → 人物 → 前景 → 前台特效 → 调色 → 甩镜模糊）。字幕、标题条、水印在合成阶段统一加（ui.py），转场也在那之后。

解析（分镜表 → 元素）和画图分开：解析很便宜，出片前主进程对每个镜头都解析一遍，把所有错一次报完；图在第一次画的时候才读。
"""
import math

import cv2
import numpy as np
from PIL import Image

from . import anim
from . import consts as C
from .anim import Camera, Tracks
from .canvas import Canvas


class SceneError(ValueError):
    pass


LAYER_KEYS = {"img", "depth", "pos", "anchor", "w", "h", "scale", "flip", "blur", "alpha", "repeat", "sway", "anim", "enter", "note"}
ACTOR_KEYS = {"id", "who", "img", "pos", "h", "flip", "depth", "enter", "acts", "anim", "alpha", "note"}
SHOT_KEYS = {"id", "from", "to", "size", "bg", "fg", "actors", "camera", "fx", "sfx", "grade", "transition", "note", "notes"}
ENTERS = ("pop", "slide_left", "slide_right", "drop", "flip", "fade")
ACT_DO = ("bounce", "jump", "nod", "shake", "wobble", "pop", "exit")
ENTER_SFX = {"pop": "pop"}      # 人物出场自动配的音效（enter 里写 "sfx": null 关掉）

GRADES = {   # 名字 → (叠色 RGB, 叠色强度, 暗角, 颗粒)
    "normal": (None, 0.0, 0.0, 0.0),
    "warm": ((255, 190, 150), 0.16, 0.0, 0.0),          # 得意、暖
    "gold": ((255, 215, 120), 0.14, 0.0, 0.0),          # 得意用金色
    "cool": ((120, 140, 170), 0.16, 0.0, 0.0),          # 密谋、夜晚
    "memory": ((222, 196, 140), 0.28, 0.25, 6.0),       # 回忆：旧纸黄 + 颗粒 + 暗角
    "tense": ((40, 40, 60), 0.14, 0.35, 0.0),           # 紧张：稍暗、暗角，不用血红
}


def _header_size(path):
    with Image.open(path) as im:
        return im.size


def _unknown(spec, allowed, where):
    bad = set(spec) - allowed
    if bad:
        raise SceneError(f"{where}：不认识的字段 {sorted(bad)}（拼错了？可用：{sorted(allowed)}）")


# ============================== 人物小动作 ==============================
def _hop(u, amp):
    dy = -amp * 4 * u * (1 - u)
    if u < 0.25:
        sy = 1 - 0.08 * math.sin(math.pi * u / 0.25)
    elif u < 0.75:
        sy = 1 + 0.05 * math.sin(math.pi * (u - 0.25) / 0.5)
    else:
        sy = 1 - 0.06 * math.sin(math.pi * (u - 0.75) / 0.25)
    return dy, 1 / sy, sy, 0.0, 1.0


ACTS = {   # 名字 → (默认时长, u → (dy, sx, sy, rot, scale))
    "bounce": (C.BOUNCE_DUR, lambda u: _hop(u, C.BOUNCE_AMP)),
    "jump": (0.5, lambda u: _hop(u, 60.0)),
    "nod": (0.5, lambda u: (0.0, 1.0, 1 - 0.04 * math.sin(4 * math.pi * u) * (1 - u), 0.0, 1.0)),
    "shake": (0.5, lambda u: (0.0, 1.0, 1.0, 4.0 * math.sin(6 * math.pi * u) * (1 - u), 1.0)),
    "wobble": (0.8, lambda u: (0.0, 1.0, 1.0, 6.0 * math.sin(5 * math.pi * u) * (1 - u) ** 1.5, 1.0)),
    "pop": (0.3, lambda u: (0.0, 1.0, 1.0, 0.0, 1.0 + 0.12 * math.sin(math.pi * u))),
}


# ============================== 元素（背景层 / 人物 / 前景） ==============================
class Element:
    def __init__(self, spec, kind, scene, idx):
        self.kind, self.spec, self.scene = kind, spec, scene
        self.where = f"镜头 {scene.id} {kind}[{idx}]"
        actor = kind == "actor"
        _unknown(spec, ACTOR_KEYS if actor else LAYER_KEYS, self.where)
        if "img" not in spec:
            raise SceneError(f"{self.where}：缺 img")
        self.img = spec["img"]
        if not (isinstance(spec.get("pos"), list) and len(spec["pos"]) == 2):
            raise SceneError(f"{self.where}：缺 pos: [x, y]（人物 pos 是脚底中点）")
        self.depth = float(spec.get("depth", 1.0))
        self.flip = bool(spec.get("flip", False))
        self.alpha = float(spec.get("alpha", 1.0))
        self.anchor = tuple(spec.get("anchor", (0.5, 1.0) if actor else (0.0, 0.0)))
        sz = {k: spec[k] for k in ("w", "h", "scale") if k in spec}
        if actor:
            if "h" not in spec:
                raise SceneError(f"{self.where}：人物要写 h（屏幕上多高，像素）")
            sz = {"h": spec["h"]}
        elif len(sz) > 1:
            raise SceneError(f"{self.where}：w、h、scale 只能写一个（写了 {sorted(sz)}）")
        elif not sz:
            sz = {"scale": 1.0}                    # 什么都不写 = 原图大小（1 个原图像素 = 1 个设计像素）
        self.size = sz
        self.blur = float(spec.get("blur", 0.0))
        self.repeat = spec.get("repeat")
        if self.repeat not in (None, "x"):
            raise SceneError(f"{self.where}：repeat 只能是 \"x\"")
        self.sway = spec.get("sway")
        if self.sway is not None:
            _unknown(self.sway, {"x", "y", "period", "phase"}, f"{self.where} sway")
        self.who = spec.get("who", spec.get("id")) if actor else None
        self._sp = {}
        # 尺寸（读图片头，不读整张图）
        self.path = scene.store.resolve(self.img)
        sw, sh = _header_size(self.path)
        if "w" in sz:
            self.wd = float(sz["w"])
        elif "h" in sz:
            self.wd = sw * float(sz["h"]) / sh
        else:
            self.wd = sw * float(sz["scale"])
        self.hd = sh * self.wd / sw
        self.upscale = self.wd / sw
        self.tile = 1
        if self.repeat == "x":
            self.tile = 2 * math.ceil(C.W / self.wd) + 1          # 奇数份，原图在正中间；pos 和 anchor 仍然指原图那一份
            self.anchor = ((self.anchor[0] + (self.tile - 1) / 2) / self.tile, self.anchor[1])
        # 可动属性：位置 / 缩放 / 透明度 + 补间 + 出场
        base = dict(x=float(spec["pos"][0]), y=float(spec["pos"][1]), scale=1.0, sx=1.0, sy=1.0, alpha=self.alpha, rot=0.0)
        self.tracks = Tracks(base, spec.get("anim"), scene.rel, self.where)
        self.sfx_events = []
        self._enter(spec.get("enter"), base)
        # 人物：换表情、小动作
        self.swaps = []          # (镜头内时间, 图路径, h)
        self.acts = []           # (镜头内时间, 名字, 时长, 参数)
        if actor:
            for i, a in enumerate(spec.get("acts", [])):
                self._act(a, i)
        self.speech = scene.speech_spans(self.who) if actor and self.who else []
        self.phase = anim.seed_of(spec.get("id", self.img), "breath") % 628 / 100

    # ---------- 出场 ----------
    def _enter(self, e, base):
        if e is None:
            return
        if isinstance(e, str):
            e = {"type": e}
        _unknown(e, {"type", "at", "dur", "sfx"}, f"{self.where} enter")
        typ = e.get("type")
        if typ not in ENTERS:
            raise SceneError(f"{self.where}：出场 {typ!r} 不存在，只有 {list(ENTERS)}")
        at = self.scene.rel(e["at"]) if "at" in e else 0.0
        dur = float(e.get("dur", C.ENTER_DUR[typ]))
        tr, ax, ay = self.tracks, self.anchor[0], self.anchor[1]
        x, y = base["x"], base["y"]
        if typ == "pop":
            tr.base["scale"] = 0.0
            tr.add(at, dur, anim.back_out, scale=1.0)
        elif typ == "slide_left":
            tr.base["x"] = -(1 - ax) * self.wd - 40
            tr.add(at, dur, anim.back_out, x=x, y=y)
        elif typ == "slide_right":
            tr.base["x"] = C.W + ax * self.wd + 40
            tr.add(at, dur, anim.back_out, x=x, y=y)
        elif typ == "drop":
            tr.base["y"] = -(1 - ay) * self.hd - 20
            tr.add(at, dur, anim.bounce_out, x=x, y=y)
        elif typ == "flip":
            tr.base["sx"] = 0.0
            tr.add(at, dur, anim.back_out, sx=1.0)
        elif typ == "fade":
            tr.base["alpha"] = 0.0
            tr.add(at, dur, anim.smooth, alpha=base["alpha"])
        sfx = e.get("sfx", ENTER_SFX.get(typ) if self.kind == "actor" else None)     # 只有人物出场自动配音效；卡片、图层要音效自己写
        if sfx:
            self.sfx_events.append((at, sfx, 0.0))

    # ---------- 表演 ----------
    def _act(self, a, i):
        w = f"{self.where} acts[{i}]"
        _unknown(a, {"at", "do", "swap", "h", "dur", "amp", "bounce", "sfx", "dir"}, w)
        if "at" not in a:
            raise SceneError(f"{w}：缺 at")
        at = self.scene.rel(a["at"])
        if "swap" in a:
            self.scene.store.resolve(a["swap"])
            self.swaps.append((at, a["swap"], float(a.get("h", self.size["h"]))))
            if a.get("bounce", True):
                self.acts.append((at, "bounce", ACTS["bounce"][0], {}))
            sfx = a.get("sfx", C.SWAP_SFX)
            if sfx:
                self.sfx_events.append((at, sfx, 0.0))
            return
        do = a.get("do")
        if do not in ACT_DO:
            raise SceneError(f"{w}：do {do!r} 不存在，只有 {list(ACT_DO)}（换表情写 swap）")
        if do == "exit":
            d = a.get("dir", "left")
            if d not in ("left", "right", "down"):
                raise SceneError(f"{w}：exit 的 dir 只能是 left / right / down")
            dur = float(a.get("dur", 0.4))
            ax, ay = self.anchor
            tx = -(1 - ax) * self.wd - 40 if d == "left" else C.W + ax * self.wd + 40 if d == "right" else None
            if tx is not None:
                self.tracks.add(at, dur, anim.in_cubic, x=tx, y=self.tracks.base["y"])
            else:
                self.tracks.add(at, dur, anim.in_cubic, x=self.tracks.base["x"], y=C.H + self.hd + 40)
            return
        dur = float(a.get("dur", ACTS[do][0]))
        self.acts.append((at, do, dur, a))

    # ---------- 画 ----------
    def _sprite(self, path, size):
        key = (str(path), tuple(sorted(size.items())))
        if key not in self._sp:
            self._sp[key] = self.scene.store.image(path, flip=self.flip, blur=self.blur, tile_x=self.tile, **size)
        return self._sp[key]

    def draw(self, cv, t, t_abs):
        v = self.tracks.value(t)
        x, y, scale, sx, sy, rot, alpha = v["x"], v["y"], v["scale"], v["sx"], v["sy"], v["rot"], v["alpha"]
        path, size = self.img, self.size
        if self.kind == "actor":
            for at, p, h in self.swaps:
                if t >= at:
                    path, size = p, {"h": h}
            for at, name, dur, a in self.acts:
                u = (t - at) / dur
                if 0 <= u < 1:
                    if name in ("bounce", "jump") and "amp" in a:
                        dy, ax_, ay_, rr, ss = _hop(u, float(a["amp"]))
                    else:
                        dy, ax_, ay_, rr, ss = ACTS[name][1](u)
                    y += dy
                    sx *= ax_
                    sy *= ay_
                    rot += rr
                    scale *= ss
            # 说话的人随句子轻轻起伏（2–4 像素），没说话的人呼吸（高度 ±0.8%）
            env = 0.0
            for s0, s1 in self.speech:
                if s0 - 0.1 <= t_abs <= s1 + 0.1:
                    env = max(env, anim.clamp((t_abs - s0 + 0.1) / 0.1) * anim.clamp((s1 + 0.1 - t_abs) / 0.1))
                    y -= C.SPEAK_BOB_AMP * env * (0.5 - 0.5 * math.cos(2 * math.pi * C.SPEAK_BOB_HZ * (t_abs - s0)))
                    break
            sy *= 1 + C.BREATH_AMP * math.sin(2 * math.pi * t_abs / C.BREATH_PERIOD + self.phase)
        if self.sway:
            s = self.sway
            per = float(s.get("period", 3.7))
            ph = float(s.get("phase", 0.0))
            x += float(s.get("x", 0)) * math.sin(2 * math.pi * t_abs / per + ph)
            y += float(s.get("y", 0)) * math.sin(2 * math.pi * t_abs * 1.35 / per + 1.3 + ph)
        sp = self._sprite(path, size)
        cv.blit(sp, x, y, scale=scale, sx=sx, sy=sy, rot=rot, alpha=alpha, anchor=self.anchor, depth=self.depth)


# ============================== 一个镜头 ==============================
class Scene:
    def __init__(self, spec, tl, t0, dur, store, fx_table):
        """spec = 分镜表里的一个 shot；tl = Timeline；t0 = 镜头第一帧的绝对时间（秒）；dur = 镜头长度（秒）；
        store = AssetStore（只用来找路径，出片时才读图）；fx_table = fx.FX。"""
        self.spec, self.tl, self.t0, self.dur, self.store = spec, tl, t0, dur, store
        self.id = spec.get("id", "?")
        _unknown(spec, SHOT_KEYS, f"镜头 {self.id}")
        self.warnings = []
        self._speech_cache = {}
        self.camera = Camera(spec.get("camera"), dur, self.rel, self.id)
        self.warnings += self.camera.warnings
        self.bg = [Element(s, "bg", self, i) for i, s in enumerate(spec.get("bg", []))]
        self.actors = [Element(s, "actor", self, i) for i, s in enumerate(spec.get("actors", []))]
        self.fg = [Element(s, "fg", self, i) for i, s in enumerate(spec.get("fg", []))]
        for e in self.bg + self.actors + self.fg:
            if e.upscale > C.MAX_UPSCALE + 1e-6:
                self.warnings.append(f"{e.where}：{e.img} 屏幕显示 ÷ 原图 = {e.upscale:.2f}，超过 {C.MAX_UPSCALE}（会发糊，用高清图）")
        self.grade = spec.get("grade", "normal")
        if self.grade not in GRADES:
            raise SceneError(f"镜头 {self.id}：grade {self.grade!r} 不存在，只有 {sorted(GRADES)}")
        self.fx = []       # (at 镜头内秒, 插件, 参数)
        for i, e in enumerate(spec.get("fx", [])):
            w = f"镜头 {self.id} fx[{i}]"
            typ = e.get("type")
            if typ not in fx_table:
                raise SceneError(f"{w}：没有叫 {typ!r} 的特效（已登记：{sorted(fx_table)}）")
            plug = fx_table[typ]
            errs = plug.check(e) if plug.check else []
            if errs:
                raise SceneError(f"{w}：{'；'.join(errs)}")
            at = self.rel(e["at"]) if "at" in e else 0.0
            self.fx.append((at, plug, e))
            if at > dur:
                self.warnings.append(f"{w}：{typ} 开始在镜头结束以后（{at:.2f} > {dur:.2f} 秒），永远不会出现")
        self.sfx = []      # (镜头内秒, 名字, 增益 dB)
        for i, e in enumerate(spec.get("sfx", [])):
            _unknown(e, {"name", "at", "gain"}, f"镜头 {self.id} sfx[{i}]")
            if "name" not in e:
                raise SceneError(f"镜头 {self.id} sfx[{i}]：缺 name")
            self.sfx.append((self.rel(e["at"]) if "at" in e else 0.0, e["name"], float(e.get("gain", 0.0))))

    # 锚点 → 镜头内秒
    def rel(self, anchor, edge="start"):
        return self.tl.resolve(anchor, shot_t0=self.t0, edge=edge) - self.t0

    def speech_spans(self, who):
        """这个镜头范围附近、who 说话的时间段（绝对秒）。"""
        if who not in self._speech_cache:
            lo, hi = self.t0 - 1.0, self.t0 + self.dur + 1.0
            out = []
            for i, ln in enumerate(self.tl.lines):
                if ln["who"] == who and self.tl.is_speech(i):
                    s0, s1 = self.tl.speech_span(i)
                    if s1 >= lo and s0 <= hi:
                        out.append((s0, s1))
            self._speech_cache[who] = out
        return self._speech_cache[who]

    def elements(self):
        return self.bg + self.actors + self.fg

    def asset_paths(self):
        """这个镜头读的所有图（绝对路径）：缓存哈希和「素材在不在」检查用。"""
        out = [e.path for e in self.elements()]
        for a in self.actors:
            out += [self.store.resolve(p) for _, p, _ in a.swaps]
        for _, plug, e in self.fx:
            for p in (plug.assets(e) if plug.assets else []):
                out.append(self.store.resolve(p))
        return out

    def sfx_events(self):
        """这个镜头所有音效 → [(绝对秒, 名字, 增益 dB)]：分镜表 sfx + 特效自带 + 出场 / 换表情自带。"""
        ev = [(self.t0 + at, n, g) for at, n, g in self.sfx]
        for at, plug, e in self.fx:
            name = e["sfx"] if "sfx" in e else plug.sfx
            if name:
                ev.append((self.t0 + at, name, 0.0))
        for el in self.elements():
            ev += [(self.t0 + at, n, g) for at, n, g in el.sfx_events]
        return ev

    # ---------- 画一帧 ----------
    def draw(self, cv: Canvas, t, t_abs):
        tt = max(t, 0.0)
        zoom, px, py, (bx, by) = self.camera.state(tt, t_abs)
        cv.reset()
        cv.zoom, cv.px, cv.py = zoom, px, py
        for e in self.bg:
            e.draw(cv, tt, t_abs)
        self._fx(cv, tt, "back")
        for e in self.actors:
            e.draw(cv, tt, t_abs)
        for e in self.fg:
            e.draw(cv, tt, t_abs)
        self._fx(cv, tt, "front")
        self._grade(cv, t_abs)
        if bx > 1.5 or by > 1.5:                       # 甩镜的运动模糊
            kx, ky = max(1, int(round(bx * cv.S)) | 1), max(1, int(round(by * cv.S)) | 1)
            cv.img[:] = cv2.blur(cv.img, (kx, ky))

    def _fx(self, cv, tt, layer):
        for at, plug, e in self.fx:
            if plug.layer == layer and tt >= at:
                plug.fn(cv, tt, e, at)

    def _grade(self, cv, t_abs):
        tint, a, vig, grain = GRADES[self.grade]
        if tint:
            cv.tint(tint, a)
        if vig > 0:
            cv.img[:] = _vignette(cv, vig)
        if grain > 0:
            rng = np.random.default_rng(int(round(t_abs * C.FPS)) + 977)
            noise = rng.normal(0.0, grain, (cv.h // 2, cv.w // 2, 1)).astype(np.float32)
            noise = cv2.resize(noise, (cv.w, cv.h), interpolation=cv2.INTER_NEAREST)[..., None]
            cv.img[:] = np.clip(cv.img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


_vig_cache = {}


def _vignette(cv, strength):
    key = (cv.w, cv.h, strength)
    if key not in _vig_cache:
        yy, xx = np.mgrid[0:cv.h, 0:cv.w].astype(np.float32)
        r = np.hypot((xx - cv.w / 2) / (cv.w / 2), (yy - cv.h / 2) / (cv.h / 2)) / 1.414
        _vig_cache[key] = (1 - strength * np.clip((r - 0.45) / 0.55, 0, 1) ** 2)[..., None].astype(np.float32)
    return np.clip(cv.img.astype(np.float32) * _vig_cache[key], 0, 255).astype(np.uint8)
