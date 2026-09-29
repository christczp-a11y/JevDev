"""logic_qa 提示词的回归测试：对 ep01v2 每一场每个时刻，生成发给观察员的完整提示词，和金标准 golden_prompts_ep01v2.txt 逐字比对。
金标准 = 第 0 步第 8 项改动之前（d589a8a 时期，动作说明和「横版动画」写死在 logic_qa.py 里）的 logic_qa 对这些场景导出的提示词，所以这个测试等于
「参数化以后，试做集的提示词和以前一字不差」。不真跑观察员（慢、要花钱）。
用法（仓库根目录）：python video/tests/logic_qa/compare_prompts.py    退出码 0 = 一字不差。输出在 video/out/tests/logic_qa/prompts_new.txt。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
import logic_qa  # noqa: E402
import render  # noqa: E402
from episode_config import qa_config  # noqa: E402

qa, why = qa_config("ep01v2")
assert not why, why
out, n, key_words = [], 0, 0
for k in range(1, 7):
    scene = render.load_scene(ROOT / f"video/scenes/ep01v2/shot{k}.json")
    if not scene["actors"]:
        continue   # 没有角色的场次（第 6 场）以前根本跑不了（StopIteration），金标准里没有；由 check_no_actors.py 测
    for t, id_, name in logic_qa.moments(scene):
        band = f"C:/x/out/logic_shot{k}/t{t:05.2f}_band.png"
        zoom = f"C:/x/out/logic_shot{k}/t{t:05.2f}_zoom.png"
        bg = f"C:/x/out/logic_shot{k}/t{t:05.2f}_bg.png" if id_ is None else None
        beat = logic_qa.beat_of(scene, t, id_, name, qa["action_text"])
        out.append(f"### shot{k} t={t}\n{logic_qa.obs_prompt(band, zoom, t, beat, bg, qa['format'])}\n")
        n += 1
        key_words += ("木杆" in beat) + ("金块" in beat)
text = "\n".join(out)
o = ROOT / "video/out/tests/logic_qa"; o.mkdir(parents=True, exist_ok=True)
(o / "prompts_new.txt").write_text(text, encoding="utf-8")
gold = (HERE / "golden_prompts_ep01v2.txt").read_text(encoding="utf-8")
ok = text == gold
print(f"{'PASS' if ok else 'FAIL'}  ep01v2 有角色的 5 场共 {n} 个时刻的提示词和金标准{'一字不差' if ok else '不一致'}；其中 {key_words} 个时刻含「木杆」「金块」（按集配置的动作说明确实被用到了）")
if not ok:
    import difflib
    for l in list(difflib.unified_diff(gold.splitlines(), text.splitlines(), "golden", "new", lineterm="", n=0))[:20]:
        print("   ", l)
sys.exit(0 if ok else 1)
