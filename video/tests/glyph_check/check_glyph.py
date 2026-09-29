"""字形覆盖检查（video/glyph_check.py）的测试：
1 试做集六场：退出 0；2 塞了子集外生僻字的副本：退出 1，报出哪一场、哪个位置、哪个字，给出重新子集化的命令；
3 ZCOOL 缺、Noto 补的字（絺）不算缺；字库本身缺的字，报「字库本身没有」；4 每种要上画面的文字字段都会被查到；
5 coverage.json 和现有 woff2 的 cmap 一致；6 build_stage3d.py qa / render 和分场脚本模板渲染前的自动检查。
用法（仓库根目录）：python video/tests/glyph_check/check_glyph.py    退出码 0 = 全过。输出在 video/out/tests/glyph_check/。"""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/glyph_check"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "video"))
sys.stdout.reconfigure(encoding="utf-8")
import glyph_check as gc  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"：{detail}" if detail else ""))


py = str(ROOT / ".venv/Scripts/python")
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
sh = lambda *a, **e: subprocess.run([py, *a], capture_output=True, text=True, encoding="utf-8", env={**env, **e}, cwd=ROOT)
cov = gc.load_coverage()
# 不在字符集里的生僻字（每次现选，免得以后字符集变了测试就失效）
rare = [c for c in "龘麤𠮷㐀靐" if c not in cov["charset"]]
check("有可用的测试字：至少两个不在字符集里的生僻字", len(rare) >= 2, str(rare))
R1, R2 = rare[0], rare[1]
scenes = sorted((ROOT / "video/scenes/ep01v2").glob("shot*.json"))

# 1
r = sh("video/glyph_check.py", *map(str, scenes))
check("试做集六场：退出码 0", r.returncode == 0 and "6 个场景" in r.stdout, f"退出码 {r.returncode}")

