"""画面质检：Claude 看画面写「客观观察」→ Jev 按写明的标准打分 → 任何一项不过关就不出片。

两道保险（2026-09-27 实测 Claude 看图会偶尔看错，比如把完整的木头说成伸出画框）：
  - 自洽性：每帧两个观察员独立描述，Jev 分别判断；闸门题取两次里较小的概率（两次都认定才算问题），分数取平均
  - 校准：参考图也走同一套流程；过关线 = 参考图的分数减去容差，而不是拍脑袋的绝对值

分工：Jev 看不到图，所以先由 Claude（看图模型）逐帧描述看到了什么（被切掉的、被挡住的、字清不清楚、
和参考图的差距……），只写事实不打分；再由 Jev 按 QUESTIONS 判断。判断标准写在题里，可审计、可调整。

抽哪些帧：每句字幕的中点、每个事件发生后 0.4 秒（这些是观众最可能停下来看的时刻）。

用法：python video/qa.py video/scenes/ep01_ximulixin_demo.json
一开头就检查环境变量 TYPESAFE_API_KEY，没有就非 0 退出（P8）：不等截帧、观察员跑完才报。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")   # 不设 PYTHONIOENCODING 时，key 缺失的中文提示也能正常显示（E5、E7）

import render  # noqa: E402
from jevdev import jev  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

REF = ROOT / "assets/ref/paper_style_ref.png"

OBS_SCHEMA = {"type": "object", "properties": {
    "cut_off": {"type": "string", "description": "画面里有没有东西被画面边缘、HUD 面板或其他元素切掉一部分；逐个列出是什么、切掉多少。没有就写「无」"},
    "overlaps": {"type": "string", "description": "人物之间、人物和道具之间的重叠：谁挡住了谁、有没有脸被挡住。没有就写「无」"},
    "text": {"type": "string", "description": "画面里每一处文字（气泡、布告牌、卷轴、HUD、字幕、标题）：写的是什么、在手机上看清不清楚、有没有超出它所在的框"},
    "focus": {"type": "string", "description": "这一刻的故事主角是谁、在做什么；观众视线会先落在哪里；有没有东西抢了主角的注意力"},
    "depth": {"type": "string", "description": "远景、中景、舞台、前景各有什么；远近层次拉开了没有"},
    "style": {"type": "string", "description": "所有元素的画风是否统一（纸艺质感、纹理、描边）；有没有哪一处看起来像另一种风格或像粗糙的占位图"},
    "vs_ref": {"type": "string", "description": "和参考图相比：精致度、细节丰富度、色彩和质感上差在哪里、好在哪里"},
}, "required": ["cut_off", "overlaps", "text", "focus", "depth", "style", "vs_ref"]}

OBS_PROMPT = """第一张图是画风参考（我们想达到的质量）。第二张是我们的横版闯关动画在第 {t:.1f} 秒的一帧（竖屏 9:16：顶部是标题，中间是闯关画面，下面是字幕）。
这一刻剧本里发生的事：{beat}
镜头：{camera}
说明：人物是有意做成 Q 版（大头、约 2.5 头身）的，和参考图的人物比例不同是设计要求，不算风格不统一；
顶部的大标题是整集固定的问句钩子，判断「视线落点、主角是否清楚」时只看中间的闯关画面。
但人物的纸张质感、以及画面上所有界面元素（标题胶囊、信用和赏金面板、气泡、字幕标签、印章）都应该是同一种纸艺质感。
用 Read 打开这两张图：
- 参考：{ref}
- 画面：{frame}
只写客观观察，不要打分、不要给建议。"""

QUESTIONS = {
    "polish": {"type": "score", "instructions": "根据 `obs`（对动画画面的客观观察），这一帧的美术精致度如何？",
               "criteria": ["有明显粗糙的占位图或简陋的几何色块",
                            "素材精致，但摆放生硬、有明显瑕疵（穿帮、错位）",
                            "整体精致，有一两处小瑕疵",
                            "精致，细节丰富，接近商业动画",
                            "和参考图同一水准，可以直接当宣传图"]},
    "focus": {"type": "score", "instructions": "根据 `obs`，观众能多快看懂这一刻的主角和发生的事（`beat`）？",
              "criteria": ["看不出主角是谁或在干什么",
                           "主角被遮挡或被别的东西抢了注意力",
                           "能看懂，但画面有点挤或乱",
                           "一眼看懂，主体清楚",
                           "一眼看懂，而且构图把视线引向关键动作"]},
    "depth": {"type": "score", "instructions": "根据 `obs`，画面的远近层次（景深）拉开得怎么样？",
              "criteria": ["平的，没有层次", "有两层，但远近差别不明显", "远中近都有，层次清楚",
                           "层次清楚，远处淡、近处虚，衬托舞台", "层次丰富得像立体书一样"]},
    "g_cut": {"type": "noul", "instructions": "根据 `obs`，有重要的东西（人物的脸或身体大部分、关键道具、文字）被画面边缘、HUD 或其他元素切掉或挡住"},
    "g_face": {"type": "noul", "instructions": "根据 `obs`，有人物的脸被别的人物或道具挡住"},
    "g_text": {"type": "noul", "instructions": "根据 `obs`，画面里有文字看不清，或文字超出了它所在的框（气泡、布告牌、卷轴）"},
    "g_style": {"type": "noul", "instructions": "根据 `obs`，有元素的画风和其他元素明显不统一，或看起来像粗糙的占位图"},
}
TOLERANCE = {"polish": 0.6, "focus": 0.8, "depth": 0.6}   # 允许比参考图低多少（0–4 档）；g_ 题「是」的概率必须 < 0.5
OBSERVER = "claude-opus-5-5"


def beats(scene):
    """抽帧的时刻：每句字幕中点 + 每个事件后 0.4 秒，附上这一刻的剧情。"""
    out = [((s[0] + s[1]) / 2, f"{s[2]}：{s[3]}") for s in scene["subtitles"]]
    out += [(ev["t"] + 0.4, f"事件：{ev['type']}") for ev in scene["events"]]
    for p in scene["props"]:
        if p.get("hitAt"):
            out.append((p["hitAt"] + 0.15, "主角跳起顶到竹简方块，蹦出奖励"))
        if p.get("carry"):
            out.append((p["carry"][0] + 0.9, "有人把木头举过头顶"))
    return sorted(out)


def camera_state(scene, t):
    ks = scene["camera"]
    for a, b in zip(ks, ks[1:]):
        if a[0] <= t < b[0] and a[1] != b[1]:
            return "镜头正在横向平移，画面边缘有人物或景物正在进画、出画是正常的，不算被切掉"
    return "镜头静止"


def observe(frame, t, beat, camera="镜头静止"):
    proc = subprocess.run(
        [str(CLAUDE_EXE), "-p", "--model", OBSERVER, "--output-format", "json", "--tools", "Read",
         "--allowedTools", "Read", "--add-dir", str(Path(frame).parent), "--add-dir", str(REF.parent),
         "--json-schema", json.dumps(OBS_SCHEMA, ensure_ascii=False)],
        input=OBS_PROMPT.format(t=t, beat=beat, ref=REF, frame=frame, camera=camera),
        capture_output=True, text=True, encoding="utf-8", timeout=600)
    return json.loads(proc.stdout)["structured_output"]


def judge_one(obs, beat):
    a, _ = jev.ask({"beat": beat, "obs": obs}, QUESTIONS)
    return {k: v["score"] if v["type"] == "score" else v["noul"] for k, v in a.items()}


def combine(runs):
    """两次独立观察的合并：分数取平均；闸门取较小值（两个观察员都认定才算问题）。"""
    return {k: round(min(r[k] for r in runs) if k.startswith("g_") else sum(r[k] for r in runs) / len(runs), 2)
            for k in runs[0]}


def verdict(s, bar):
    fails = [f"{k} {s[k]}<{bar[k]:.2f}" for k in bar if s[k] < bar[k]]
    fails += [f"{k} {s[k]}" for k in s if k.startswith("g_") and s[k] >= 0.5]
    return fails


def require_key():
    """没有 Jev 的 key 就立刻退出：截帧和观察员要跑很久，不许白跑之后才报（P8）。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 质检跑不了。质检不许跳过（P8）。\n"
                 "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                 "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


