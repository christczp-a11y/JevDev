"""tj02 小红书封面（3:4，1080×1440），版式同 tj01 第 2 版（`video/stories/tj01/make_cover_v2.py`）：上方奶白卡片两行大字 + 红签「第2集 · 魏文侯之约」+ 下方人物大特写。
K1（推荐）「下大雨了 / 约好的事还去吗？」；K4（备选）「冒着大雨赶去 / 只为说一句话」。Jev 比较见 `picks/combo_pick.py`。
用法：.venv/Scripts/python video/stories/tj02/make_cover.py → video/out/tj02/publish/cover_K1.png、cover_K4.png
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[3]
A = REPO / "video/assets"
FUN = str(REPO / "video/vendor/fonts/ZCOOLKuaiLe-Regular.ttf")
BOLD = str(REPO / "video/vendor/fonts/NotoSansSC-Bold.ttf")
OUT = REPO / "video/out/tj02/publish"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1440
BROWN, CREAM, RED, WHITE = (74, 44, 22), (248, 240, 222), (200, 55, 45), (255, 255, 255)


def layer(path, width):
    im = Image.open(path).convert("RGBA")
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def rain(cv, n=170, alpha=110, seed=7):
    """斜雨丝：半透明白线，一层就够，不挡脸（只画在人物后面）。"""
    rnd = random.Random(seed)
    over = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(over)
    for _ in range(n):
        x, y, ln = rnd.randint(-200, W), rnd.randint(-100, H), rnd.randint(40, 90)
        d.line((x, y, x + ln * 0.35, y + ln), fill=(255, 255, 255, alpha), width=3)
    cv.alpha_composite(over)


def background():
    cv = Image.new("RGBA", (W, H))
    cv.alpha_composite(layer(A / "sets/jin_land/sky_rain.png", W), (0, 0))
    for name, y in (("ridge_far", 640), ("ridge_mid", 840), ("ridge_near", 980)):
        cv.alpha_composite(layer(A / f"sets/jin_land/{name}.png", W), (0, y))
    road = layer(A / "sets/mountain/mud_road.png", 1500)
    cv.alpha_composite(road, ((W - 1500) // 2, H - road.height + 40))
    rain(cv)
    return cv


def put(cv, path, scale, x, y):
    im = Image.open(path).convert("RGBA")
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.35)))
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x + 10, y + 14))
    cv.alpha_composite(im, (x, y))


def banner(cv, lines, label, size=122):
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
    tw = d.textlength(label, font=tag)
    d.rounded_rectangle((x0 + 24, y0 - 38, x0 + 24 + tw + 44, y0 + 22), 22, fill=RED, outline=WHITE, width=5)
    d.text((x0 + 46, y0 - 34), label, font=tag, fill=WHITE)
    return y1


LABEL = "第2集 · 魏文侯之约"
for name, lines, pose in (
    ("K1", [[("下大雨了", BROWN)], [("约好的事", BROWN), ("还去吗？", RED)]], "wwh_hi_rain_firm"),
    ("K4", [[("冒着大雨赶去", BROWN)], [("只为", BROWN), ("说一句话", RED)]], "wwh_hi_rain_mud"),
):
    cv = background()
    bottom = banner(cv, lines, LABEL)
    s = 1.12
    put(cv, A / f"chars/{pose}.png", s, round(540 - 863 * s / 2), max(bottom + 40, H - round(1115 * s) + 60))
    p = OUT / f"cover_{name}.png"
    cv.convert("RGB").save(p)
    print(p)
