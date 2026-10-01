"""tj01 小红书封面（3:4，1080×1440）：智伯落汤鸡大特写 + 青蛙 + Jev 选出的大字「本事满分 / 尊重0分」+ 左上角「第1集」。"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path("C:/Users/Chris/Claude x Jev/JevDev")
A = REPO / "video/assets"
FONT_FUN = str(REPO / "video/vendor/fonts/ZCOOLKuaiLe-Regular.ttf")
FONT_BOLD = str(REPO / "video/vendor/fonts/NotoSansSC-Bold.ttf")
OUT = REPO / "video/out/tj01/publish"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1440
BROWN, CREAM, RED = (74, 44, 22), (248, 240, 222), (200, 55, 45)


def layer(path, width):
    im = Image.open(path).convert("RGBA")
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


cv = Image.new("RGBA", (W, H))
sky = layer(A / "sets/jin_land/sky.png", W)
cv.alpha_composite(sky, (0, 0))
for name, y in (("ridge_far", 560), ("ridge_mid", 760), ("ridge_near", 900)):
    cv.alpha_composite(layer(A / f"sets/jin_land/{name}.png", W), (0, y))

# 智伯：脸中心（原图 x≈470）对准画面中线，冠顶落在 y≈150
s = 1.30
zb = Image.open(A / "chars/zb_b_soaked.png").convert("RGBA")
zb = zb.resize((round(zb.width * s), round(zb.height * s)), Image.LANCZOS)
zx, zy = round(540 - 470 * s), 150
shadow = Image.new("RGBA", zb.size, (0, 0, 0, 0))
shadow.putalpha(zb.getchannel("A").point(lambda v: int(v * 0.35)))
cv.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)), (zx + 10, zy + 14))
cv.alpha_composite(zb, (zx, zy))

# 青蛙蹲在歪掉的冠顶高处（原图冠顶右端约 (360, 10)）
frog = layer(A / "props/frog_wait.png", 215)
cv.alpha_composite(frog, (zx + round(340 * s) - 107, zy + round(10 * s) - frog.height + 62))

d = ImageDraw.Draw(cv)

# 底部大字卡
cx0, cy0, cx1, cy1 = 70, 1010, 1010, 1375
card = Image.new("RGBA", (W, H))
cd = ImageDraw.Draw(card)
cd.rounded_rectangle((cx0 + 8, cy0 + 12, cx1 + 8, cy1 + 12), 44, fill=(0, 0, 0, 90))
card = card.filter(ImageFilter.GaussianBlur(8))
cv.alpha_composite(card)
d.rounded_rectangle((cx0, cy0, cx1, cy1), 44, fill=CREAM, outline=BROWN, width=9)

big = ImageFont.truetype(FONT_FUN, 168)
digit = ImageFont.truetype(FONT_BOLD, 168)   # 快乐体的「0」像「口」，数字用黑体


def line(parts, y):
    """parts: [(文字, 颜色, 字体, 竖向微调)]，整行水平居中，白描边。"""
    widths = [d.textlength(t, font=f) for t, _, f, _ in parts]
    x = (W - sum(widths)) / 2
    for (t, col, f, dy), w in zip(parts, widths):
        d.text((x, y + dy), t, font=f, fill=col, stroke_width=6, stroke_fill=(255, 255, 255))
        x += w


line([("本事", BROWN, big, 0), ("满分", RED, big, 0)], cy0 + 22)
line([("尊重", BROWN, big, 0), ("0", RED, digit, -38), ("分", RED, big, 0)], cy0 + 190)

# 左上角集数
badge = ImageFont.truetype(FONT_BOLD, 62)
bx, by, bw, bh = 36, 36, 222, 100
d.rounded_rectangle((bx, by, bx + bw, by + bh), 28, fill=RED, outline=(255, 255, 255), width=6)
tw = d.textlength("第1集", font=badge)
d.text((bx + (bw - tw) / 2, by + 10), "第1集", font=badge, fill=(255, 255, 255))
small = ImageFont.truetype(FONT_BOLD, 38)
d.rounded_rectangle((bx, by + bh + 14, bx + bw, by + bh + 74), 20, fill=CREAM, outline=BROWN, width=4)
tw = d.textlength("三家分晋", font=small)
d.text((bx + (bw - tw) / 2, by + bh + 17), "三家分晋", font=small, fill=BROWN)

out = OUT / "cover_3x4.png"
cv.convert("RGB").save(out)
print(out)
sys.exit(0)
