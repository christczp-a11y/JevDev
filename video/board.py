#!/usr/bin/env python
"""某一集的三种总览图（给 Chris 看造型和布景用；工作流第 5 步过关时拼）。由 board_tj01.py 通用化而来：不写死角色和布景，从素材登记表 REGISTRY.md 里取这一集的定稿素材。

  python video/board.py tj01 lineup        角色阵容图：这一集的人物 + 系列角色（司马光），按成片里的大小（登记表的 PX）站在一起，按家族分组，带家族颜色和旗
  python video/board.py tj01 silhouette    剪影图：每个人涂成纯黑拼在一起，一眼分得开吗；有分镜表的话再按「同一镜里出现的人」加几行
  python video/board.py tj01 sets [名字…]  场景总览：每个地点（sets/<名字>/）一张：竖屏 1080×1920 分层拼的一帧（没有人物）+ 右边每一层的缩略图、原图尺寸、屏幕显示 ÷ 原图（≤ 1.3）
                                           不写名字 = 这一集的全部地点（共用的天空 / 山 / 地面 / 水 / 前景框那一组做背景，不单独出）
  python video/board.py tj01 all
  --out 目录         输出目录（默认 video/assets/ref/<集>/；文件名 board_lineup.png、board_silhouette.png、board_set_<名字>.png，不覆盖 board_tj01.py 出的图）
  --registry 路径    换素材登记表；--assets-root 目录 换素材根目录（默认 video/assets/）；--storyboard 路径 剪影图用哪份分镜表（默认 video/stories/<集>/storyboard.json，没有就只出阵容那一行）
退出码：0 = 出图了；2 = 输入有错（找不到登记表 / 字体 / 这一集没有定稿人物或布景 / 名字不对）。

取材规则（都来自 REGISTRY.md，改了登记表再跑就行）
  人物    「一、历史人物表」里「首次出现的集」是这一集、状态是定稿的；PX 用表里的数（没有就 0.42）；站姿图 = chars/<前缀>stand.png，没有就取该前缀第一张朝右的定稿图
  系列角色  chars/ 里范围是「系列」、状态定稿的前缀（司马光）：放在最后一列当大小参照
  家族    人物行文字里写了家族名（「智家」）/ 家族颜色（#8e2b2b）/ 提到同集另一个人（「韩康子身边……」）/ 名字第一个字对得上家族名（周 → 周王室），按这个顺序认；认不出来就归「其他」
          （要改就改登记表里那一行的文字）。家族颜色和旗来自 video/series_style.json
  布景    sets/ 下范围是这一集或「系列」、状态定稿的图，按目录分；有 sky + ground 的目录当共用背景（天空、三层山、地面、水、前景框），别的目录是一个地点
          自动排版：长条（宽 ÷ 高 ≥ 3.5：城墙、堤）贴地面线，大件（宽 ≥ 900：城门、高台、大殿）居中，其余的小件一排排摆在前面
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent                   # video/
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
import registry_check as RC  # noqa: E402

ASSETS = HERE / "assets"
REGISTRY = ASSETS / "REGISTRY.md"
STYLE = HERE / "series_style.json"
FONT_DIR = HERE / "vendor" / "fonts"
CREAM, INK, MUTED = (244, 232, 208), (42, 35, 32), (110, 95, 80)
DEFAULT_PX = 0.42
K = 2.6                       # 阵容图：1 个引擎单位 = 2.6 像素
SW, SH = 1080, 1920
GROUND_TOP = 1330


class Fail(Exception):
    pass


def font(kind, size):
    """标签用 ZCOOL KuaiLe、名字用 Noto Sans SC Bold（vendor/fonts/）；找不到就报错，不退回系统字体。"""
    p = FONT_DIR / ("ZCOOLKuaiLe-Regular.ttf" if kind == "label" else "NotoSansSC-Bold.ttf")
    if not p.exists():
        raise Fail(f"找不到字体 {p}（不许退回系统字体）")
    return ImageFont.truetype(str(p), size)


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def paper(w, h, base=CREAM, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 4, (h, w, 1))
    n = np.asarray(Image.fromarray(np.clip(n * 8 + 128, 0, 255).astype(np.uint8)[..., 0]).filter(ImageFilter.GaussianBlur(1.2)), dtype=float)[..., None] - 128
    arr = np.clip(np.array(base, float)[None, None, :] + n / 8 * 3, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def scaled(im, s):
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def silhouette(im, color=(0, 0, 0)):
    a = np.array(im)[..., 3]
    out = np.zeros(a.shape + (4,), np.uint8)
    out[..., :3] = color
    out[..., 3] = a
    return Image.fromarray(out, "RGBA")


def tint(im, mul=(1, 1, 1), add=(0, 0, 0)):
    a = np.array(im).astype(float)
    for i in range(3):
        a[..., i] = np.clip(a[..., i] * mul[i] + add[i], 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


# ------------------------------------------------------------------ 读登记表
class Ep:
    pass


def load_ep(ep, registry, assets_root, storyboard=None):
    p = Path(registry)
    if not p.exists():
        raise Fail(f"找不到素材登记表 {p}")
    assets, persons, _ = RC.parse(p.read_text(encoding="utf-8"))
    E = Ep()
    E.ep, E.root, E.storyboard = ep, Path(assets_root), storyboard
    E.rows = {k: {"owner": c[1], "facing": c[2], "size": c[3], "status": RC.status_of(c[5]), "note": c[6], "scope": c[7]} for k, (_, c) in assets.items()}
    style = json.loads(STYLE.read_text(encoding="utf-8"))["houses"] if STYLE.exists() else {}
    E.houses = {n: {"color": v["color"], "flag": v.get("flag", {}).get("img")} for n, v in style.items()}

    def usable(row):
        return row["status"] == "定稿" and (row["scope"] == ep or row["scope"] == "系列")

    series_prefixes = {Path(k).name.split("_")[0] + "_" for k, r in E.rows.items() if k.startswith("chars/") and r["status"] == "定稿" and r["scope"] == "系列"}
    E.people, E.refs = [], []
    for _, c in persons:
        m = re.fullmatch(r"`?([a-z0-9]+_)`?", c[1].strip())
        if not m or RC.status_of(c[5]) != "定稿":
            continue
        prefix = m.group(1)
        name = re.split(r"[（(]", c[0])[0].strip()
        px = re.match(r"\s*(\d+(?:\.\d+)?)", c[4])
        who = {"prefix": prefix, "name": name, "text": c[0] + " " + c[3], "px": float(px.group(1)) if px else DEFAULT_PX, "house": None}
        who["img"] = stand_image(E, prefix, usable)
        if ep in c[2] and who["img"]:
            E.people.append(who)
        elif ep in c[2]:
            print(f"  没进阵容：{name}（{prefix}）没有定稿的站姿图（皮影 shadow 不算）", file=sys.stderr)
        elif prefix in series_prefixes and who["img"]:
            E.refs.append(who)
    if not E.people:
        raise Fail(f"登记表里没有 {ep} 的定稿人物（「一、历史人物表」里「首次出现的集」写 {ep}、状态定稿、并且 chars/ 里有这个前缀的定稿图）")
    assign_houses(E)
    return E


def stand_image(E, prefix, usable):
    """站姿图：chars/<前缀>stand.png；没有就取该前缀第一张朝右的定稿图（不要道具），再没有就第一张。"""
    rows = [(k, r) for k, r in sorted(E.rows.items()) if k.startswith(f"chars/{prefix}") and usable(r) and "道具" not in r["owner"] and "shadow" not in Path(k).stem]   # 皮影（前史用）不是站姿
    if not rows:
        return None
    for k, r in rows:
        if k == f"chars/{prefix}stand.png":
            return k
    right = [k for k, r in rows if r["facing"] == "右"]
    return (right or [rows[0][0]])[0]


def assign_houses(E):
    """认家族：家族名 → 家族颜色 → 提到同集另一个人 → 名字第一个字（都认不出来 = 「其他」）。"""
    for w in E.people:
        for hn, h in E.houses.items():
            if hn in w["text"] or h["color"].lower() in w["text"].lower():
                w["house"] = hn
                break
    for _ in range(3):
        for w in E.people:
            if w["house"]:
                continue
            for o in E.people:
                if o is not w and o["house"] and o["name"] and o["name"] in w["text"].split("（", 1)[-1]:
                    w["house"] = o["house"]
                    break
    for w in E.people:
        if not w["house"]:
            w["house"] = next((hn for hn in E.houses if hn[0] == w["name"][:1]), "其他")


def load_image(E, rel):
    return Image.open(E.root / rel).convert("RGBA")


def out_dir(a, ep):
    d = Path(a.out) if a.out else ASSETS / "ref" / ep
    d.mkdir(parents=True, exist_ok=True)
    return d


def ep_title(ep):
    for f, key in ((HERE / "stories" / ep / "storyboard.json", "title"), (HERE / "stories" / ep / "episode.json", "core_question")):
        if f.exists():
            try:
                v = json.loads(f.read_text(encoding="utf-8")).get(key)
            except ValueError:
                continue
            if isinstance(v, list):
                v = "".join(v)
            if v:
                return v
    return ""


# ------------------------------------------------------------------ 阵容图
def lineup(E, out, maxw=3300, gap=36, pad=60, flag_gap=26):
    groups = {}
    for w in E.people:
        groups.setdefault(w["house"], []).append(w)
    cols = []
    for house, ws in groups.items():
        ims = [scaled(load_image(E, w["img"]), w["px"] * K) for w in ws]
        flag_rel = E.houses.get(house, {}).get("flag")
        flag = None
        if flag_rel and (E.root / flag_rel).exists():
            flag = load_image(E, flag_rel)
            flag = scaled(flag, 1.1 * max(i.height for i in ims) / flag.height)
        cols.append({"kind": "house", "house": house, "ws": ws, "ims": ims, "flag": flag,
                     "w": (flag.width + flag_gap if flag else 0) + sum(i.width for i in ims) + gap * (len(ims) - 1), "h": max([i.height for i in ims] + ([flag.height] if flag else []))})
    if E.refs:
        ims = [scaled(load_image(E, w["img"]), w["px"] * K) for w in E.refs]
        cols.append({"kind": "ref", "ws": E.refs, "ims": ims, "w": sum(i.width for i in ims) + gap * (len(ims) - 1), "h": max(i.height for i in ims)})
    rows, row, w = [], [], pad
    for c in cols:
        if row and w + c["w"] + pad > maxw:
            rows.append(row)
            row, w = [], pad
        row.append(c)
        w += c["w"] + pad
    rows.append(row)
    W = int(max(sum(c["w"] + pad for c in r) + pad for r in rows))
    row_hs = [int(max(c["h"] for c in r) * 1.05 + 300) for r in rows]
    top = 170
    H = top + sum(row_hs) + 30
    img = paper(W, H)
    d = ImageDraw.Draw(img)
    title = ep_title(E.ep)
    d.text((pad, 36), f"资治通鉴  {E.ep}  角色阵容" + (f"：{title}" if title else ""), fill=INK, font=font("label", 64))
    d.text((pad, 116), "按成片里的大小站在一起（登记表的 PX）；同一家同一个颜色和旗；古人一律交领右衽、席地，圆领只属于司马光", fill=MUTED, font=font("name", 28))
    for ri, r in enumerate(rows):
        y0 = top + sum(row_hs[:ri])
        ground = y0 + row_hs[ri] - 190
        x = pad
        for c in r:
            if c["kind"] == "house":
                hs = E.houses.get(c["house"])
                color = hex_rgb(hs["color"]) if hs else (120, 110, 100)
                bw = int(c["w"] + 40)
                img.alpha_composite(Image.new("RGBA", (bw, row_hs[ri] - 60), color + (40,)), (int(x - 20), y0))
                d = ImageDraw.Draw(img)
                d.rectangle([int(x - 20), ground, int(x - 20 + bw), ground + 22], fill=color)
                d.text((x + 4, y0 + 8), c["house"], fill=color, font=font("label", 64))
                d.text((x + 8, y0 + 84), f"颜色 {hs['color']}" if hs else "没有家族颜色", fill=MUTED, font=font("name", 22))
                fx = x
                if c["flag"] is not None:
                    img.alpha_composite(c["flag"], (int(x), int(ground - c["flag"].height + 22)))
                    fx = x + c["flag"].width + flag_gap
            else:
                d = ImageDraw.Draw(img)
                d.text((x + 4, y0 + 8), "系列角色（大小参照）", fill=INK, font=font("label", 52))
                fx = x
            for wpers, s in zip(c["ws"], c["ims"]):
                img.alpha_composite(s, (round(fx), int(ground - s.height + 12)))
                d = ImageDraw.Draw(img)
                d.text((fx + s.width / 2, ground + 40), wpers["name"], fill=INK, font=font("name", 38), anchor="mt")
                d.text((fx + s.width / 2, ground + 88), f"{wpers['prefix']}  PX {wpers['px']:g}", fill=MUTED, font=font("name", 22), anchor="mt")
                fx += s.width + gap
            x += c["w"] + pad
    f = out / "board_lineup.png"
    img.convert("RGB").save(f)
    print(f, img.size, f"{len(E.people)} 个人物 + {len(E.refs)} 个系列角色，{len(groups)} 个家族")


# ------------------------------------------------------------------ 剪影图
def scene_rows(E, limit=4):
    """有分镜表时：同一镜里出现的人（≥ 2 个），按出现次数排，取前几组。"""
    f = Path(E.storyboard) if E.storyboard else HERE / "stories" / E.ep / "storyboard.json"
    if not f.exists():
        return []
    try:
        sb = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return []
    by_prefix = {w["prefix"]: w for w in E.people + E.refs}
    combos, first = {}, {}
    for s in sb.get("shots", []):
        items = []
        for a in s.get("actors", []) or []:
            img = a.get("img", "")
            w = by_prefix.get(Path(img).name.split("_")[0] + "_")
            if w and (E.root / img).exists() and img not in [i[1] for i in items]:
                items.append((w, img))
        if len({i[0]["prefix"] for i in items}) >= 2:
            key = tuple(sorted(i[1] for i in items))
            combos[key] = combos.get(key, 0) + 1
            first.setdefault(key, (s.get("id"), items))
    order = sorted(combos, key=lambda k: -combos[k])[:limit]
    return [(f"镜头 {first[k][0]}（这样的组合出现 {combos[k]} 镜）", [(w["name"], img, w["px"]) for w, img in first[k][1]]) for k in order]


def silhouette_board(E, out, k2=2.0, pad=60):
    rows = [("阵容（站姿，按成片里的大小）", [(w["name"], w["img"], w["px"]) for w in E.people + E.refs])] + scene_rows(E)
    built = []
    for title, items in rows:
        built.append((title, [(nm, silhouette(scaled(load_image(E, rel), px * k2))) for nm, rel, px in items]))
    W = max(sum(i[1].width for i in r[1]) + 40 * len(r[1]) + 2 * pad for r in built)
    row_h = [max(i[1].height for i in r[1]) + 130 for r in built]
    H = sum(row_h) + 130
    img = paper(W, H, base=(250, 246, 236))
    d = ImageDraw.Draw(img)
    d.text((pad, 30), f"{E.ep} 剪影图：每个人涂成纯黑，一眼分得开吗", fill=INK, font=font("label", 50))
    y = 110
    for (title, r), rh in zip(built, row_h):
        d.text((pad, y), title, fill=MUTED, font=font("name", 30))
        base = y + rh - 60
        x = pad
        for nm, s in r:
            img.alpha_composite(s, (x, base - s.height))
            d = ImageDraw.Draw(img)
            d.text((x + s.width / 2, base + 10), nm, fill=INK, font=font("name", 26), anchor="mt")
            x += s.width + 40
        d.line([(pad, base), (W - pad, base)], fill=(200, 190, 175), width=2)
        y += rh
    f = out / "board_silhouette.png"
    img.convert("RGB").save(f)
    print(f, img.size, f"{len(built)} 行")


# ------------------------------------------------------------------ 场景总览
class Canvas:
    """竖屏 1080×1920 的画布；put() 记下每一层的名字、原图尺寸和屏幕显示 ÷ 原图（≤ 1.3）。"""

    def __init__(self, E):
        self.E, self.img, self.layers = E, Image.new("RGBA", (SW, SH), (0, 0, 0, 255)), []

    def put(self, name, rel, scale, cx=None, bottom=None, top=None, x=None, mul=None):
        im = load_image(self.E, rel)
        s = scaled(im, scale)
        if mul:
            s = tint(s, mul)
        px = round((SW / 2 if cx is None else cx) - s.width / 2) if x is None else x
        py = round(top) if top is not None else round(bottom - s.height)
        self.img.alpha_composite(s, (px, py))
        self.layers.append((name, rel, im.size, scale))
        return s


def set_dirs(E):
    """{目录: [(路径, 行)]}：范围是这一集或系列、状态定稿的 sets/ 图。"""
    out = {}
    for k, r in sorted(E.rows.items()):
        if k.startswith("sets/") and r["status"] == "定稿" and r["scope"] in (E.ep, "系列") and (E.root / k).exists():
            out.setdefault(k.split("/")[1], []).append((k, r))
    return out


def is_base(files):
    stems = {Path(k).stem for k, _ in files}
    return {"sky", "ground"} <= stems


def draw_base(cv, base_files):
    """共用背景：天空、三层山、地面（下面接同一块土层）、水、前景框。返回地面线（y）。"""
    files = {Path(k).stem: k for k, _ in base_files}
    E = cv.E
    if "sky" in files:
        cv.put("天空 sky", files["sky"], 1.25, cx=SW / 2, top=0)
    for stem, bottom, shift in (("ridge_far", 990, -40), ("ridge_mid", 1150, 30), ("ridge_near", 1340, -20)):
        if stem in files:
            im = load_image(E, files[stem])
            s = scaled(im, 1.12)
            cv.img.alpha_composite(s, (round(SW / 2 - s.width / 2 + shift), bottom - s.height))
            cv.layers.append((f"山 {stem}", files[stem], im.size, 1.12))
    if "ground" in files:
        im = load_image(E, files["ground"])
        arr = np.array(im)
        earth = arr[int(arr.shape[0] * 0.45):]
        x0, y, flip = round(SW / 2 - im.width / 2), GROUND_TOP + im.height - 2, False
        while y < SH:                                      # 地面条下面接同一块土层（上下镜像地铺下去，铺到画面底）
            blk = Image.fromarray(earth[::-1] if flip else earth, "RGBA")
            cv.img.alpha_composite(blk, (x0, y))
            y += blk.height - 2
            flip = not flip
        cv.img.alpha_composite(im, (x0, GROUND_TOP))
        cv.layers.append(("地面 ground", files["ground"], im.size, 1.0))
    return GROUND_TOP


def draw_front(cv, base_files):
    files = {Path(k).stem: k for k, _ in base_files}
    if "fore" in files:
        cv.put("前景框 fore（暗）", files["fore"], 1.0, cx=SW / 2, bottom=SH + 6, mul=(0.9, 0.9, 0.9))


def layout_location(cv, files, gtop):
    """长条贴地面线、大件居中、小件一排排摆在前面。"""
    E = cv.E
    info = []
    for k, r in files:
        w, h = Image.open(E.root / k).size
        info.append((k, r, w, h))
    strips = [i for i in info if i[2] / i[3] >= 3.5]
    bigs = sorted([i for i in info if i not in strips and i[2] >= 900], key=lambda i: -i[2] * i[3])
    smalls = [i for i in info if i not in strips and i not in bigs]
    for k, r, w, h in strips:
        cv.put(f"{Path(k).stem}（长条）", k, min(0.9, 1300 / w), cx=SW / 2, bottom=gtop + 55)
    for k, r, w, h in bigs:
        cv.put(f"{Path(k).stem}（大件）", k, min(0.9, 1000 / w), cx=SW / 2, bottom=gtop + 85)
    x, y, row_h = 90, gtop + 150, 0
    for k, r, w, h in smalls:
        s = min(1.0, 300 / w, 330 / h)
        if x + w * s > SW - 90 and x > 90:
            x, y, row_h = 90, y + row_h + 30, 0
        cv.put(Path(k).stem, k, s, x=round(x), bottom=y + h * s)
        x += w * s + 40
        row_h = max(row_h, h * s)


def overview(E, name, files, base_files, out, col_w=820):
    cv = Canvas(E)
    gtop = draw_base(cv, base_files) if base_files else GROUND_TOP
    if not base_files:
        cv.img.paste((238, 230, 214, 255), (0, 0, SW, SH))
    layout_location(cv, files, gtop)
    if base_files:
        draw_front(cv, base_files)
    W = SW + 40 + col_w
    img = paper(W, SH, base=(250, 246, 236))
    img.alpha_composite(cv.img, (0, 0))
    d = ImageDraw.Draw(img)
    x0 = SW + 30
    owner = files[0][1]["owner"]
    d.text((x0, 30), f"{E.ep}  {owner}", fill=INK, font=font("name", 26))
    d.text((x0, 66), "左：竖屏 1080×1920 分层拼的一帧（无人物，自动排版）", fill=MUTED, font=font("name", 22))
    y = 110
    for nm, rel, src, sc in cv.layers:
        im = load_image(E, rel)
        th = scaled(im, min(300 / im.width, 130 / im.height))
        bg = Image.new("RGBA", th.size, (200, 200, 200, 255))
        bg.alpha_composite(th)
        img.alpha_composite(bg, (x0, y))
        d = ImageDraw.Draw(img)
        d.text((x0 + th.width + 12, y + 4), nm, fill=INK, font=font("name", 22))
        d.text((x0 + th.width + 12, y + 34), f"原图 {src[0]}×{src[1]}；屏幕显示 ÷ 原图 = {sc:g}", fill=MUTED, font=font("name", 20))
        y += max(th.height, 66) + 14
        if y > SH - 60:
            break
    f = out / f"board_set_{name}.png"
    img.convert("RGB").save(f)
    print(f, img.size, "最大放大倍数", max(l[3] for l in cv.layers))


def sets(E, out, names):
    dirs = set_dirs(E)
    base = next((fs for n, fs in dirs.items() if is_base(fs)), None)
    places = {n: fs for n, fs in dirs.items() if not is_base(fs)}
    if not places:
        raise Fail(f"登记表里没有 {E.ep} 的定稿布景（sets/<名字>/，范围写 {E.ep} 或系列）")
    if names:
        bad = [n for n in names if n not in places]
        if bad:
            raise Fail(f"没有这些布景：{bad}（{E.ep} 有：{sorted(places)}）")
    for n in names or places:
        overview(E, n, places[n], base, out)


def main():
    ap = argparse.ArgumentParser(description="某一集的阵容图、剪影图、场景总览（board_tj01.py 通用化）")
    ap.add_argument("ep", help="集号，比如 tj01")
    ap.add_argument("what", choices=["lineup", "silhouette", "sets", "all"])
    ap.add_argument("names", nargs="*", help="sets：只出这几个地点（sets/ 下的目录名）")
    ap.add_argument("--out")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--assets-root", default=str(ASSETS))
    ap.add_argument("--storyboard", help="剪影图用的分镜表（默认 video/stories/<集>/storyboard.json）")
    a = ap.parse_args()
    try:
        E = load_ep(a.ep, a.registry, a.assets_root, a.storyboard)
        out = out_dir(a, a.ep)
        if a.what in ("lineup", "all"):
            lineup(E, out)
        if a.what in ("silhouette", "all"):
            silhouette_board(E, out)
        if a.what in ("sets", "all"):
            sets(E, out, a.names)
    except Fail as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
