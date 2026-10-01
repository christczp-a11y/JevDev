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


def detect(img, ui=False):
    """→ [{"kind": "block" | "seam" | "strip", "bbox": [x0, y0, x1, y1]（设计坐标）, "area": 占整幅画面的比例, ……}]
    block / seam 见上；strip = 局部直边平条（detect_strips，下面）。ui=True：画面是带字幕 / 卡片 / 贴纸的成片（blank_scan 用），strip 多排除一类卡片边框。"""
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
    for e in detect_strips(img, ui):
        if not any(_inside(e["bbox"], o["bbox"]) >= 0.5 for o in found):           # 大块 / 细缝已经报过的地方不再报一遍
            found.append(e)
    return found


# ---------- 局部直边露缝（M7 再犯，PITFALLS 待补 19）----------
# 上面的 block / seam 都要碰到画面边缘；改了某一层的 y 以后，相邻层的平直底边从两座山峰之间露出一小条淡色平色（tj02 第 2 版 s68：中层山的底边，
# 约 150×25 像素），不碰边缘也不横贯，它们认不出来。这里认「一段水平直边 + 贴着它的一条淡色平条」：
#   · 直边：图片裁切边是严格水平的。竖向差分的阶跃边取亚像素位置（±2 行的重心），同一个位置（漂移 ≤ ±0.6 设计像素）上连续 ≥ 60 设计像素才算；
#     纸剪的山、人物、云的轮廓是锯齿 / 曲线，手绘的线（船板、屋脊、波浪线）在 60 像素里总会漂过去 0.6 像素；
#     平条在直边的下面（露缝出在图层平直的底边下面：山层 PNG 的底边整行不透明、顶边是山的轮廓）；直边在平条下面的（屋脊上面的雨天空、道具顶上面的背景）不算；
#   · 平条：从直边往下逐行走（strip_candidates 里往上的也量，标定时看，_is_strip 只认往下的），颜色一直在这一列参考色 ±16 以内，走了多少行 = 厚度；厚度 ≥ 10 设计像素的连续列合起来宽 ≥ 60、
#     厚度中位数 ≤ 60，直边另一侧的颜色和它差 ≥ 40；
#   · 淡色（和 block / seam 一样，M7 说的是「淡色空白」）：最大通道 ≥ 150、饱和度 ≤ 40/255、灰度稳健标准差 ≤ 3.4（天空饱和度 55+，布景里的木条 / 屋顶 / 装饰
#     条是有色的，不报）；
#   · 排除：① 两边都是直边的矩形条（厚度几乎处处一样：道具上的装饰条、仪表盘、窗格），露缝的另一边是下一层的山 / 水 / 地面的轮廓，是不规则的；
#     ② 纯白的细条（贴纸描边、水波上的白线，< 24 像素）；③ 暖色的奶油色（R − B ≥ 16：天空图最下面一截的地平线雾——城墙 / 远山和地面之间 40 像素的奶油色带，
#     tj01 s01 开头就有，小样的好镜头里也有，一直算正常——还有 UI 卡片的奶油色底），除非颜色就是引擎的纸底色（C.PAPER，那是什么都没盖住）；
#     ④ ui=True（成片）：直边另一侧是卡片的棕色边框。
# 阈值在 consts.py 的 STRIP_*，用 tj01 / tj02 的整集布景帧（逐镜头每 0.5 秒一帧，只画背景 / 人物 / 前景）和 tj02 第 2 版 s68 标定。
SW, SH = 540, 960
S2 = C.W // SW                         # 一个工作像素 = 2 个设计像素
_KMAX = 36                             # 平条厚度最多量这么多行（工作像素），再厚的算大块平涂


