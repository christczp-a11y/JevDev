"""空白检测（PITFALLS M7：画面中间一大块淡色空白、分层之间露出白缝）。

背景：远景、中景、地面层层叠上去，层与层之间没接上，就会露出最底下的天空图或纸色，变成一整条平涂的淡色带（0:28 远山和地面之间），
或者两层之间一条笔直的白缝（2:17 山和水之间）。这些地方「淡色 + 几乎没有纹理」，而正常的天空有纸纹、饱和度高，云是小块的圆形。

做法（在 1/4 分辨率上，只看 y 340–1400：标题条以下、字幕区以上）：
  1. 「空白像素」= 饱和度低（< 20/255，淡色）+ 亮度高 + 局部标准差低（平涂）；去掉零星噪点。饱和度是关键：空白带 5–12、淡色雪山 ≈ 28、天空 55–90；
  2. 连通块按 y 范围重叠合并成组（人物挡在中间时，一条空白带会被切成左右几块，合起来还是一条）；
  3. 一组满足下面任何一条就报：
     · 大块：占整幅面积 ≥ 1.2%、碰到左 / 右画面边缘（图层是整幅铺开的，空白一定通到边上；云不会）、高 ≥ 60 像素、宽 ≥ 画面 40%；
     · 细缝：横贯画面（碰到左右两边）、高 8–120 像素、上沿笔直（≥ 90% 的列上沿在同一行 ±8 像素）、面积 ≥ 0.3%。
阈值在 consts.py（BLANK_*），用 tj01 成片标定。detect() 输入任何比例的 BGR 画面，返回设计坐标（1080×1920）里的位置。
"""
import cv2
import numpy as np

from . import consts as C

WORK_W, WORK_H = 270, 480
Q = C.W // WORK_W                      # 一个工作像素 = 4 个设计像素


def _loc_std(g, k=5):
    g = g.astype(np.float32)
    m = cv2.blur(g, (k, k))
    m2 = cv2.blur(g * g, (k, k))
    return np.sqrt(np.maximum(m2 - m * m, 0))


def mask_of(img):
    """画面 → (1/4 分辨率的「空白像素」掩码, 用的小图)。只保留 y 340–1400。"""
    small = cv2.resize(img, (WORK_W, WORK_H), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    sd = _loc_std(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    m = ((hsv[..., 1] < C.BLANK_SAT_MAX) & (hsv[..., 2] > C.BLANK_VAL_MIN) & (sd < C.BLANK_STD_MAX)).astype(np.uint8)
    m[:C.BLANK_Y0 // Q] = 0
    m[C.BLANK_Y1 // Q:] = 0
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), small


def detect(img):
    """→ [{"kind": "block" | "seam", "bbox": [x0, y0, x1, y1]（设计坐标）, "area": 占整幅画面的比例, "straight": 上沿笔直度}]"""
    m, _ = mask_of(img)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    comps = [dict(i=i, x0=int(st[i][0]), y0=int(st[i][1]), x1=int(st[i][0] + st[i][2]), y1=int(st[i][1] + st[i][3])) for i in range(1, n) if st[i][4] >= 40]
    comps.sort(key=lambda c: c["y0"])
    groups = []
    for c in comps:
        for g in groups:
            ov = min(c["y1"], g["y1"]) - max(c["y0"], g["y0"])
            if ov >= 0.5 * min(c["y1"] - c["y0"], g["y1"] - g["y0"]):
                g["cs"].append(c)
                g["y0"], g["y1"] = min(g["y0"], c["y0"]), max(g["y1"], c["y1"])
                break
        else:
            groups.append(dict(cs=[c], y0=c["y0"], y1=c["y1"]))
    found = []
    total = C.W * C.H
    for g in groups:
        gm = np.isin(lab, [c["i"] for c in g["cs"]])
        area = int(gm.sum()) * Q * Q
        x0, x1 = min(c["x0"] for c in g["cs"]), max(c["x1"] for c in g["cs"])
        cols = np.flatnonzero(gm.any(0))
        tops = np.array([np.flatnonzero(gm[:, c])[0] for c in cols])
        mode = int(np.argmax(np.convolve(np.bincount(tops), np.ones(5), "same")))
        straight = float((np.abs(tops - mode) <= 2).mean())
        edge_l, edge_r = x0 * Q <= 0.02 * C.W, x1 * Q >= 0.98 * C.W
        h_px, w_px = (g["y1"] - g["y0"]) * Q, (x1 - x0) * Q
        kind = None
        if area >= C.BLANK_BLOCK_AREA * total and (edge_l or edge_r) and h_px >= C.BLANK_BLOCK_H and w_px >= C.BLANK_BLOCK_W * C.W:
            kind = "block"
        elif area >= C.BLANK_SEAM_AREA * total and edge_l and edge_r and C.BLANK_SEAM_H[0] <= h_px <= C.BLANK_SEAM_H[1] and straight >= C.BLANK_SEAM_STRAIGHT:
            kind = "seam"
        if kind:
            found.append({"kind": kind, "bbox": [x0 * Q, g["y0"] * Q, x1 * Q, g["y1"] * Q], "area": round(area / total, 4), "straight": round(straight, 2)})
    return found
