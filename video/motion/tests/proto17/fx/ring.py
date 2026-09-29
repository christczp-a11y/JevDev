"""proto17 测试用的本地特效：倒计时圈（考你的倒计时）。演示「直接往 canvas.img 上画」的写法：canvas.S 是渲染比例，坐标用设计坐标 × S。
阶段 B 的「考你」特效会取代它；这里只是为了在 A 阶段还原小样，同时证明分镜表旁边的 fx/ 目录也能放插件。
分镜表：{"type": "ring", "pos": [760, 1130], "at": {...}, "dur": 1.0}"""
import cv2

from engine import anim
from engine.consts import RED
from fx import fx


@fx("ring", sfx=None, check=lambda p: [] if "pos" in p else ["ring 缺 pos"])
def ring(canvas, t, params, at):
    dur = float(params.get("dur", 1.0))
    u = (t - at) / dur
    if u < 0 or u > 1.05:
        return
    S = canvas.S
    cx, cy = int(params["pos"][0] * S), int(params["pos"][1] * S)
    pop = anim.back_out(min(1.0, (t - at) / 0.25))
    r = 75 * S * pop
    cv2.circle(canvas.img, (cx, cy), int(r), (244, 252, 255), -1, cv2.LINE_AA)
    cv2.ellipse(canvas.img, (cx, cy), (int(r * 0.78), int(r * 0.78)), 0, -90, -90 + 360 * (1 - min(u, 1.0)),
                (RED[2], RED[1], RED[0]), max(2, int(16 * S * pop)), cv2.LINE_AA)
