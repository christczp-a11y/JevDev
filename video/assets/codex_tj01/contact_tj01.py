"""联系表（看朝向、看有没有拆错用）：contact_tj01.py <输出.png> <文件...>（每张缩到 260 像素高，带文件名；模块里加分组）"""
import sys
from PIL import Image, ImageDraw, ImageFont
FONT = r"C:\Windows\Fonts\msyh.ttc"
def make(out, files, h=260, cols=8, bg=(200, 200, 200)):
    f = ImageFont.truetype(FONT, 14)
    cells = []
    for p in files:
        im = Image.open(p).convert("RGBA")
        r = h / im.height
        im = im.resize((max(1, int(im.width * r)), h))
        cells.append((im, p.split("/")[-1].split("\\")[-1][:-4]))
    rows, row, w = [], [], 0
    maxw = 2000
    for c in cells:
        if row and w + c[0].width + 8 > maxw:
            rows.append(row); row, w = [], 0
        row.append(c); w += c[0].width + 8
    rows.append(row)
    H = len(rows) * (h + 24)
    sheet = Image.new("RGB", (maxw, H), bg)
    d = ImageDraw.Draw(sheet)
    y = 0
    for row in rows:
        x = 0
        for im, nm in row:
            sheet.paste(im, (x, y + 20), im)
            d.text((x + 2, y + 2), nm, fill=(0, 0, 0), font=f)
            x += im.width + 8
        y += h + 24
    sheet.save(out)
if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2:])
