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
  --- 整集其余（素材清单第二节 12–35 号）---
  bubble_checkers / bubble_shot -> props/ 同名
  screen_cups       -> props/screen_cup_before.png（左幅）、screen_cup_after.png（右幅）
  inset_yinduo2     -> props/inset_yinduo.png（v1 尹铎穿了红色，是智家的颜色，重画成棕褐）
  chariot_full      -> props/chariot_back.png + props/chariot_front.png（同一张画布拆成前后两层，严丝合缝：两层叠起来和原图逐像素一致）
  hands_douli       -> props/hands_stack.png（左）、props/douli.png（右）
  city_icons2       -> props/city_han.png、city_wei.png、city_jinyang.png（从左到右；v1 墙色太艳，重画）
  book_page_hi      -> sets/study/book_page_hi.png（整幅不透明）
  sky_night         -> sets/jin_land/sky_night.png（整幅不透明）
  zb_expr_a         -> chars/zb_hi_greedy.png、zb_hi_shock.png
  zb_expr_b         -> chars/zb_hi_proud.png、zb_hi_side.png
  zxz_expr_a        -> chars/zxz_hi_no.png、zxz_hi_smile.png
  zxz_no_l / hkz_stand_l / zb_cheer_l / wgh_reins_l -> chars/ 同名（整集分镜表要朝左的交领人物，重画的，不是镜像：PITFALLS M1）
  zxz_expr_d        -> chars/zxz_hi_order.png（b 的衣服偏蓝、c 的下边被画布切掉，重画成 d）
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


def split_chariot(arr):
    """把整辆车按「近侧」和「远侧」拆成两层（同一块画布，逐像素分区，叠起来 = 原图）。
    front（前层）= 近侧的大轮（圆，含白纸边）、近侧的低栏杆（含三根立柱和柱帽）和它下面的边梁、车辆下面的车架、车辕、车衡、车轭；
    back（后层）= 车厢底板、车厢后面的旗座和后梁、远侧较高的栏杆（近侧栏杆上沿以上的部分）、远侧车轮露出来的一小条。
    近侧栏杆的上沿在 y=128（柱帽在 y=99），大轮圆心 (566,389)、半径 280（在 chariot_full 裁完边的画布上量的）。"""
    H, W = arr.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    F = ((xx - 566) ** 2 + (yy - 389) ** 2) <= 280 ** 2
    top = np.full(W, 10 ** 6)
    top[278:] = 128
    for a, b in [(278, 324), (808, 850), (1092, 1142)]:
        top[a:b] = 99
    F |= (yy >= top[None, :]) & (xx >= 278) & (yy < 345)
    F |= (xx >= 278) & (yy >= 345)
    front, back = arr.copy(), arr.copy()
    front[~F] = 0
    back[F] = 0
    return back, front


def two(folder, src, names):
    """一张表里几件（从左到右）：抠绿、按顺序存。"""
    ps = sorted(split_sheet.pieces(str(src)), key=lambda p: p[1])
    assert len(ps) == len(names), f"{src.name} 切出 {len(ps)} 件，要 {len(names)} 件：{[(p[1], p[2].shape[1], p[2].shape[0]) for p in ps]}"
    for (y, x, c), nm in zip(ps, names):
        save(f"{folder}/{nm}.png", c)


def opaque(src, dst):
    im = Image.open(src).convert("RGBA")
    p = ASSETS / dst
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p)
    print(f"{dst} {im.width}x{im.height}")


def main():
    todo = sys.argv[1:] or ["stove_flooded", "zb_shadow_young", "icons_new", "bubble_nickname2", "banquet_row", "shadow_screen", "zgo_shadow_l", "dg_kneel_l",
                         "bubble_checkers", "bubble_shot", "screen_cups", "inset_yinduo2", "chariot_full", "hands_douli",
                         "city_icons2", "book_page_hi", "sky_night", "zb_expr_a", "zb_expr_b", "zxz_expr_a", "zxz_expr_d",
                         "zxz_no_l", "hkz_stand_l", "zb_cheer_l", "wgh_reins_l"]
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
        elif n in ("zgo_shadow_l", "dg_kneel_l", "zxz_no_l", "hkz_stand_l", "zb_cheer_l", "wgh_reins_l"):
            save(f"chars/{n}.png", union_crop(src))
        elif n in ("bubble_checkers", "bubble_shot"):
            save(f"props/{n}.png", union_crop(src))
        elif n == "inset_yinduo2":
            save("props/inset_yinduo.png", union_crop(src))
        elif n == "screen_cups":
            two("props", src, ["screen_cup_before", "screen_cup_after"])
        elif n == "hands_douli":
            two("props", src, ["hands_stack", "douli"])
        elif n == "city_icons2":
            two("props", src, ["city_han", "city_wei", "city_jinyang"])
        elif n == "chariot_full":
            back, front = split_chariot(union_crop(src))
            save("props/chariot_back.png", back)
            save("props/chariot_front.png", front)
        elif n == "book_page_hi":
            opaque(src, "sets/study/book_page_hi.png")
        elif n == "sky_night":
            opaque(src, "sets/jin_land/sky_night.png")
        elif n == "zb_expr_a":
            two("chars", src, ["zb_hi_greedy", "zb_hi_shock"])
        elif n == "zb_expr_b":
            two("chars", src, ["zb_hi_proud", "zb_hi_side"])
        elif n == "zxz_expr_a":
            two("chars", src, ["zxz_hi_no", "zxz_hi_smile"])
        elif n == "zxz_expr_d":
            two("chars", src, ["zxz_hi_order"])
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