def _straight_edges(g, y0, y1):
    """水平直边：[(边的位置 t（亚像素行）, x0, x1)]。"""
    yy = np.arange(y0 - 2, y1 + 2)
    d = np.abs(g[yy + 1] - g[yy - 1])                                     # d[i]：以第 y0 − 2 + i 行为中心的竖向差分
    pk = (d >= C.STRIP_EDGE_STEP) & (d >= np.roll(d, 1, 0)) & (d >= np.roll(d, -1, 0))
    pk[:2] = pk[-2:] = False
    iy, ix = np.nonzero(pk)
    if not len(iy):
        return []
    w = np.stack([d[iy + k, ix] for k in (-2, -1, 0, 1, 2)])             # 5 × N
    cen = (w * (iy[None] + np.arange(-2, 3)[:, None])).sum(0) / w.sum(0) + (y0 - 2)
    order = np.argsort(cen)
    cen, ix = cen[order], ix[order]
    need = C.STRIP_EDGE_W // S2
    tol = C.STRIP_EDGE_TOL
    runs = []
    for t in np.arange(np.floor(cen[0]), cen[-1] + 0.25, 0.25):
        lo, hi = np.searchsorted(cen, t - tol), np.searchsorted(cen, t + tol, "right")
        if hi - lo < 0.85 * need:
            continue
        xs = np.unique(ix[lo:hi])
        for seg in np.split(xs, np.flatnonzero(np.diff(xs) > 3) + 1):
            if seg[-1] - seg[0] + 1 >= need and len(seg) >= 0.85 * (seg[-1] - seg[0] + 1):
                runs.append((float(t), int(seg[0]), int(seg[-1])))
    runs.sort(key=lambda r: -(r[2] - r[1]))
    out = []
    for r in runs:                                                        # 同一条边在相邻的 t 上会各找到一次：留最长的
        for k in out:
            ov = min(r[2], k[2]) - max(r[1], k[1])
            if abs(r[0] - k[0]) <= 1.0 and ov >= 0.7 * min(r[2] - r[1], k[2] - k[1]):
                break
        else:
            out.append(r)
    return out


def _flat_depth(small, edge_row, xa, xb, side):
    """从边往 side（+1 下 / −1 上）逐行走：每一列颜色一直在参考色 ±STRIP_FLAT_DIST 以内的行数。→ (厚度数组, 参考色数组, 走过的像素块 K×W×3)。"""
    cols = np.arange(xa, xb + 1)
    first = int(np.ceil(edge_row)) if side > 0 else int(np.floor(edge_row))
    rows = first + side * np.arange(_KMAX)
    ok = (rows >= 0) & (rows < SH)
    rows = np.clip(rows, 0, SH - 1)
    blk = small[rows][:, cols].astype(np.int16)
    ref = np.median(blk[2:5], axis=0)                                    # 边外第 3–5 行的中位数
    dist = np.abs(blk - ref[None]).max(2)
    flat = (dist <= C.STRIP_FLAT_DIST) & ok[:, None]
    flat[:2] = True                                                      # 紧挨边的两行是抗锯齿过渡
    return np.cumprod(flat, axis=0).sum(0), ref, blk


def _robust_std(x):
    """1.4826 × 中位数绝对偏差：边上几列带纹理的像素（平条两端和山峰擦边的几列）不会把「平不平」拉高。"""
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def strip_candidates(img):
    """宽松条件下的候选（带特征：厚度、对比、标准差、平均色、厚度是否处处一样、直边另一侧的颜色），detect_strips 在它上面卡阈值；标定时直接看这里。"""
    small = cv2.resize(img, (SW, SH), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 0.7)
    y0, y1 = C.BLANK_Y0 // S2, C.BLANK_Y1 // S2
    h_lo = C.STRIP_H[0] // S2
    w_min = C.STRIP_W // S2
    found = []
    for edge, xa, xb in _straight_edges(g, y0, y1):
        for side in (+1, -1):
            depth, ref, blk = _flat_depth(small, edge, xa, xb, side)
            xs = np.flatnonzero(depth >= h_lo)
            if not len(xs):
                continue
            for seg in np.split(xs, np.flatnonzero(np.diff(xs) > 2) + 1):
                if len(seg) < w_min:
                    continue
                dep = depth[seg]
                first_o = int(np.floor(edge)) if side > 0 else int(np.ceil(edge))
                rows_o = np.clip(first_o - side * np.arange(2, 5), 0, SH - 1)
                other = np.median(small[rows_o][:, xa + seg].astype(np.int16), axis=0)         # 直边另一侧（外面）每一列的颜色
                rows_n = np.clip(first_o - side * np.arange(1, 3), 0, SH - 1)
                near = np.median(small[rows_n][:, xa + seg].astype(np.int16), axis=0)          # 紧挨着直边外面的两行（卡片边框只有 3 行厚，往外第 3 行起就是白描边了）
                contrast = np.abs(other - ref[seg]).max(1)
                first = int(np.ceil(edge)) if side > 0 else int(np.floor(edge))
                hh = int(np.percentile(dep, 90))
                ya, yb = (first, first + hh) if side > 0 else (first - hh + 1, first + 1)
                kk = np.arange(_KMAX)[:, None]
                inside = ((kk >= 2) & (kk < dep[None] - 1))[:, :, None]                         # 去掉紧挨边的两行和贴着外沿的最后一行
                px = blk[:, seg][np.broadcast_to(inside, (_KMAX, len(seg), 3))].reshape(-1, 3)
                if not len(px):
                    continue
                found.append({
                    "kind": "strip", "edge": "top" if side > 0 else "bottom",                   # top = 直边在平条的上沿（平条在直边下面）
                    "bbox": [(xa + int(seg[0])) * S2, ya * S2, (xa + int(seg[-1]) + 1) * S2, yb * S2],
                    "area": round(float(dep.sum()) * S2 * S2 / (C.W * C.H), 5), "len": (xb - xa + 1) * S2, "w": len(seg) * S2,
                    "h_med": float(np.median(dep)) * S2, "contrast": float((contrast >= C.STRIP_CONTRAST).mean()),
                    "std": _robust_std(px.astype(np.float32).mean(1)), "mean": [float(v) for v in np.median(px, axis=0)],
                    "bar": float((np.abs(dep - np.median(dep)) <= 1).mean()), "other": [float(v) for v in np.median(other, axis=0)], "near": [float(v) for v in np.median(near, axis=0)],
                })
    return found


