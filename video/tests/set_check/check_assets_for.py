"""布景缺图时 render.assets_for 报中文错误（不是 traceback）。用法：python video/tests/set_check/check_assets_for.py  退出码 0 = 通过"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "video"))
import render  # noqa: E402

sc = json.loads((ROOT / "video/scenes/ep01v2/shot5.json").read_text(encoding="utf-8"))
sc["set"] = json.loads((ROOT / "video/out/tests/set_check/bad_missing_image.json").read_text(encoding="utf-8"))
try:
    render.assets_for(sc)
except SystemExit as e:
    print(str(e))
    sys.exit(0 if "jinyang_tower.png" in str(e) and "set_check.py" in str(e) else 1)
print("没有报错")
sys.exit(1)
