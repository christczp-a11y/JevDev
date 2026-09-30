"""tj01 G 版素材（素材清单 G-2）：抠绿、裁到内容外框、放进 chars/ props/；登记；出总览图。

  .venv/Scripts/python video/assets/codex_tj01/split_G.py split [名字 ...]   # 不写名字 = 全部已经画好的
  .venv/Scripts/python video/assets/codex_tj01/split_G.py register           # 登记 REGISTRY.md（幂等）
  .venv/Scripts/python video/assets/codex_tj01/split_G.py sheets             # 总览图 video/out/tj01/design/zb_brand_poses.png、g_other_assets.png
"""
import re
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
REG = ASSETS / "REGISTRY.md"

ZB = ["zb_b_cheer", "zb_b_glance", "zb_b_soaked", "zb_b_spill", "zb_b_point_l", "zb_b_kick_l",
      "zb_b_hi_greedy_l", "zb_b_hi_shock_l", "zb_b_hi_angry_l", "zb_b_float"]
OTHER = ["zmt_raft", "guests_toast", "zhao_dig", "hand_reach_b", "wave_dragon", "bubble_xueba_a", "bubble_xueba_b",
         "bubble_elephant", "bubble_river_city", "bubble_race_track", "bubble_race_driver"]
DEST = {n: "chars" for n in ZB + ["zmt_raft", "guests_toast", "zhao_dig"]}
DEST.update({n: "props" for n in ["hand_reach_b", "wave_dragon", "bubble_xueba_a", "bubble_xueba_b", "bubble_elephant",
                                  "bubble_river_city", "bubble_race_track", "bubble_race_driver"]})
OPAQUE = {"bubble_race_track"}


def union_crop(path):
    ps = split_sheet.pieces(str(path))
    y0 = min(p[0] for p in ps)
    x0 = min(p[1] for p in ps)
    y1 = max(p[0] + p[2].shape[0] for p in ps)
    x1 = max(p[1] + p[2].shape[1] for p in ps)
    canvas = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
    for y, x, c in ps:
        sub = canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]]
        canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]] = np.where(c[..., 3:4] > 0, c, sub)
    return canvas, len(ps)


# 互换表情/互换图的几组：切出来放在同一块画布上（同尺寸、对齐），分镜表里同一个锚点放就行
GROUPS = [
    # (成员, 整体缩放, 对齐方式)：buckle = 按腰带扣中心对齐到第 2 张；none = 原画布位置不动
    (["zb_b_soaked", "zb_b_spill"], {}, "none"),
    (["zb_b_hi_greedy_l", "zb_b_hi_shock_l", "zb_b_hi_angry_l"], {"zb_b_hi_greedy_l": 0.92}, "buckle"),
]


def buckle_center(raw_path):
    """腰带扣（金色实心大块）在原画布上的中心。"""
    from scipy import ndimage
    a = np.array(Image.open(raw_path).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gold = ndimage.binary_closing((r > 190) & (g > 130) & (g < 200) & (b < 100), iterations=3)
    lab, _ = ndimage.label(gold)
    best = None
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        area = int((lab[sl] == i).sum())
        if 100 < w < 300 and h > 50 and area / (w * h) > 0.4 and (best is None or area > best[0]):
            best = (area, (sl[1].start + sl[1].stop) / 2, (sl[0].start + sl[0].stop) / 2)
    return best[1], best[2]


def group_split(names, scales, align):
    items = []   # (名字, 抠好的 RGBA, 在公共坐标里的左上角 (x, y))
    for n in names:
        ps = split_sheet.pieces(str(HERE / f"{n}.png"))
        y0, x0 = min(p[0] for p in ps), min(p[1] for p in ps)
        y1 = max(p[0] + p[2].shape[0] for p in ps)
        x1 = max(p[1] + p[2].shape[1] for p in ps)
        canvas = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
        for y, x, c in ps:
            sub = canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]]
            canvas[y - y0:y - y0 + c.shape[0], x - x0:x - x0 + c.shape[1]] = np.where(c[..., 3:4] > 0, c, sub)
        s = scales.get(n, 1.0)
        pos = (float(x0), float(y0))
        if s != 1.0:
            im = Image.fromarray(canvas, "RGBA").resize((round(canvas.shape[1] * s), round(canvas.shape[0] * s)), Image.LANCZOS)
            canvas = np.array(im)
            pos = (pos[0] * s, pos[1] * s)
        if align == "buckle":
            bx, by = buckle_center(HERE / f"{n}.png")
            bx, by = bx * s, by * s
            items.append([n, canvas, pos, (bx, by)])
        else:
            items.append([n, canvas, pos, None])
    if align == "buckle":
        rx, ry = items[1][3]                      # 以第 2 张（shock）为准
        for it in items:
            it[2] = (it[2][0] + rx - it[3][0], it[2][1] + ry - it[3][1])
    X0 = min(it[2][0] for it in items)
    Y0 = min(it[2][1] for it in items)
    X1 = max(it[2][0] + it[1].shape[1] for it in items)
    Y1 = max(it[2][1] + it[1].shape[0] for it in items)
    W, H = round(X1 - X0), round(Y1 - Y0)
    for n, arr, pos, _ in items:
        full = np.zeros((H, W, 4), np.uint8)
        ox, oy = round(pos[0] - X0), round(pos[1] - Y0)
        full[oy:oy + arr.shape[0], ox:ox + arr.shape[1]] = arr[:H - oy, :W - ox]
        full[..., 3] = np.where(full[..., 3] >= 240, 255, full[..., 3])
        Image.fromarray(full, "RGBA").save(ASSETS / DEST[n] / f"{n}.png")
        print(f"{DEST[n]}/{n}.png {W}x{H}（同组对齐，缩放 {scales.get(n, 1.0)}）")


