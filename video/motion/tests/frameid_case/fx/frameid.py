"""测试用的本地特效：把「镜头序号 × 1000 + 镜头内帧号」画成一排 24 个黑白方块（y 345–385，标题条下面）。
截段拼接的测试用它从成片里把每一帧是「第几个镜头的第几帧」读出来，逐帧核对：拼接点不跳帧、不重复帧、不错位。
分镜表：{"type": "frameid", "k": 镜头序号}。方块够大（设计坐标 40 像素），有损编码以后照样能读。"""
import cv2

from fx import fx

BITS, BLOCK, X0, Y0 = 24, 40, 60, 345


@fx("frameid", sfx=None, check=lambda p: [] if "k" in p else ["frameid 缺 k"])
def frameid(canvas, t, params, at):
    v = int(params["k"]) * 1000 + int(round(max(t, 0.0) * canvas.fps))
    S = canvas.S
    for i in range(BITS):
        bit = (v >> (BITS - 1 - i)) & 1
        x = X0 + i * BLOCK
        cv2.rectangle(canvas.img, (int(x * S), int(Y0 * S)), (int((x + BLOCK) * S) - 1, int((Y0 + BLOCK) * S) - 1), (255, 255, 255) if bit else (0, 0, 0), -1)
