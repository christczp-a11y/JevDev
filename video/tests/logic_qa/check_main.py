"""logic_qa.main 的流程测试（不真跑观察员和 Jev：observe、jev.ask 换成假的）：
1. 没有角色的场次（下集预告）能跑完，报告写出来，不再 StopIteration（第 2 轮问题 7）；
2. 读不到集配置：退出码 1，说清楚，不往下跑（第 2 轮问题 6；以前只警告，动作说明缺了、提示词里的画面形式也不对）；
3. tj01 的 QA.format 是「纸艺动画（这里看的是 2D 引擎画的人物）」，进到提示词里读得通；
4. 没有 TYPESAFE_API_KEY：退出码 1（P8，别人做的，这里只确认没被改坏）。
用法（仓库根目录）：python video/tests/logic_qa/check_main.py    退出码 0 = 全过。输出在 video/out/tests/logic_qa/。"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/logic_qa"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"：{detail}" if detail else ""))


shot6 = json.loads((ROOT / "video/scenes/ep01v2/shot6.json").read_text(encoding="utf-8"))
(OUT / "t_noactors.json").write_text(json.dumps(shot6, ensure_ascii=False, indent=1), encoding="utf-8")   # 没有角色的场次，放在 video/scenes/<集>/ 之外，用 --ep 指定集
assert not shot6["actors"]

# 1 没有角色的场次：main 跑完
os.environ["TYPESAFE_API_KEY"] = "test-not-real"
import logic_qa  # noqa: E402

seen = []
logic_qa.observe = lambda band, zoom, t, beat, bg=None, fmt="": seen.append((t, beat, bg, fmt)) or {"pose": "", "contact": "", "effort": "", "scene": "", "clip": "", "attach": "", "world": ""}
logic_qa.jev.ask = lambda inp, questions: ({q: {"noul": 0.1} for q in questions}, None)
sys.argv = ["logic_qa.py", "--ep", "ep01v2", str(OUT / "t_noactors.json")]
try:
    logic_qa.main()
    done = True
except BaseException as e:   # noqa: BLE001
    done = False
    print("   ", type(e).__name__, e)
rep = ROOT / "video/out/logic_t_noactors/report.json"
check("没有角色的场次：logic_qa.main 跑完，写出报告，每个时刻都是查背景", done and rep.exists() and seen and all(b is not None and "没有角色" in beat for _, beat, b, _ in seen), f"{len(seen)} 个时刻")

# 2 读不到集配置：退出码 1
env = {**os.environ, "TYPESAFE_API_KEY": "test-not-real", "PYTHONIOENCODING": "utf-8"}
py = str(ROOT / ".venv/Scripts/python")
r = subprocess.run([py, str(ROOT / "video/logic_qa.py"), str(OUT / "t_noactors.json")], capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
check("场景不在 video/scenes/<集>/ 下又没写 --ep：退出码 1，说清楚怎么办，没有往下跑", r.returncode == 1 and "没有读到这一集的配置" in r.stderr and "--ep" in r.stderr and not (OUT / "x").exists(), f"退出码 {r.returncode}")
r = subprocess.run([py, str(ROOT / "video/logic_qa.py"), "--ep", "no_such_ep", str(OUT / "t_noactors.json")], capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)
check("--ep 写了不存在的集：退出码 1", r.returncode == 1 and "找不到这一集的配置" in r.stderr, f"退出码 {r.returncode}")
env_nokey = {k: v for k, v in env.items() if k != "TYPESAFE_API_KEY"}
r = subprocess.run([py, str(ROOT / "video/logic_qa.py"), "--ep", "ep01v2", str(OUT / "t_noactors.json")], capture_output=True, text=True, encoding="utf-8", env=env_nokey, cwd=ROOT)
check("没有 TYPESAFE_API_KEY：退出码 1（P8）", r.returncode == 1 and "TYPESAFE_API_KEY" in r.stderr, f"退出码 {r.returncode}")

# 3 tj01 的 format
from episode_config import qa_config  # noqa: E402
qa, why = qa_config("tj01")
check("tj01 的 QA.format = 「纸艺动画（这里看的是 2D 引擎画的人物）」", not why and qa["format"] == "纸艺动画（这里看的是 2D 引擎画的人物）", qa["format"])
prompt = logic_qa.obs_prompt("b.png", "z.png", 1.0, "主角：站着说话", None, qa["format"])
check("提示词里读得通：「这是一部纸艺动画（这里看的是 2D 引擎画的人物）里的一刻」", prompt.startswith("这是一部纸艺动画（这里看的是 2D 引擎画的人物）里的一刻（第 1.0 秒）。"), prompt.splitlines()[0])

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
