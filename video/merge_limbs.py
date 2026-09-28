"""纸偶的手腕、脚踝不再显得「断成两截」（Chris 第三轮：手腕和前臂、脚和小腿不要分开节点，看着很怪不自然）。

手：前臂 + 手合成一张纸片（手腕不能单独转）。
  分开的部件各带一圈白纸边，接在一起时上面那块的白边正好压在关节上；原画的前臂末端和手腕又各画了一个关节圆盘，
  叠在一起会鼓出一个「球」。做法：剥掉白边 → 两块都在圆盘旁最细处切开，切口对齐拼接（手腕角度 0），接缝羽化
  → 统一描一圈同样粗细的白边。手臂因此短了一截，IK 按新长度算。
脚：脚踝保留转动（鞋底要一直贴地：小腿倾角站着约 −25°、走路 −42°～0°、下蹲约 −53°，焊死就成了踮脚尖），
  只去掉鞋口那圈压在小腿上的白边：这里生成不带白边的 shin_bare / foot_bare，puppet.js 每帧用小腿纸芯盖掉那段白边。

原始部件（forearm、hand_*）放在 rig.json 的 sources 里，改了原图以后重跑本脚本；parts 里生成 fore_<手形>
（pivot = 手肘，tip = 手的握点），bare 列出有纸芯图的部件。
用法：python video/merge_limbs.py video/assets/rig/youth video/assets/rig/youth_q
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

BARE = ("shin", "foot")


def load(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float64) / 255


def to_image(rgb, alpha):
    return Image.fromarray((np.dstack([rgb, alpha]) * 255).round().clip(0, 255).astype(np.uint8), "RGBA")


def strip_edge(a):
    """去掉白纸边（和外面透明区连通的近白色像素），只留最大的一块（去掉原图里的细杂线）。
    返回（预乘颜色, 剪影 alpha, 白边粗细, 白边颜色）。"""
    rgb, al = a[..., :3], a[..., 3]
    white = (rgb.min(-1) > 228 / 255) & (np.ptp(rgb, -1) < 22 / 255)
    lab, _ = ndimage.label((al <= 0.5) | white)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    edge = np.isin(lab, border[border > 0])
    ring = edge & white & (al > 0.5)
    body = ndimage.binary_opening(~edge & (al > 0.5), iterations=2)
    lab, n = ndimage.label(body)
    if n > 1:
        body = lab == 1 + np.argmax(ndimage.sum(body, lab, range(1, n + 1)))
    thick = float(np.median(ndimage.distance_transform_edt(al > 0.5)[body & ndimage.binary_dilation(ring)]))
    color = np.median(rgb[ring], axis=0)
    alpha = np.clip(ndimage.gaussian_filter(body.astype(float), 0.6), 0, 1)
    return rgb * alpha[..., None], alpha, thick, color


def axes(p):
    piv, tip = np.array(p["pivot"], float), np.array(p["tip"], float)
    L = np.linalg.norm(tip - piv)
    u = (tip - piv) / L
    return piv, u, np.array([-u[1], u[0]]), L


def neck(alpha, p, lo, hi, far=False):
    """在骨头方向 [lo, hi]（占骨长的比例）里找剪影最细的地方，返回（沿骨头的位置, 该处剪影的中心点）。
    far=True：宽度不超过最细处 4% 的位置里取最靠后的（手腕圆盘和手掌之间没有明显细腰时，切在圆盘后沿）。"""
    ys, xs = np.nonzero(alpha > 0.5)
    piv, u, w, L = axes(p)
    P = np.stack([xs, ys], 1) - piv
    A, S = P @ u, P @ w
    pos, wid, mid = np.arange(lo * L, hi * L, 4), [], []
    for t in pos:
        m = (A >= t - 3) & (A < t + 3)
        wid.append(np.ptp(S[m]) if m.any() else np.inf)
        mid.append((S[m].max() + S[m].min()) / 2 if m.any() else 0)
    wid = np.array(wid)
    i = int(np.argmin(wid))
    if far:
        i = int(np.nonzero(wid <= wid[i] * 1.04)[0].max())
    return pos[i], piv + u * pos[i] + w * mid[i]


def ramp(shape, p, start, end):
    """沿骨头方向的渐变：位置 start 处为 0、end 处为 1（start > end 则反过来）。"""
    piv, u, _, _ = axes(p)
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    A = (xx - piv[0]) * u[0] + (yy - piv[1]) * u[1]
    return np.clip((A - start) / (end - start), 0, 1)


def paste(canvas_pm, canvas_a, pm, alpha, M, off):
    """把一块（预乘颜色 + alpha）按仿射变换画到画布上（叠在上面）。M、off：画布 (行, 列) → 部件 (行, 列)。"""
    shape = canvas_a.shape
    warp = lambda ch: ndimage.affine_transform(ch, M, off, output_shape=shape, order=1, cval=0)
    a = np.clip(warp(alpha), 0, 1)
    p = np.dstack([warp(pm[..., i]) for i in range(3)])
    canvas_pm[:] = p + canvas_pm * (1 - a[..., None])
    canvas_a[:] = a + canvas_a * (1 - a)


def merge_arm(folder, fp, hn, hp, feather=6):
    """前臂 + 手：都在圆盘旁最细处切开，手的切口接到前臂切口上，骨头方向对齐，按 size 之比缩放。
    接缝处前臂渐隐、盖在手上面，颜色平滑过渡。返回（RGBA 图, 前臂像素坐标 → 新图, 手像素坐标 → 新图）。"""
    b_pm, b_a, thick, color = strip_edge(load(folder / "forearm.png"))
    a_pm, a_a, _, _ = strip_edge(load(folder / f"{hn}.png"))
    r = hp.get("size", 1) / fp.get("size", 1)
    tb, jb = neck(b_a, fp, 0.55, 1.0)
    ta, ja = neck(a_a, hp, 0.0, 0.6, far=True)
    k = ramp(b_a.shape, fp, tb + feather, tb - feather)
    b_pm, b_a = b_pm * k[..., None], b_a * k
    k = ramp(a_a.shape, hp, ta - 3 * feather / r, ta - feather / r)
    a_pm, a_a = a_pm * k[..., None], a_a * k
    rot = math.atan2(fp["tip"][1] - fp["pivot"][1], fp["tip"][0] - fp["pivot"][0]) \
        - math.atan2(hp["tip"][1] - hp["pivot"][1], hp["tip"][0] - hp["pivot"][0])
    c, s = math.cos(rot), math.sin(rot)
    m = int(max(a_a.shape) * r + thick * 2 + 8)
    H, W = b_a.shape[0] + 2 * m, b_a.shape[1] + 2 * m
    to_b = lambda q: (q[0] + m, q[1] + m)
    C = to_b(jb)
    to_a = lambda q: (C[0] + r * (c * (q[0] - ja[0]) - s * (q[1] - ja[1])),
                      C[1] + r * (s * (q[0] - ja[0]) + c * (q[1] - ja[1])))
    # 画布 (y, x) → 手 (y, x)：q = ja + R(-rot)(X - C) / r
    Ma = np.array([[c, -s], [s, c]]) / r
    Ma_off = np.array([ja[1], ja[0]]) - Ma @ np.array([C[1], C[0]])
    pm, al = np.zeros((H, W, 3)), np.zeros((H, W))
    paste(pm, al, a_pm, a_a, Ma, Ma_off)                                  # 手在下面
    paste(pm, al, b_pm, b_a, np.eye(2), np.array([-m, -m], float))        # 前臂渐隐的末端盖在上面
    # 统一描白边：剪影外 thick 像素一圈
    dist = ndimage.distance_transform_edt(al < 0.5)
    ring = np.clip(thick + 0.5 - dist, 0, 1)
    out_a = al + ring * (1 - al)
    out_rgb = (pm + color * (ring * (1 - al))[..., None]) / np.maximum(out_a, 1e-6)[..., None]
    ys, xs = np.where(out_a > 0.01)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    shift = lambda f: (lambda q: [round(float(f(q)[0] - x0), 1), round(float(f(q)[1] - y0), 1)])
    return to_image(out_rgb[y0:y1, x0:x1], out_a[y0:y1, x0:x1]), shift(to_b), shift(to_a)


def dump(rig):
    """和原来的 rig.json 一样：每个部件一行。"""
    one = lambda v: json.dumps(v, ensure_ascii=False)
    block = lambda d, ind: "{\n" + ",\n".join(f'{ind} {one(k)}: {one(v)}' for k, v in d.items()) + f"\n{ind}}}"
    out = []
    for k, v in rig.items():
        if k == "sources":
            out.append(' "sources": {\n' + ",\n".join(
                f'  {one(kk)}: {block(vv, "  ") if isinstance(vv, dict) else one(vv)}' for kk, vv in v.items()) + "\n }")
        elif isinstance(v, dict):
            out.append(f' {one(k)}: {block(v, " ")}')
        else:
            out.append(f" {one(k)}: {one(v)}")
    return "{\n" + ",\n".join(out) + "\n}\n"


def run(folder):
    folder = Path(folder)
    rig_path = folder / "rig.json"
    rig = json.loads(rig_path.read_text(encoding="utf-8"))
    if "sources" not in rig:   # 第一次跑：把前臂和各种手从 parts 挪到 sources
        parts = rig["parts"]
        rig["sources"] = {"hands": rig["hands"],
                          "parts": {n: parts.pop(n) for n in list(parts) if n == "forearm" or n.startswith("hand_")}}
    sp = rig["sources"]["parts"]
    hands = {}
    for shape, hn in rig["sources"]["hands"].items():
        name = f"fore_{shape}"
        img, fb, fa = merge_arm(folder, sp["forearm"], hn, sp[hn])
        img.save(folder / f"{name}.png")
        rig["parts"][name] = {"pivot": fb(sp["forearm"]["pivot"]), "tip": fa(sp[hn]["tip"]), "size": sp["forearm"].get("size", 1)}
        hands[shape] = name
    rig["hands"] = hands
    for n in BARE:   # 纸芯：不带白边，位置和原图一一对应
        pm, a, _, _ = strip_edge(load(folder / f"{n}.png"))
        to_image(pm / np.maximum(a, 1e-6)[..., None], a).save(folder / f"{n}_bare.png")
    rig["bare"] = list(BARE)
    rig_path.write_text(dump(rig), encoding="utf-8")
    print(folder.name, "→", ", ".join(list(hands.values()) + [f"{n}_bare" for n in BARE]))


if __name__ == "__main__":
    for f in sys.argv[1:]:
        run(f)
