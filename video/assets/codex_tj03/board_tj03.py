"""tj03 阵容总览：本集新角色（魏武侯、吴起、划桨的士兵、下集预告的子思 / 苟变 / 卫侯）+ 魏文侯、司马光（对比身高），按成片里的大小站在一起。

  .venv/Scripts/python video/assets/codex_tj03/board_tj03.py [--min-w 600]          阵容总览 video/out/tj03/lineup.png
  .venv/Scripts/python video/assets/codex_tj03/board_tj03.py poses                   新姿势总览 video/out/tj03/poses_new.png（每个人物的所有新图，带文件名）
输出在 video/out/tj03/（video/out 不进 git）。阵容图里每个人的显示宽度不小于 --min-w 像素（默认 600）；大小 = 站姿图 × PX × K（同一个 K，所以和成片里一样的比例）。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
ROOT = ASSETS.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ASSETS.parent))
import board_tj01 as B  # noqa: E402  复用纸纹底、字体
import tj03_meta as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUTDIR = ROOT / "video" / "out" / "tj03"
GROUPS = [
    ("魏武侯、吴起（魏文侯、司马光对比身高）", ["wuh", "wq", "wwh", "sgm"]),
    ("划桨的士兵：5 个人坐着划桨（每个人也不小于最小宽度）", ["rower"]),
    ("下集预告：子思、苟变、卫侯（吴起、司马光对比身高）", ["zs", "gb", "wh", "wq", "sgm"]),
]


def figure(p):
    if p in M.CHARS:
        name, rel = M.CHARS[p][:2]
        return name, B.load(rel), M.px(p)
    name, rel, px = M.REFS[p]
    return name, B.load(rel), px


def lineup(min_w):
    figs = {}
    for g in GROUPS:
        for p in g[1]:
            if p not in figs:
                figs[p] = figure(p)
    # K：所有人里「图宽 ÷ 人数 × PX」最小的那个要 ≥ min_w（群像：宽度除以图里的人数）
    K = max(min_w / (im.width / M.persons(p) * px) for p, (_, im, px) in figs.items())
    print(f"K = {K:.3f}")
    gap, pad, label_h, top = 70, 90, 150, 200
    rows = []
    for title, ps in GROUPS:
        items = [(p, figs[p][0], B.scaled(figs[p][1], figs[p][2] * K)) for p in ps]
        rows.append((title, items, max(i[2].height for i in items), sum(i[2].width for i in items) + gap * (len(items) - 1)))
    W = max(r[3] for r in rows) + pad * 2
    H = top + sum(r[2] + label_h + 140 for r in rows) + 40
    img = B.paper(W, H)
    d = ImageDraw.Draw(img)
    d.text((pad, 40), "资治通鉴 · 卷一  在德不在险（tj03）  新角色阵容", fill=B.INK, font=B.font("label", 84))
    d.text((pad, 140), f"按成片里的大小站在一起（同一比例，单人最小的也不小于 {min_w} 像素宽）；古人一律交领右衽、一人一顶帽子；司马光（圆领）按 PX 0.62 放在旁边对比", fill=(110, 95, 80), font=B.font("name", 40))
    y = top
    for title, items, rh, rw in rows:
        d.text((pad, y), title, fill=B.INK, font=B.font("label", 56))
        ground = y + 120 + rh
        d.rectangle([pad - 20, ground, W - pad + 20, ground + 10], fill=(200, 170, 120))
        x = pad + (W - pad * 2 - rw) // 2
        for p, name, im in items:
            img.alpha_composite(im, (x, ground - im.height + 6))
            tw = d.textlength(name, font=B.font("name", 54))
            d.text((x + (im.width - tw) / 2, ground + 30), name, fill=B.INK, font=B.font("name", 54))
            d.text((x + im.width / 2 - 70, ground + 98), f"{p}_ {im.width}×{im.height}", fill=(110, 95, 80), font=B.font("name", 34))
            x += im.width + gap
        y = ground + label_h + 60
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / "lineup.png"
    img.convert("RGB").save(out)
    print(f"{out} {img.width}x{img.height}")
    for p, (name, im, px) in figs.items():
        print(f"  {p:6s} {name}  图 {im.width}×{im.height}  PX {px}  显示 {round(im.width * px * K)}×{round(im.height * px * K)}")


def poses():
    """每个人物的所有新图，等比缩成同一行高，带文件名。"""
    groups = [
        ("魏武侯 wuh_（全身）", sorted(p.name for p in (ASSETS / "chars").glob("wuh_*.png") if "_hi_" not in p.name and p.name != "wuh_point.png")),
        ("魏武侯 wuh_（高清半身，同一块画布）", sorted(p.name for p in (ASSETS / "chars").glob("wuh_hi_*.png"))),
        ("吴起 wq_（本集新姿势）", ["wq_frown_l.png", "wq_point_l.png", "wq_speak_l.png", "wq_speak.png", "wq_bow_l.png"]),
        ("吴起 wq_（高清半身，同一块画布）", ["wq_hi_frown.png", "wq_hi_speak.png", "wq_hi_nod.png"]),
        ("划桨的士兵 rower_", ["rower_row.png", "rower_stop.png"]),
        ("下集预告 zs_ gb_ wh_", ["zs_stand.png", "gb_stand_l.png", "gb_scratch_l.png", "wh_stand_l.png"]),
    ]
    cell_h, gap, pad = 560, 40, 60
    rows = []
    for title, names in groups:
        ims = []
        for n in names:
            f = ASSETS / "chars" / n
            if f.exists():
                im = Image.open(f).convert("RGBA")
                hh = cell_h if im.height > 0.6 * im.width or im.width < 900 else int(cell_h * 0.7)
                ims.append((n, B.scaled(im, hh / im.height)))
        if ims:
            rows.append((title, ims))
    W = max(sum(i[1].width for i in ims) + gap * (len(ims) - 1) for _, ims in rows) + pad * 2
    H = 120 + sum(cell_h + 130 for _ in rows)
    img = B.paper(W, H, seed=3)
    d = ImageDraw.Draw(img)
    d.text((pad, 24), "tj03 新姿势总览（带文件名；每张缩到同样的行高方便看，真实大小比例见 lineup.png）", fill=B.INK, font=B.font("label", 52))
    y = 110
    for title, ims in rows:
        d.text((pad, y), title, fill=B.INK, font=B.font("label", 40))
        x = pad
        for n, im in ims:
            img.alpha_composite(im, (x, y + 70))
            d.text((x, y + 76 + cell_h), n, fill=(110, 95, 80), font=B.font("name", 28))
            x += im.width + gap
        y += cell_h + 130
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / "poses_new.png"
    img.convert("RGB").save(out)
    print(f"{out} {img.width}x{img.height}")


if __name__ == "__main__":
    if "poses" in sys.argv:
        poses()
    else:
        mw = 600
        if "--min-w" in sys.argv:
            mw = int(sys.argv[sys.argv.index("--min-w") + 1])
        lineup(mw)
