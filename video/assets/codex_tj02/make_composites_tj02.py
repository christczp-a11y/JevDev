"""tj02 第 5 步：两张不用 Codex、用现成图拼的素材（素材清单第四节）。

  .venv/Scripts/python video/assets/codex_tj02/make_composites_tj02.py [screen_rain_ride] [bubble_yr_wait]

  props/screen_rain_ride.png  开场那一幕的定格画（4:3，1600×1200，四周白纸边）：
                              sky_rain + ridge_far/mid/near + mud_road + chariot_back + wwh_reins + horse + chariot_front + 雨丝
  props/bubble_yr_wait.png    椭圆泡泡画（1536×1024，透明底、外圈白纸边）：
                              sky_rain + ridge_* + mud_road + hut + yr_sit_l + 雨丝，裁成椭圆
车、人、马的相对位置：和 tj01 分镜表一致（车 w=1100 时马 w=360、马中心在车中心右边 300；魏文侯的位置沿用 `video/out/tj02/chariot_check.png` 的
x=1000、脚 y=289（车画布里量的，脚藏在近侧栏杆后面）、PX 0.453、车缩放 0.626）。雨丝照特效包 rain（两层斜着的细线、颜色 226,238,250、斜 12 度）按图的大小等比画。
"""
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.stdout.reconfigure(encoding="utf-8")
PAPER = (250, 247, 238)


def L(p):
    return Image.open(ASSETS / p).convert("RGBA")


def cover(img, W, H, y_off=0.0):
    s = max(W / img.width, H / img.height)
    im = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x0 = (im.width - W) // 2
    y0 = int((im.height - H) * y_off)
    return im.crop((x0, y0, x0 + W, y0 + H))


def mirrored_strip(img, W, scale, offset=0):
    """远山 1016 宽不够铺满：左右镜像接起来再裁（山是自然的，接缝处两边对称）。"""
    im = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    strip = Image.new("RGBA", (im.width * 3, im.height))
    strip.paste(im, (0, 0))
    strip.paste(im.transpose(Image.FLIP_LEFT_RIGHT), (im.width, 0))
    strip.paste(im, (im.width * 2, 0))
    return strip.crop((offset, 0, offset + W, im.height))


def put(canvas, img, x, y):
    canvas.alpha_composite(img, (int(round(x)), int(round(y))))


def landscape(W, H, ridges_below_road_top):
    """天空 + 三层远山 + 泥路。远山底边 = 泥路上沿 + 给定的偏移（负数在路上沿之上；最近一层伸到路里面，盖住缝）。返回画布和泥路上沿 y。"""
    c = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    put(c, cover(L("sets/jin_land/sky_rain.png"), W, H, 0.30), 0, 0)
    road = L("sets/mountain/mud_road.png")
    road = road.resize((W, round(road.height * W / road.width)), Image.LANCZOS)
    top = H - road.height
    for (name, sc, off), d in zip((("ridge_far", W / 1500, 120), ("ridge_mid", W / 1500 * 1.05, 380), ("ridge_near", W / 1500 * 1.1, 60)),
                                  ridges_below_road_top):
        r = mirrored_strip(L(f"sets/jin_land/{name}.png"), W, sc, off)
        put(c, r, 0, top + d - r.height)
    put(c, road, 0, top)
    return c, top


def rain(canvas, k, dens=1.0, dim=0.16, seed=7):
    """雨丝：照 motion/fx/weather.py 的 rain，两层（远的细淡、近的粗亮），k 是相对 1080×1920 的缩放。"""
    a = np.array(canvas.convert("RGB")).astype(np.float32)
    a = a * (1 - dim) + np.array((58, 74, 96), np.float32) * dim
    H, W = a.shape[:2]
    rng = np.random.default_rng(seed)
    slant = math.radians(12)
    sx, sy = math.sin(slant), math.cos(slant)
    for n, ln, th, alpha in ((int(150 * dens), 84 * k, 3.6 * k, 0.45), (int(70 * dens), 150 * k, 6.0 * k, 0.66)):
        m = np.zeros((H, W), np.float32)
        for _ in range(n):
            x, y = rng.uniform(-200, W + 200), rng.uniform(-100, H)
            cv2.line(m, (int(x), int(y)), (int(x + ln * sx), int(y + ln * sy)), 1.0, max(1, round(th)), cv2.LINE_AA)
        a = a * (1 - m[..., None] * alpha) + np.array((226, 238, 250), np.float32) * (m[..., None] * alpha)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def paper_frame(img, border):
    """四周加一圈白纸边（带一点点柔影）。"""
    W, H = img.size
    out = Image.new("RGBA", (W + 2 * border, H + 2 * border), PAPER + (255,))
    out.alpha_composite(img, (border, border))
    return out


