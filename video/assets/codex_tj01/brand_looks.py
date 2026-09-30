"""tj01 第 5 步：智伯（全身名牌）、赵襄子（戴眼镜）的新造型定妆图（Chris 09-30）。

  .venv/Scripts/python video/assets/codex_tj01/brand_looks.py split      # 绿底抠成透明 -> chars/zb_hi_brand.png、chars/zxz_hi_glasses.png
  .venv/Scripts/python video/assets/codex_tj01/brand_looks.py register   # 登记 REGISTRY.md（幂等）
  .venv/Scripts/python video/assets/codex_tj01/brand_looks.py compare    # 对比图 video/out/tj01/design/zb_zxz_before_after.png
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
ROOT = ASSETS.parent.parent
sys.path.insert(0, str(ASSETS.parent))
sys.path.insert(0, str(HERE))
import split_sheet  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

LOOKS = {   # 表名 -> 输出名
    "zb_hi_brand": "zb_hi_brand",
    "zxz_hi_glasses": "zxz_hi_glasses",
}
REG = ASSETS / "REGISTRY.md"
NOTES = {
    "zb_hi_brand": ("智伯 `zb_`", "**高清半身特写 · 定妆图**（09-30 新造型定妆图）：**全身名牌**——红袍上满印编出来的金色「智」字花押 logo（圆角方块里一个「智」字，像奢侈品满印花纹；没有任何真实品牌的标志和字母），腰带正中金色大扣子，冠下沿金边加小金牌，扣子和冠上有几颗金色星芒；鼻孔朝天、双手叉腰、得意大笑；不拿弓、不拿杯；3/4；**以后智伯的姿势图都照这张的名牌造型画**；第 1 场、大笑的镜头用"),
    "zxz_hi_glasses": ("赵襄子 `zxz_`", "**高清半身特写 · 定妆图**（09-30 新造型定妆图）：**戴一副圆框黑眼镜**（其余和原来一样：青绿交领右衽深衣、黑边白三角纹、黑冠金方扣、小胡子）；双手抱胸、沉着镇定、眼神坚定、不让步；不背包袱；3/4；**以后赵襄子的姿势图都照这张的眼镜造型画**"),
}


def split():
    for sheet, name in LOOKS.items():
        src = HERE / f"{sheet}.png"
        if not src.exists():
            print(f"没有 {src.name}，跳过")
            continue
        ps = split_sheet.pieces(str(src))
        ps.sort(key=lambda p: -p[2].shape[0] * p[2].shape[1])
        print(f"{sheet}: 切出 {len(ps)} 件：" + "，".join(f"{p[2].shape[1]}x{p[2].shape[0]}" for p in ps))
        c = ps[0][2].copy()
        c[..., 3] = np.where(c[..., 3] >= 240, 255, c[..., 3])
        out = ASSETS / "chars" / f"{name}.png"
        Image.fromarray(c, "RGBA").save(out)
        print(f"chars/{name}.png {c.shape[1]}x{c.shape[0]}")


def register():
    md = REG.read_text(encoding="utf-8")
    lines = md.split("\n")
    rows = []
    for name, (owner, note) in NOTES.items():
        rel = f"chars/{name}.png"
        if f"`{rel}`" in md or not (ASSETS / rel).exists():
            continue
        im = Image.open(ASSETS / rel)
        w, h = im.size
        rows.append(f"| `{rel}` | {owner} | 右 | {w}×{h} | 无 | 定稿 | {note}（原图 {w}×{h}，屏幕显示不超过 {int(w * 1.3)}×{int(h * 1.3)}） | tj01 |")
    if not rows:
        print("没有要登记的")
        return
    j = next(k for k, l in enumerate(lines) if l.startswith("### 2.2"))
    k = j - 1
    while k > 0 and not lines[k].startswith("|"):
        k -= 1
    lines[k + 1:k + 1] = rows
    REG.write_text("\n".join(lines), encoding="utf-8")
    print(f"登记 {len(rows)} 行")


def compare():
    rows = [
        ("智伯", ASSETS / "chars/zb_hi_proud.png", ASSETS / "chars/zb_hi_brand.png"),
        ("赵襄子", ASSETS / "chars/zxz_hi_smile.png", ASSETS / "chars/zxz_hi_glasses.png"),
    ]
    H, W, PAD, TOP = 900, 1800, 40, 70
    bg = (244, 232, 208)
    font = ImageFont.truetype(str(ASSETS.parent / "vendor/fonts/NotoSansSC-Bold.ttf"), 44)
    small = ImageFont.truetype(str(ASSETS.parent / "vendor/fonts/NotoSansSC-Bold.ttf"), 34)
    sheet = Image.new("RGB", (W, len(rows) * (H + TOP) + PAD), bg)
    d = ImageDraw.Draw(sheet)
    for i, (who, a, b) in enumerate(rows):
        y0 = PAD // 2 + i * (H + TOP)
        d.text((PAD, y0), f"{who}  原来", fill=(42, 35, 32), font=font)
        d.text((W // 2 + PAD, y0), f"{who}  新造型（09-30 定妆图）", fill=(200, 55, 45), font=font)
        for j, p in enumerate((a, b)):
            im = Image.open(p).convert("RGBA")
            r = (H - 20) / im.height
            im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
            x = j * (W // 2) + (W // 2 - im.width) // 2
            sheet.paste(im, (x, y0 + TOP), im)
        d.text((W // 2 - 10, y0 + TOP + H // 2), "→", fill=(42, 35, 32), font=font, anchor="mm")
    out = ROOT / "video/out/tj01/design/zb_zxz_before_after.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    {"split": split, "register": register, "compare": compare}[sys.argv[1]]()
