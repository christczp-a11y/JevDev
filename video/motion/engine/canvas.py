"""画布：一帧画面（BGR uint8）+ 镜头变换 + 贴图。特效插件和引擎共用这一个类。

坐标都是设计坐标（1080×1920，原点左上，y 向下）；画布内部按渲染比例 S（预览 0.5）放大缩小，调用的人不用管。
depth 是视差系数：0 = 钉在屏幕上（界面、字幕），1 = 主体（人物）跟着镜头走，0.1 = 远景几乎不动，1.2 = 前景动得多。
"""
import math

import cv2
import numpy as np

from .consts import H, PAPER, W

CX, CY = W / 2, H / 2
_PAPER_BGR = (PAPER[2], PAPER[1], PAPER[0])


class Canvas:
    def __init__(self, assets, scale, fps, dur, seed=0):
        self.assets = assets            # AssetStore：canvas.assets.image / .text / .sticker
        self.S = scale
        self.w, self.h = round(W * scale), round(H * scale)
        self.fps = fps
        self.dur = dur                  # 本镜头长度（秒）
        self.rng = np.random.default_rng(seed)   # 固定种子：同样输入每帧一样
        self.img = np.empty((self.h, self.w, 3), np.uint8)
        self.zoom, self.px, self.py = 1.0, 0.0, 0.0   # 当前镜头（由引擎每帧设置）
        self.reset()

    def reset(self):
        self.img[:] = _PAPER_BGR

    # ---------- 镜头变换 ----------
    def xform(self, x, y, depth=0.0):
        """世界坐标 (x, y) 在当前镜头下的屏幕位置和放大倍数 → (sx, sy, Z)。depth=0 时原样返回。"""
        Z = 1.0 + (self.zoom - 1.0) * depth
        return CX + Z * (x - CX) - depth * self.px, CY + Z * (y - CY) - depth * self.py, Z

    # ---------- 贴图 ----------
    def blit(self, sp, x, y, scale=1.0, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), depth=0.0, zoom_size=True):
        """把 Sprite 贴到设计坐标 (x, y)：anchor 是图上的锚点比例（人物脚底中点 = (0.5, 1.0)），
        scale = 整体缩放（弹出用），sx / sy = 横竖各自的缩放（挤压用），rot = 顺时针角度，depth = 视差。"""
        if alpha <= 0.0 or scale <= 0.0 or sx == 0.0 or sy == 0.0:
            return
        X, Y, Z = self.xform(x, y, depth)
        if not zoom_size:
            Z = 1.0
        f = scale * Z * self.S / sp.k
        fx, fy = f * sx, f * sy
        a = math.radians(rot)
        c, s = math.cos(a), math.sin(a)
        ah, aw = sp.arr.shape[:2]
        Ax, Ay = anchor[0] * aw, anchor[1] * ah
        Dx, Dy = X * self.S, Y * self.S
        m00, m01, m10, m11 = c * fx, -s * fy, s * fx, c * fy
        tx, ty = Dx - (m00 * Ax + m01 * Ay), Dy - (m10 * Ax + m11 * Ay)
        xs = [tx, tx + m00 * aw, tx + m01 * ah, tx + m00 * aw + m01 * ah]
        ys = [ty, ty + m10 * aw, ty + m11 * ah, ty + m10 * aw + m11 * ah]
        x0, y0 = max(0, math.floor(min(xs)) - 1), max(0, math.floor(min(ys)) - 1)
        x1, y1 = min(self.w, math.ceil(max(xs)) + 1), min(self.h, math.ceil(max(ys)) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        M = np.array([[m00, m01, tx - x0], [m10, m11, ty - y0]], np.float64)
        tile = cv2.warpAffine(sp.arr, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        if alpha < 1.0:
            tile = cv2.multiply(tile, (alpha, alpha, alpha, alpha))
        dst = self.img[y0:y1, x0:x1]
        inv = cv2.cvtColor(255 - tile[..., 3], cv2.COLOR_GRAY2BGR)
        self.img[y0:y1, x0:x1] = cv2.add(cv2.multiply(dst, inv, scale=1 / 255.0), tile[..., :3])

    def tint(self, rgb, alpha):
        """整幅盖一层颜色（调色用）。"""
        if alpha <= 0:
            return
        col = np.empty_like(self.img)
        col[:] = (rgb[2], rgb[1], rgb[0])
        self.img[:] = cv2.addWeighted(self.img, 1.0 - alpha, col, alpha, 0)
