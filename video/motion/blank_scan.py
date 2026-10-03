"""对一集（或一条成片）做空白检测（M7）：报出画面中间的淡色空白块、分层之间的白缝、局部直边露缝（见 engine/blank.py）。
合成器出片时自带这项检查（只看场景，不含字幕）；这个脚本是给已经有的东西用的（标定阈值、reviewer 对老片子查一遍）。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  blank_scan.py --bare tj02 [--every 0.5]           按分镜表逐镜头每 0.5 秒画一帧「只有背景 / 人物 / 前景三层」的画面再查（和出片时同一套检查，
                                                    没有字幕、卡片、特效的干扰，推荐；要读素材和配音时间线，整集约 1–2 分钟）。
                                                    扫描范围是整屏 y 0–1920（标题条、字幕卡在这个模式里本来就不画，底部 300 像素平台遮挡区也要有画；
                                                    淡色大块 / 白缝 / 直边平条扫 y 8–1912，engine/blank.py 的直边检测要读上下各 2 行，到不了最边上），
                                                    另外认「纸底色」：图层没盖住的地方露出画布的纸底色（C.PAPER，平涂），连成厚 ≥ 10、面积 ≥ 400 像素²
                                                    的一块就报（待补 23：tj03 第一版书房镜头只铺了 1620 高的 wall.png，最下面 300 像素空米色条，米色不算「淡色」、
                                                    以前扫不到）。这一项只在这个模式里做（成片里有字幕卡 / 标题条，纸底色和卡片底色分不开）。
  blank_scan.py video/out/tj01/full/tj01_full.mp4 [tj01] [--every 0.5]
                                                    解码成片查（只有成片没有分镜表时用）。成片里有字幕、卡片、特效，局部直边那一项会多排除卡片边框，
                                                    而且要求连续两个采样点都在同一个位置；仍可能把特效线之类误报，仅供参考。
                                                    给了集名（或分镜表路径）就把每个时间点对到镜头号。
退出码：0 = 没有空白，1 = 有。
"""
import argparse
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import blank  # noqa: E402
from engine import consts as C  # noqa: E402

W2, H2 = 540, 960                       # 解码成片时的分辨率（局部直边要 540×960；detect 内部自己缩到各检查的工作分辨率）
BARE_Y0, BARE_Y1 = 8, C.H - 8           # --bare：淡色大块 / 白缝 / 直边平条扫的范围（blank._straight_edges 要读 y0 − 2 … y1 + 2 行，所以不到最边上 8 像素）
PAPER_BGR = np.array([C.PAPER[2], C.PAPER[1], C.PAPER[0]], np.int16)
PAPER_TOL = 3                           # 纸底色：三个通道和 C.PAPER 都差 ≤ 3（没画到的格子就是整幅填的纸底色，一点不差；有一点点盖住的像素会被图的颜色拉开）
PAPER_GRID = 2                          # 纸底色检测在 540×960 上做（2 个设计像素一格）
PAPER_MIN_PX, PAPER_MIN_AREA = 10, 400  # 厚 ≥ 10 设计像素（同 storyboard_check 的 FILL_ERR_PX、blank.py 的 STRIP_H 下限）、面积 ≥ 400 像素² 才报（图边抗锯齿、贴着屏幕边的几像素不报）


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


