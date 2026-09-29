"""2D 布景检查（工作流第 0 步第 9a 项）：每个新地点都要有一份 2D 布景 video/sets/<名字>.json，
层次照 engine.html 的 init / buildSet：far、mid、stage、fore 四层（hills、frame 可选），引用的图都在 video/assets/<dir>/ 里。
第 5 步的 layout_qa、puppet_qa、logic_qa、selfcheck 都经 render.load_scene 读它，没有或缺层缺图就直接报错；这个脚本在那之前把问题查出来。

用法（仓库根目录，命令里的 python 见工作流第一节「运行环境」）：
  python video/set_check.py                           # video/sets/*.json 全部
  python video/set_check.py qin_gate classroom        # 按布景名
  python video/set_check.py video/out/x/copy.json     # 按文件路径（dir 仍然指 video/assets/ 下的目录）
  python video/set_check.py --scenes video/scenes/tj01/shot*.json   # 检查这些场景 JSON 用到的布景（没有这份布景也算问题）
退出码：0 = 全部通过；1 = 有问题。警告（[警告]）不影响退出码。
做法说明见 video/sets/README.md。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # video/
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
LAYERS = ("far", "mid", "stage", "fore")          # engine.html init 必须有的四层
OPTIONAL_LAYERS = ("hills", "frame")               # 可选：中间的山 / 固定在画框上的纸框
TOP_KEYS = {"about", "dir", "name", "qa", *LAYERS, *OPTIONAL_LAYERS}
BAND_W = 1080                                      # 闯关画面宽度（engine.html 的 BAND.w）


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_set(data):
    """返回 (errors, warnings, 用到的图名集合)。"""
    errs, warns, names = [], [], set()

    def need(cond, msg):
        if not cond:
            errs.append(msg)
        return cond

    def item_list(items, where, allow_flip=False):
        if not need(isinstance(items, list), f"{where} 要是列表（每一项 [图名, 中心 x, 底边 y, 显示高度]）"):
            return
        for i, it in enumerate(items):
            ok = (isinstance(it, list) and len(it) in ((4, 5) if allow_flip else (4,)) and isinstance(it[0], str)
                  and all(num(x) for x in it[1:4]))
            if not need(ok, f"{where}[{i}] = {it!r}：要写成 [图名, 中心 x, 底边 y, 显示高度{', 翻转(可选)' if allow_flip else ''}]"):
                continue
            need(it[3] > 0, f"{where}[{i}]（{it[0]}）显示高度要大于 0")
            names.add(it[0])

    def layer(name):
        L = data.get(name)
        if not need(isinstance(L, dict), f"缺少「{name}」层（engine.html init 要 far、mid、stage、fore 四层）"):
            return None
        return L

    d = data.get("dir")
    need(isinstance(d, str) and d, "缺少 dir（图所在的目录，相对 video/assets/，例如 \"sets/qin_gate\"）")
    for k in data:
        if k not in TOP_KEYS:
            warns.append(f"顶层多了不认识的键「{k}」（写错了？引擎不会用它）")
    qa = data.get("qa")
    if qa is not None:
        if need(isinstance(qa, dict), "qa 要是字典，例如 {\"pine\": 260}"):
            if "pine" in qa:
                need(num(qa["pine"]) and qa["pine"] >= 0, "qa.pine 要是不小于 0 的数（画框左边大树挡住的宽度，像素；没有大树就不写）")

    far = layer("far")
    if far is not None:
        need(isinstance(far.get("img"), str), "far.img 要写图名")
        need(num(far.get("parallax")), "far.parallax 要是数（视差，秦国城门是 0.12）")
        need(num(far.get("y")), "far.y 要是数（远景图在画面里的上沿 y；不写引擎会画不出来）")
        need(num(far.get("height")) and far["height"] > 0, "far.height 要是大于 0 的数（远景图显示高度）")
        if isinstance(far.get("img"), str):
            names.add(far["img"])
    for name in ("mid", "stage", "fore", "hills"):
        L = layer(name) if name != "hills" else data.get("hills")
        if L is None:
            continue
        if not need(isinstance(L, dict), f"{name} 要是字典"):
            continue
        need(num(L.get("width")) and L["width"] > 0, f"{name}.width 要是大于 0 的数（这一层的画布宽度）")
        if num(L.get("width")) and L["width"] < BAND_W:
            warns.append(f"{name}.width = {L['width']} 比画面宽度 {BAND_W} 还窄，镜头一动就露出空白")
        if name != "stage":
            need(num(L.get("parallax")), f"{name}.parallax 要是数（视差：远山 0.33、中景 0.55、前景 1.35）")
            item_list(L.get("items"), f"{name}.items")   # buildSet 一定会遍历 hills / mid / fore 的 items（可以是空列表）
        if name == "stage":
            need(num(L.get("offset")), "stage.offset 要是数（这一层画布左边对应的世界 x，秦国城门是 -400）")
            item_list(L.get("items", []), "stage.items")
            g = L.get("ground")
            if g is not None:
                if need(isinstance(g, dict) and isinstance(g.get("img"), str) and num(g.get("top")) and num(g.get("height")),
                        "stage.ground 要写 {\"img\": 图名, \"top\": 相对地面的上沿, \"height\": 高度}"):
                    names.add(g["img"])
        if name == "mid":
            if L.get("behind") is not None:
                item_list(L["behind"], "mid.behind")
            for i, f in enumerate(L.get("fields") or []):
                need(isinstance(f, dict) and all(k in f for k in ("x0", "x1", "top", "bottom", "far", "near")),
                     f"mid.fields[{i}] 要有 x0、x1、top、bottom、far、near")
            ws = L.get("wallStrip")
            if ws is not None:
                if need(isinstance(ws, dict), "mid.wallStrip 要是字典"):
                    need(ws.get("img") == "wall", "mid.wallStrip.img 必须叫 wall：engine.html init 只给「wall」存了拼城墙用的原图（img.wall_raw），别的名字会画不出来")
                    c = ws.get("crop")
                    need(isinstance(c, list) and len(c) == 2 and all(num(x) for x in c) and c[0] < c[1], "mid.wallStrip.crop 要是 [起点, 终点]（原图里切一节的像素范围）")
                    need(num(ws.get("height")) and ws["height"] > 0, "mid.wallStrip.height 要是大于 0 的数")
                    need(num(ws.get("base")), "mid.wallStrip.base 要是数（墙脚 y）")
                    need(num(ws.get("from")) and num(ws.get("to")) and ws["from"] < ws["to"], "mid.wallStrip.from / to 要是数，from < to")
                    need(all(isinstance(g, list) and len(g) == 2 for g in ws.get("gaps", [])), "mid.wallStrip.gaps 要是 [[x0, x1], ...]")
                    if isinstance(ws.get("img"), str):
                        names.add(ws["img"])
    fr = data.get("frame")
    if fr is not None and need(isinstance(fr, dict), "frame 要是字典"):
        item_list(fr.get("items"), "frame.items", allow_flip=True)
        if fr.get("items") and not (isinstance(qa, dict) and "pine" in qa):   # 画框层有东西却没写 qa.pine：layout_qa 不会查「人物被画框左边的东西挡住」
            warns.append("frame（画框层）里有摆件，但没写 qa.pine：layout_qa 不查人物有没有被画框边上的东西挡住。"
                         "画框边上挡住了多宽就写多少（像素）；确认不会挡住任何位置，就写 \"qa\": {\"pine\": 0}")

    # 引用的图都要在 video/assets/<dir>/ 里，并且打得开
    if isinstance(d, str) and d:
        folder = ROOT / "assets" / d
        if not folder.is_dir():
            errs.append(f"图的目录 video/assets/{d}/ 不存在")
        else:
            from PIL import Image
            cutout = {it[0] for L in ("hills", "mid", "stage", "fore", "frame") for it in
                      [*(data.get(L) or {}).get("items", []), *(data.get(L) or {}).get("behind", [])] if isinstance(it, list) and it and isinstance(it[0], str)}
            for n in sorted(names):
                p = folder / f"{n}.png"
                if not p.exists():
                    errs.append(f"引用的图不存在：video/assets/{d}/{n}.png")
                    continue
                try:
                    with Image.open(p) as im:
                        im.load()
                        far = data.get("far")
                        if isinstance(far, dict) and n == far.get("img") and num(far.get("height")) and far["height"] > 0 and num(far.get("parallax")):
                            fw = im.width * far["height"] / im.height   # engine.html buildSet：远景按 far.height 缩放，画两张拼成一条缓存，每帧只画这一条
                            need_w = BAND_W if far["parallax"] else BAND_W / 2
                            if fw < need_w:
                                errs.append(f"远景图 {n}.png 按 far.height={far['height']} 缩放后只有 {fw:.0f} 宽，小于 {need_w:.0f}：镜头一动，画面右边会露出空白。"
                                            f"图要更宽（宽高比至少 {need_w / far['height']:.2f}），或者加大 far.height")
                        if n in cutout and "A" not in im.getbands() and n != "wall":
                            warns.append(f"{n}.png 没有透明通道（{im.mode}）：摆件要抠成透明底，不然会在画面里显出一个方块")
                except Exception as e:  # noqa: BLE001
                    errs.append(f"图打不开：video/assets/{d}/{n}.png（{type(e).__name__}: {e}）")
    return errs, warns, names


def camera_errors(scene_path, scene, data):
    """镜头走过的范围里，每一层的画布够不够宽（engine.html drawLayerCache：第 L 层画在 offset - camX×视差 的位置，画布不够宽就露出空白）。"""
    cams = [k[1] for k in scene.get("camera", []) if isinstance(k, list) and len(k) > 1 and num(k[1])]
    if not cams:
        return []
    lo, hi, out = min(cams), max(cams), []
    for name in ("hills", "mid", "fore"):
        L = data.get(name)
        if isinstance(L, dict) and num(L.get("width")) and num(L.get("parallax")) and L["width"] < BAND_W + hi * L["parallax"]:
            out.append(f"{scene_path}：镜头最远走到 {hi:g}，{name} 层（视差 {L['parallax']:g}）画布宽度要 ≥ {BAND_W + hi * L['parallax']:.0f}，现在只有 {L['width']:g}")
    st = data.get("stage")
    if isinstance(st, dict) and st.get("ground") and num(st.get("width")) and num(st.get("offset")) and (st["offset"] > lo or st["offset"] + st["width"] < hi + BAND_W):
        out.append(f"{scene_path}：镜头在 {lo:g}–{hi:g} 之间走，stage 层画布只盖住世界坐标 {st['offset']:g}–{st['offset'] + st['width']:g}，要盖住 {lo:g}–{hi + BAND_W:g}")
    return out


def resolve(arg):
    p = Path(arg)
    if p.suffix == ".json" or p.exists():
        return p
    return ROOT / "sets" / f"{arg}.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sets", nargs="*", help="布景名或 json 路径；不写 = video/sets/*.json 全部")
    ap.add_argument("--scenes", nargs="+", help="改成检查这些场景 JSON 用到的布景（找不到布景文件也算问题）")
    args = ap.parse_args()
    paths = []
    bad = 0
    if args.scenes:
        seen = set()
        for sp in args.scenes:
            scene = json.loads(Path(sp).read_text(encoding="utf-8"))
            name = scene.get("set")
            if not isinstance(name, str) or not name:
                print(f"❌ {sp}：没有写 set（布景名）"); bad += 1
                continue
            p = ROOT / "sets" / f"{name}.json"
            if not p.exists():
                if name not in seen:
                    print(f"❌ 布景 {name}（{sp} 要用）：找不到 video/sets/{name}.json，做法见 video/sets/README.md"); bad += 1
                seen.add(name)
                continue
            if name not in seen:
                paths.append(p)
            seen.add(name)
            for e in camera_errors(sp, scene, json.loads(p.read_text(encoding="utf-8"))):
                print(f"❌ [镜头范围] {e}"); bad += 1
    else:
        paths = [resolve(a) for a in args.sets] or sorted((ROOT / "sets").glob("*.json"))
    for p in paths:
        if not p.exists():
            print(f"❌ {p}：文件不存在"); bad += 1
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ {p.name}：不是合法的 JSON（第 {e.lineno} 行第 {e.colno} 列，{e.msg}）"); bad += 1
            continue
        errs, warns, names = check_set(data)
        print(f"{'✅' if not errs else '❌'} 布景 {p.stem}：{'四层齐全，引用的 ' + str(len(names)) + ' 张图都在' if not errs else str(len(errs)) + ' 个问题'}")
        for e in errs:
            print(f"    [问题] {e}")
        for w in warns:
            print(f"    [警告] {w}")
        bad += bool(errs)
    print(f"共检查 {len(paths)} 份布景，{bad} 份有问题")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
