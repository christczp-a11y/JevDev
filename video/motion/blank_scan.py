"""对一集（或一条成片）做空白检测（M7）：报出画面中间的淡色空白块、分层之间的白缝、局部直边露缝（见 engine/blank.py）。
合成器出片时自带这项检查（只看场景，不含字幕）；这个脚本是给已经有的东西用的（标定阈值、reviewer 对老片子查一遍）。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  blank_scan.py --bare tj02 [--every 0.5]           按分镜表逐镜头每 0.5 秒画一帧「只有背景 / 人物 / 前景三层」的画面再查（和出片时同一套检查，
                                                    没有字幕、卡片、特效的干扰，推荐；要读素材和配音时间线，整集约 1–2 分钟）
  blank_scan.py video/out/tj01/full/tj01_full.mp4 [tj01] [--every 0.5]
                                                    解码成片查（只有成片没有分镜表时用）。成片里有字幕、卡片、特效，局部直边那一项会多排除卡片边框，
                                                    而且要求连续两个采样点都在同一个位置；仍可能把特效线之类误报，仅供参考。
                                                    给了集名（或分镜表路径）就把每个时间点对到镜头号。
退出码：0 = 没有空白，1 = 有。
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import blank  # noqa: E402
from engine import consts as C  # noqa: E402

W2, H2 = 540, 960                       # 解码成片时的分辨率（局部直边要 540×960；detect 内部自己缩到各检查的工作分辨率）


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def video_frames(path, every):
    """成片 → 每 every 秒一帧（BGR，540×960），逐帧产出，不一次读进内存。"""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={1 / every},scale={W2}:{H2}:flags=area", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    size = W2 * H2 * 3
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H2, W2, 3)
    finally:
        p.stdout.close()
        p.wait()


def bare_frames(sb_path, every):
    """分镜表 → 逐镜头每 every 秒一帧「只画背景 / 人物 / 前景」的画面（和合成器出片时的抽帧一样，不含特效、调色、字幕），产出 (时间, 镜头号, 画面)。"""
    from engine import segment as S
    from engine.canvas import Canvas
    from engine.plan import build_plan
    plan = build_plan(sb_path, None, 1.0, "normal")
    cache = C.OUT_ROOT / "_blank_scan"                                   # 只是给 make_job 一个路径，不会往里写
    step = max(1, int(round(every * C.FPS)))
    for sp in plan.shots:
        job = S.make_job(plan, sp, cache, "normal")
        fxreg, tl, store, _ui = S._context(job)
        own = S._scene(job["own"], tl, store, fxreg)
        cv = Canvas(store, 1.0, C.FPS, own.dur)
        seed = int(job["own"]["key"][:8], 16)
        for f in range(sp.f0 + 3, sp.f1 - 1, step):
            cv.rng = np.random.default_rng([seed, f])
            own.draw(cv, (f - own.f0i) / C.FPS, f / C.FPS, bare=True)
            yield f / C.FPS, sp.id, cv.img


def keep_persistent(per_frame):
    """成片模式：strip 要在相邻的采样点上也出现（y 上沿差 ≤ 8、横向重叠 ≥ 50%）才算：特效线、转瞬即逝的东西每帧位置都不一样，布景里露出来的缝一整个镜头都在。"""
    out = []
    for k, evs in enumerate(per_frame):
        keep = []
        for e in evs:
            if e["kind"] != "strip":
                keep.append(e)
                continue
            for j in (k - 1, k + 1):
                if 0 <= j < len(per_frame) and any(o["kind"] == "strip" and abs(o["bbox"][1] - e["bbox"][1]) <= 8 and
                                                    blank._inside(e["bbox"], o["bbox"]) >= 0.5 for o in per_frame[j]):
                    keep.append(e)
                    break
        out.append(keep)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="空白检测（M7）", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("video", nargs="?", help="成片 mp4（不给就必须用 --bare）")
    ap.add_argument("episode", nargs="?", help="集名（video/stories/<集>/storyboard.json）或分镜表路径：给了才标镜头号")
    ap.add_argument("--bare", metavar="集名", help="不解码成片，按这一集的分镜表画只有背景 / 人物 / 前景的画面来查（推荐）")
    ap.add_argument("--every", type=float, default=0.5, help="每隔几秒抽一帧（默认 0.5）")
    a = ap.parse_args(argv)
    if not a.video and not a.bare:
        ap.error("要么给成片，要么 --bare 集名")

    def sb_of(name):
        p = Path(name)
        return p if p.exists() else C.ROOT / "video" / "stories" / name / "storyboard.json"

    rows = []                                              # [(秒, 镜头号 | None, 事件列表)]
    if a.bare:
        for t, sid, img in bare_frames(sb_of(a.bare), a.every):
            rows.append((t, sid, blank.detect(img)))
        n = len(rows)
    else:
        shots = None
        if a.episode:
            from engine.plan import build_plan
            shots = build_plan(sb_of(a.episode), None, 1.0, "normal").shots
        frames = [blank.detect(img, ui=True) for img in video_frames(a.video, a.every)]
        n = len(frames)
        frames = keep_persistent(frames)
        for k, evs in enumerate(frames):
            t = k * a.every
            sid = next((s.id for s in shots if s.f0 <= t * C.FPS < s.f1), "?") if shots else None
            rows.append((t, sid, evs))

    hits = [(t, sid, e) for t, sid, evs in rows for e in evs]
    # 同一处露缝连续几帧都在：合成一行（同镜头、同种、y 上沿差 ≤ 12、横向重叠 ≥ 50%，时间间隔 ≤ 2 个采样间隔）
    groups = []
    for t, sid, e in hits:
        for g in groups:
            if g["sid"] == sid and g["e"]["kind"] == e["kind"] and t - g["t1"] <= 2.5 * a.every and abs(g["e"]["bbox"][1] - e["bbox"][1]) <= 12 \
                    and blank._inside(e["bbox"], g["e"]["bbox"]) >= 0.5:
                g["t1"], g["n"] = t, g["n"] + 1
                break
        else:
            groups.append(dict(sid=sid, e=e, t0=t, t1=t, n=1))
    names = {"block": "大块", "seam": "白缝", "strip": "直边平条"}
    for g in groups:
        e = g["e"]
        when = mmss(g["t0"]) if g["n"] == 1 else f"{mmss(g['t0'])}–{mmss(g['t1'])}"
        extra = f"，厚 {e['h']:.0f}，颜色 RGB{tuple(e['color'])}" if e["kind"] == "strip" else ""
        print(f"{when}  {g['sid'] or ''}  {names[e['kind']]}  bbox {e['bbox']}  面积 {e['area']:.2%}{extra}  （{g['n']} 个采样点）")
    ids = sorted({g["sid"] for g in groups if g["sid"]}, key=lambda s: (len(s), s))
    print(f"共 {len(hits)} 处、{len(groups)} 组（抽了 {n} 帧）" + (f"，镜头：{', '.join(ids)}" if ids else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