def uncovered_paper(img):
    """bare 画面（1080×1920 BGR）里露出画布纸底色的地方（没有任何图层盖住）→ [{"kind": "paper", "bbox": [x0, y0, x1, y1]（设计坐标）, "area": 占整幅画面的比例}]。
    不看饱和度也不看纹理：纸底色就是整幅画布一开始填的 C.PAPER，没盖住的格子一点不差，所以直接比颜色；整屏 y 0–1920。
    （engine/blank.py 的淡色大块靠「饱和度 < 20」认空白，C.PAPER 的饱和度是 33，不算淡色，所以底部那条米色空条一直扫不到。）"""
    m = (np.abs(img.astype(np.int16) - PAPER_BGR).max(2) <= PAPER_TOL).astype(np.uint8)
    g = cv2.resize(m, (C.W // PAPER_GRID, C.H // PAPER_GRID), interpolation=cv2.INTER_AREA)          # 任何分辨率都缩 / 放到 540×960
    g = cv2.morphologyEx((g > 0.5).astype(np.uint8), cv2.MORPH_OPEN, np.ones((max(1, PAPER_MIN_PX // PAPER_GRID),) * 2, np.uint8),
                         borderType=cv2.BORDER_CONSTANT, borderValue=0)                                                    # 画面外面算「不是纸底色」：贴着屏幕边的细缝不会因为 cv2 默认的腐蚀边界当无穷而显得更厚
    n, _, st, _ = cv2.connectedComponentsWithStats(g, connectivity=8)
    sx = sy = float(PAPER_GRID)                                         # 格子 → 设计坐标
    out = []
    for i in range(1, n):
        area = int(st[i][4]) * sx * sy
        if area >= PAPER_MIN_AREA:
            x0, y0, bw, bh = (int(v) for v in st[i][:4])
            out.append({"kind": "paper", "bbox": [round(x0 * sx), round(y0 * sy), round((x0 + bw) * sx), round((y0 + bh) * sy)], "area": round(area / (C.W * C.H), 4)})
    return out


@contextmanager
def wide_range():
    """把 engine/blank.py 的扫描范围临时放大到整屏（BARE_Y0–BARE_Y1），出来时还原。blank.py 自己的范围常量（consts.BLANK_Y0 / Y1 = 340 / 1400）一个字不动。"""
    saved = C.BLANK_Y0, C.BLANK_Y1
    C.BLANK_Y0, C.BLANK_Y1 = BARE_Y0, BARE_Y1
    try:
        yield
    finally:
        C.BLANK_Y0, C.BLANK_Y1 = saved


def detect_bare(img):
    """--bare 的一帧：engine/blank.py 的检查（整屏范围）+ 纸底色。"""
    with wide_range():
        found = blank.detect(img)
    paper = uncovered_paper(img)
    found = [e for e in found if not any(blank._inside(e["bbox"], p["bbox"]) >= 0.5 for p in paper)]       # 同一块地方（淡色平条 / 大块把纸底色也算进去了）只报「纸底色」那一条
    if len(paper) > 1:                                                                                      # 同一帧里好几块（桌腿之间、几条地面缝）合成一条：外框是并集，面积是各块之和
        x0, y0 = min(p["bbox"][0] for p in paper), min(p["bbox"][1] for p in paper)
        x1, y1 = max(p["bbox"][2] for p in paper), max(p["bbox"][3] for p in paper)
        paper = [{"kind": "paper", "bbox": [x0, y0, x1, y1], "area": round(sum(p["area"] for p in paper), 4), "n": len(paper)}]
    return found + paper


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
            rows.append((t, sid, detect_bare(img)))
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
    # 同一处露缝连续几帧都在：合成一行（同镜头、同种、和这一组上一个采样点的位置比：y 上沿差 ≤ 12（纸底色 ≤ 24：镜头推 / 摇时它每 0.5 秒会漂十几个像素）、横向重叠 ≥ 50%，时间间隔 ≤ 2 个采样间隔）
    groups = []
    for t, sid, e in hits:
        tol = 24 if e["kind"] == "paper" else 12
        for g in groups:
            if (g["sid"] == sid and g["e"]["kind"] == e["kind"] and t - g["t1"] <= 2.5 * a.every and abs(g["last"][1] - e["bbox"][1]) <= tol
                    and blank._inside(e["bbox"], g["last"]) >= 0.5):
                g["t1"], g["n"], g["last"] = t, g["n"] + 1, e["bbox"]
                if e["area"] > g["e"]["area"]:
                    g["e"] = e                                       # 一组里面积最大的那个采样点当代表
                break
        else:
            groups.append(dict(sid=sid, e=e, t0=t, t1=t, n=1, last=e["bbox"]))
    names = {"block": "大块", "seam": "白缝", "strip": "直边平条", "paper": "纸底色（没铺满）"}
    for g in groups:
        e = g["e"]
        when = mmss(g["t0"]) if g["n"] == 1 else f"{mmss(g['t0'])}–{mmss(g['t1'])}"
        extra = f"，厚 {e['h']:.0f}，颜色 RGB{tuple(e['color'])}" if e["kind"] == "strip" else f"，{e['n']} 块（外框是并集，面积是各块之和）" if e.get("n", 1) > 1 else ""
        print(f"{when}  {g['sid'] or ''}  {names[e['kind']]}  bbox {e['bbox']}  面积 {e['area']:.2%}{extra}  （{g['n']} 个采样点）")
    ids = sorted({g["sid"] for g in groups if g["sid"]}, key=lambda s: (len(s), s))
    print(f"共 {len(hits)} 处、{len(groups)} 组（抽了 {n} 帧）" + (f"，镜头：{', '.join(ids)}" if ids else ""))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
