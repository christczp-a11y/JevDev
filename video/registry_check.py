"""素材登记表检查（tj01 第 0 步第 3 项；PITFALLS S4、S6、T13、T17、R11、T19）。

用法：
  python video/registry_check.py                        只查登记表本身
  python video/registry_check.py video/scenes/tj01 ...  再查这些场景 JSON（文件或目录）
  --ep 集名                                              场景 JSON 不在 video/scenes/<集>/ 下时，指定它属于哪一集（T19 要用）
  --registry <路径>                                     换一份登记表（试验用）

登记表本身查：
  1. chars、props、rig、sets、brand 下每个 png 都有一行；登记的文件都还在；同一个路径不重复；
  2. 每行 8 列；朝向是 左 / 右 / 正面；尺寸和实际图片一致；状态是 定稿 / 未定稿 / 停用；范围是 系列 / 试做集 / 宣传图 / tj<两位集号>；
  3. 「内含别的角色」和各集配置（video/episodes/<集>.py 的 QA.baked，layout_qa 用的同一份）对得上；
  4. 历史人物表：前缀不重名，也不互为前缀；停用的前缀，对应的素材都标了停用；
     S4 点名的三张（coin、d2_gold_yuanbao、youth_coins）必须是停用。

场景 JSON 查（有一项不过退出码就是 1）：
  1. 用了停用的素材、coinRain 事件、含 yuanbao 的字符串（S4）；
  2. 新集（所在目录不是 ep01、ep01v2）用了「试做集」范围的素材、纸偶，或者 qin_gate、classroom 布景（T19）；
  3. 每个 actor 的 native 和它用到的姿势图登记朝向对账：登记右要 native=1，登记左要 -1，正面不查（T13、T17）；
     姿势图没登记也报错；
  4. 用了「未定稿」的素材只打印警告，不影响退出码。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
DIRS = ["chars", "props", "rig", "sets", "brand"]
FACING = {"左": -1, "右": 1}                 # 登记朝向 → 应有的 native；正面不查
COLS = 8
STATUS = ["未定稿", "停用", "定稿"]         # 「未定稿」要排在「定稿」前面判断（都含「定稿」）
SCOPES = {"系列", "试做集", "宣传图"}         # 另外允许 tj01、tj02……（某一集新画的素材）
PILOT_EPS = {"ep01", "ep01v2"}               # 试做集：可以用试做集的素材；别的集不行（T19）
MUST_STOP = ["props/coin.png", "chars/d2_gold_yuanbao.png", "chars/youth_coins.png"]   # S4 点名的
ASSET_ROW = re.compile(r"^(chars|props|rig|sets|brand)/\S+\.png$")
SIZE = re.compile(r"^(\d+)\s*[×x]\s*(\d+)$")


def status_of(cell):
    return next((s for s in STATUS if cell.startswith(s)), None)


def scope_ok(s):
    return s in SCOPES or re.fullmatch(r"tj\d+", s) is not None


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse(md):
    """返回（素材行 {路径: (行号, 各列)}，人物行 [(行号, 各列)]，解析中发现的问题）。"""
    assets, persons, errs = {}, [], []
    section = ""
    for n, line in enumerate(md.splitlines(), 1):
        if line.startswith("## "):
            section = line
        if not line.startswith("|"):
            continue
        c = split_row(line)
        key = c[0].strip("`")
        if ASSET_ROW.match(key) and not section.startswith("## 二、"):
            if not section.startswith("## 三、"):   # 第三节停用栏也写路径，不是素材行
                errs.append(f"第 {n} 行：{key} 写在了「二、素材表」以外的地方，不算登记")
        elif ASSET_ROW.match(key):
            if key in assets:
                errs.append(f"第 {n} 行：{key} 登记了两次（第 {assets[key][0]} 行）")
            elif len(c) != COLS:
                errs.append(f"第 {n} 行：{key} 应该有 {COLS} 列，实际 {len(c)} 列")
            else:
                assets[key] = (n, c)
        elif section.startswith("## 一、") and c[0] != "人物" and not set("".join(c)) <= set("-: "):
            if len(c) != 6:
                errs.append(f"第 {n} 行：历史人物表每行应有 6 列，实际 {len(c)} 列（{c[0]}）")
            else:
                persons.append((n, c))
    return assets, persons, errs


def load_baked():
    """各集配置（video/episodes/<集>.py 的 QA.baked，layout_qa 用同一份）里「姿势图自带别的角色」的并集。
    返回（{姿势图名前缀: ...}，问题列表）。"""
    sys.path.insert(0, str(HERE))
    try:
        import episode_config
    except Exception as ex:   # noqa: BLE001
        return None, [f"读不了 video/episode_config.py（{type(ex).__name__}: {ex}），「内含别的角色」没法和各集配置对账"]
    baked, errs = {}, []
    for f in sorted((HERE / "episodes").glob("*.py")):
        qa, why = episode_config.qa_config(f.stem)
        if why:
            errs.append(f"集配置 {f.name} 读不出来（{why}），「内含别的角色」没法对账")
        baked.update(qa["baked"])
    if not baked and not errs:
        errs.append("video/episodes/ 里所有集的 QA.baked 都是空的，登记表里「有：谁」的行对不上任何配置")
    return baked, errs


def check_registry(reg_path):
    errs = []
    md = Path(reg_path).read_text(encoding="utf-8")
    assets, persons, e = parse(md)
    errs += e

    disk = {p.relative_to(ASSETS).as_posix() for d in DIRS for p in (ASSETS / d).rglob("*.png")}
    for p in sorted(disk - set(assets)):
        errs.append(f"没登记：{p}")
    for p in sorted(set(assets) - disk):
        errs.append(f"登记了但文件不在：{p}（第 {assets[p][0]} 行）")

    stats = {"左": 0, "右": 0, "正面": 0}
    scopes = {}
    stopped = set()
    for p, (n, c) in sorted(assets.items()):
        _, owner, facing, size, baked, status, _note, scope = c
        if facing not in stats:
            errs.append(f"第 {n} 行 {p}：朝向必须是 左 / 右 / 正面，写的是「{facing}」")
        else:
            stats[facing] += 1
        m = SIZE.match(size)
        if not m:
            errs.append(f"第 {n} 行 {p}：尺寸要写成 宽×高，写的是「{size}」")
        elif p in disk:
            real = Image.open(ASSETS / p).size
            if (int(m.group(1)), int(m.group(2))) != real:
                errs.append(f"第 {n} 行 {p}：登记尺寸 {size}，实际 {real[0]}×{real[1]}（图重新导出过？更新这一行）")
        st = status_of(status)
        if st is None:
            errs.append(f"第 {n} 行 {p}：状态必须以 定稿 / 未定稿 / 停用 开头，写的是「{status}」")
        elif st == "停用":
            stopped.add(p)
        if not (baked.startswith("有") or baked.startswith("无")):
            errs.append(f"第 {n} 行 {p}：「内含别的角色」要写 无 或 有：谁，写的是「{baked}」")
        if not owner:
            errs.append(f"第 {n} 行 {p}：「属于」是空的")
        if not scope_ok(scope):
            errs.append(f"第 {n} 行 {p}：范围必须是 系列 / 试做集 / 宣传图 / tj<集号>，写的是「{scope}」")
        else:
            scopes[scope] = scopes.get(scope, 0) + 1
    for p in MUST_STOP:
        if p in assets and p not in stopped:
            errs.append(f"{p} 必须是停用（S4），现在是「{assets[p][1][5]}」")
        elif p not in assets:
            errs.append(f"{p} 不在登记表里（S4 点名要停用的）")

    # 「内含别的角色」和各集配置的 QA.baked（layout_qa 查重影用的那份）对账
    baked_reg, e = load_baked()
    errs += e
    if baked_reg is not None:
        marked = {Path(p).stem for p, (_, c) in assets.items() if p.startswith("chars/") and c[4].startswith("有")}
        for k in sorted(set(baked_reg) - marked):
            errs.append(f"各集配置的 QA.baked 里有 {k}，登记表里它的「内含别的角色」没写「有：谁」（R11）")
        for k in sorted(marked - set(baked_reg)):
            errs.append(f"登记表说 chars/{k}.png 里画着别的角色，但没有任何一集的 QA.baked 登记它（R11）")

    # 历史人物表：前缀
    toks = []   # (前缀, 行号, 状态)
    for n, c in persons:
        st = status_of(c[5])
        if st is None:
            errs.append(f"第 {n} 行 人物「{c[0]}」：状态必须以 定稿 / 未定稿 / 停用 开头，写的是「{c[5]}」")
        for t in re.findall(r"`([^`]+)`", c[1]):
            if "/" not in t:
                toks.append((t, n, st))
    for i, (a, na, _) in enumerate(toks):
        for b, nb, _ in toks[i + 1:]:
            if a == b:
                errs.append(f"前缀 {a} 重名（第 {na} 行和第 {nb} 行）")
            elif a.startswith(b) or b.startswith(a):
                errs.append(f"前缀 {a}（第 {na} 行）和 {b}（第 {nb} 行）互为前缀")
    for t, n, st in toks:
        if st != "停用":
            continue
        for p, (_, c) in assets.items():
            if p.startswith("chars/") and Path(p).stem.startswith(t) and p not in stopped:
                errs.append(f"人物表第 {n} 行把前缀 {t} 标成停用，但 {p} 的状态是「{c[5]}」")

    print(f"登记表 {reg_path}：素材 {len(assets)} 行（磁盘上 {len(disk)} 张 png），"
          f"朝向 左 {stats['左']} / 右 {stats['右']} / 正面 {stats['正面']}，停用 {len(stopped)} 行，"
          f"范围 {'、'.join(f'{k} {v}' for k, v in sorted(scopes.items()))}，人物 {len(persons)} 行")
    return errs, assets


def scene_files(args):
    files, errs = [], []
    for a in args:
        p = Path(a)
        if p.is_dir():
            js = sorted(p.rglob("*.json"))
            if not js:
                errs.append(f"{a} 里没有 json 文件（目录写错了？）")
            files += js
        elif p.is_file():
            files.append(p)
        else:
            errs.append(f"找不到 {a}")
    return files, errs


def strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)
    elif isinstance(o, str):
        yield o


def episode_of(f):
    """video/scenes/<集>/shotN.json → <集>；不在这种目录里返回 None。"""
    p = Path(f).resolve()
    return p.parent.name if p.parent.parent.name == "scenes" else None


def check_scenes(args, assets, ep_arg):
    files, errs = scene_files(args)
    warns = []
    # 姿势图、道具名 → 登记路径（chars 优先，和 render.assets_for 一样）
    by_name = {}
    for p in sorted(assets, key=lambda p: (not p.startswith("chars/"), p)):
        if p.startswith(("chars/", "props/")):
            by_name.setdefault(Path(p).stem, p)
    row = lambda p: assets[p][1]                                    # noqa: E731
    stopped = {Path(p).stem: p for p in assets if status_of(row(p)[5]) == "停用" and p in by_name.values()}
    pilot_sets = {p.split("/")[1] for p in assets if p.startswith("sets/") and row(p)[7] == "试做集"}
    pilot_rigs = {p.split("/")[1] for p in assets if p.startswith("rig/") and row(p)[7] == "试做集"}

    for f in files:
        fname = f.as_posix()
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception as ex:   # noqa: BLE001
            errs.append(f"{fname}：读不了（{ex}）")
            continue
        ep = ep_arg or episode_of(f)
        hits, used = {}, {}
        for s in strings(j):
            if s == "coinRain":
                k = "事件 coinRain（画方孔圆钱雨，S4）"
            elif "yuanbao" in s.lower():
                k = f"字符串「{s}」含 yuanbao（元宝，S4）"
            elif s in stopped:
                k = f"停用的素材 {stopped[s]}"
            else:
                k = None
            if k:
                hits[k] = hits.get(k, 0) + 1
            if s in by_name:
                used[by_name[s]] = used.get(by_name[s], 0) + 1
        for k, n in sorted(hits.items()):
            errs.append(f"{fname}：用了{k}，出现 {n} 次")

        # 未定稿：只警告
        for p in sorted(used):
            if status_of(row(p)[5]) == "未定稿":
                warns.append(f"{fname}：用了未定稿的素材 {p}（状态「{row(p)[5]}」），出现 {used[p]} 次")

        # T19：新集不许用试做集的素材、纸偶、布景
        if ep is None:
            print(f"提示：{fname} 不在 video/scenes/<集>/ 下，T19（试做集素材、试做集布景）这一项没查；用 --ep 集名指定")
        elif ep not in PILOT_EPS:
            for p in sorted(used):
                if row(p)[7] == "试做集" and status_of(row(p)[5]) != "停用":   # 停用的上面已经报过
                    errs.append(f"{fname}：新集 {ep} 用了试做集的素材 {p}（T19：不许拿试做集的素材凑）")
            if j.get("set") in pilot_sets:
                errs.append(f"{fname}：新集 {ep} 用了试做集的布景 {j['set']}（T19：试做集的布景只作参考）")
            for id_, a in (j.get("actors") or {}).items():
                for rig in {*(a.get("rigs") or {}).values(), *([a["rig"]] if a.get("rig") else [])}:
                    if rig in pilot_rigs:
                        errs.append(f"{fname}：新集 {ep} 的 actor {id_} 用了试做集的纸偶 rig/{rig}（T19）")

        # native 和登记朝向对账（T13、T17）
        seen = set()
        for id_, a in (j.get("actors") or {}).items():
            nat = a.get("native", 1)
            names = [n for _, n in a.get("poses", [])] + list((a.get("sprites") or {}).values())
            for n in names:
                if (id_, n) in seen:
                    continue
                seen.add((id_, n))
                p = by_name.get(n)
                if p is None:
                    errs.append(f"{fname}：actor {id_} 的姿势图 {n} 登记表里没有（T13：每张图都要登记朝向）")
                    continue
                facing = row(p)[2]
                if facing in FACING and FACING[facing] != nat:
                    errs.append(f"{fname}：actor {id_} 的 native={nat}，但姿势图 {n} 原图朝{facing}，应该 native={FACING[facing]}（T13、T17）")
    print(f"场景 JSON：查了 {len(files)} 个文件")
    return errs, warns


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="素材登记表检查")
    ap.add_argument("scenes", nargs="*", help="场景 JSON 或目录（可以不写）")
    ap.add_argument("--registry", default=str(ASSETS / "REGISTRY.md"))
    ap.add_argument("--ep", help="集名；场景 JSON 不在 video/scenes/<集>/ 下时用")
    a = ap.parse_args()
    errs, assets = check_registry(a.registry)
    warns = []
    if a.scenes:
        e, warns = check_scenes(a.scenes, assets, a.ep)
        errs += e
    for w in warns:
        print("警告：" + w)
    for e in errs:
        print("错误：" + e)
    print(("通过" if not errs else f"不通过：{len(errs)} 个问题") + (f"（{len(warns)} 条警告）" if warns else ""))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
