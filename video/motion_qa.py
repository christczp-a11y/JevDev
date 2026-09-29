"""动作质检：同一段剧情，「改前」和「改后」哪个人物动作更好？（成对比较，比打绝对分稳）

流程：
  1. 两个版本各截一张连续帧的联系表（镜头跟着人物，每秒 6 帧）
  2. Claude（看图模型）分别描述每张表里人物怎么动：只写事实、不打分、看不到另一个版本
     每张表两个观察员独立描述（Claude 看图偶尔会看错）
  3. Jev 拿两段描述做成对判断：更流畅 / 更精细 / 更看得懂 / 更像专业动画；a、b 两种顺序都问，抵消位置偏差
     结果 = 「改后」赢的概率，四种组合（2 个观察员 × 2 种顺序）取平均

用法：python video/motion_qa.py <配置.json>
配置：{"beat": "这段剧情", "before": {"scene": ..., "t0": .., "t1": .., "actor": ..}, "after": {...}}
一开头就检查环境变量 TYPESAFE_API_KEY，没有就非 0 退出（P8）：不等截图、观察员跑完才报。
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")   # 不设 PYTHONIOENCODING 时，中文报错也能正常显示，不变成 \u 转义（E5、E7）

import contact  # noqa: E402
from jevdev import jev  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

OBSERVER = "claude-opus-5-5"
OBS_SCHEMA = {"type": "object", "properties": {
    "body_parts": {"type": "string", "description": "逐帧看，人物身上哪些部位在动、怎么动（头、眼睛、嘴、手臂、手、腿、脚、身体前倾后仰、衣服或飘带）；哪些部位从头到尾一动不动"},
    "locomotion": {"type": "string", "description": "人物走、跑、跳时腿和脚怎么动；脚和地面的关系（有没有像溜冰一样滑、有没有悬空、落地有没有缓冲）。没有走跑就写「无」"},
    "transitions": {"type": "string", "description": "动作和动作之间怎么衔接：有没有从一个姿势突然跳到另一个姿势；大动作前有没有预备动作（比如跳之前先蹲），之后有没有缓冲"},
    "face": {"type": "string", "description": "表情、眼睛、嘴在这段里有没有变化，怎么变"},
    "props": {"type": "string", "description": "人物和道具怎么配合：手有没有真的握住道具，道具跟不跟手，重量感如何。没有道具就写「无」"},
    "flaws": {"type": "string", "description": "看得出的穿帮或别扭的地方（部件错位、关节断开、穿进地里、挡住脸等）。没有就写「无」"},
}, "required": ["body_parts", "locomotion", "transitions", "face", "props", "flaws"]}
OBS_PROMPT = """这张图是一段横版动画里连续的帧，每格左上角标了时间，按时间从左到右、从上到下排列（每秒 6 帧），镜头跟着主角。
这段剧情：{beat}
主角：{who}
用 Read 打开这张图：{sheet}
逐帧对比着看，只写客观观察（看到了什么动作变化），不要打分、不要给建议、不要评价好坏。"""

QUESTIONS = {
    "m_smooth": {"type": "choice", "criteria": {"a": "片段 a", "b": "片段 b"},
                 "instructions": "`a` 和 `b` 是同一段剧情的两个动画版本（对人物动作的客观描述）。哪一段的人物动作更流畅、更连贯：动作之间过渡自然，没有生硬的跳变、滑行或定格？"},
    "m_detail": {"type": "choice", "criteria": {"a": "片段 a", "b": "片段 b"},
                 "instructions": "`a` 和 `b` 是同一段剧情的两个动画版本（对人物动作的客观描述）。哪一段的人物动作更精细：手臂、手、腿、脚、头、表情各自都有动作，而不是整个人一张图平移或只换几张姿势图？"},
    "m_read": {"type": "choice", "criteria": {"a": "片段 a", "b": "片段 b"},
               "instructions": "`a` 和 `b` 是同一段剧情 `beat` 的两个动画版本（对人物动作的客观描述）。看哪一段，观众更能一眼看懂人物在做什么、心情如何？"},
    "m_pro": {"type": "choice", "criteria": {"a": "片段 a", "b": "片段 b"},
              "instructions": "`a` 和 `b` 是同一段剧情的两个动画版本（对人物动作的客观描述）。哪一段的人物动画更接近专业动画片的水准（考虑流畅、精细，也考虑穿帮和别扭的地方）？"},
}


def observe(sheet, beat, who):
    proc = subprocess.run(
        [str(CLAUDE_EXE), "-p", "--model", OBSERVER, "--output-format", "json", "--tools", "Read",
         "--allowedTools", "Read", "--add-dir", str(Path(sheet).parent),
         "--json-schema", json.dumps(OBS_SCHEMA, ensure_ascii=False)],
        input=OBS_PROMPT.format(beat=beat, who=who, sheet=sheet),
        capture_output=True, text=True, encoding="utf-8", timeout=900)
    return json.loads(proc.stdout)["structured_output"]


def require_key():
    """没有 Jev 的 key 就立刻退出：截图和观察员要跑很久，不许白跑之后才报（P8）。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 质检跑不了。质检不许跳过（P8）。\n"
                 "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                 "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


def main():
    require_key()
    cfg_path = Path(sys.argv[1])
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = ROOT / "out" / f"motion_{cfg_path.stem}"
    out.mkdir(parents=True, exist_ok=True)
    sheets = {}
    for k in ("before", "after"):
        c = cfg[k]
        sheets[k] = str(contact.sheet(str(ROOT.parent / c["scene"]), str(out / f"{k}.png"), c["t0"], c["t1"], 6,
                                      cols=4, width=380, follow=c["actor"], half=220))
    jobs = [(sheets[k], cfg["beat"], cfg[k].get("who", "扛木头的小伙")) for k in ("before", "after") for _ in range(2)]
    with ThreadPoolExecutor(4) as ex:
        obs = list(ex.map(lambda j: observe(*j), jobs))
    before, after = obs[:2], obs[2:]
    wins = {q: [] for q in QUESTIONS}
    for ob, oa in zip(before, after):
        for order in ("ab", "ba"):
            a, b = (ob, oa) if order == "ab" else (oa, ob)
            ans, _ = jev.ask({"beat": cfg["beat"], "a": a, "b": b}, QUESTIONS)
            for q, v in ans.items():
                p_after = v["probabilities"]["b"] if order == "ab" else v["probabilities"]["a"]
                wins[q].append(p_after)
    res = {q: round(sum(v) / len(v), 2) for q, v in wins.items()}
    names = {"m_smooth": "更流畅", "m_detail": "更精细", "m_read": "更看得懂", "m_pro": "更像专业动画"}
    print("「改后」赢的概率：" + "  ".join(f"{names[q]} {p:.2f}" for q, p in res.items()))
    (out / "report.json").write_text(json.dumps({"cfg": cfg, "result": res, "before": before, "after": after, "raw": wins},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"报告：{out / 'report.json'}")


if __name__ == "__main__":
    main()