def split(names):
    grouped = set()
    for members, scales, align in GROUPS:
        if all((HERE / f"{m}.png").exists() for m in members) and (not names or set(members) & set(names)):
            group_split(members, scales, align)
            grouped |= set(members)
    for n in names or [k for k in DEST if (HERE / f"{k}.png").exists()]:
        if n in grouped:
            continue
        src = HERE / f"{n}.png"
        if not src.exists():
            print(f"没有 {n}.png，跳过")
            continue
        out = ASSETS / DEST[n] / f"{n}.png"
        if n in OPAQUE:
            im = Image.open(src).convert("RGBA")
            im.save(out)
            print(f"{DEST[n]}/{n}.png {im.width}x{im.height}（整幅不透明）")
            continue
        arr, k = union_crop(src)
        arr[..., 3] = np.where(arr[..., 3] >= 240, 255, arr[..., 3])
        Image.fromarray(arr, "RGBA").save(out)
        print(f"{DEST[n]}/{n}.png {arr.shape[1]}x{arr.shape[0]}（{k} 块）")


# ---- 登记：名字 -> (属于, 朝向, 备注) ----
BRAND = "智伯名牌造型（红袍满印金色「智」字花押、金腰扣、冠下沿金边加小金牌，照定妆图 zb_hi_brand）"
NOTES = {
    "zb_b_cheer": ("智伯 `zb_`", "右", f"G1：{BRAND}，**全身**站，双臂斜上方张开、仰头哈哈大笑、鼻孔朝天，后面那只手握一张小木弓（竖着，不搭箭、不对人）；鞋画全（开场站在山顶）；3/4；第 0、29、31、32 句"),
    "zb_b_glance": ("智伯 `zb_`", "左", f"G2：{BRAND}，全身站，**身体朝右（右衽，和别的智伯图一致）、头扭回来看左后方，脸和视线朝左**，眼睛斜瞟、一边眉毛挑高、嘴抿着，一脸怀疑，一手叉腰一手握弓；登记朝向按脸和视线记「左」，**按原样放，不要翻转**（翻了衣襟成左衽）；和 zb_b_cheer 大小一致，战车上直接换图；第 30 句"),
    "zb_b_soaked": ("智伯 `zb_`", "正面", f"G3：{BRAND}，全身**正面**站，两手垂在身侧、一手耷拉着小木弓；**落汤鸡**：红袍湿透变深贴身（「智」字还看得见）、鬓发湿成一团贴脸、冠歪着滴水、嘴里「噗」地喷出一小股水；懵、狼狈（不害怕不哭）；头顶留空（青蛙另叠）；和 zb_b_spill **同一块画布（937×1479）、同站姿、脚底对齐**，同一个锚点放就能互换；第 0、1、39 句"),
    "zb_b_spill": ("智伯 `zb_`", "正面", f"G4：{BRAND}，全身**正面**站，和 zb_b_soaked **同一块画布（937×1479）、同一个站姿、脚底对齐**（同一个锚点放就能互换），衣服是干的、不拿弓；胸前一大片蓝紫色酒渍，一只漆耳杯倒扣在冠上、几滴酒往下掉；眼睛发直、嘴成小 o，愣住；第 12 句"),
    "zb_b_point_l": ("智伯 `zb_`", "左", f"G5：{BRAND}，**跪坐**前倾、**朝左**（3/4），一手伸食指指向左前方、一手拍大腿，张大嘴哈哈嘲笑、鼻孔朝天；不画矮案；**重画的，不是镜像**（PITFALLS M1）：交领右衽按朝左画对；第 9、10、13、23 句"),
    "zb_b_kick_l": ("智伯 `zb_`", "左", f"G6：{BRAND}，全身站、**朝左**（3/4），近侧一条腿往前（画面左边）踢出、脚尖上翘，一只袖子往后一甩，仰头大笑；手里没有杯子；**重画的，不是镜像**（PITFALLS M1）；第 11 句（「我是大象！」踢飞酒杯）"),
    "zb_b_hi_greedy_l": ("智伯 `zb_`", "左", f"G7：{BRAND}，**高清半身特写**、3/4 **朝左**：两条胳膊在胸前拢成一个圈，**怀里是空的**（城图标由合成器叠）；贪心地笑，眼睛眯成缝、嘴角咧到耳根；**重画的，不是镜像**（PITFALLS M1）；已缩放 0.92 并和 G8、G9 放在**同一块画布（795×1167、腰带扣对齐）**，同一个锚点放就能互换表情；第 14、18、20、22 句"),
    "zb_b_hi_shock_l": ("智伯 `zb_`", "左", f"G8：{BRAND}，高清半身、朝左，**和 zb_b_hi_greedy_l 同一块画布（795×1167、腰带扣对齐），互换表情**：惊呆了，眼睛瞪圆、嘴张成大 O、鬓发炸开一点、手指张开（怀里空，城由合成器往下掉）；重画的，不是镜像；第 24 句"),
    "zb_b_hi_angry_l": ("智伯 `zb_`", "左", f"G9：{BRAND}，高清半身、朝左，**和 zb_b_hi_greedy_l 同一块画布（795×1167、腰带扣对齐），互换表情**：「红温」——咬牙、眉毛倒竖、鬓发根根竖起、两手在胸前握拳、脸颊涨红（没有青筋、没有红眼）；重画的，不是镜像；第 25 句"),
    "zb_b_float": ("智伯 `zb_`", "正面", "G10：智伯穿**名牌睡衣**（米白底满印金色「智」字的交领右衽睡袍，尖顶软睡帽、帽尖一个小金球，不戴冠），趴在一根粗浮木上，两手抱浮木、两脚在后面（画面左边）扑腾划水，两腮鼓着「噗」地喷出一小股水，鬓发湿成一团；狼狈、发懵，不惊恐（只是泡在水里，不涉及生死）；**水不画**，用 sets/jin_land/water 盖住下半截；正面略朝右；第 38 句"),
    "zmt_raft": ("张孟谈 `zmt_`", "右", "G11：张孟谈（灰绿交领右衽长衣配青绿边、披深灰黑粗布从头盖到肩、山羊小胡子）弯腰半蹲在一只**黑色小竹筏**（五六根黑竹用麻绳捆成）上，双手握长竹篙往后（画面左边）撑，眼睛警觉地看向右前方；左边的筏面上有竹篙斜穿过，**青蛙用 frog_wait 叠在竹筏左段、竹篙的前面**；水不画，篙尖不插水；3/4；第 33 句（深夜撑竹筏溜到韩、魏营帐边）"),
    "guests_toast": ("宴会宾客 `guests_`", "右", "G12：三位宴会宾客跪坐成一排、**全朝右**（对着右边的智伯），左 1 米白、中 2 灰褐举漆耳杯敬酒、右 3 土黄，两边的拍手，都笑得有点讨好；黑小冠；**不用智、赵、韩、魏四家颜色**；不画矮案（案用 sets/lantai/banquet_row）；第 7 句"),
    "zhao_dig": ("赵家的人 `zhao_`", "右", "**夜里挖堤的赵家兵**（远景用）：青绿 #2f7d5b 头巾、青绿交领右衽短衣配黑边加白色小三角纹（和赵襄子同款）、深灰裤子、绑腿、草鞋，**全身没有红色、赭黄、黑皮甲**（不是智伯的兵）；弯腰、双手握长柄青铜镐举在身后右肩上方、正要往下挖；3/4；第 37 句；**挖堤用它，不用 folk_dig**（folk_dig 穿智家兵的衣服）"),
    "sold_spear": ("智伯的兵 `sold_`", "右", "智伯的兵（赭黄上衣、黑皮甲、红头巾），拿矛站着（矛竖着，不对人）；从 codex_tj01/pose_crowd.png 左上拆出；第 5 句（「兵马最多」：复制几份排成一排）"),
    "folk_dig": ("晋阳百姓 `folk_`", "右", "扛镐的人，**穿智家兵的衣服**（赭黄上衣、黑皮甲、红头巾），**挖堤不用它，用 zhao_dig**；从 codex_tj01/pose_crowd.png 右上拆出；原本是「赵家这边的人」的设想，颜色不对，只留作备用"),
    "hand_reach_b": ("道具", "左", "G13：智伯的大手，名牌袖子（赭红底满印金色「智」字的宽袖、袖口墨黑边加金色回纹），从画面右边伸进来，手心向上摊开；**正好 5 根手指（1 拇指 + 4 指，R13 重画，逐根数过）**；只有袖子和手；第 14、21 句"),
    "wave_dragon": ("道具", "右", "G14：一道巨大的卷浪，白、浅蓝、蓝的纸片层层叠出，浪头卷成 Q 版圆滚滚的龙头（圆眼睛、调皮地笑，不画牙、不画凶脸、不画红眼），往右扑，左边拖出长长的水尾；不画人；可以翻转（不是人物）；第 0、37 句"),
    "bubble_xueba_a": ("道具", "正面", "G15：椭圆小画面（想象泡泡里的画，之前）：现代小学教室（蓝白校服、红领巾），大个子男生站在一摞金色奖杯堆成的高塔上、双手叉腰、鼻孔朝天；下面四个老实的同学手拉手站成一排抬头看着他；奖杯上没有字；外面是透明底、边缘一圈白纸边；图里的小孩是现代的，只能放在泡泡里；第 1 句前半"),
    "bubble_xueba_b": ("道具", "正面", "G16：椭圆小画面（泡泡里的画，之后），和 bubble_xueba_a 同教室同构图同人物：奖杯塔「哗啦」倒了一地，大个子坐在奖杯堆里发愣（没受伤），四个同学还手拉手、最前面两人的手刚推过奖杯塔（推倒的是塔不是人），松了口气、不嘲笑；现代小孩，只能放在泡泡里；第 1 句后半"),
    "bubble_elephant": ("道具", "右", "G17：椭圆小画面（泡泡里的画）：草地上一头 Q 版纸艺大象朝右，背上披一块满印金色「智」字的红毯子，鼻子高高扬起、一脸得意；象鼻尖上站着一只小黑蚂蚁、双手叉腰、一点也不怕；第 11 句（「我是大象！」）"),
    "bubble_river_city": ("道具", "正面", "G18：椭圆小画面（泡泡里的画）：一座夯土小城（方门洞加木过梁、平缓灰瓦门楼、屋檐平直），城边一条大河，河水涨起来漫到城墙脚、城墙下半截泡在水里；城头左右留了空地方（家族小旗由合成器叠 flag_wei / flag_han）；不画人、不标河名；第 31、32 句"),
    "bubble_race_track": ("道具", "右", "G19（R13 重画）：整幅不透明的横版宽图，全图只有一条连续环形赛道，左半笔直直道上黑白格起跑线垂直横跨路面、红色赛车刚冲出，右半弯道、蓝色小赛车滑出停在外侧草地；第 44、47 句"),
    "bubble_race_driver": ("道具", "正面", "G20：椭圆小画面（泡泡里的画）：赛车驾驶座特写，戴红色头盔的司机（成年人、笑眯眯、很稳）双手稳稳握住方向盘，胸口一块空白的圆角方形布标（合成器写「人品和尊重」），背景速度线；第 45 句"),
}


