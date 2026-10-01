"""tj01 小红书封面第 2 版（10-02，PITFALLS H1）：大字放上半部分（同赛道爆款都这样，底部会被「小眼睛」数字挡住）。
三个方向：A 创作者自述「我把《资治通鉴》做成了动画」、B 悬念「样样都强的人，为什么一夜输光？」、C 借名人「砸缸的司马光，写了本什么书？」。
用法：.venv/Scripts/python video/stories/tj01/make_cover_v2.py → video/out/tj01/publish/cover_v2_{A,B,C}.png（3:4，1080×1440）
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[3]
A = REPO / "video/assets"
FUN = str(REPO / "video/vendor/fonts/ZCOOLKuaiLe-Regular.ttf")
BOLD = str(REPO / "video/vendor/fonts/NotoSansSC-Bold.ttf")
OUT = REPO / "video/out/tj01/publish"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1440
BROWN, CREAM, RED, WHITE = (74, 44, 22), (248, 240, 222), (200, 55, 45), (255, 255, 255)


def layer(path, width):
    im = Image.open(path).convert("RGBA")
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def background():
    cv = Image.new("RGBA", (W, H))
    cv.alpha_composite(layer(A / "sets/jin_land/sky.png", W), (0, 0))
    for name, y in (("ridge_far", 640), ("ridge_mid", 840), ("ridge_near", 980)):
        cv.alpha_composite(layer(A / f"sets/jin_land/{name}.png", W), (0, y))
    return cv


def put(cv, path, scale, x, y):
    """贴人物：带一层柔和投影。x、y 是缩放后图片左上角。"""
    im = Image.open(path).convert("RGBA")
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.35)))
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x + 10, y + 14))
    cv.alpha_composite(im, (x, y))
    return im.size


def banner(cv, lines, size=122):
    """上方大字卡：lines = [[(文字, 颜色), ...], ...]，每行居中，白描边；左上角压一个「第1集 · 三家分晋」小签。"""
    d = ImageDraw.Draw(cv)
    big = ImageFont.truetype(FUN, size)
    x0, y0, x1 = 40, 66, W - 40
    y1 = y0 + 50 + len(lines) * (size + 26)
    shadow = Image.new("RGBA", (W, H))
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 8, y0 + 12, x1 + 8, y1 + 12), 44, fill=(0, 0, 0, 90))
    cv.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
    d.rounded_rectangle((x0, y0, x1, y1), 44, fill=CREAM, outline=BROWN, width=9)
    y = y0 + 34
    for parts in lines:
        widths = [d.textlength(t, font=big) for t, _ in parts]
        x = (W - sum(widths)) / 2
        for (t, col), w in zip(parts, widths):
            d.text((x, y), t, font=big, fill=col, stroke_width=5, stroke_fill=WHITE)
            x += w
        y += size + 26
    tag = ImageFont.truetype(BOLD, 40)
    label = "第1集 · 三家分晋"
    tw = d.textlength(label, font=tag)
    d.rounded_rectangle((x0 + 24, y0 - 38, x0 + 24 + tw + 44, y0 + 22), 22, fill=RED, outline=WHITE, width=5)
    d.text((x0 + 46, y0 - 34), label, font=tag, fill=WHITE)
    return y1


def save(cv, name):
    p = OUT / f"cover_v2_{name}.png"
    cv.convert("RGB").save(p)
    print(p)


# A：创作者自述（同赛道「我把中国历史做成了动画」5.2 万赞）
cv = background()
bottom = banner(cv, [[("我把《资治通鉴》", BROWN)], [("做成了", BROWN), ("动画", RED)]])
put(cv, A / "chars/zb_b_soaked.png", 0.88, 470, bottom + 40)
frog = layer(A / "props/frog_wait.png", 170)
cv.alpha_composite(frog, (470 + round(340 * 0.88) - 85, bottom + 40 + round(10 * 0.88) - frog.height + 50))
put(cv, A / "chars/sgm_hi_remote.png", 0.62, -30, H - round(1310 * 0.62) + 40)
save(cv, "A")

# B：悬念（智伯落汤鸡大特写）
cv = background()
bottom = banner(cv, [[("样样都强的人", BROWN)], [("为什么", BROWN), ("一夜输光？", RED)]])
s = 1.12
zx, zy = round(540 - 470 * s), bottom + 70
put(cv, A / "chars/zb_b_soaked.png", s, zx, zy)
frog = layer(A / "props/frog_wait.png", 190)
cv.alpha_composite(frog, (zx + round(340 * s) - 95, zy + round(10 * s) - frog.height + 56))
save(cv, "B")

# C：借名人（人人都知道司马光砸缸）
cv = background()
bottom = banner(cv, [[("砸缸的司马光", BROWN)], [("写了本", BROWN), ("什么书？", RED)]])
s = 0.86
put(cv, A / "chars/sgm_hi_magnify.png", s, round(540 - 1016 * s / 2), bottom + 40)
save(cv, "C")
