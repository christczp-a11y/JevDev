"""tj01 第 3 步的三种总览图（给 Chris 看造型和布景用）：

  python video/board_tj01.py lineup       角色阵容图：本集新角色 + 司马光、试做集商鞅，按成片里的大小站在一起，按家族分组，带家族颜色和旗
  python video/board_tj01.py silhouette   剪影图：阵容里每个人涂成纯黑拼在一起，再按「同一场出现的人」分行（一眼分得开吗）
  python video/board_tj01.py sets [名字]  布景总览：晋阳城 jinyang、蓝台宴会 lantai、智伯营地和土堤 camp、周王宫 palace、书房 study、小剧场 theater（不写名字 = 图已经有的全部）；
                                          每张 = 竖屏 1080×1920 分层拼出来的一帧 + 右边每一层的缩略图、原图尺寸、屏幕显示 ÷ 原图（≤ 1.3）
  python video/board_tj01.py all
输出在 video/assets/ref/tj01/。数据（角色、PX、家族颜色）在 video/assets/codex_tj01/tj01_meta.py。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent            # video/
ASSETS = HERE / "assets"
OUT = ASSETS / "ref" / "tj01"
sys.path.insert(0, str(ASSETS / "codex_tj01"))
import tj01_meta as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
CREAM = (244, 232, 208)
INK = (42, 35, 32)
K = 3.0                      # 阵容图：1 个引擎单位 = 3 像素


def font(kind, size):
    """标签用 ZCOOL KuaiLe（系列的标签字体）、名字用 Noto Sans SC；本机没有原字体就用微软雅黑。"""
    src = HERE / "out" / "fonts_src"
    for p in ([src / "ZCOOLKuaiLe-Regular.ttf"] if kind == "label" else [src / "NotoSansSC-500-900.ttf"]) + [Path(r"C:\Windows\Fonts\msyhbd.ttc")]:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                pass
    return ImageFont.load_default()


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def paper(w, h, base=CREAM, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 4, (h, w, 1))
    n = np.asarray(Image.fromarray(np.clip(n * 8 + 128, 0, 255).astype(np.uint8)[..., 0]).filter(ImageFilter.GaussianBlur(1.2)), dtype=float)[..., None] - 128
    arr = np.clip(np.array(base, float)[None, None, :] + n / 8 * 3, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def load(rel):
    return Image.open(ASSETS / rel).convert("RGBA")


def scaled(im, s):
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def silhouette(im, color=(0, 0, 0)):
    a = np.array(im)[..., 3]
    out = np.zeros(a.shape + (4,), np.uint8)
    out[..., :3] = color
    out[..., 3] = a
    return Image.fromarray(out, "RGBA")


def figure_list():
    """阵容里的每个人：(前缀, 名字, 家, 图, PX)。"""
    out = []
    for p in M.LINEUP:
        name, house, tgt, std, px = M.CHARS[p]
        out.append((p, name, house, load(f"chars/{p}_stand.png"), px))
    return out


# ------------------------------------------------------------------ 阵容图
def lineup(k=2.6):
    """两行：第一行 智、赵、韩，第二行 魏、周王室、已定稿的参考（司马光、商鞅）。"""
    figs = figure_list()
    groups = {}
    for f in figs:
        groups.setdefault(f[2], []).append(f)
    gap, pad, flag_gap = 36, 60, 26
    cols = []       # dict: house/kind、宽、要画的东西
    for house, fs in groups.items():
        hs = [f[3].height * f[4] * k for f in fs]
        ws = [f[3].width * f[4] * k for f in fs]
        flag = load(f"props/{M.HOUSES[house][2]}.png")
        flag = scaled(flag, 1.1 * max(hs) / flag.height)
        cols.append(dict(kind="house", house=house, fs=fs, ws=ws, flag=flag,
                         w=flag.width + flag_gap + sum(ws) + gap * (len(fs) - 1)))
    refs = [(nm, scaled(load(rel), px * k), p) for p, (nm, rel, px) in M.REFS.items()]
    cols.append(dict(kind="ref", refs=refs, w=sum(r[1].width for r in refs) + gap * (len(refs) - 1)))
    order = ["智家", "赵家", "韩家", "魏家", "周王室", "ref"]
    key = lambda c: c.get("house", "ref")
    cols.sort(key=lambda c: order.index(key(c)))
    rows = [cols[:3], cols[3:]]
    W = int(max(sum(c["w"] + pad for c in r) + pad for r in rows))
    def col_tall(c):
        if c["kind"] == "house":
            return max(c["flag"].height, max(f[3].height * f[4] * k for f in c["fs"]) * 1.0)
        return max(r[1].height for r in c["refs"])
    row_hs = [int(max(col_tall(c) for c in r) * 1.05 + 300) for r in rows]
    top = 170
    H = top + sum(row_hs) + 30
    img = paper(W, H)
    d = ImageDraw.Draw(img)
    d.text((pad, 36), "资治通鉴 · 卷一  三家分晋（tj01）  角色阵容", fill=INK, font=font("label", 64))
    d.text((pad, 116), "按成片里的大小站在一起：试做集商鞅 = 187 单位高，司马光按 0.62；同一家同一个颜色和旗；古人一律交领右衽、席地，圆领只属于司马光", fill=(110, 95, 80), font=font("name", 28))
    for ri, r in enumerate(rows):
        row_h = row_hs[ri]
        y0 = top + sum(row_hs[:ri])
        ground = y0 + row_h - 190
        x = pad
        for c in r:
            if c["kind"] == "house":
                color = hex_rgb(M.HOUSES[c["house"]][0])
                bw = int(c["w"] + 40)
                img.alpha_composite(Image.new("RGBA", (bw, row_h - 60), color + (40,)), (int(x - 20), y0))
                d = ImageDraw.Draw(img)
                d.rectangle([int(x - 20), ground, int(x - 20 + bw), ground + 22], fill=color)
                img.alpha_composite(c["flag"], (int(x), int(ground - c["flag"].height + 22)))
                d.text((x + 4, y0 + 8), c["house"], fill=color, font=font("label", 64))
                d.text((x + 8, y0 + 84), f"旗：{M.HOUSES[c['house']][1].split('（')[0]}纹 + 一个字", fill=(90, 78, 68), font=font("name", 22))
                d.text((x + 8, y0 + 112), f"颜色 {M.HOUSES[c['house']][0]}", fill=(90, 78, 68), font=font("name", 22))
                fx = x + c["flag"].width + flag_gap
                for (p, name, hs_, im, px), w in zip(c["fs"], c["ws"]):
                    s = scaled(im, px * k)
                    img.alpha_composite(s, (round(fx), int(ground - s.height + 12)))
                    d = ImageDraw.Draw(img)
                    d.text((fx + s.width / 2, ground + 40), name, fill=INK, font=font("name", 38), anchor="mt")
                    d.text((fx + s.width / 2, ground + 88), f"{p}_  PX {px}", fill=(110, 95, 80), font=font("name", 22), anchor="mt")
                    fx += s.width + gap
            else:
                d = ImageDraw.Draw(img)
                d.text((x + 4, y0 + 8), "已定稿（参考）", fill=INK, font=font("label", 56))
                fx = x
                for nm, s, p in c["refs"]:
                    img.alpha_composite(s, (round(fx), int(ground - s.height + 12)))
                    d = ImageDraw.Draw(img)
                    d.text((fx + s.width / 2, ground + 40), nm, fill=INK, font=font("name", 38), anchor="mt")
                    d.text((fx + s.width / 2, ground + 88), f"{p}_", fill=(110, 95, 80), font=font("name", 22), anchor="mt")
                    fx += s.width + gap
            x += c["w"] + pad
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "lineup.png"
    img.convert("RGB").save(out)
    print(out, img.size)


# ------------------------------------------------------------------ 剪影图
SCENES = [   # (标题, [(名字, 图, PX)])：同一场出现的人，用姿势图
    ("蓝台宴会（都席地跪坐）", [("智伯", "zb_cup", "zb"), ("韩康子", "hkz_low", "hkz"), ("段规", "dg_kneel", "dg"), ("魏桓子", "wgh_kneel", "wgh"), ("赵襄子", "zxz_kneel", "zxz")]),
    ("战车「行水」", [("智伯", "zb_cheer", "zb"), ("魏桓子", "wgh_reins", "wgh"), ("韩康子", "hkz_lookup", "hkz")]),
    ("夜里出城", [("张孟谈", "zmt_sneak", "zmt"), ("赵襄子", "zxz_order", "zxz")]),
    ("要地（智伯 / 赵襄子 / 韩康子）", [("智伯", "zb_grab", "zb"), ("赵襄子", "zxz_no", "zxz"), ("韩康子", "hkz_give", "hkz")]),
]


def silhouette_board():
    figs = figure_list()
    K2 = 2.0
    pad = 60
    rows = []
    # 第 1 行：阵容里每个人（站姿）+ 司马光、商鞅
    row1 = [(nm, silhouette(scaled(im, px * K2))) for p, nm, h, im, px in figs]
    for p, (nm, rel, px) in M.REFS.items():
        row1.append((nm, silhouette(scaled(load(rel), px * K2))))
    rows.append(("阵容（站姿，按成片里的大小）", row1))
    for title, items in SCENES:
        r = []
        for nm, f, p in items:
            px = M.CHARS[p][4]
            r.append((nm, silhouette(scaled(load(f"chars/{f}.png"), px * K2))))
        rows.append((title, r))
    W = max(sum(i[1].width for i in r[1]) + 40 * len(r[1]) + 2 * pad for r in rows)
    row_h = [max(i[1].height for i in r[1]) + 130 for r in rows]
    H = sum(row_h) + 130
    img = paper(W, H, base=(250, 246, 236))
    d = ImageDraw.Draw(img)
    d.text((pad, 30), "剪影图：每个人涂成纯黑，一眼分得开吗（阵容 + 同一场出现的人）", fill=INK, font=font("label", 50))
    y = 110
    for (title, r), rh in zip(rows, row_h):
        d.text((pad, y), title, fill=(110, 95, 80), font=font("name", 30))
        base = y + rh - 60
        x = pad
        for nm, s in r:
            img.alpha_composite(s, (x, base - s.height))
            d = ImageDraw.Draw(img)
            d.text((x + s.width / 2, base + 10), nm, fill=INK, font=font("name", 26), anchor="mt")
            x += s.width + 40
        d.line([(pad, base), (W - pad, base)], fill=(200, 190, 175), width=2)
        y += rh
    out = OUT / "silhouette.png"
    OUT.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    print(out, img.size)


# ------------------------------------------------------------------ 布景总览
SW, SH = 1080, 1920


def tint(im, mul=(1, 1, 1), add=(0, 0, 0)):
    a = np.array(im).astype(float)
    for i in range(3):
        a[..., i] = np.clip(a[..., i] * mul[i] + add[i], 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


class Canvas:
    """竖屏 1080×1920 的画布；layer() 记下每一层的名字、原图尺寸和屏幕显示 ÷ 原图（≤ 1.3）。"""

    def __init__(self):
        self.img = Image.new("RGBA", (SW, SH), (0, 0, 0, 255))
        self.layers = []

    def put(self, name, rel, scale, cx=None, bottom=None, top=None, x=None, mul=None, add=None, flip=False):
        im = load(rel)
        src = im.size
        s = scaled(im, scale)
        if flip:
            s = s.transpose(Image.FLIP_LEFT_RIGHT)
        if mul or add:
            s = tint(s, mul or (1, 1, 1), add or (0, 0, 0))
        px = round((SW / 2 if cx is None else cx) - s.width / 2) if x is None else x
        py = round(top) if top is not None else round(bottom - s.height)
        self.img.alpha_composite(s, (px, py))
        self.layers.append((name, rel, src, scale))
        return s

    def fill_below(self, y, color):
        d = ImageDraw.Draw(self.img)
        d.rectangle([0, y, SW, SH], fill=color)


def base_land(cv, mood, ridge_bottoms=(990, 1150, 1340), horizon=1330):
    """共用的天空和三层山。mood: day / dusk / night / spring。"""
    mul = {"day": (1, 1, 1), "dusk": (1.0, 0.86, 0.78), "night": (0.32, 0.4, 0.62), "spring": (1, 1, 1)}[mood]
    add = {"day": (0, 0, 0), "dusk": (18, 0, -6), "night": (0, 4, 14), "spring": (0, 0, 0)}[mood]
    cv.put("天空 sky", "sets/jin_land/sky.png", 1.25, bottom=SH - 0, top=0, mul=mul, add=add)
    for nm, f, sc, b, sh in (("远山 ridge_far", "ridge_far", 1.12, ridge_bottoms[0], -40), ("中远山 ridge_mid", "ridge_mid", 1.12, ridge_bottoms[1], 30), ("近山 ridge_near", "ridge_near", 1.12, ridge_bottoms[2], -20)):
        im = load(f"sets/jin_land/{f}.png")
        s = scaled(im, sc)
        s = tint(s, mul, add)
        cv.img.alpha_composite(s, (round(SW / 2 - s.width / 2 + sh), b - s.height))
        cv.layers.append((nm, f"sets/jin_land/{f}.png", im.size, sc))


def base_ground(cv, mood, top=1330):
    mul = {"day": (1, 1, 1), "dusk": (1.0, 0.86, 0.78), "night": (0.32, 0.4, 0.62), "spring": (1, 1, 1)}[mood]
    add = {"day": (0, 0, 0), "dusk": (18, 0, -6), "night": (0, 4, 14), "spring": (0, 0, 0)}[mood]
    im = load("sets/jin_land/ground.png")
    s = tint(scaled(im, 1.0), mul, add)
    # 地面条下面接同一块土层（把土层的下半截上下镜像地铺下去，一直铺到画面底）
    arr = np.array(s)
    earth = arr[int(arr.shape[0] * 0.45):]
    earth_f = earth[::-1]
    x0 = round(SW / 2 - s.width / 2)
    y = top + s.height - 2
    flip = False
    while y < SH:
        blk = Image.fromarray(earth_f if flip else earth, "RGBA")
        cv.img.alpha_composite(blk, (x0, y))
        y += blk.height - 2
        flip = not flip
    cv.img.alpha_composite(s, (x0, top))
    cv.layers.append(("地面 ground", "sets/jin_land/ground.png", im.size, 1.0))
    return top + s.height


def fore(cv, mood, bottom=SH + 6, scale=1.0):
    mul = {"day": (0.9, 0.9, 0.9), "dusk": (0.85, 0.72, 0.66), "night": (0.3, 0.36, 0.55), "spring": (0.9, 0.9, 0.9)}[mood]
    cv.put("前景框 fore（暗）", "sets/jin_land/fore.png", scale, bottom=bottom, mul=mul)


def ov_jinyang():
    cv = Canvas()
    base_land(cv, "day")
    gtop = 1330
    base_ground(cv, "day", gtop)
    cv.put("城墙条 wall（夯土夹板印）", "sets/jinyang/wall.png", 0.85, cx=SW / 2, bottom=gtop + 55)
    cv.put("城门 gate（夯土 + 木过梁 + 平缓灰瓦门楼）", "sets/jinyang/gate.png", 0.85, cx=SW / 2, bottom=gtop + 85)
    cv.put("水 water（水位盖住下半截城墙）", "sets/jin_land/water.png", 0.9, cx=SW / 2, top=1250)
    fore(cv, "day")
    return cv, "晋阳城（赵家）：夯土城墙数得出夹板印、城门两侧砌墙；水漫到只剩上面几版"


def ov_lantai():
    cv = Canvas()
    base_land(cv, "dusk")
    gtop = 1340
    base_ground(cv, "dusk", gtop)
    cv.put("蓝台 terrace（夯土高台 + 敞亭）", "sets/lantai/terrace.png", 0.92, cx=SW / 2, bottom=gtop + 60, mul=(1.0, 0.92, 0.86))
    cv.put("案 table", "sets/lantai/table.png", 1.0, cx=170, bottom=gtop + 150)
    cv.put("席 mat", "sets/lantai/mat.png", 1.0, cx=SW / 2 - 40, bottom=gtop + 190)
    cv.put("漆耳杯 cup", "sets/lantai/cup.png", 1.0, cx=SW / 2 + 130, bottom=gtop + 170)
    cv.put("洒了的杯 cup_spill", "sets/lantai/cup_spill.png", 1.0, cx=SW / 2 + 260, bottom=gtop + 190)
    cv.put("青铜壶 hu", "sets/lantai/hu.png", 1.0, cx=880, bottom=gtop + 175)
    cv.put("青铜鼎 ding", "sets/lantai/ding.png", 1.0, cx=985, bottom=gtop + 150)
    fore(cv, "dusk")
    return cv, "蓝台宴会：夯土高台加四面敞开的木亭，席地、矮案、漆耳杯、青铜壶和鼎（傍晚）"


def ov_camp():
    cv = Canvas()
    base_land(cv, "day")
    gtop = 1300
    base_ground(cv, "day", gtop)
    cv.put("水 water（堤外）", "sets/jin_land/water.png", 0.9, cx=SW / 2, top=1130)
    cv.put("土堤 dike", "sets/camp/dike.png", 0.85, cx=SW / 2, bottom=gtop + 45)
    cv.put("小帐 tent_s1", "sets/camp/tent_s1.png", 0.9, cx=200, bottom=gtop + 120)
    cv.put("小帐 tent_s2", "sets/camp/tent_s2.png", 0.9, cx=880, bottom=gtop + 120)
    cv.put("大帐 tent_big", "sets/camp/tent_big.png", 1.0, cx=SW / 2, bottom=gtop + 165)
    cv.put("木栅栏 palisade", "sets/camp/palisade.png", 1.0, cx=800, bottom=gtop + 380)
    fore(cv, "day")
    return cv, "智伯营地和土堤：军帐、夯土堤、木栅栏；堤外是水（决口的堤 dike_breach 单独一张）"


def ov_palace():
    cv = Canvas()
    base_land(cv, "spring", ridge_bottoms=(960, 1120, 1330))
    gtop = 1330
    base_ground(cv, "spring", gtop)
    cv.put("大殿 hall（夯土台基 + 朱红木柱 + 平缓灰瓦）", "sets/palace/hall.png", 0.72, cx=SW / 2, bottom=gtop + 70)
    cv.put("青铜鼎 ding_a", "sets/palace/ding_a.png", 0.8, cx=150, bottom=gtop + 180)
    cv.put("青铜鼎 ding_b", "sets/palace/ding_b.png", 0.8, cx=930, bottom=gtop + 180)
    cv.put("竹简策书 slips_table", "sets/palace/slips_table.png", 0.9, cx=SW / 2 - 90, bottom=gtop + 205)
    cv.put("白玉圭 jade_gui", "sets/palace/jade_gui.png", 0.9, cx=SW / 2 + 190, bottom=gtop + 205)
    fore(cv, "spring", scale=1.0)
    return cv, "周王宫（封诸侯）：夯土台基加木构大殿，朱红柱，平缓灰瓦，不是明清宫殿；一个镜头交代"


def ov_study():
    """司马光书房（片头片尾用）：后墙整张 + 书桌、椅子、书堆、竹筐、落地油灯。图还没画出来时不要跑。"""
    cv = Canvas()
    cv.put("后墙 wall（纸窗、书架、人物卡墙）", "sets/study/wall.png", 1.25, cx=SW / 2, top=0)
    cv.put("落地油灯 lamp_stand", "sets/study/lamp_stand.png", 1.0, cx=960, bottom=1560)
    cv.put("竹筐 basket", "sets/study/basket.png", 1.0, cx=130, bottom=1600)
    cv.put("木椅 chair", "sets/study/chair.png", 1.0, cx=250, bottom=1690)
    cv.put("书堆 books", "sets/study/books.png", 1.0, cx=900, bottom=1690)
    cv.put("大书桌 desk", "sets/study/desk.png", 0.95, cx=SW / 2 + 40, bottom=1810)
    return cv, "司马光书房：后墙（纸窗、书架、人物卡墙）+ 桌椅（宋代可以用椅子和纸书）；片头片尾用"


def ov_theater():
    """「考你」小剧场（全系列固定）：幕布、横幔、招牌、台面、台下观众。图还没画出来时不要跑。"""
    cv = Canvas()
    d = ImageDraw.Draw(cv.img)
    d.rectangle([0, 0, SW, SH], fill=(60, 44, 40))                # 暗色后台
    d.rectangle([90, 250, SW - 90, 1300], fill=(244, 232, 208))    # 舞台后幕（米色纸）
    cv.put("台面前沿 stage_floor", "sets/theater/stage_floor.png", 0.75, cx=SW / 2, top=1240)
    cv.put("侧幕（左）curtain", "sets/theater/curtain.png", 1.2, x=-20, top=230)
    cv.put("侧幕（右，镜像）curtain", "sets/theater/curtain.png", 1.2, x=SW - 470, top=230, flip=True)
    cv.put("横幔 valance", "sets/theater/valance.png", 0.75, cx=SW / 2, top=120)
    cv.put("招牌 sign（空白，字由程序写）", "sets/theater/sign.png", 0.8, cx=SW / 2, top=330)
    for i, x in enumerate((160, 340, 520, 700, 880, 1010), 1):
        cv.put(f"观众 aud_{i}", f"sets/theater/aud_{i}.png", 0.9, cx=x, bottom=SH + 40 - (i % 2) * 40)
    return cv, "「考你」小剧场（全系列固定，4 次考你都用）：两边幕布、横幔、招牌、台面、台下纸片观众举牌"


OVERVIEWS = {"jinyang": ov_jinyang, "lantai": ov_lantai, "camp": ov_camp, "palace": ov_palace}
OVERVIEWS_LATER = {"study": ov_study, "theater": ov_theater}      # 这两张表还没画出来（Codex 额度用完），画完拆完图再跑


def overview(name):
    cv, title = {**OVERVIEWS, **OVERVIEWS_LATER}[name]()
    # 右边：每一层的缩略图和数据
    col_w = 620
    W = SW + 40 + col_w
    img = paper(W, SH, base=(250, 246, 236))
    img.alpha_composite(cv.img, (0, 0))
    d = ImageDraw.Draw(img)
    x0 = SW + 30
    d.text((x0, 30), title, fill=INK, font=font("name", 26))
    d.text((x0, 66), "左：竖屏 1080×1920 分层拼的一帧（无人物）", fill=(110, 95, 80), font=font("name", 22))
    y = 110
    for nm, rel, src, sc in cv.layers:
        im = load(rel)
        th = scaled(im, min(col_w / im.width, 140 / im.height))
        bg = Image.new("RGBA", th.size, (200, 200, 200, 255))
        bg.alpha_composite(th)
        img.alpha_composite(bg, (x0, y))
        d = ImageDraw.Draw(img)
        d.text((x0 + th.width + 12, y + 4), nm, fill=INK, font=font("name", 22))
        d.text((x0 + th.width + 12, y + 34), f"原图 {src[0]}×{src[1]}；屏幕显示 ÷ 原图 = {sc:g}", fill=(110, 95, 80), font=font("name", 20))
        y += max(th.height, 66) + 14
        if y > SH - 60:
            break
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"set_{name}_overview.png"
    img.convert("RGB").save(out)
    print(out, img.size, "最大放大倍数", max(l[3] for l in cv.layers))


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("lineup", "all"):
        lineup()
    if what in ("silhouette", "all"):
        silhouette_board()
    if what in ("sets", "all"):
        names = sys.argv[2:] or [n for n in list(OVERVIEWS) + list(OVERVIEWS_LATER) if n in OVERVIEWS or (ASSETS / "sets" / n / ("wall.png" if n == "study" else "valance.png")).exists()]
        for n in names:
            overview(n)


if __name__ == "__main__":
    main()
