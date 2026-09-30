"""定格：司马光按一下遥控器，画面停在那一帧，轻轻降一点饱和度，四周套一圈纸框（角上贴一个小「⏸」），dur 秒以后恢复。

  {"type": "freeze", "at": {"line": 12, "word": "伸"}, "dur": 2.4}
参数：
  dur     定格多久（秒，默认 2.0）。定格中：背景、人物、镜头、**定格开始之前就开始的特效**都停在 at 那一帧；
          定格开始以后才开始的特效（弹幕、按钮、贴纸……）照常走——它们就是叠在定格画面上的东西；dur 到了画面接上**现在**的时间（不是从停住的地方接着放，锚点不会错位）；
  corner  「⏸」贴纸的位置：tl（左上，默认）/ bl / br；pos 直接写贴纸中心坐标也行；
  desat   降饱和的程度（0–0.5，默认 0.24：画面留 76% 的颜色）；
  sfx     默认 freeze（「咔哒」定格声），写 null 静音。
出现：纸框从画面外面「合」上来（0.2 秒，缓出），饱和度同时降下去，贴纸弹出；结束：纸框打开、颜色回来（0.25 秒）。
（引擎：scene.py 里认 type 是 freeze 的特效，给它的 [at, at+dur) 这段时间让场景用 at 那一刻的时间画；freeze 自己和它之后开始的特效用真时间。）
"""
import cv2
import numpy as np

from engine import anim
from engine import consts as C
from fx import _paper as P
from fx import fx

IN, EXIT = 0.2, 0.25
BORDER = 40
CORNERS = {"tl": (84, 50), "bl": (84, 1842), "br": (996, 1842)}


def _check(p):
    errs = []
    if p.get("corner", "tl") not in CORNERS:
        errs.append(f"corner 只能是 {sorted(CORNERS)}")
    if "pos" in p:
        errs += P.need_pos(p)
    d = p.get("dur", 2.0)
    if not isinstance(d, (int, float)) or not 0.3 <= d <= 8:
        errs.append("freeze 的 dur 要写 0.3–8 秒")
    ds = p.get("desat", 0.24)
    if not isinstance(ds, (int, float)) or not 0 <= ds <= 0.5:
        errs.append("desat 要写 0–0.5")
    return errs


def _border():
    """整幅画面大的纸框：四周一圈米色纸（带纸纹、内沿一条白纸边），框里面贴着内沿有一圈往里淡出的软阴影。RGBA，设计坐标 1080×1920。"""
    W, H = C.W, C.H
    inner = np.zeros((H, W), np.uint8)
    m = P.deckle(P.shape_mask(W - 2 * BORDER, H - 2 * BORDER, 44), amp=3.0, seed=91, scale=7.0)
    inner[BORDER:H - BORDER, BORDER:W - BORDER] = m
    border_a = 255 - inner
    rgb = np.empty((H, W, 3), np.float32)
    rgb[:] = P.CREAM
    rgb *= (1.0 + 0.05 * P.paper_tex(W, H, 92))[..., None]
    near = cv2.dilate(inner, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))) > 0           # 内沿往外 8 像素：一条白纸边
    rgb[near & (border_a > 0)] = P.WHITE
    shadow = cv2.GaussianBlur(border_a.astype(np.float32), (0, 0), 16) / 255.0 * 0.42
    shadow = shadow * (inner.astype(np.float32) / 255.0)
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = np.where(border_a[..., None] > 0, rgb, np.array([60, 44, 30], np.float32))
    out[..., 3] = np.where(border_a > 0, border_a.astype(np.float32), shadow * 255.0)
    return P.Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def _pause_icon(size=84):
    ss = 3
    S = size * ss
    im = P.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = P.ImageDraw.Draw(im)
    d.ellipse((0, 0, S - 1, S - 1), fill=P.RED + (255,))
    bw, bh, gap = int(S * 0.15), int(S * 0.44), int(S * 0.13)
    for x in (S // 2 - gap // 2 - bw, S // 2 + gap // 2):
        d.rounded_rectangle((x, (S - bh) // 2, x + bw, (S + bh) // 2), int(bw * 0.3), fill=(255, 252, 244, 255))
    im = im.resize((size, size), P.Image.LANCZOS)
    return P.add_shadow(P.edged(im, 6, False), (3, 5), 5, 0.3, 12)


@fx("freeze", params=["corner", "pos", "desat"], layer="front", sfx="freeze", check=_check)
def freeze(canvas, t, params, at):
    u = t - at
    dur = float(params.get("dur", 2.0))
    if u < 0 or P.gone(u, dur, EXIT):
        return
    k_in = anim.smooth(u / IN)
    k_out = 1.0 - anim.smooth((u - dur) / EXIT) if u > dur else 1.0
    k = k_in * k_out
    # 降饱和：向灰度靠
    desat = float(params.get("desat", 0.24)) * k
    if desat > 0:
        g = cv2.cvtColor(canvas.img, cv2.COLOR_BGR2GRAY)
        g3 = cv2.merge([g, g, g])
        canvas.img[:] = cv2.addWeighted(canvas.img, 1.0 - desat, g3, desat, 0)
    # 纸框：从画面外面合上来（放大的框先在屏幕外，缓出缩回原大小）；结束时反过来打开
    sp = P.sprite(canvas, ("freeze_border",), _border)
    s = 1.0 + 0.16 * (1.0 - anim.out_cubic(u / IN)) if u < IN else 1.0
    if u > dur:
        s = 1.0 + 0.16 * anim.in_cubic((u - dur) / EXIT)
    canvas.blit(sp, C.W / 2, C.H / 2, scale=s, alpha=min(1.0, k * 1.5), depth=0)
    # 角上的「⏸」
    x, y = params.get("pos", CORNERS[params.get("corner", "tl")])
    icon = P.sprite(canvas, ("freeze_pause",), _pause_icon)
    ps, psx, psy = P.pop_xy(u - 0.1, 2.4, 7.0, 0.1)
    pulse = 1.0 + 0.04 * np.sin(2 * np.pi * u / 1.6)
    canvas.blit(icon, x, y, scale=max(ps, 0.0) * pulse * (k_out if u > dur else 1.0), sx=psx, sy=psy, alpha=min(1.0, max(0.0, (u - 0.1) / 0.05)) * k_out, depth=0)
