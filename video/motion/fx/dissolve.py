"""示例转场：交叉淡化（前一镜淡出、后一镜淡入）。也是写新转场的模板。

转场函数：fn(a, b, p, params, canvas) -> ndarray
  a：前一镜这一帧，b：后一镜这一帧（BGR uint8，形状 (canvas.h, canvas.w, 3)，画面里没有字幕和标题条：界面在转场之后才加）
  p：0..1 的进度（线性，缓动自己在函数里用）；params：分镜表 "transition" 里的整个字典；canvas：只用它的 .assets / .w / .h / .S / .rng
  返回混好的一帧（不许改 a、b）。转场以切点为中心：前一半是前一镜的收尾，后一半是后一镜的开头，配音时间线不动。
分镜表：本镜「进来」的方式写在本镜里："transition": "dissolve" 或 {"type": "dissolve", "dur": 0.5}；不写 = 硬切（cut）。
"""
import cv2

from engine import anim
from fx import transition


@transition("dissolve", params=[], dur=0.4)
def dissolve(a, b, p, params, canvas):
    e = anim.smooth(p)
    return cv2.addWeighted(a, 1.0 - e, b, e, 0)
