"""人名牌测试（reviewer 第 2 轮问题 1、2，工作流第 0 步第 9 项，T23、T24）。
用法（仓库根目录）：python video/tests/nametag/check_nametags.py     退出码 0 = 全过。输出（截图）在 video/out/tests/nametag/。
先用 make_scenes.py 生成带人名牌的场景 JSON（试做集的角色 + 测试用系列表），再在 3D 舞台和 2D 引擎里查。"""
import json
import os
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/nametag"
SCENES = OUT / "scenes"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["STAGE3D_SCENES"] = str(SCENES)
os.environ["STAGE3D_OUT"] = str(OUT / "stage3d")
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT / "video/stage3d")); sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
import build_stage3d as bs  # noqa: E402
import imgdiff  # noqa: E402
import make_scenes  # noqa: E402
import render  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"[{'通过' if ok else '不通过'}] {name}" + (f"：{detail}" if detail else ""))


SAFE_L, SAFE_R, SAFE_TOP = 1080 * 0.07, 1080 * 0.93, 270
make_scenes.build(SCENES)
tagged = json.loads((SCENES / "shot1.json").read_text(encoding="utf-8"))
check("场景 JSON 里有 nametags，每张牌有 name、house、color、t0、t1、hold；颜色来自系列表（同一个家同色，颜色占位的家是 null）",
      all({"id", "name", "house", "color", "t0", "t1", "hold"} <= set(t) for t in tagged["nametags"])
      and {t["name"]: t["color"] for t in tagged["nametags"]} == {"商鞅": "#2f6d9a", "大婶": "#2f6d9a", "小豆子": "#2f6d9a", "爹": None, "司马光": "#7a4fa3", "小伙": None},
      str([(t["name"], t["color"]) for t in tagged["nametags"]]))
check("同一个人的两个角色 id（shangyang、shangyang2）只出一张牌", sum(t["name"] == "商鞅" for t in tagged["nametags"]) == 1)
src = (ROOT / "video/stage3d/stage.html").read_text(encoding="utf-8")
check("3D：人名牌画在 2D 特效层（选择题、横幅）之下（drawNametags 在 renderOverlay 之前）", src.index("  drawNametags(t);   // 人名牌") < src.index("ENG.renderOverlay(t, overlayC)"))

