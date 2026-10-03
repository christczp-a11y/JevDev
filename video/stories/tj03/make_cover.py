"""tj03 小红书封面（3:4，1080×1440），版式同 tj01 第 2 版、tj02：上方奶白卡片两行大字 + 红签「第3集 · 在德不在险」+ 下方人物。
第 2 版（10-03，Chris：「封面太难看了吧 主角魏武侯的形象没有让我想点进去的想法啊」；PITFALLS H1 再犯、P22）：
不用魏武侯（娃娃脸撑不起封面），改成常胜将军吴起大特写，背后是视频里的高山和河浪。原来的「成语」说法查无此条，删掉。
A「常胜将军说： / 山河再险也守不住」；B「船上的人 / 都可能变成对手？」。Jev 比较见 `picks/combo2_pick.py`。
用法：.venv/Scripts/python video/stories/tj03/make_cover.py → video/out/tj03/publish/cover_v2_A.png、cover_v2_B.png
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
    for name, y, wd in (("ridge_far", 330, 1500), ("ridge_mid", 560, 1450), ("ridge_near", 760, 1400)):
        cv.alpha_composite(layer(A / f"sets/jin_land/{name}.png", wd), ((W - wd) // 2, y))
    water = layer(A / "sets/jin_land/water.png", 1600)
    for y in (1060, H - water.height):   # 两层叠到画面底边，下面不留空白（M7）
        cv.alpha_composite(water, ((W - 1600) // 2, max(1060, y)))
    return cv


LABEL = "第3集 · 在德不在险"
for name, lines, pose in (
    ("A", [[("常胜将军说：", BROWN)], [("山河再险也", BROWN), ("守不住", RED)]], "wq_hi_frown"),
    ("B", [[("船上的人", BROWN)], [("都可能", BROWN), ("变成对手？", RED)]], "wq_hi_speak"),
):
    cv = scene()
    bottom = banner(cv, lines, LABEL, size=120)
    s_ = 0.86
    put(cv, A / f"chars/{pose}.png", s_, W - round(1020 * s_) + 60, bottom + 36)
    p = OUT / f"cover_v2_{name}.png"
    cv.convert("RGB").save(p)
    print(p)

# M：吴起放大在前（主角），魏武侯缩小在后面冒冷汗（留住「将军给国君上课」的故事感）
cv = scene()
bottom = banner(cv, [[("“", BROWN), ("在德不在险", RED), ("”", BROWN)], [("原来是这么来的", BROWN)]], LABEL, size=120)
put(cv, A / "chars/wuh_hi_sweat.png", 0.50, -10, bottom + 150)
boat = layer(A / "props/boat_front.png", 1500)   # 船舷挡住魏武侯的半身切边（M7），人在船上
cv.alpha_composite(boat, (-380, 1050))
put(cv, A / "chars/wq_hi_speak.png", 0.80, W - round(1020 * 0.80) + 70, bottom + 40)
p = OUT / "cover_v2_M.png"
cv.convert("RGB").save(p)
print(p)
