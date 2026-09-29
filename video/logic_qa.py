"""合理性复查（每集必做）：人物姿势、手脚接触、场景接缝有没有「一看就不对」的地方。

Chris 2026-09-27：扛木杆时手臂伸直平举、两段城墙没接上——这种不合逻辑的地方每集都要查出来。
Chris 2026-09-28：旗杆悬空、回头时发带跑到脸前面、城墙把城门门洞堵死——之前都漏了，原因和对策：
  只抽动作正中间一帧（回头动作的中点正好转回来了）→ 加抽每个动作的关键瞬间（KEY_MOMENTS）和每次换视角之后；
  清单里没问配饰和背景常理 → 观察加 attach / world 两项，Jev 加两道闸门；
  人物常常正好挡住门洞 → 镜头移动中和每个机位停下时，另截一张藏起人物的纯背景图。
流程：
  1. 抽帧：每个动作的中段和关键瞬间、换视角之后、道具交接的时刻（扛起、放下、接住），再加上镜头移动中每 1.5 秒一帧、
     每个机位停下时一帧（查背景）。每个时刻截两张：整个闯关画面 + 人物放大图；查背景的时刻再加一张纯背景图
  2. Claude（看图模型）对照清单写客观观察（手臂弯还是直、手握没握住、脚踩没踩地、背景有没有断口……），不打分
     每个时刻两个观察员独立写
  3. Jev 按六道闸门判断：姿势说不通 / 该接触的没接触 / 场景没接上 / 不合理的穿插 / 配饰朝向不对 / 背景不合常理
     两个观察员都判「是」= 确定有问题；只有一个判「是」= 可能有问题，人来看

用法：python video/logic_qa.py <剧本.json>
一开头就检查环境变量 TYPESAFE_API_KEY，没有就非 0 退出（P8）：不等渲染、观察员跑完才报。
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")   # 不设 PYTHONIOENCODING 时，中文报错也能正常显示，不变成 \u 转义（E5、E7）

import render  # noqa: E402
from jevdev import jev  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

OBSERVER = "claude-opus-5-5"
ACTION_TEXT = {   # 动作名 → 这一刻人物在做的事（给观察员和 Jev 看）
    "talk": "站着说话，边说边比划", "fist": "握拳给自己打气", "reach": "伸手去够面前那根竖着的高木杆，但伸到一半停住犹豫（手还没碰到木杆是剧情设计）",
    "look": "回头张望", "crouch": "蹲下", "lift": "握住那根三丈长（约 7 米）、很重的竖着的木杆靠下的地方，让杆顶往前方倒下放平，再把它抱到腰前",
    "carry": "双臂从下面兜住那根三丈长、很重的木杆，抱在腰前，迈着沉重的步子往前走", "drop": "把抱在腰前的长木杆放下：弯腰先压前端着地，再放后端",
    "lookup": "抬头看天上", "catch": "伸手准备接住飞来的金块（金块还在空中飞过来，这时手里还没有东西是正常的）", "hug": "双手捧着接到的一小堆金块，开心地笑",
    "cheer": "欢呼",
}
KEY_MOMENTS = {   # 动作名 → 除了中点以外还要抽的时刻（离动作开始的秒数）：姿势最极端、最容易露馅的瞬间
    "look": [0.32, 1.22],     # 两次回头最深的时候（puppet.js 的 look：0.08–0.55、1.0–1.45 秒回头）
    "lift": [0.3],            # 蹲下抓杆
    "hug": [0.6],             # 刚捧住、两肘外撑
}
OBS_SCHEMA = {"type": "object", "properties": {
    "pose": {"type": "string", "description": "逐个人物写：两条手臂各是弯的还是伸直的、手在什么位置、做什么手形；腿是直的还是弯的；身体前倾还是后仰"},
    "contact": {"type": "string", "description": "手有没有真的握住/托住它该拿的东西；道具靠什么撑着（有没有悬空）；脚有没有踩在地面上（有没有悬空或陷进地里）"},
    "effort": {"type": "string", "description": "如果人物在搬、扛、拿重东西：身体有没有表现出用力和重量（弯腰、屈膝、弯肘、身体往一边倾）；没有就写「不涉及」"},
    "scene": {"type": "string", "description": "背景各层（远山、城墙、城楼、地面、草、树丛）有没有明显的接缝、断口、错位、白边，墙脚和地面之间有没有露出不该有的空隙或底下另一层的颜色；有东西悬空吗"},
    "clip": {"type": "string", "description": "有没有东西不合理地穿插或遮挡：道具穿过身体或脸、手臂穿进身体、前景挡住关键动作"},
    "attach": {"type": "string", "description": "人物身上的配饰（发带、头巾、帽子、辫子、腰带）：先写脸朝左还是朝右，再写配饰在头的哪一侧、朝哪边飘；有没有跑到脸前面，或者和头、身体的朝向对不上"},
    "world": {"type": "string", "description": "背景里的东西合不合常理：旗杆、树、房子、摊位的底部有没有落在地面或墙上（有没有悬空）；城门、门洞、窗户、通道里看到的是门外的景色，还是被后面的墙或别的东西堵住了；有没有不该出现的重复或断掉的东西。有纯背景图时以纯背景图为准"},
}, "required": ["pose", "contact", "effort", "scene", "clip", "attach", "world"]}
OBS_PROMPT = """这是一部纸艺风格横版动画里的一刻（第 {t:.1f} 秒）。
此刻剧情：{beat}
图用 Read 打开：整个画面 {band}；主角放大 {zoom}{bg}
画风说明：人物是 Q 版纸片人，手脚是一块块纸片用关节连起来的，肩膀、手肘、膝盖处有圆头和白色纸边，这是设计，不算问题。
对照描述要求逐项写客观观察，只写看到了什么，不打分、不给建议。"""

QUESTIONS = {
    "g_pose": {"type": "noul", "instructions": "根据 `obs`，人物的姿势和他此刻在做的事（`beat`）在现实里说不通：例如扛着很重的长木杆却两条手臂都伸直、平举在身前；搬重东西时身体一点不用力；手臂或腿弯向人不可能弯的方向"},
    "g_contact": {"type": "noul", "instructions": "根据 `obs`，手或脚没有接触到应该接触的东西：手没握住正在拿的道具、道具悬空没有东西撑着、脚没踩在地上或陷进地里"},
    "g_seam": {"type": "noul", "instructions": "根据 `obs`，背景场景有明显没接上的地方：两段墙、两段地面之间有断口或错位，墙脚和地面之间露出空隙或底下另一层的颜色"},
    "g_clip": {"type": "noul", "instructions": "根据 `obs`，有东西不合理地穿插或遮挡：道具穿过身体或脸、手臂穿进身体里、前景挡住了关键动作"},
    "g_attach": {"type": "noul", "instructions": "根据 `obs`，人物的配饰（发带、头巾、帽子、辫子）和头或身体的朝向对不上：例如脸已经转向左边，发带却还飘在左边、挡在脸前面；帽子戴反"},
    "g_world": {"type": "noul", "instructions": "根据 `obs`，背景里有不合常理的地方：旗杆、树、房子等悬在半空没落在地面或墙上；城门门洞、通道被后面的墙堵死（门洞里看到的是墙而不是门外的景色）；东西无故重复或断掉"},
}
NAMES = {"g_pose": "姿势说不通", "g_contact": "没接触上", "g_seam": "场景没接上", "g_clip": "穿插遮挡", "g_attach": "配饰朝向不对", "g_world": "背景不合常理"}


def moments(scene):
    """（时刻, 角色, 动作名, 优先级）：两个时刻挨得太近（0.35 秒内）时留优先级高的（关键瞬间 > 换视角 > 动作中点）。
    查背景的时刻（角色为 None，会另截纯背景图）单独去重，不和人物的时刻互相顶替。"""
    out = []
    for id_, a in scene["actors"].items():
        for t0, t1, name, *_ in a.get("actions", []):
            out.append(((t0 + t1) / 2, id_, name, 1))
            out += [(t0 + dt, id_, name, 3) for dt in KEY_MOMENTS.get(name, []) if t0 + dt < t1]
        for ts, _v in (a.get("views") or [])[1:]:   # 换视角之后（纸片翻面、部件换一套，最容易出错）
            out.append((ts + 0.3, id_, None, 2))
    for p in scene["props"]:
        if p["type"] == "pole":
            out += [(p["lift"][1] - 0.2, p["by"], "lift", 3), (p["drop"][0] + 0.3, p["by"], "drop", 3)]
    cam = scene["camera"]
    for a, b in zip(cam, cam[1:]):
        if a[1] != b[1]:
            t = a[0] + 0.75
            while t < b[0]:
                out.append((t, None, None, 0))
                t += 1.5
    for k in cam[1:]:   # 每个机位停下时查一次背景
        if k[0] + 0.2 < scene["duration"]:
            out.append((k[0] + 0.2, None, None, 0))
    def dedup(ms):
        kept = []
        for m in sorted(ms, key=lambda m: (m[0], -m[3])):
            if kept and m[0] - kept[-1][0] <= 0.35:
                if m[3] > kept[-1][3]:
                    kept[-1] = m
            else:
                kept.append(m)
        return kept
    both = dedup([m for m in out if m[1]]) + dedup([m for m in out if not m[1]])
    return [m[:3] for m in sorted(both, key=lambda m: m[0])]


def beat_of(scene, t, id_, name):
    a = scene["actors"][id_ or next(iter(scene["actors"]))]
    acts = [n for t0, t1, n, *_ in a.get("actions", []) if t0 <= t <= t1] or ([name] if name else [])
    parts = [ACTION_TEXT.get(n, n) for n in acts]
    for t0, t1, n, *pp in a.get("actions", []):   # 动作里的「蹦」：开心地蹦起来时脚离地是正常的
        for h0, k in (pp[0].get("hops", []) if pp else []):
            if t0 + h0 - 0.05 <= t <= t0 + h0 + k * 0.42 + 0.05:
                parts.append("正在开心地原地蹦起来（这时脚离开地面是正常的）")
    if any(t0 - 0.2 <= t <= t1 + 0.25 for t0, t1, _h in a.get("jumps", [])):
        parts.append("正在起跳/腾空跨过地上的石头/落地（这时脚离开地面是正常的）")
    views = a.get("views")
    if views:
        v = [n for ts, n in views if ts <= t][-1]
        parts.append("人物是" + ("45° 半正面（朝着观众偏右）" if v == "q" else "侧面") + "的样子")
    text = "；".join(parts)
    if not id_:
        return "镜头平移中（主要检查背景有没有接缝）" + (f"。主角此刻：{text}" if text else "")
    return "主角：" + text


def observe(band, zoom, t, beat, bg=None):
    bg_line = f"；纯背景（把人物藏起来了，专门查背景）{bg}" if bg else ""
    proc = subprocess.run(
        [str(CLAUDE_EXE), "-p", "--model", OBSERVER, "--output-format", "json", "--tools", "Read", "--allowedTools", "Read",
         "--add-dir", str(Path(band).parent), "--json-schema", json.dumps(OBS_SCHEMA, ensure_ascii=False)],
        input=OBS_PROMPT.format(t=t, beat=beat, band=band, zoom=zoom, bg=bg_line), capture_output=True, text=True, encoding="utf-8", timeout=900)
    return json.loads(proc.stdout)["structured_output"]


def require_key():
    """没有 Jev 的 key 就立刻退出：渲染和观察员要跑很久，不许白跑之后才报（P8）。放在 main() 开头：selfcheck.py 会 import 本文件借用 moments()，那时不需要 key。"""
    if not os.environ.get("TYPESAFE_API_KEY"):
        sys.exit("错误：环境变量 TYPESAFE_API_KEY 没有值，Jev 质检跑不了。质检不许跳过（P8）。\n"
                 "Git Bash 里这样设：export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "
                 "\"[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')\" | tr -d '\\r')")


def main():
    require_key()
    scene_path = Path(sys.argv[1])
    scene = render.load_scene(scene_path)
    out = ROOT / "out" / f"logic_{scene_path.stem}"
    out.mkdir(parents=True, exist_ok=True)
    ms = moments(scene)
    shots = []
    main_actor = next(iter(scene["actors"]))
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        for t, id_, name in ms:
            im = Image.open(BytesIO(render.grab(page, t, "image/png"))).convert("RGB")
            band = im.crop((0, 560, 1080, 1168))
            cx = page.evaluate("([id, t]) => actorScreenX(id, t)", [id_ or main_actor, t])
            cx = max(200, min(880, cx))
            zoom = band.crop((int(cx - 190), 140, int(cx + 190), 608)).resize((570, 702), Image.LANCZOS)
            bp, zp = out / f"t{t:05.2f}_band.png", out / f"t{t:05.2f}_zoom.png"
            band.save(bp)
            zoom.save(zp)
            gp = None
            if id_ is None:   # 查背景：藏起人物再截一张
                page.evaluate("window.hideActors = true")
                gp = out / f"t{t:05.2f}_bg.png"
                Image.open(BytesIO(render.grab(page, t, "image/png"))).convert("RGB").crop((0, 560, 1080, 1168)).save(gp)
                page.evaluate("window.hideActors = false")
            shots.append((t, beat_of(scene, t, id_, name), str(bp), str(zp), str(gp) if gp else None))
        browser.close()
    jobs = [s for s in shots for _ in range(2)]
    with ThreadPoolExecutor(6) as ex:
        obs = list(ex.map(lambda s: observe(s[2], s[3], s[0], s[1], s[4]), jobs))
    report, bad = [], 0
    for i, (t, beat, bp, zp, gp) in enumerate(shots):
        pair = obs[2 * i: 2 * i + 2]
        answers = [jev.ask({"beat": beat, "obs": o}, QUESTIONS)[0] for o in pair]
        probs = {q: [round(a[q]["noul"], 2) for a in answers] for q in QUESTIONS}
        sure = [q for q, ps in probs.items() if min(ps) >= 0.5]
        maybe = [q for q, ps in probs.items() if max(ps) >= 0.5 and q not in sure]
        bad += bool(sure)
        report.append({"t": t, "beat": beat, "probs": probs, "sure": sure, "maybe": maybe, "obs": pair, "band": bp, "zoom": zp})
        mark = "❌" if sure else ("⚠️" if maybe else "✅")
        print(f"{mark} {t:5.2f}s  {beat[:28]:<28}  " + "  ".join(f"{NAMES[q]}{'!' if q in sure else '?'}" for q in sure + maybe))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(shots)} 个时刻，{bad} 个确定有问题。报告：{out / 'report.json'}")


if __name__ == "__main__":
    main()