with sync_playwright() as p:
    # ---- placeNametags 单元测试（engine.html 里的纯函数，2D、3D 共用）----
    browser = p.chromium.launch(executable_path=render.CHROMIUM)
    pg = browser.new_page(viewport={"width": 1080, "height": 1920})
    pg.goto((ROOT / "video/engine.html").as_uri())
    B = {"xmin": 75.6, "xmax": 1004.4, "tmin": 290, "tmax": 1400}
    place = lambda items: pg.evaluate("([i, b]) => window.placeNametags(i, b)", [items, B])
    mk = lambda ax, w=300, top0=1200: {"ax": ax, "top0": top0, "w": w, "h": 62}

    def ok_geometry(items, put):
        good = True
        for it, r in zip(items, put):
            good &= abs(r["cx"] - it["ax"]) <= it["w"] / 2 - 45 + 1e-6 or (it["ax"] < B["xmin"] + 45 or it["ax"] > B["xmax"] - 45)   # 指针落在牌子平直的那一段
            good &= B["xmin"] - 1e-6 <= r["cx"] - it["w"] / 2 and r["cx"] + it["w"] / 2 <= B["xmax"] + 1e-6 and B["tmin"] <= r["top"] and r["top"] + it["h"] <= B["tmax"]   # 在安全区里
        return good

    def overlap(a, ia, b, ib):
        return a["cx"] - ia["w"] / 2 < b["cx"] + ib["w"] / 2 and b["cx"] - ib["w"] / 2 < a["cx"] + ia["w"] / 2 and a["top"] < b["top"] + ib["h"] and b["top"] < a["top"] + ia["h"]

    items = [mk(400), mk(800)]; put = place(items)
    check("摆放：两张牌离得远：不挪，牌子正对本人", all(abs(r["cx"] - it["ax"]) < 1e-6 and r["top"] == 1200 for it, r in zip(items, put)))
    items = [mk(500), mk(620)]; put = place(items)
    check("摆放：两张牌横向挤：横着错开，指针都还在本人脚下（偏差 ≤ w/2 - 45），不重叠，同高",
          ok_geometry(items, put) and not overlap(put[0], items[0], put[1], items[1]) and put[0]["top"] == put[1]["top"] and not any(r["clash"] for r in put),
          str([(round(r["cx"]), r["top"]) for r in put]))
    items = [mk(500), mk(520)]; put = place(items)
    check("摆放：挤到横着推不开：后一张竖着叠到下面，指针仍在本人脚下，不重叠",
          ok_geometry(items, put) and not overlap(put[0], items[0], put[1], items[1]) and put[1]["top"] > put[0]["top"] and not any(r["clash"] for r in put),
          str([(round(r["cx"]), r["top"]) for r in put]))
    items = [mk(120), mk(990)]; put = place(items)
    check("摆放：脚在画面边上：牌子夹回左右 7% 的安全区里", ok_geometry(items, put), str([(round(r["cx"]), r["top"]) for r in put]))
    tight = pg.evaluate("([i, b]) => window.placeNametags(i, b)", [[mk(500), mk(520)], {**B, "tmin": 1200, "tmax": 1270}])
    check("摆放：可用高度只够一张、横着也推不开：clash = true（不悄悄重叠）", tight[1]["clash"] and not tight[0]["clash"])
    items = [mk(238, 280, 1252), mk(843, 280, 1245), mk(739, 320, 1263)]; put = place(items)   # 第 1 场 9.0 秒：reviewer 发现「大婶的牌子指着小豆子」的那一帧
    check("摆放：第 1 场 9.0 秒的三张牌：每张牌的指针都离本人最近", all(min(range(3), key=lambda j: abs(items[j]["ax"] - items[i]["ax"])) == i for i in range(3)) and ok_geometry(items, put) and not any(r["clash"] for r in put))
    browser.close()

    # ---- 3D 舞台：第 1 场 ----
    srv = bs.serve()
    browser, page, scene = bs.open_stage(p, 1, srv)
    stats = {s["id"]: s for s in page.evaluate("window.nametagStats()")}
    foot = lambda i, t: page.evaluate(f"window.nametagFoot({json.dumps(i)}, {t})")
    inview = lambda f: bool(f) and f["front"] and SAFE_L + 45 <= f["fx"] <= SAFE_R - 45 and SAFE_TOP <= f["fy"] <= 1312

    # T24：从第一次入画开始计 2 秒
    sy = stats["shangyang"]
    check("T24：商鞅 2D 里 2.79 秒出场，但 3D 镜头 8 秒以后才拍到他：牌子从他第一次入画（脚在安全区里）的时刻开始计，不是 2.79 秒",
          sy["ts"] > 5 and inview(foot("shangyang", sy["ts"])) and not inview(foot("shangyang", sy["ts"] - 0.1)) and not inview(foot("shangyang", sy["t0"])),
          f"ts={sy['ts']}（前一步 {sy['ts'] - 0.1:.2f} 秒不在画面里）")
    check("T24：牌子窗口 = 入画那一刻起 2 秒，画出来的时间 ≥ 1.5 秒", abs(sy["te"] - sy["ts"] - 2) < 0.06 and sy["secs"] >= 1.5, f"[{sy['ts']}, {sy['te']}]，画出 {sy['secs']} 秒")
    check("T24：商鞅、大婶、小豆子、爹、小伙的牌子都画够 1.5 秒", all(stats[i]["secs"] >= 1.5 for i in ("shangyang", "auntie0", "douzi", "dad", "youth")), str({i: stats[i]["secs"] for i in stats}))
    host = stats["host"]
    check("T24：司马光第一次入画在书桌机位，0.9 秒以后镜头切到脚在安全区外的特写：牌子只画出很短一段，没有硬压在袍子上", host["secs"] < 1.5, f"画出 {host['secs']} 秒")
    errs = bs.tag_errors(1, page)
    check("build_stage3d.py frame 的人名牌检查：画出来不到 1.5 秒的只报司马光一张", [e[4] for e in errs if "只画出" in e[3]] == ["「司马光」"], str([(e[3][:12], e[4]) for e in errs]))
    # 实际画了多少帧：窗口前、窗口中、窗口后
    page.evaluate(f"window.renderFrame({sy['ts'] - 0.3})")
    before = [q["id"] for q in page.evaluate("window.nametagPlacements()")]
    page.evaluate(f"window.renderFrame({sy['ts'] + 0.6})")
    during = [q["id"] for q in page.evaluate("window.nametagPlacements()")]
    page.evaluate(f"window.renderFrame({sy['te'] + 0.3})")
    after = [q["id"] for q in page.evaluate("window.nametagPlacements()")]
    drawn = {s["id"]: s["drawn"] for s in page.evaluate("window.nametagStats()")}
    check("T24：窗口之前不画、窗口里画、窗口之后不画；nametagStats 记录实际画了几帧",
          "shangyang" not in before and "shangyang" in during and "shangyang" not in after and drawn["shangyang"] == 1, f"前 {before}、中 {during}、后 {after}、画了 {drawn['shangyang']} 帧")

    # T23：9.0 秒三张牌（reviewer 的用例）：每张牌的指针尖在本人脚下、离别人更远；牌子在安全区里；不重叠
    page.evaluate("window.renderFrame(9.0)")
    pl = page.evaluate("window.nametagPlacements()")
    page.screenshot(path=str(OUT / "s1_t009.00.png"))
    dist = lambda q, o: abs(q["tipX"] - o["footX"])
    own = all(abs(q["tipX"] - q["footX"]) <= 40 and all(dist(q, q) <= dist(q, o) for o in pl) for q in pl)
    check("T23：第 1 场 9.0 秒（三张牌挤在一起）：每张牌指针尖离本人脚底横向 ≤ 40 像素，而且比离别人的近", len(pl) == 3 and own, str([(q["name"], round(q["tipX"] - q["footX"], 1)) for q in pl]))
    inside = all(SAFE_L - 1e-6 <= q["cx"] - q["w"] / 2 and q["cx"] + q["w"] / 2 <= SAFE_R + 1e-6 and SAFE_TOP + 20 <= q["top"] and q["top"] + q["h"] <= q["bottom"] for q in pl)
    check("T23：三张牌都夹在安全区里（左右各留 7%、上沿不压计分牌、下沿不压字幕）", inside)
    no_overlap = not any(pl[i]["cx"] - pl[i]["w"] / 2 < pl[j]["cx"] + pl[j]["w"] / 2 and pl[j]["cx"] - pl[j]["w"] / 2 < pl[i]["cx"] + pl[i]["w"] / 2
                         and pl[i]["top"] < pl[j]["top"] + pl[j]["h"] and pl[j]["top"] < pl[i]["top"] + pl[i]["h"] for i in range(len(pl)) for j in range(i + 1, len(pl)))
    check("T23：三张牌互相不重叠", no_overlap and not any(q["clash"] for q in pl))

    # 牌子中途因为脚离开安全区消失：淡出，不直接消失（司马光的脚 0.9 秒离开：书桌机位切到特写）
    def alpha_at(t):
        page.evaluate(f"window.renderFrame({t})")
        q = [x for x in page.evaluate("window.nametagPlacements()") if x["id"] == "host"]
        return q[0]["alpha"] if q else None
    a_mid, a_late, a_last, a_gone = alpha_at(0.6), alpha_at(0.75), alpha_at(0.85), alpha_at(0.95)
    check("牌子中途因为脚离开安全区消失：先淡出再消失，不是一下子没了（0.6、0.75、0.85 秒的不透明度递减，0.95 秒已经不画）",
          a_mid and a_late and a_last and a_mid > a_late > a_last > 0 and a_gone is None, f"{a_mid}、{a_late}、{a_last}、{a_gone}")
    # 四行字幕：说话人标签顶得更高，牌子下沿跟着上移
    page.evaluate("window.renderFrame(49.6)")
    pl4 = page.evaluate("window.nametagPlacements()")
    page.screenshot(path=str(OUT / "s1_t049.60.png"))
    y0 = pl4[0]["bottom"] + 58 if pl4 else 0
    lines = round((2 * (1600 - y0) - 40) / 76) if pl4 else 0
    check("字幕四行：说话人标签顶在 1378，牌子下沿在 1370 以上，不叠", len(pl4) == 2 and lines == 4 and all(q["top"] + q["h"] <= q["bottom"] <= 1370 for q in pl4),
          f"{len(pl4)} 张牌，字幕 {lines} 行，下沿上限 {pl4[0]['bottom'] if pl4 else '-'}")
    # 爹和小伙的脚 50 秒左右几乎在同一个横坐标，四行字幕又把下沿压低了：一张放到另一张上面，不重叠，也不出安全区
    page.evaluate("window.renderFrame(50.6)")
    pl5 = page.evaluate("window.nametagPlacements()")
    page.screenshot(path=str(OUT / "s1_t050.60.png"))
    ov = [(pl5[i], pl5[j]) for i in range(len(pl5)) for j in range(i + 1, len(pl5))
          if pl5[i]["cx"] - pl5[i]["w"] / 2 < pl5[j]["cx"] + pl5[j]["w"] / 2 and pl5[j]["cx"] - pl5[j]["w"] / 2 < pl5[i]["cx"] + pl5[i]["w"] / 2 and pl5[i]["top"] < pl5[j]["top"] + pl5[j]["h"] and pl5[j]["top"] < pl5[i]["top"] + pl5[i]["h"]]
    check("50.6 秒爹和小伙的脚重合、四行字幕压低了下沿：两张牌叠放，不重叠，都在安全区里，指针横向仍在本人脚下",
          len(pl5) == 2 and not ov and all(SAFE_TOP + 20 <= q["top"] and q["top"] + q["h"] <= q["bottom"] and abs(q["tipX"] - q["footX"]) <= 40 for q in pl5), str([(q["name"], round(q["top"])) for q in pl5]))
    # frame 质检的「人名牌摆不开」：nametagClashes 找出来、tag_errors 报出来（把 engine 的摆放函数换成永远摆不开的，测这条线接对了）
    page.evaluate("() => { document.getElementById('engine').contentWindow.placeNametags = items => items.map(() => ({ cx: 0, top: 0, clash: true })); }")
    cl = page.evaluate("window.nametagClashes()")
    check("摆不开会被 frame 质检报出来（tag_errors 里有「人名牌摆不开」，带人名）", cl and any("摆不开" in e[3] and "「" in e[4] for e in bs.tag_errors(1, page)), str(cl[:2]))
    browser.close()
    srv.shutdown()

    # ---- 2D 引擎：牌子出现，hideNametags 时不画（质检截图用）----
    sc2d = render.load_scene(SCENES / "shot1.json")
    plain = json.loads(json.dumps(sc2d)); plain.pop("nametags")
    shots = {}
    for name, sc, hide in (("有牌", sc2d, False), ("藏起来", sc2d, True), ("没有名单", plain, False)):
        b2, pg2 = render.open_page(p, sc, hide_nametags=hide)
        shots[name] = np.asarray(Image.open(BytesIO(render.grab(pg2, 9.0, "image/png"))).convert("RGB")).astype(np.int16)
        b2.close()
    Image.fromarray(shots["有牌"].astype("uint8")).save(OUT / "2d_t009.00.png")
    check("2D：9.0 秒有人名牌（和没有名单时不一样）", not imgdiff.report(shots["有牌"], shots["没有名单"])["same"])
    r = imgdiff.report(shots["藏起来"], shots["没有名单"])
    check("2D：hide_nametags=True（logic_qa、puppet_qa、selfcheck 用）：画面和没有名单时一样", r["same"], imgdiff.describe(r))

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
