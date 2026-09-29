"""缓动函数、镜头运动（缓推缓拉、摇移、冲击推、震屏、甩镜、呼吸漂移）、图层补间。参数照《节奏和特效》第三节，常量在 consts.py。"""
import math
import zlib

from . import consts as C


# ============================== 缓动 ==============================
def clamp(u, a=0.0, b=1.0):
    return a if u < a else b if u > b else u


def smooth(u):
    """smootherstep：所有镜头运动默认用它，起步和收尾的速度都是 0，不抖。"""
    u = clamp(u)
    return u * u * u * (u * (6 * u - 15) + 10)


def linear(u):
    return clamp(u)


def out_cubic(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def in_cubic(u):
    u = clamp(u)
    return u ** 3


def back_out(u, c=1.70158):
    """带过冲的弹出：先冲过头再回来。"""
    u = clamp(u)
    return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2


def bounce_out(u):
    u = clamp(u)
    n, d = 7.5625, 2.75
    if u < 1 / d:
        return n * u * u
    if u < 2 / d:
        u -= 1.5 / d
        return n * u * u + 0.75
    if u < 2.5 / d:
        u -= 2.25 / d
        return n * u * u + 0.9375
    u -= 2.625 / d
    return n * u * u + 0.984375


EASES = {"smooth": smooth, "linear": linear, "out": out_cubic, "in": in_cubic, "back": back_out, "bounce": bounce_out}


def ease_fn(name, where):
    if name not in EASES:
        raise ValueError(f"{where}：缓动 {name!r} 不存在，只有 {sorted(EASES)}")
    return EASES[name]


def seed_of(*parts):
    """字符串 → 固定的整数种子（zlib.crc32，同样输入永远同一个数）。"""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


# ============================== 镜头 ==============================
CONTINUOUS = ("push", "pull", "pan")
ALIASES = {"move": "pan", "track": "pan"}
MOVES = CONTINUOUS + ("punch", "shake", "whip", "frame")


class Camera:
    """一个镜头的镜头运动。camera 是分镜表里的 [{"move": "push", "amount": 0.07}, ...]；
    resolve(anchor) 把锚点变成镜头内的秒数。没有推 / 拉 / 摇的镜头自动加一个缓推（每镜都要有）。"""

    def __init__(self, moves, dur, resolve, shot_id):
        self.dur = dur
        self.warnings = []
        self.moves = []
        moves = list(moves or [])
        for i, m in enumerate(moves):
            if not isinstance(m, dict) or "move" not in m:
                raise ValueError(f"镜头 {shot_id} camera[{i}]：要写成 {{\"move\": \"push\", ...}}，得到 {m!r}")
            kind = ALIASES.get(m["move"], m["move"])
            if kind not in MOVES:
                raise ValueError(f"镜头 {shot_id} camera[{i}]：不认识的镜头运动 {m['move']!r}，只有 {sorted(MOVES + tuple(ALIASES))}")
            self.moves.append(self._norm(kind, m, i, dur, resolve, shot_id))
        if not any(m["kind"] in CONTINUOUS for m in self.moves):
            self.moves.insert(0, self._norm("push", {"move": "push", "amount": C.DEFAULT_PUSH}, -1, dur, resolve, shot_id))

    def _norm(self, kind, m, i, dur, resolve, shot_id):
        where = f"镜头 {shot_id} camera[{i}]"
        at = resolve(m["at"]) if "at" in m else 0.0
        d = dict(kind=kind, at=at, ease=ease_fn(m.get("ease", "smooth"), where), where=where)
        if kind in CONTINUOUS:
            d["dur"] = float(m.get("dur", max(dur - at, 0.1)))
        if kind in ("push", "pull"):
            d["amount"] = float(m.get("amount", C.DEFAULT_PUSH))
            if not C.PUSH_RANGE[0] <= d["amount"] <= C.PUSH_RANGE[1]:
                self.warnings.append(f"{where}：{kind} 放大 {d['amount']:.0%}，超出 {C.PUSH_RANGE[0]:.0%}–{C.PUSH_RANGE[1]:.0%}")
        elif kind == "pan":
            d["dx"], d["dy"] = float(m.get("dx", 0)), float(m.get("dy", 0))
            peak = 1.875 * math.hypot(d["dx"], d["dy"]) / d["dur"]        # smootherstep 最快时是平均速度的 1.875 倍
            if peak > C.PAN_MAX_FRAC_PER_S * C.W:
                self.warnings.append(f"{where}：摇 / 移最快每秒 {peak:.0f} 像素，超过画面宽度的 {C.PAN_MAX_FRAC_PER_S:.0%}（{C.PAN_MAX_FRAC_PER_S * C.W:.0f}）")
        elif kind == "punch":
            d["amount"] = float(m.get("amount", C.PUNCH_AMOUNT))
            d["keep"] = float(m.get("keep", C.PUNCH_KEEP))
            if not C.PUNCH_RANGE[0] <= d["amount"] <= C.PUNCH_RANGE[1]:
                self.warnings.append(f"{where}：冲击推 {d['amount']:.0%}，超出 {C.PUNCH_RANGE[0]:.0%}–{C.PUNCH_RANGE[1]:.0%}")
        elif kind == "shake":
            d["dur"] = float(m.get("dur", C.SHAKE_DUR))
            d["amp"] = float(m.get("amp", C.SHAKE_AMP))
            if not C.SHAKE_DUR_RANGE[0] <= d["dur"] <= C.SHAKE_DUR_RANGE[1]:
                self.warnings.append(f"{where}：震屏 {d['dur']} 秒，超出 {C.SHAKE_DUR_RANGE[0]}–{C.SHAKE_DUR_RANGE[1]} 秒")
            if d["amp"] > C.SHAKE_AMP_MAX:
                self.warnings.append(f"{where}：震屏振幅 {d['amp']:.0f} 像素，超过画面宽度的 1.5%（{C.SHAKE_AMP_MAX:.1f}），已按上限算")
                d["amp"] = C.SHAKE_AMP_MAX
            rng = seed_of(shot_id, i, "shake")
            d["ph"] = [(rng >> s & 0xFF) / 255 * 2 * math.pi for s in (0, 8, 16, 24)]
        elif kind == "frame":
            d["zoom"], d["dx"], d["dy"] = float(m.get("zoom", 1.0)), float(m.get("dx", 0)), float(m.get("dy", 0))
        elif kind == "whip":
            d["dur"] = float(m.get("dur", C.WHIP_DUR))
            d["dir"] = m.get("dir", "left")
            d["mode"] = m.get("mode", "in")
            if d["dir"] not in ("left", "right", "up", "down") or d["mode"] not in ("in", "out"):
                raise ValueError(f"{where}：甩镜的 dir 只能是 left / right / up / down，mode 只能是 in / out")
            d["dist"] = float(m.get("dist", C.WHIP_DIST * (C.W if d["dir"] in ("left", "right") else C.H)))
        return d

    def _whip(self, m, t):
        # dir 是内容滑动的方向（left = 内容向左滑）；px > 0 = 内容向左走。入镜：内容从反方向滑进来，出镜：朝 dir 滑出去。
        u = clamp((t - m["at"]) / m["dur"])
        sgn = 1 if m["dir"] in ("left", "up") else -1
        if m["mode"] == "in":
            return -sgn * m["dist"] * (1 - out_cubic(u))
        return sgn * m["dist"] * in_cubic(u)

    def state(self, t, t_abs):
        """镜头内时间 t（秒，负数当 0）和整集绝对时间 t_abs（呼吸漂移用）→ (zoom, px, py, (横向模糊, 纵向模糊))，模糊是设计像素。"""
        t = max(t, 0.0)
        zoom, px, py, bx, by = 1.0, 0.0, 0.0, 0.0, 0.0
        for m in self.moves:
            k = m["kind"]
            if k in ("push", "pull"):
                e = m["ease"](clamp((t - m["at"]) / m["dur"]))
                zoom *= 1 + m["amount"] * (e if k == "push" else 1 - e)
            elif k == "pan":
                e = m["ease"](clamp((t - m["at"]) / m["dur"]))
                px += m["dx"] * e
                py += m["dy"] * e
            elif k == "punch":
                tt = t - m["at"]
                a = m["amount"]
                if tt <= 0:
                    z = 0.0
                elif tt < C.PUNCH_IN:
                    z = a * out_cubic(tt / C.PUNCH_IN)
                elif tt < C.PUNCH_IN + C.PUNCH_OUT:
                    z = a * (1 - (1 - m["keep"]) * smooth((tt - C.PUNCH_IN) / C.PUNCH_OUT))
                else:
                    z = a * m["keep"]
                zoom *= 1 + z
            elif k == "shake":
                tt = t - m["at"]
                if 0 <= tt < m["dur"]:
                    env = (1 - tt / m["dur"]) ** 2
                    f1, f2 = C.SHAKE_FREQS
                    ph = m["ph"]
                    n1 = 0.6 * math.sin(2 * math.pi * f1 * tt + ph[0]) + 0.4 * math.sin(2 * math.pi * f2 * tt + ph[1])
                    n2 = 0.6 * math.sin(2 * math.pi * f2 * tt + ph[2]) + 0.4 * math.sin(2 * math.pi * f1 * tt + ph[3])
                    px += m["amp"] * env * n1
                    py += m["amp"] * env * n2
            elif k == "frame":
                zoom *= m["zoom"]
                px += m["dx"]
                py += m["dy"]
            elif k == "whip":
                v0 = self._whip(m, t)
                v1 = self._whip(m, t - 1.0 / C.FPS)
                if m["dir"] in ("left", "right"):
                    px += v0
                    bx = max(bx, abs(v0 - v1) * C.WHIP_BLUR_GAIN)
                else:
                    py += v0
                    by = max(by, abs(v0 - v1) * C.WHIP_BLUR_GAIN)
        # 呼吸漂移：全片统一的慢速正弦，按整集绝对时间算（切镜头不断）
        px += C.DRIFT_AMP * math.sin(2 * math.pi * t_abs / C.DRIFT_PERIOD)
        py += 0.6 * C.DRIFT_AMP * math.sin(2 * math.pi * t_abs / (C.DRIFT_PERIOD * 1.31) + 1.1)
        return zoom, px, py, (bx, by)


# ============================== 图层补间 ==============================
BASE_PROPS = ("x", "y", "scale", "sx", "sy", "alpha", "rot")


class Tracks:
    """一个图层 / 人物的「可动属性」：x y scale sx sy alpha rot。
    anim 是 [{"at": 锚点, "dur": 0.5, "ease": "smooth", "pos": [x, y] | "dpos": [dx, dy], "scale": 1.2, "alpha": 0, "rot": 5, "sx": 1, "sy": 1}]，
    每一段从「这一刻的当前值」补到目标值；按 at 排序依次生效。"""

    def __init__(self, base, anim, resolve, where):
        self.base = dict(base)
        self.tw = []
        for i, a in enumerate(anim or []):
            w = f"{where} anim[{i}]"
            bad = set(a) - {"at", "dur", "ease", "pos", "dpos", "scale", "alpha", "rot", "sx", "sy"}
            if bad:
                raise ValueError(f"{w}：不认识的字段 {sorted(bad)}")
            self.tw.append(dict(at=resolve(a["at"]) if "at" in a else 0.0, dur=float(a.get("dur", 0.4)),
                                ease=ease_fn(a.get("ease", "smooth"), w), spec=a))
        self.tw.sort(key=lambda x: x["at"])

    def add(self, at, dur, ease, **target):
        """代码里直接加一段补间（出场预设用）。target 可以有 x、y、scale、sx、sy、alpha、rot。"""
        spec = {}
        if "x" in target or "y" in target:
            spec["pos"] = (target.pop("x", None), target.pop("y", None))
        spec.update(target)
        self.tw.append(dict(at=at, dur=dur, ease=ease, spec=spec))
        self.tw.sort(key=lambda x: x["at"])

    def value(self, t):
        cur = dict(self.base)
        for tw in self.tw:
            if t < tw["at"]:
                break
            a = tw["spec"]
            target = {}
            if "pos" in a:
                target["x"], target["y"] = float(a["pos"][0]), float(a["pos"][1])
            if "dpos" in a:
                target["x"], target["y"] = cur["x"] + float(a["dpos"][0]), cur["y"] + float(a["dpos"][1])
            for k in ("scale", "alpha", "rot", "sx", "sy"):
                if k in a:
                    target[k] = float(a[k])
            u = (t - tw["at"]) / tw["dur"] if tw["dur"] > 0 else 1.0
            e = 1.0 if u >= 1 else tw["ease"](u)
            for k, v in target.items():
                cur[k] = cur[k] + (v - cur[k]) * e
        return cur