def register():
    md = REG.read_text(encoding="utf-8")
    lines = md.split("\n")
    rows_c, rows_p = [], []
    for n, (owner, face, note) in NOTES.items():
        d = "chars" if n in DEST and DEST[n] == "chars" else ("props" if n in DEST else "chars")
        rel = f"{d}/{n}.png"
        if f"`{rel}`" in md or not (ASSETS / rel).exists():
            continue
        w, h = Image.open(ASSETS / rel).size
        row = f"| `{rel}` | {owner} | {face} | {w}×{h} | 无 | 定稿 | {note}（原图 {w}×{h}，屏幕显示不超过 {int(w * 1.3)}×{int(h * 1.3)}） | tj01 |"
        (rows_c if d == "chars" else rows_p).append(row)

    def insert_before(heading_prefix, rows):
        if not rows:
            return
        j = next(k for k, l in enumerate(lines) if l.startswith(heading_prefix))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = rows

    insert_before("### 2.2", rows_c)
    insert_before("### 2.3", rows_p)
    # 历史人物表：新前缀 zhao_、guests_
    new_people = [
        ("| 赵家的兵（虚构群众，夜里挖堤） | `zhao_` | tj01 | 青绿 #2f7d5b 头巾、青绿交领右衽短衣配黑边加白色小三角纹（和赵襄子同款）、深灰裤子、绑腿、草鞋；**没有红色、赭黄、黑皮甲**（那是智伯的兵） | — | 定稿 |", "`zhao_`"),
        ("| 宴会宾客（虚构，蓝台上捧智伯场的三位客人） | `guests_` | tj01 | 米白、灰褐、土黄的交领右衽深衣，黑小冠；不用智、赵、韩、魏四家的颜色 | — | 定稿 |", "`guests_`"),
    ]
    txt = "\n".join(lines)
    add = [r for r, key in new_people if f"| {key} |" not in txt]
    if add:
        j = next(k for k, l in enumerate(lines) if l.startswith("| 智宣子"))
        lines[j + 1:j + 1] = add
    REG.write_text("\n".join(lines), encoding="utf-8")
    print(f"登记：姿势图 {len(rows_c)}，道具 {len(rows_p)}，人物行 {len(add)}")


