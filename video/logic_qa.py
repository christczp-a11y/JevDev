"""合理性复查（每集必做）：人物姿势、手脚接触、场景接缝有没有「一看就不对」的地方。

Chris 2026-09-27：扛木杆时手臂伸直平举、两段城墙没接上——这种不合逻辑的地方每集都要查出来。
流程：
  1. 抽帧：每个动作的中段、道具交接的时刻（扛起、放下、接住），再加上镜头移动中每 1.5 秒一帧（查背景接缝）
     每个时刻截两张：整个闯关画面 + 人物放大图
  2. Claude（看图模型）对照清单写客观观察（手臂弯还是直、手握没握住、脚踩没踩地、背景有没有断口……），不打分
     每个时刻两个观察员独立写
  3. Jev 按四道闸门判断：姿势说不通 / 该接触的没接触 / 场景没接上 / 不合理的穿插
     两个观察员都判「是」= 确定有问题；只有一个判「是」= 可能有问题，人来看

用法：python video/logic_qa.py <剧本.json>
"""
import json
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

import render  # noqa: E402
from jevdev import jev  # noqa: E402
from jevdev.writer import CLAUDE_EXE  # noqa: E402

OBSERVER = "claude-opus-5-5"
ACTION_TEXT = {   # 动作名 → 这一刻人物在做的事（给观察员和 Jev 看）
    "talk": "站着说话，边说边比划", "fist": "握拳给自己打气", "reach": "伸手去够面前那根竖着的高木杆",
    "look": "回头张望", "crouch": "蹲下", "lift": "抓住那根三丈长（约 7 米）、很重的木杆，把它放倒扛上肩",
    "carry": "把那根三丈长、很重的木杆扛在肩上走/跑", "drop": "弯腰把肩上的长木杆放到地上",
    "lookup": "抬头看天上", "catch": "伸手准备接住飞来的金块", "hug": "双手捧着接到的一小堆金块，开心地笑",
    "cheer": "欢呼",
}
OBS_SCHEMA = {"type": "object", "properties": {
    "pose": {"type": "string", "description": "逐个人物写：两条手臂各是弯的还是伸直的、手在什么位置、做什么手形；腿是直的还是弯的；身体前倾还是后仰"},
    "contact": {"type": "string", "description": "手有没有真的握住/托住它该拿的东西；道具靠什么撑着（有没有悬空）；脚有没有踩在地面上（有没有悬空或陷进地里）"},
    "effort": {"type": "string", "description": "如果人物在搬、扛、拿重东西：身体有没有表现出用力和重量（弯腰、屈膝、弯肘、身体往一边倾）；没有就写「不涉及」"},
    "scene": {"type": "string", "description": "背景各层（远山、城墙、城楼、地面、草、树丛）有没有明显的接缝、断口、错位、白边，墙脚和地面之间有没有露出不该有的空隙或底下另一层的颜色；有东西悬空吗"},
    "clip": {"type": "string", "description": "有没有东西不合理地穿插或遮挡：道具穿过身体或脸、手臂穿进身体、前景挡住关键动作"},
}, "required": ["pose", "contact", "effort", "scene", "clip"]}
OBS_PROMPT = """这是一部纸艺风格横版动画里的一刻（第 {t:.1f} 秒）。
此刻剧情：{beat}
两张图用 Read 打开：整个画面 {band}；主角放大 {zoom}
画风说明：人物是 Q 版纸片人，手脚是一块块纸片用关节连起来的，关节处有圆头和白色纸边，这是设计，不算问题。
对照描述要求逐项写客观观察，只写看到了什么，不打分、不给建议。"""

QUESTIONS = {
    "g_pose": {"type": "noul", "instructions": "根据 `obs`，人物的姿势和他此刻在做的事（`beat`）在现实里说不通：例如扛着很重的长木杆却两条手臂都伸直、平举在身前；搬重东西时身体一点不用力；手臂或腿弯向人不可能弯的方向"},
    "g_contact": {"type": "noul", "instructions": "根据 `obs`，手或脚没有接触到应该接触的东西：手没握住正在拿的道具、道具悬空没有东西撑着、脚没踩在地上或陷进地里"},
    "g_seam": {"type": "noul", "instructions": "根据 `obs`，背景场景有明显没接上的地方：两段墙、两段地面之间有断口或错位，墙脚和地面之间露出空隙或底下另一层的颜色"},
    "g_clip": {"type": "noul", "instructions": "根据 `obs`，有东西不合理地穿插或遮挡：道具穿过身体或脸、手臂穿进身体里、前景挡住了关键动作"},
}
NAMES = {"g_pose": "姿势说不通", "g_contact": "没接触上", "g_seam": "场景没接上", "g_clip": "穿插遮挡"}


def moments(scene):
    out = []
    for id_, a in scene["actors"].items():
        for t0, t1, name, *_ in a.get("actions", []):
            out.append(((t0 + t1) / 2, id_, name))
    for p in scene["props"]:
        if p["type"] == "pole":
            out += [(p["lift"][1] - 0.2, p["by"], "lift"), (p["drop"][0] + 0.3, p["by"], "drop")]
    cam = scene["camera"]
    for a, b in zip(cam, cam[1:]):
        if a[1] != b[1]:
            t = a[0] + 0.75
            while t < b[0]:
                out.append((t, None, None))
                t += 1.5
    out.sort()
    dedup = []
    for m in out:
        if not dedup or m[0] - dedup[-1][0] > 0.35:
            dedup.append(m)
    return dedup


def beat_of(scene, t, id_, name):
    a = scene["actors"][id_ or next(iter(scene["actors"]))]
    acts = [n for t0, t1, n, *_ in a.get("actions", []) if t0 <= t <= t1] or ([name] if name else [])
    parts = [ACTION_TEXT.get(n, n) for n in acts]
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


def observe(band, zoom, t, beat):
    proc = subprocess.run(
        [str(CLAUDE_EXE), "-p", "--model", OBSERVER, "--output-format", "json", "--tools", "Read", "--allowedTools", "Read",
         "--add-dir", str(Path(band).parent), "--json-schema", json.dumps(OBS_SCHEMA, ensure_ascii=False)],
        input=OBS_PROMPT.format(t=t, beat=beat, band=band, zoom=zoom), capture_output=True, text=True, encoding="utf-8", timeout=900)
    return json.loads(proc.stdout)["structured_output"]


def main():
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
            shots.append((t, beat_of(scene, t, id_, name), str(bp), str(zp)))
        browser.close()
    jobs = [s for s in shots for _ in range(2)]
    with ThreadPoolExecutor(6) as ex:
        obs = list(ex.map(lambda s: observe(s[2], s[3], s[0], s[1]), jobs))
    report, bad = [], 0
    for i, (t, beat, bp, zp) in enumerate(shots):
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
