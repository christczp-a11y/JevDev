"""tj01 第 5 步（第一场）：把第一场新画的图（绿底）抠掉绿色、裁到内容外框、放进清单写的路径。

  .venv/Scripts/python video/assets/codex_tj01/split_new_scene1.py [名字 ...]      # 不写名字 = 全部已经画好的

  stove_flooded     -> props/stove_flooded.png
  zb_shadow_young   -> chars/zb_shadow_young.png
  icons_new         -> props/icon_look.png、icon_speech.png、icon_resolve.png（从左到右）
  bubble_nickname2  -> props/bubble_nickname.png（v1 的大个子表情太凶，重画成 2）
  banquet_row       -> sets/lantai/banquet_row.png（3 张案连成一整排，一张图）
  shadow_screen     -> sets/shadow/screen.png（整幅不透明，原样拷贝）
  zgo_shadow_l      -> chars/zgo_shadow_l.png（智果皮影朝左，重画的，不是镜像：PITFALLS M1）
  dg_kneel_l        -> chars/dg_kneel_l.png（段规跪坐朝左，重画的，右衽）
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
sys.path.insert(0, str(ASSETS.parent))
import split_sheet  # noqa: E402


def union_crop(path):
    ps = split_sheet.pieces(str(path))
    y0 = min(p[0] for p in ps)
    x0 = min(p[1] for p in ps)
    y1 = max(p[0] + p[2].shape[0] for p in ps)
    x1 = max(p[1] + p[2].shape[1] for p in ps)
    canvas = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    for y, x, c in ps:
        canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]] = np.where(
            c[..., 3:4] > 0, c, canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]])
    return canvas


def add_cut_border(arr, trim=4, width=8, color=(250, 247, 238)):
    """水面的左右两端和底边是平直的切边，Codex 没给切边加白纸边：先削掉 trim 像素（切边上有一两像素抠绿留下的色偏），再在左、右、底三边补一圈 width 像素的白纸边。
    底边在原图里并不完全水平（左右差几个像素），所以逐列找最后一行不透明的像素。"""
    a = arr[:, trim:arr.shape[1] - trim]
    h, w = a.shape[:2]
    out = np.zeros((h + width, w + 2 * width, 4), np.uint8)
    out[:h, width:width + w] = a
    col = np.array(list(color) + [255], np.uint8)
    left = a[:, 0, 3] > 200
    right = a[:, -1, 3] > 200
    for i in range(width):
        out[:h][left, i] = col
        out[:h][right, width + w + i] = col
    for x in range(out.shape[1]):
        rows = np.where(out[:, x, 3] > 200)[0]
        if rows.size == 0:
            continue
        r = int(rows.max()) - trim            # 削掉 trim 行
        out[r + 1:, x] = 0
        out[r + 1:r + 1 + width, x] = col
    return out


def save(dst, arr):
    p = ASSETS / dst
    p.parent.mkdir(parents=True, exist_ok=True)
    arr = arr.copy()
    arr[..., 3] = np.where(arr[..., 3] >= 240, 255, arr[..., 3])
    Image.fromarray(arr, "RGBA").save(p)
    print(f"{dst} {arr.shape[1]}x{arr.shape[0]}")


def main():
    todo = sys.argv[1:] or ["stove_flooded", "zb_shadow_young", "icons_new", "bubble_nickname2", "banquet_row", "shadow_screen", "zgo_shadow_l", "dg_kneel_l"]
    for n in todo:
        src = HERE / f"{n}.png"
        if not src.exists():
            print(f"缺 {n}.png，跳过")
            continue
        if n == "stove_flooded":
            save("props/stove_flooded.png", add_cut_border(union_crop(src)))
        elif n == "zb_shadow_young":
            save("chars/zb_shadow_young.png", union_crop(src))
        elif n == "icons_new":
            ps = sorted(split_sheet.pieces(str(src)), key=lambda p: p[1])
            assert len(ps) == 3, f"icons_new 切出 {len(ps)} 件"
            for (y, x, c), nm in zip(ps, ["icon_look", "icon_speech", "icon_resolve"]):
                save(f"props/{nm}.png", c)
        elif n in ("zgo_shadow_l", "dg_kneel_l"):
            save(f"chars/{n}.png", union_crop(src))
        elif n == "bubble_nickname2":
            save("props/bubble_nickname.png", union_crop(src))
        elif n == "banquet_row":
            save("sets/lantai/banquet_row.png", union_crop(src))
        elif n == "shadow_screen":
            im = Image.open(src).convert("RGBA")
            (ASSETS / "sets/shadow").mkdir(parents=True, exist_ok=True)
            im.save(ASSETS / "sets/shadow/screen.png")
            print(f"sets/shadow/screen.png {im.width}x{im.height}")


if __name__ == "__main__":
    main()
