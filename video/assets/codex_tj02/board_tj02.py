"""tj02 阵容总览：本集新角色 + 魏桓子（同家配色参考）+ 司马光（对比身高），按成片里的大小站在一起。

  .venv/Scripts/python video/assets/codex_tj02/board_tj02.py [--min-w 600]
输出 video/out/tj02/lineup.png（video/out 不进 git）。每个人在图上的显示宽度不小于 --min-w 像素（默认 600）。
大小 = 站姿图 × PX × K（同一个 K，所以和成片里一样的比例）。
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
import tj02_meta as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "video" / "out" / "tj02" / "lineup.png"
GROUPS = [
    ("魏国宫里：魏文侯、虞人、三位大臣（魏桓子是第一集同家的参考）", ["wgh", "wwh", "yr", "wdc_a", "wdc_b", "wdc_c"]),
    ("四位人才（吴起下一集还要用）+ 司马光对比身高", ["wq", "ly", "lk", "xmb", "sgm"]),
]


def figure(p):
    if p in M.CHARS:
        name, rel, _ = M.CHARS[p]
        return name, B.load(rel), M.px(p)
    name, rel, px = M.REFS[p]
    return name, B.load(rel), px


def main():
    min_w = 600
    if "--min-w" in sys.argv:
        min_w = int(sys.argv[sys.argv.index("--min-w") + 1])
    figs = {p: figure(p) for g in GROUPS for p in g[1]}
    # K：所有人里「图宽 × PX」最小的那个要 ≥ min_w
    K = max(min_w / (im.width * px) for _, im, px in figs.values()) * 1.0
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
    d.text((pad, 40), "资治通鉴 · 卷一  魏文侯之约（tj02）  新角色阵容", fill=B.INK, font=B.font("label", 84))
    d.text((pad, 140), f"按成片里的大小站在一起（同一比例，最小的人也不小于 {min_w} 像素宽）；古人一律交领右衽、一人一顶帽子；司马光（圆领）按 PX 0.62 放在旁边对比", fill=(110, 95, 80), font=B.font("name", 40))
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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT)
    print(f"{OUT} {img.width}x{img.height}")
    for p, (name, im, px) in figs.items():
        print(f"  {p:6s} {name}  图 {im.width}×{im.height}  PX {px}  显示 {round(im.width * px * K)}×{round(im.height * px * K)}")


if __name__ == "__main__":
    main()