def screen_rain_ride():
    W, H = 1600, 1200
    ground = 950
    c, road_top = landscape(W, H, (-150, -70, 70))
    back, front = L("props/chariot_back.png"), L("props/chariot_front.png")
    ks = 0.73                                   # 车画布 1756 宽 -> 屏上 1282 宽（车 + 马正好放进 4:3 还留边）
    sz = (round(back.width * ks), round(back.height * ks))
    back, front = back.resize(sz, Image.LANCZOS), front.resize(sz, Image.LANCZOS)
    left, top = 90, ground - sz[1]
    put(c, back, left, top)
    wwh = L("chars/wwh_reins.png")
    s = (0.453 / 0.626) * ks                    # 魏文侯在车坐标里的缩放（chariot_check：PX 0.453、车 0.626；check 图里脚在车画布 y≈289，x≈1000），再乘车的缩放
    wwh = wwh.resize((round(wwh.width * s), round(wwh.height * s)), Image.LANCZOS)
    put(c, wwh, left + 1000 * ks - wwh.width / 2, top + 289 * ks - wwh.height)
    # 马：颈根（马图 (300,150)）正好落在车辕前端的车轭中心（车图 (1700,270)）；马比分镜表里画得大一点，才够得着车轭的高度
    horse = L("props/horse.png")
    hs = 0.88
    horse = horse.resize((round(horse.width * hs), round(horse.height * hs)), Image.LANCZOS)
    yoke_x, yoke_y = left + 1700 * ks, top + 270 * ks
    put(c, horse, yoke_x - 300 * hs, yoke_y - 150 * hs)
    put(c, front, left, top)                    # 前层（近侧栏杆、大轮、车辕、车轭）盖在人和马上
    c = rain(c, k=W / 1080 * 0.7, dens=0.8)
    out = paper_frame(c, 28)
    out.save(ASSETS / "props/screen_rain_ride.png")
    print(f"props/screen_rain_ride.png {out.width}x{out.height}")


def ellipse_bubble(img, rim=18):
    """把整幅画裁成椭圆、外圈白纸边、外面透明（和 bubble_nickname 同款）。"""
    W, H = img.size
    ss = 3
    m = Image.new("L", (W * ss, H * ss), 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).ellipse((0, 0, W * ss - 1, H * ss - 1), fill=255)
    outer = m.resize((W, H), Image.LANCZOS)
    inner = Image.new("L", (W * ss, H * ss), 0)
    ImageDraw.Draw(inner).ellipse((rim * ss, rim * ss, (W - rim) * ss - 1, (H - rim) * ss - 1), fill=255)
    inner = inner.resize((W, H), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), PAPER + (0,))
    out.putalpha(outer)
    pic = img.copy()
    pic.putalpha(inner)
    out.alpha_composite(pic)
    # 白边：outer 里有、inner 里没有的环（用纸色铺），picture 在 inner 里
    ring = Image.new("RGBA", (W, H), PAPER + (255,))
    ring.putalpha(outer)
    base = ring.copy()
    base.alpha_composite(pic)
    return base


def bubble_yr_wait():
    W, H = 1536, 1024
    c, road_top = landscape(W, H, (-150, -70, 70))
    hut = L("sets/mountain/hut.png")
    hs = 0.90
    hut = hut.resize((round(hut.width * hs), round(hut.height * hs)), Image.LANCZOS)
    hx = W - hut.width - 20
    hy = H - 110 - hut.height + 40            # 棚脚落在路面里
    put(c, hut, hx, hy)
    yr = L("chars/yr_sit_l.png")
    ys = 0.40 * hs
    yr = yr.resize((round(yr.width * ys), round(yr.height * ys)), Image.LANCZOS)
    # 虞人坐在棚口（棚的左前柱旁，棚下干草上），朝左
    put(c, yr, hx + 330 * hs - yr.width / 2 + 60, hy + 905 * hs - yr.height)
    # 画在棚后面的东西已经在 hut 里；再把前景的湿草（泥路上沿）盖不盖都行，这里不盖
    c = rain(c, k=W / 1080 * 0.6, dens=0.9)
    out = ellipse_bubble(c)
    out.save(ASSETS / "props/bubble_yr_wait.png")
    print(f"props/bubble_yr_wait.png {out.width}x{out.height}")


if __name__ == "__main__":
    todo = sys.argv[1:] or ["screen_rain_ride", "bubble_yr_wait"]
    for n in todo:
        {"screen_rain_ride": screen_rain_ride, "bubble_yr_wait": bubble_yr_wait}[n]()