# 2 塞了子集外生僻字：字幕（Noto）、横幅（Noto）、卷号（ZCOOL）、人名牌名字（ZCOOL）
bad = OUT / "scenes"
bad.mkdir(exist_ok=True)
for p in scenes:
    (bad / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
sc = json.loads((bad / "shot1.json").read_text(encoding="utf-8"))
sc["subtitles"][3][3] += R1
sc["events"].append({"type": "banner", "t": 1, "d": 2, "text": "第 2 关：" + R2})
sc["title"]["kicker"] += R1
sc["nametags"] = [{"id": "shangyang", "name": "商鞅" + R2, "house": "", "color": None, "t0": 1, "t1": 5, "hold": 2}]
(bad / "shot1.json").write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
r = sh("video/glyph_check.py", *map(str, sorted(bad.glob("shot*.json"))))
err = r.stderr
check("塞了子集外生僻字的副本：退出码 1", r.returncode == 1, f"退出码 {r.returncode}")
check("报出哪一场、哪个位置、缺哪个字（字幕、横幅、卷号、人名牌各一条）",
      all(k in err for k in ("第 1 场", "字幕[3]", "事件[", "banner", "卷号", "人名牌[0]", R1, R2)) and "第 2 场" not in err, err.splitlines()[0][:100])
check("给出重新子集化的一条命令，并说明字库本身没有的字重新子集化也没用", "python video/vendor/fonts/subset_fonts.py" in err and "字库本身没有" in err)

# 3 ZCOOL 缺、Noto 补
check("fonts.css 里 ZCOOL 缺、由 Noto 补的字读得出来（絺在里面）", "絺" in cov["zcool_fallback"] and len(cov["zcool_fallback"]) > 100 and "絺" not in cov["zcool"] and "絺" in cov["noto"], f"{len(cov['zcool_fallback'])} 个")
ok_sc = copy.deepcopy(json.loads(scenes[0].read_text(encoding="utf-8")))
ok_sc["nametags"] = [{"id": "x", "name": "絺疵", "house": "智家", "color": None, "t0": 1, "t1": 5, "hold": 2}]
ok_sc["title"]["kicker"] = "絺"
(OUT / "ok_chi.json").write_text(json.dumps(ok_sc, ensure_ascii=False), encoding="utf-8")
check("ZCOOL 缺、Noto 补的字（絺）出现在人名牌、卷号（都是 ZCOOL 的字）：不算缺", gc.check_files([OUT / "ok_chi.json"]) == [])
c2 = copy.deepcopy(cov)
c2["noto"].discard("好")
miss = gc.missing_chars("好", "noto", c2)
check("字库本身缺的字（字符集里有、cmap 里没有）：报「字库本身没有」", miss and "字库本身没有" in miss[0][1], str(miss))
check("……ZCOOL 里有的话，ZCOOL 的字段照样能画（Noto 缺不影响）", gc.missing_chars("好", "zcool", c2) == [])
c3 = copy.deepcopy(cov)
c3["zcool"].discard("好")
c3["noto"].discard("好")
check("ZCOOL 缺、Noto 也缺：ZCOOL 的字段报缺", gc.missing_chars("好", "zcool", c3) != [])
punct = " abcXYZ019，。！？「」…—·"
check("空白、ASCII、常用标点不算缺", gc.missing_chars(punct, "noto", cov) == [] and gc.missing_chars(punct, "zcool", cov) == [])

# 4 每种要上画面的文字字段都查到
full = {"title": {"kicker": R1, "lines": [R1, "[[" + R1 + "]]"]}, "footer": R1, "hud": {"label": R1},
        "subtitles": [[1, 2, R1, R1]], "nametags": [{"id": "a", "name": R1, "house": R1}],
        "actors": {"a": {"bubbles": [[1, 2, R1]]}},
        "props": [{"type": "sprite", "img": "p", "text": [[R1, 0, 0, 40, "#000"]], "say": [[1, 2, R1]]}, {"type": "board", "texts": [[0, [R1, "!" + R1]]]}, {"type": "block", "reward": R1}],
        "events": [{"type": "banner", "text": R1}, {"type": "choice", "options": [R1, R1], "label": R1, "after": R1}, {"type": "nope", "items": [[1, 2, R1]]},
                   {"type": "badges", "items": [[1, R1]]}, {"type": "stamp", "text": R1}, {"type": "birds", "text": R1}]}
(OUT / "full.json").write_text(json.dumps(full, ensure_ascii=False), encoding="utf-8")
wheres = [i["where"] for i in gc.check_files([OUT / "full.json"])]
want = ["卷号", "标题第 1 行", "标题第 2 行", "出处行", "计分牌标签", "字幕[0]（1–2 秒）说话人", "字幕[0]（1–2 秒）", "人名牌[0]（a）名字", "人名牌[0]（a）家名", "角色 a 的气泡", "上的字", "的话", "告示牌[1]（0 秒）",
        "奖励字", "事件[0]（banner）", "选项 1", "选项 2", "标题", "揭晓后的话", "事件[2]（nope）", "事件[3]（badges）", "事件[4]（stamp）", "事件[5]（birds）"]
lost = [w for w in want if not any(w in x for x in wheres)]
check("每种要上画面的文字字段都会被查（卷号、标题、出处、字幕、说话人、计分牌、人名牌、气泡、道具字、告示牌、横幅、选择题、反例卡、徽章、印章、纸鸟）", not lost and len(wheres) >= 24, f"漏了 {lost}；共 {len(wheres)} 处")

# 5 coverage.json 和 woff2 的 cmap 一致
try:
    from fontTools.ttLib import TTFont
    fonts = ROOT / "video/vendor/fonts"
    same = True
    for key, name in (("noto", "NotoSansSC-subset.woff2"), ("zcool", "ZCOOLKuaiLe-subset.woff2")):
        cmap = {chr(c) for c in TTFont(str(fonts / name)).getBestCmap() if c >= 0x20}
        same &= cmap == cov[key]
    check("coverage.json 和现有两个 woff2 的 cmap 一致（改了字体没重新生成 coverage.json 就会不一致）", same)
except ImportError:
    print("SKIP  coverage.json 和 woff2 的对账：没装 fonttools / brotli（pip install fonttools brotli）")

# 6 接进流程
r = sh("video/stage3d/build_stage3d.py", "qa", "1", STAGE3D_SCENES=str(bad), STAGE3D_OUT=str(OUT / "out"))
check("build_stage3d.py qa：先查缺字，退出码 1，不往下渲（几秒就返回）", r.returncode == 1 and "缺字：第 1 场" in r.stderr and "穿帮" not in r.stdout, f"退出码 {r.returncode}")
r = sh("video/stage3d/build_stage3d.py", "render", STAGE3D_SCENES=str(bad), STAGE3D_OUT=str(OUT / "out"))
check("build_stage3d.py render：渲染前先查缺字，退出码 1", r.returncode == 1 and "缺字：第 1 场" in r.stderr and not list((OUT / "out").glob("*.mp4")), f"退出码 {r.returncode}")
import build_ep01_v2 as b  # noqa: E402
import episode_build as eb  # noqa: E402
cfg = copy.deepcopy(b.CFG)
cfg["TITLE"] = {"kicker": "资治通鉴 · 卷二" + R1, "lines": ["一根木头，怎么让", "秦国人开始[[相信]]？"]}
try:
    eb.main(cfg, b.SHOTS, ["--no-render", "--voice", str(ROOT / "video/tests/fixtures/ep01v2_voice"), "--scenes-out", str(OUT / "eb_scenes"), "--out", str(OUT / "eb_out")])
    code = None
except SystemExit as e:
    code = e.code
check("分场脚本模板：生成场景 JSON 以后、渲染之前查缺字，退出码 1（--no-render 也查）", code == 1, f"退出码 {code}")

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
