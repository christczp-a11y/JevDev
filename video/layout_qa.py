"""站位质检：每 0.25 秒算一次画面里每个人物、落地道具占的框，自动找出站位的逻辑错误。

为什么要有它（Chris 2026-09-28）：第 1 关的大婶和小豆子叠在一起、商鞅站在画框松树后面被挡了 30 秒、
爹的姿势图里自带小豆子时又放了一个小豆子（重影）——都是站位问题，靠看缩略图总是漏。

查 4 类错误（持续 1.5 秒以上才报，重影除外；任何一条都要改，除非剧本里写了 overlapOk 说明是故意的）：
1. 重叠：两个人物（或人物和落地道具）左右重叠超过窄的那个宽度的 25%，而且都站在地上；
2. 被松树挡：人物的框有一半以上落在画框左边松树后面（画面 x < 布景 JSON 里 qa.pine，秦国城门是 260；没写 qa.pine 的布景不查这一条）；
3. 出画：人物的框有一半以上在画面外（x < 0 或 x > 1080），但他正在说话；
4. 重影：某个姿势图里已经画了另一个角色（这一集配置 QA.baked，第 0 步第 8 项），这个角色同时又单独出现。

按布景、按集配置（不写死在这个脚本里）：
- 松树宽度是布景的属性：video/sets/<布景>.json 里的 "qa": {"pine": 像素}；
- 姿势图自带角色是这一集的属性：video/episodes/<集>.py 里 CFG["QA"]["baked"]（写法见 video/episode_config.py）。
  集名取场景 JSON 所在目录名（video/scenes/<集>/shotN.json），不在这种目录里就用 --ep 指定。

用法：python video/layout_qa.py [--ep 集名] <剧本.json> [<剧本.json> ...]
有错误时退出码为 1，并打印每个错误第一次出现的时刻和持续多久。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render
from episode_config import episode_of_scene, qa_config
from playwright.sync_api import sync_playwright

W = 1080
MIN_SEC = 1.5       # 走过去时和别人、松树短暂交错是正常的；持续 1.5 秒以上才算站位错误（重影不管多短都算）


def check(scene_path, page_factory, baked=None):
    """baked：姿势图里「自带」的角色，key 是姿势图名字的前缀，value 是画在里面的那个角色的姿势名前缀（这一集的配置 QA.baked）。
    松树宽度 pine 从布景 JSON 的 qa.pine 读（DECISIONS 2026-09-28 站位规则：秦国城门左边那棵大松树挡住 260 像素）。"""
    baked = baked or {}
    scene = render.load_scene(Path(scene_path))
    pine = (scene["set"].get("qa") or {}).get("pine", 0)
    ok_pairs = {tuple(sorted(p)) for a in scene["actors"].values() for p in (a.get("overlapOk") or [])}
    speakers = {id_: a.get("speaker") for id_, a in scene["actors"].items()}
    subs = scene["subtitles"]
    errs = {}
    with page_factory(scene) as page:
        t = 0.0
        while t < scene["duration"]:
            info = page.evaluate(f"layoutBoxes({t})")
            boxes = info["boxes"]
            people = [b for b in boxes if b["kind"] in ("actor", "rig")]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    if a["kind"] == "prop" and b["kind"] == "prop":
                        continue
                    if tuple(sorted((a["id"], b["id"]))) in ok_pairs:
                        continue
                    ov = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
                    narrow = min(a["x1"] - a["x0"], b["x1"] - b["x0"])
                    vert = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
                    if ov > 0.25 * narrow and vert > 0.3 * min(a["y1"] - a["y0"], b["y1"] - b["y0"]):
                        errs.setdefault(("重叠", a["id"] + " × " + b["id"]), []).append(t)
            for p in people:
                w = p["x1"] - p["x0"]
                if pine and min(p["x1"], pine) - max(p["x0"], 0) > 0.5 * w and p["x1"] > 0:
                    errs.setdefault(("被松树挡", p["id"]), []).append(t)
                out = max(0, -p["x0"]) + max(0, p["x1"] - W)
                talking = any(s[0] <= t <= s[1] and s[2] == speakers.get(p["id"]) for s in subs)
                if talking and out > 0.5 * w:
                    errs.setdefault(("说话时出画", p["id"]), []).append(t)
            for p in people:
                for pre, twins in baked.items():
                    if p["pose"].startswith(pre):
                        for q in people:
                            if q is not p and q["pose"].startswith(twins):
                                errs.setdefault(("重影", f"{p['id']}（{p['pose']}里已画了小豆子）+ {q['id']}"), []).append(t)
            t = round(t + 0.25, 2)
    return {k: ts for k, ts in errs.items() if k[0] == "重影" or len(ts) * 0.25 >= MIN_SEC}


class Page:
    def __init__(self, pw):
        self.pw = pw

    def __call__(self, scene):
        self.scene = scene
        return self

    def __enter__(self):
        self.browser, page = render.open_page(self.pw, self.scene)
        return page

    def __exit__(self, *a):
        self.browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="+", help="场景 JSON（shot*.json 要在 Git Bash 里让 shell 展开）")
    ap.add_argument("--ep", help="集名（video/episodes/<集>.py）；不写就取场景 JSON 所在目录名")
    args = ap.parse_args()
    bad = 0
    cfgs = []
    for sp in args.scenes:   # 先把每个场景的集配置都读出来：读不到就退出 1，不往下查（读不到配置时重影检查会被跳过，以前只警告，R11 会漏）
        qa, why = qa_config(args.ep or episode_of_scene(sp))
        if why:
            sys.exit(f"错误：{sp}：没有读到这一集的配置，layout_qa 没有跑：{why}" + chr(10) + "场景 JSON 不在 video/scenes/<集>/ 下时，用 --ep <集名> 指定（配置在 video/episodes/<集>.py）")
        cfgs.append(qa)
    with sync_playwright() as pw:
        for sp, qa in zip(args.scenes, cfgs):
            errs = check(sp, Page(pw), qa["baked"])
            print(f"== {sp}：{'没有站位错误' if not errs else f'{len(errs)} 个站位错误'}")
            for (kind, who), ts in sorted(errs.items(), key=lambda kv: kv[1][0]):
                print(f"  [{kind}] {who}：{ts[0]:.2f}s 起，共 {len(ts) * 0.25:.2f} 秒")
            bad += len(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
