"""tj02 第 5 步（画面素材）新素材总览：本步新画 / 新拼的每一件东西摆在一张图上，每张显示宽度不小于 600 像素（小图放大看清楚，大图缩到不超过 1400 宽）。

  .venv/Scripts/python video/assets/codex_tj02/board_tj02_5.py
输出 video/out/tj02/assets_new.png（video/out 不进 git）。分五块：布景、人物、道具、青蛙、泡泡画和拼图；每件下面写素材清单编号、路径、原图尺寸。
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
OUT = ROOT / "video" / "out" / "tj02" / "assets_new.png"
W, MARGIN, GAP, MIN_W, MAX_W, MAX_H = 4200, 70, 60, 600, 1400, 1000

SECTIONS = [
    ("一、布景（T1–T3）", [
        ("T1", "sets/jin_land/sky_rain.png"), ("T3", "sets/mountain/hut.png"), ("T2", "sets/mountain/mud_road.png"),
    ]),
    ("二、人物（C1–C13；魏武侯是新角色 wuh_）", [
        ("C1", "chars/wwh_hi_rain_firm.png"), ("C2", "chars/wwh_hi_rain_mud.png"), ("C3", "chars/wwh_hi_rain_smile.png"),
        ("C4", "chars/yr_sit_l.png"), ("C5", "chars/yr_kneel_l.png"), ("C6", "chars/yr_helped_l.png"),
        ("C7", "chars/yr_hi_sigh_l.png"), ("C8", "chars/yr_hi_cry_l.png"), ("C9", "chars/yr_hi_laugh_l.png"),
        ("C10", "chars/wdc_run.png"), ("C11", "chars/wdc_pant.png"),
        ("C12", "chars/sgm_hi_magnify.png"), ("C13", "chars/wuh_point.png"),
    ]),
    ("三、道具（P1–P17）", [
        ("P1", "props/brazier.png"), ("P2", "props/hands_suoyi.png"),
        ("P3", "props/flag_plain_a.png"), ("P4", "props/flag_plain_b.png"), ("P5", "props/flag_plain_c.png"),
        ("P6", "props/magnet.png"), ("P7", "props/bird_news.png"),
        ("P8", "props/scale_a.png"), ("P9", "props/scale_b.png"),
        ("P10", "props/paperman_wave.png"), ("P11", "props/paperman_shrug.png"), ("P12", "props/paperman_thumb.png"),
        ("P13", "props/remote.png"), ("P14", "props/magnifier.png"), ("P15", "props/pigeon_king.png"),
        ("P16+P17", "BOAT"),
    ]),
    ("四、青蛙（F1–F3）", [
        ("F1", "props/frog_leaf.png"), ("F2", "props/frog_leaf_sigh.png"), ("F3", "props/frog_proud.png"),
    ]),
    ("五、想象泡泡里的画（B1–B5）和用现成图拼的两张", [
        ("B1", "props/bubble_sweeper.png"), ("B2", "props/bubble_shoe_mud.png"), ("B3", "props/bubble_rain_meet.png"),
        ("B4", "props/bubble_watch_msg.png"), ("B5", "props/bubble_door.png"),
        ("拼 1", "props/screen_rain_ride.png"), ("拼 2", "props/bubble_yr_wait.png"),
    ]),
]


def boat_combo():
    back, front = B.load("props/boat_back.png"), B.load("props/boat_front.png")
    c = Image.new("RGBA", (back.width, back.height + 60), (0, 0, 0, 0))
    water = Image.new("RGBA", (back.width, 90), (74, 150, 190, 255))
    c.alpha_composite(back, (0, 0))
    # 两层中间站两个纸片小人当比例参考（红、蓝方块只是示意站位，不是素材）
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((900, 70, 980, 260), 14, fill=(200, 80, 80, 255))
    d.rounded_rectangle((1300, 80, 1370, 250), 14, fill=(80, 90, 200, 255))
    c.alpha_composite(front, (0, 0))
    wl = Image.new("RGBA", c.size, (0, 0, 0, 0))
    wl.alpha_composite(water, (0, 320))
    c.alpha_composite(wl)
    return c


def item_image(rel):
    return boat_combo() if rel == "BOAT" else B.load(rel)


def caption(code, rel, im, font):
    name = "boat_back + boat_front（叠起来；红蓝块只示意站位）" if rel == "BOAT" else rel.split("/", 1)[1]
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
    d.text((MARGIN, 40), "资治通鉴 · 卷一  魏文侯之约（tj02）  第 5 步新画面素材总览", fill=B.INK, font=font_t)
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
