"""tj03 小红书封面（3:4，1080×1440），版式同 tj01 第 2 版、tj02：上方奶白卡片两行大字 + 红签「第3集 · 在德不在险」+ 下方人物。
大木船上，左边魏武侯（冒冷汗，朝右）、右边吴起（皱眉说话，朝左）面对面。
K3（推荐）「成语「在德不在险」 / 原来是这么来的」；K2（备选）「满级装备 / 不如队友齐心？」。Jev 比较见 `picks/combo_pick.py`。
用法：.venv/Scripts/python video/stories/tj03/make_cover.py → video/out/tj03/publish/cover_K3.png、cover_K2.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[3]
A = REPO / "video/assets"
FUN = str(REPO / "video/vendor/fonts/ZCOOLKuaiLe-Regular.ttf")
BOLD = str(REPO / "video/vendor/fonts/NotoSansSC-Bold.ttf")
OUT = REPO / "video/out/tj03/publish"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1440
BROWN, CREAM, RED, WHITE = (74, 44, 22), (248, 240, 222), (200, 55, 45), (255, 255, 255)


def layer(path, width):
    im = Image.open(path).convert("RGBA")
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


def put(cv, path, scale, x, y):
    im = Image.open(path).convert("RGBA")
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * 0.35)))
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x + 10, y + 14))
    cv.alpha_composite(im, (x, y))


def banner(cv, lines, label, size=112):
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


def scene():
    cv = Image.new("RGBA", (W, H))
    cv.alpha_composite(layer(A / "sets/jin_land/sky.png", W), (0, 0))
    for name, y in (("ridge_far", 560), ("ridge_mid", 760), ("ridge_near", 900)):
        cv.alpha_composite(layer(A / f"sets/jin_land/{name}.png", W), (0, y))
    water = layer(A / "sets/jin_land/water.png", 1500)
    cv.alpha_composite(water, ((W - 1500) // 2, 1080))
    return cv


LABEL = "第3集 · 在德不在险"
for name, lines in (
    ("K3", [[("成语「", BROWN), ("在德不在险", RED), ("」", BROWN)], [("原来是这么来的", BROWN)]]),
    ("K2", [[("满级装备", BROWN)], [("不如", BROWN), ("队友齐心？", RED)]]),
):
    cv = scene()
    bottom = banner(cv, lines, LABEL)
    put(cv, A / "chars/wuh_hi_sweat.png", 0.64, -40, bottom + 70)
    put(cv, A / "chars/wq_hi_speak.png", 0.58, W - round(1020 * 0.58) + 30, bottom + 40)
    boat = layer(A / "props/boat_front.png", 1700)
    cv.alpha_composite(boat, ((W - 1700) // 2, H - boat.height + 20))
    p = OUT / f"cover_{name}.png"
    cv.convert("RGB").save(p)
    print(p)