def _is_strip(e, ui):
    m = e["mean"]
    v = max(m)
    if e["edge"] != "top":
        return False                                                       # 露缝出在图层平直的底边下面（山层 PNG 的底边整行不透明、顶边是轮廓）；直边在平条下面的（屋脊、船舷、道具顶上面的天空）不是
    if e["h_med"] > C.STRIP_H[1] or e["contrast"] < 0.7:
        return False
    if v < C.STRIP_VAL_MIN or (v - min(m)) / max(v, 1) * 255 > C.STRIP_SAT_MAX or e["std"] > C.STRIP_STD_MAX:
        return False                                                       # 不是淡色平涂
    if e["bar"] >= C.STRIP_BAR:
        return False                                                       # 两边都是直边的矩形条
    if min(m) >= C.STRIP_WHITE_MIN and e["h_med"] < C.STRIP_WHITE_H:
        return False                                                       # 纯白的细条：贴纸描边、水波白线
    if m[2] - m[0] >= C.STRIP_WARM and max(abs(a - b) for a, b in zip(m[::-1], C.PAPER)) > C.STRIP_PAPER_TOL:
        return False                                                       # 暖色奶油色（天空图最下面那一截的地平线雾、卡片底）：不报，除非就是纸底色
    if ui and any(max(abs(o - c) for o, c in zip(e[k], C.STRIP_UI_BORDER_BGR)) <= C.STRIP_UI_BORDER_TOL for k in ("other", "near")):
        return False                                                       # 卡片 / 气泡的棕色边框里面的奶油色底
    return True


def detect_strips(img, ui=False):
    """→ [{"kind": "strip", "bbox": [x0, y0, x1, y1]（设计坐标，y0 = 直边的位置）, "area": 占整幅画面的比例,
    "h": 平条厚度（设计像素，中位数）, "color": 平条的颜色 [R, G, B]}]。img 是任何比例的 BGR 画面。"""
    out = []
    for e in sorted((e for e in strip_candidates(img) if _is_strip(e, ui)), key=lambda e: -e["area"]):
        if not any(_inside(e["bbox"], o["bbox"]) >= 0.5 or _inside(o["bbox"], e["bbox"]) >= 0.5 for o in out):     # 上沿和下沿都是直边的平条会被两条边各找到一次：去重
            out.append({"kind": "strip", "bbox": e["bbox"], "area": e["area"], "h": e["h_med"], "color": [int(round(v)) for v in e["mean"][::-1]]})
    return out


def _inside(a, b):
    """a 的面积有多大比例落在 b 里面。"""
    iw, ih = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    return iw * ih / max((a[2] - a[0]) * (a[3] - a[1]), 1)
