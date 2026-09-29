"""出片时的自动检查：闪烁、静止、响度、有没有人声。结果写进报告 json；render.py 见到任何一项不过就非 0 退出。
闪烁和静止在合成阶段逐帧算（用 1/8 分辨率灰度，几乎不花时间）；响度用 ffmpeg 量成片里的音轨；人声看配音轨道。
"""
import cv2
import numpy as np

from . import consts as C


class FrameMetrics:
    """逐帧收集：平均亮度、和上一帧的平均差。"""

    def __init__(self):
        self.luma, self.diff = [], []
        self._prev = None

    def push(self, bgr):
        small = cv2.resize(bgr, (bgr.shape[1] // 8, bgr.shape[0] // 8), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        self.luma.append(float(g.mean()) / 255.0)
        self.diff.append(0.0 if self._prev is None else float(np.abs(g - self._prev).mean()))
        self._prev = g


def flicker(luma, fps=C.FPS, delta=C.FLASH_DELTA, max_per_sec=C.FLASH_MAX_PER_SEC):
    """任何 1 秒内，相邻两帧平均亮度差 ≥ delta 的次数超过 max_per_sec 就是闪烁。返回事件 [{"t0", "t1", "count"}]（合并相邻窗口）。"""
    L = np.asarray(luma, np.float64)
    jumps = np.flatnonzero(np.abs(np.diff(L)) >= delta) + 1          # 发生突变的帧号
    events, win = [], int(fps)
    for k in range(len(jumps)):
        inside = jumps[(jumps >= jumps[k]) & (jumps < jumps[k] + win)]
        if len(inside) > max_per_sec:
            t0, t1 = jumps[k] / fps, (inside[-1] + 1) / fps
            if events and t0 <= events[-1]["t1"]:
                events[-1]["t1"] = max(events[-1]["t1"], t1)
                events[-1]["count"] = max(events[-1]["count"], len(inside))
            else:
                events.append({"t0": round(t0, 3), "t1": round(t1, 3), "count": int(len(inside))})
    return events


def static(diff, fps=C.FPS, eps=C.STATIC_EPS, max_sec=C.STATIC_MAX_SEC):
    """连续几帧和前一帧几乎一样（平均差 < eps）。静止的时间超过 max_sec 就是问题。返回事件 [{"t0", "t1", "sec"}]。"""
    d = np.asarray(diff, np.float64)
    events, run = [], None
    for i in range(1, len(d) + 1):
        still = i < len(d) and d[i] < eps
        if still and run is None:
            run = i - 1
        if not still and run is not None:
            sec = (i - run) / fps
            if sec > max_sec:
                events.append({"t0": round(run / fps, 3), "t1": round(i / fps, 3), "sec": round(sec, 3)})
            run = None
    return events


def loudness(lufs, peak):
    ok = abs(lufs - C.LUFS_TARGET) <= C.LUFS_TOL and peak <= C.PEAK_MAX_DB
    return {"lufs": round(lufs, 2), "true_peak_db": round(peak, 2), "target": C.LUFS_TARGET, "tol": C.LUFS_TOL, "peak_max": C.PEAK_MAX_DB, "ok": bool(ok)}


def voice(lines, min_ratio=0.2):
    bad = [l for l in lines if l["voiced_ratio"] < min_ratio]
    return {"lines": len(lines), "missing": bad, "ok": not bad}
