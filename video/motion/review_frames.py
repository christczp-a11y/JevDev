"""给 reviewer / 自己看片的抽帧：从成片里抽
  contact_1fps_<n>.png       每秒 1 帧的联系表（每张 8 格，每格标时间和镜头号）
  action_10fps/<镜头>.png    每个镜头动作段每秒 10 帧的抽帧条（前 2 秒 20 帧，5 格一行；转场镜头从切点前半个转场开始）
  dwell.md                   每镜停留时间表（PITFALLS M10）：每镜一行 = 镜头号、起止秒、时长、讲事的特效（泡泡、属性卡、任务卡、地图、砸字……）出完以后看得见多久，不够的标 ⚠；
                             算法和 storyboard_check.py 的 [停留] 是同一套（那边报错 / 警告，这里列全表）；时间是成片里的秒，和联系表每格标的「时间 镜头号」对得上。第 7 步 reviewer 逐镜对着它看
用法：.venv/Scripts/python video/motion/review_frames.py video/out/tj01/scene1/tj01_scene1.mp4 tj01 [--out 目录] [--action-sec 2.0]
第二个参数是集名或分镜表路径（用来算每个镜头从哪一帧开始）。同 fx_reel/make_review.py 的办法，不限于特效样片。
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import consts as C  # noqa: E402
from engine import plan as P  # noqa: E402
import storyboard_check as SC  # noqa: E402

FX_ZH = {"bubble": "泡泡", "stat_card": "属性卡", "person_card": "人物卡", "checklist": "清单", "progress": "进度物", "map": "地图", "map_city": "地图城",
         "map_arrow": "地图箭头", "smash": "砸字", "big_title": "大字章", "screen": "屏幕"}      # 其余（card_quest 等）直接写类型名


def label(t, text, y, scale, color):
    cv2.putText(t, text, (6, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(t, text, (6, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def tile(img, w, h, text=None, tag=None):
    """text = 时间（白字，上），tag = 镜头号（黄字，大，下）；分两行写，不挤在一起（原来一行字被粗描边糊成一团，镜头号看不清）。"""
    t = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    if text:
        label(t, text, 24, 0.7, (255, 255, 255))
    if tag:
        label(t, str(tag), 60, 1.0, (60, 230, 255))
    return t


def dwell_markdown(episode, ranges, rows, fps):
    """每镜停留时间表：ranges = [(镜头号, _, 起始帧, 结束帧)]（成片里的帧），rows = {镜头号: storyboard_check 的 dwell_rows 里的一行}。返回 (markdown, ⚠ 个数)。"""
    lines, bad = [], []
    for sid, _, f0, f1 in ranges:
        row = rows.get(sid)
        dur = (f1 - f0) / fps
        cells, marks = [], []
        for it in (row["fx"] if row else []):
            ok = SC.dwell_ok(it)
            name = FX_ZH.get(it["type"], it["type"])
            cells.append(f"{name}{'「' + it['label'] + '」' if it['label'] else ''}：看得见 {it['visible']:.1f} 秒" + ("" if ok else " ⚠"))
            if not ok:
                marks.append(f"{name}只看得见 {it['visible']:.1f} 秒（< {SC.DWELL_MIN:g}）")
        if row and row["short"]:
            marks.append(f"镜头只有 {dur:.2f} 秒（< {SC.DWELL_SHOT_MIN:g}），不在快切连段里")
        elif row and row["fast"]:
            cells.append("（快切连段）")
        elif row is None:
            cells.append("（分镜检查没算出这一镜）")
        if marks:
            bad.append((sid, f0 / fps, marks))
        lines.append(f"| {sid} | {f0 / fps:.1f}–{f1 / fps:.1f} | {dur:.2f} | " + ("<br>".join(cells) if cells else "—") + " | " + ("⚠" if marks else "") + " |")
    head = [f"# 每镜停留时间表（{episode}）", "",
            f"规则（PITFALLS M9、M10）：讲事的画面（泡泡、属性卡、任务卡、地图、砸字、大字章、清单、进度物）出完以后在镜头里要看得见 ≥ {SC.DWELL_MIN:g} 秒；"
            f"一般镜头 ≥ {SC.DWELL_SHOT_MIN:g} 秒，短于 {SC.DWELL_SHOT_MIN:g} 秒的只许在高潮快切里（连续 {SC.FAST_RUN_MIN} 个以上 0.8–1.2 秒的镜头）。⚠ = 不够。"
            "时间是成片里的秒，和联系表每格标的「时间 镜头号」一一对应；「看得见」是自动算的（出完 = 入场动画结束，见 storyboard_check.py 的 fx_enter），"
            "它只管特效，镜头里别的要交代的东西（人物的动作、表情、道具）看清了没有要你自己对着画面判断。", "",
            f"共 {len(ranges)} 镜，⚠ {len(bad)} 镜。" + ("" if not bad else " 先看这几镜：")]
    head += [f"- {sid}（{t:.1f} 秒）：" + "；".join(m) for sid, t, m in bad]
    head += ["", "| 镜头 | 起止（秒） | 时长 | 讲事的特效：出完后看得见多久 | ⚠ |", "|---|---|---|---|---|"]
    return "\n".join(head + lines) + "\n", len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("episode", help="集名（video/stories/<集>/storyboard.json）或分镜表路径")
    ap.add_argument("--out")
    ap.add_argument("--action-sec", type=float, default=2.0)
    a = ap.parse_args()
    sb = Path(a.episode)
    if not sb.exists():
        sb = C.ROOT / "video" / "stories" / a.episode / "storyboard.json"
    plan = P.build_plan(sb)
    out = Path(a.out) if a.out else Path(a.video).parent
    (out / "action_10fps").mkdir(parents=True, exist_ok=True)
    fps = C.FPS
    base = min(sp.f0 for sp in plan.selected)
    ranges = []
    for sp in plan.selected:
        lead = (sp.trans["a"] if sp.trans else 0)          # 转场切点前多渲的帧
        ranges.append((sp.id, sp.f0 - base - lead, sp.f0 - base, sp.f1 - base))
    try:
        _, _, rep, _ = SC.run(str(sb))
        rows = {r["id"]: r for r in rep.dwell}
    except Exception as e:  # noqa: BLE001  停留表算不出来不拦联系表
        rows = {}
        print(f"（每镜停留时间表里的特效部分没算出来：{type(e).__name__} {e}）")
    text, n_bad = dwell_markdown(sb.parent.name if sb.name == "storyboard.json" else sb.stem, ranges, rows, fps)
    (out / "dwell.md").write_text(text, encoding="utf-8")
    cap = cv2.VideoCapture(a.video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / 10)))
    nact = int(round(a.action_sec * 10))
    want = set(min(int(round((s + 0.5) * fps)), n - 1) for s in range(int(n / fps)))
    for sid, fa, f0, f1 in ranges:
        for j in range(nact):
            fi = fa + j * step
            if fi < f1:
                want.add(min(max(fi, 0), n - 1))
    small, i = {}, 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            small[i] = cv2.resize(f, (360, 640), interpolation=cv2.INTER_AREA)
        i += 1
    keys = sorted(small)

    def frame(fi):
        return small[fi] if fi in small else small[max(k for k in keys if k <= fi)]

    def shot_of(fi):
        for sid, fa, f0, f1 in ranges:
            if f0 <= fi < f1:
                return sid
        return "?"

    secs = list(range(int(n / fps)))
    for c in range(0, len(secs), 8):
        chunk = secs[c:c + 8]
        tiles = [tile(frame(min(int(round((s + 0.5) * fps)), n - 1)), 360, 640, f"{s + 0.5:.1f}s", shot_of(int(round((s + 0.5) * fps)))) for s in chunk]
        while len(tiles) % 4:
            tiles.append(np.full((640, 360, 3), 255, np.uint8))
        rows = [np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]
        cv2.imwrite(str(out / f"contact_1fps_{c // 8 + 1}.png"), np.vstack(rows))
    for sid, fa, f0, f1 in ranges:
        tiles = []
        for j in range(nact):
            fi = fa + j * step
            if fi >= f1:
                break
            fi_c = min(max(fi, 0), n - 1)
            tiles.append(tile(frame(fi_c), 270, 480, f"{fi_c / fps:.1f}s", sid))
        while len(tiles) % 5:
            tiles.append(np.full((480, 270, 3), 255, np.uint8))
        rows = [np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]
        cv2.imwrite(str(out / "action_10fps" / f"{sid}.png"), np.vstack(rows))
    print(f"→ {out}（{len(secs)} 秒联系表 {(len(secs) + 7) // 8} 张，动作条 {len(ranges)} 张，停留时间表 dwell.md：{n_bad} 镜有 ⚠）")


if __name__ == "__main__":
    main()