def sheet(names, out, cols, cell_h, title):
    font = ImageFont.truetype(str(ASSETS.parent / "vendor/fonts/NotoSansSC-Bold.ttf"), 26)
    big = ImageFont.truetype(str(ASSETS.parent / "vendor/fonts/NotoSansSC-Bold.ttf"), 40)
    bg = (244, 232, 208)
    ims = []
    for n in names:
        rel = f"{DEST.get(n, 'chars')}/{n}.png"
        p = ASSETS / rel
        if not p.exists():
            continue
        im = Image.open(p).convert("RGBA")
        r = min(cell_h / im.height, 720 / im.width)
        ims.append((n, im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS), im.size))
    cell_w = 720
    rows = (len(ims) + cols - 1) // cols
    sheet_im = Image.new("RGB", (cols * (cell_w + 20) + 20, 70 + rows * (cell_h + 60)), bg)
    d = ImageDraw.Draw(sheet_im)
    d.text((20, 10), title, fill=(42, 35, 32), font=big)
    for i, (n, im, sz) in enumerate(ims):
        cx, cy = 20 + (i % cols) * (cell_w + 20), 70 + (i // cols) * (cell_h + 60)
        sheet_im.paste(im, (cx + (cell_w - im.width) // 2, cy + 40 + (cell_h - im.height)), im)
        d.text((cx, cy), f"{n}  {sz[0]}×{sz[1]}", fill=(200, 55, 45), font=font)
    p = ROOT / "video/out/tj01/design" / out
    p.parent.mkdir(parents=True, exist_ok=True)
    sheet_im.save(p)
    print(p, sheet_im.size)


def sheets():
    sheet(ZB, "zb_brand_poses.png", 5, 760, "智伯名牌造型 10 张（G1–G10）")
    sheet(OTHER, "g_other_assets.png", 4, 520, "G 版其余 11 张（张孟谈竹筏、宾客、赵家兵、大手、龙浪、泡泡画 6）")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "split":
        split(sys.argv[2:])
    elif cmd == "register":
        register()
    elif cmd == "sheets":
        sheets()
