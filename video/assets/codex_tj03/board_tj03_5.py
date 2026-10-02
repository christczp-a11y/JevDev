"""tj03 第 5 步（画面素材）新素材总览：本步新画 / 新做的每一件东西摆在一张图上，每张显示宽度不小于 600 像素（小图放大看清楚，大图缩到不超过 1400 宽）。

  .venv/Scripts/python video/assets/codex_tj03/board_tj03_5.py
输出 video/out/tj03/assets_new.png（video/out 不进 git）。分五块：人物、历史快闪卡、小道具和图标、天平和桨的前景层、想象泡泡里的画；每件下面写素材清单编号、路径、原图尺寸。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
ROOT = ASSETS.parent.parent
sys.path.insert(0, str(ASSETS.parent))
import board_tj01 as B  # noqa: E402  复用纸纹底、字体

sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "video" / "out" / "tj03" / "assets_new.png"
W, MARGIN, GAP, MIN_W, MAX_W, MAX_H = 4200, 70, 60, 600, 1400, 1000

SECTIONS = [
    ("一、人物（C1、C2：魏武侯重画的两个反方向姿势；右边是原来的朝向对照）", [
        ("C1 朝右", "chars/wuh_bow.png"), ("对照 朝左 wuh_bow_l", "chars/wuh_bow_l.png"),
        ("C2 朝左", "chars/wuh_ponder_l.png"), ("对照 朝右 wuh_ponder", "chars/wuh_ponder.png"),
    ]),
    ("二、历史快闪卡（P1–P3，同一个卡框；前景正中那块平地是留给小旗的）", [
        ("P1", "props/card_sanmiao.png"), ("P2", "props/card_xiajie.png"), ("P3", "props/card_shangzhou.png"),
    ]),
    ("三、小道具和图标（P4–P9）", [
        ("P4", "props/cloud_rain_small.png"), ("P5", "props/egg.png"), ("P6", "props/mini_mountains.png"),
        ("P7", "props/heart_paper.png"), ("P8", "props/icon_boat.png"), ("P9", "props/icon_guard.png"),
    ]),
    ("四、builder 用现成图做的（scale_heart_a / b；rower_oars_fg 叠在 rower_row 上看对位）", [
        ("X1 a：山那边低", "props/scale_heart_a.png"), ("X1 b：心那边沉下去", "props/scale_heart_b.png"),
        ("X2 rower_row + rower_oars_fg", "OARS"),
    ]),
    ("五、想象泡泡里的画（B1–B4）", [
        ("B1", "props/bubble_wall_nap.png"), ("B2", "props/bubble_knight_a.png"),
        ("B3", "props/bubble_knight_bc.png"), ("B4", "props/bubble_knight_d.png"),
    ]),
]


def oars_combo():
    row, fg = B.load("chars/rower_row.png"), B.load("chars/rower_oars_fg.png")
    c = Image.new("RGBA", row.size, (200, 225, 245, 255))
    c.alpha_composite(row)
    d = ImageDraw.Draw(c)
    d.line([(0, 400), (c.width, 400)], fill=(220, 40, 40, 255), width=3)      # 抠桨的起点 y=400
    c.alpha_composite(fg)          # 前景层（和下面同一块画布，原样叠上去：和 rower_row 里的桨逐像素重合）
    return c


def item_image(rel):
    return oars_combo() if rel == "OARS" else B.load(rel)


def caption(code, rel, im, font):
    name = "rower_row + rower_oars_fg（红线 = y 400，抠桨的起点）" if rel == "OARS" else rel.split("/", 1)[1]
    return f"{code} {name} {im.width}×{im.height}"


def cell_w(it):
    d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    return max(it[3].width, int(d.textlength(it[4], font=B.font("name", 34))))


def main():
    font_h, font_c, font_t = B.font("label", 72), B.font("name", 34), B.font("label", 100)
    laid = []     # (标题 or None, 行内容)
    for title, items in SECTIONS:
        imgs = []
        for code, rel in items:
            im = item_image(rel)
            s0 = min(1.0, MAX_H / im.height, MAX_W / im.width)
            s = max(s0, MIN_W / im.width)
            imgs.append((code, rel, im, B.scaled(im, s) if abs(s - 1) > 1e-3 else im))
        imgs = [(c, r, im, sc, caption(c, r, im, font_c)) for c, r, im, sc in imgs]
        rows, cur, cw = [], [], 0
        for it in imgs:
            w = cell_w(it)
            if cur and cw + GAP + w > W - 2 * MARGIN:
                rows.append(cur)
                cur, cw = [], 0
            cur.append(it)
            cw += (GAP if len(cur) > 1 else 0) + w
        rows.append(cur)
        laid.append((title, rows))
    cap_h = 90
    H = MARGIN + 150 + sum(130 + sum(max(i[3].height for i in r) + cap_h + 40 for r in rows) for _, rows in laid) + MARGIN
    img = Image.new("RGBA", (W, H), (226, 214, 190, 255))      # 纯色底（纸纹底的噪点让 PNG 压不下去，68 MB）
    d = ImageDraw.Draw(img)
    d.text((MARGIN, 40), "资治通鉴 · 卷一  在德不在险（tj03）  第 5 步新画面素材总览", fill=B.INK, font=font_t)
    y = MARGIN + 150
    for title, rows in laid:
        d.text((MARGIN, y), title, fill=B.INK, font=font_h)
        y += 130
        for r in rows:
            rh = max(i[3].height for i in r)
            tot = sum(cell_w(i) for i in r) + GAP * (len(r) - 1)
            x = MARGIN + (W - 2 * MARGIN - tot) // 2
            for code, rel, im, sc, lab in r:
                cw = max(sc.width, int(d.textlength(lab, font=font_c)))
                x0 = x
                x = x0 + (cw - sc.width) // 2
                # 柔和投影，让白纸边在纸色底上看得清
                sh = Image.new("RGBA", sc.size, (0, 0, 0, 0))
                sh.putalpha(sc.split()[3].point(lambda v: int(v * 0.25)))
                img.alpha_composite(sh, (x + 8, y + rh - sc.height + 10))
                img.alpha_composite(sc, (x, y + rh - sc.height))
                d.text((x0 + (cw - d.textlength(lab, font=font_c)) // 2, y + rh + 14), lab, fill=(90, 70, 55), font=font_c)
                x = x0 + cw + GAP
            y += rh + cap_h + 40
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT, optimize=True)
    print(f"{OUT}  {img.width}x{img.height}")


if __name__ == "__main__":
    main()
