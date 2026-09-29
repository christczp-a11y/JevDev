"""set_check 的测试样例：从现有的 video/sets/qin_gate.json 出发，每份副本只坏一处（或者只加一处警告），生成到 video/out/tests/set_check/。
用法（仓库根目录）：python video/tests/set_check/make_cases.py"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "video/out/tests/set_check"
OUT.mkdir(parents=True, exist_ok=True)
src = json.loads((ROOT / "video/sets/qin_gate.json").read_text(encoding="utf-8"))
save = lambda name, d: (OUT / name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

save("ok_copy.json", src)                                                                          # 原样副本：通过
d = copy.deepcopy(src); del d["fore"]; save("bad_no_fore.json", d)                                  # 缺前景层
d = copy.deepcopy(src); d["mid"]["items"].append(["jinyang_tower", 1500, 506, 300]); save("bad_missing_image.json", d)   # 引用了不存在的图
d = copy.deepcopy(src); d["far"].pop("y"); d["stage"]["width"] = "3600"; save("bad_fields.json", d)   # far.y 缺、stage.width 写成字符串
d = copy.deepcopy(src); d["mid"]["wallStrip"]["img"] = "rampart"; save("bad_wallstrip_name.json", d)   # wallStrip.img 不叫 wall
d = copy.deepcopy(src); d["far"]["height"] = 500; save("bad_far_too_narrow.json", d)               # 远景图缩放后不到 1080 宽
d = copy.deepcopy(src); d["frame"] = {"items": [["pine", 100, 600, 300]], "filter": "none"}; d.pop("qa"); save("warn_frame_no_pine.json", d)   # 画框层有东西、没写 qa.pine：只警告
d = copy.deepcopy(src); d["frame"] = {"items": [["pine", 100, 600, 300]], "filter": "none"}; d["qa"] = {"pine": 0}; save("ok_frame_pine0.json", d)   # 画框层有东西、明确写了 0：不警告
sc = json.loads((ROOT / "video/scenes/ep01v2/shot1.json").read_text(encoding="utf-8")); sc["camera"] = [[0, 0], [10, 3000]]; save("scene_camera_too_far.json", sc)   # 镜头走出画布范围
sc = json.loads((ROOT / "video/scenes/ep01v2/shot5.json").read_text(encoding="utf-8")); sc["set"] = "jinyang"; save("scene_needs_jinyang.json", sc)          # 要一个没有的布景
