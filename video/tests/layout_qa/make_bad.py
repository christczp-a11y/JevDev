"""layout_qa 的测试场景：从已提交的 video/scenes/ep01v2/ 出发，造两份故意有站位错误的副本，生成到 video/out/tests/layout_qa/。
用法（仓库根目录）：python video/tests/layout_qa/make_bad.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "video/out/tests/layout_qa"
OUT.mkdir(parents=True, exist_ok=True)
load = lambda n: json.loads((ROOT / f"video/scenes/ep01v2/{n}.json").read_text(encoding="utf-8"))
save = lambda n, d: (OUT / n).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
sc = load("shot1")
sc["actors"]["douzi"]["show"][1] += 3.0                  # 小豆子晚退场 3 秒：和爹（dad2_grab 里自带小豆子）同时出现 → 重影、重叠
sc["actors"]["shangyang"]["keys"] = [[0, 100, "", 1]]    # 商鞅站到 x=100 → 被松树挡、说话时出画
save("bad_shot1.json", sc)
c = load("shot5")
c["actors"]["kid"]["keys"] = [[0, 100, "", 1]]           # 教室里站在 x=100：教室没有大松树（布景没写 qa.pine），不该报「被松树挡」
save("classroom_left.json", c)