def main():
    require_key()
    scene_path = Path(sys.argv[1])
    scene = render.load_scene(scene_path)
    qa_dir = ROOT / "out" / f"qa_{scene_path.stem}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    moments = beats(scene)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        frames = []
        for t, beat in moments:
            f = qa_dir / f"t{t:05.1f}.png"
            f.write_bytes(render.grab(page, t, "image/png"))
            frames.append((t, beat, f))
        browser.close()

    from concurrent.futures import ThreadPoolExecutor
    jobs = [(str(REF), 0.0, "参考图：官员在城墙下奔跑跳跃，头顶有竹简方块", "镜头静止")] * 2
    for t, beat, f in frames:
        jobs += [(str(f), t, beat, camera_state(scene, t))] * 2
    with ThreadPoolExecutor(6) as ex:
        obs = list(ex.map(lambda j: observe(*j), jobs))
    ref_s = combine([judge_one(o, jobs[0][2]) for o in obs[:2]])
    bar = {k: ref_s[k] - tol for k, tol in TOLERANCE.items()}
    print(f"校准：参考图 精致{ref_s['polish']} 主体{ref_s['focus']} 层次{ref_s['depth']} → 过关线 "
          + " ".join(f"{k}≥{v:.2f}" for k, v in bar.items()))
    report, ok = [{"t": "ref", "scores": ref_s, "obs": obs[:2]}], True
    for i, (t, beat, f) in enumerate(frames):
        pair = obs[2 + 2 * i: 4 + 2 * i]
        s = combine([judge_one(o, beat) for o in pair])
        fails = verdict(s, bar)
        ok &= not fails
        report.append({"t": t, "beat": beat, "scores": s, "fails": fails, "obs": pair})
        print(f"{'✅' if not fails else '❌'} {t:5.1f}s  精致{s['polish']} 主体{s['focus']} 层次{s['depth']}  "
              f"{'；'.join(fails) if fails else ''}  | {beat[:30]}")
    (qa_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{'全部通过' if ok else '有帧没通过，先修再出片'}。报告：{qa_dir / 'report.json'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
