"""渲染一个「片段」：一个镜头的最终画面（场景 + 它的转场 + 字幕 / 标题条 / 水印），直接用成片的编码参数编码成一个 .mp4，按输入哈希缓存。
最后整集 = 把所有片段用 ffmpeg concat 拷贝流拼起来（不重编码）+ 整条音轨混进去。所以改一两个镜头只重编码这一两个片段（加上转场相邻的镜头）。

片段 = 帧范围 [f0, f1)（镜头从自己的 from 到下一镜的 from，片段之间严丝合缝）。转场以切点为中心：
  · 本镜有进场转场：开头 b 帧 = 前一镜（切点之后接着走的 b 帧）和本镜的混合；
  · 下一镜有进场转场：结尾 a 帧 = 本镜和下一镜（停在开头姿势的 a 帧）的混合。
所以一个片段要画本镜的全部帧，加上相邻镜头的几帧；相邻镜头的几帧就地画（在子进程里重新建它的 Scene），不再缓存整镜头的场景视频。
片段太长就再按 CHUNK_FRAMES（50）帧切成几块，每块一个子进程、各自编码缓存（每块从 IDR 开始，拼接照样无缝；每一帧只依赖绝对时间，所以分块渲和一个进程从头渲出来的画面一模一样）。
每一帧最后算一个哈希记在 meta.json 里：同样的输入，每一帧的哈希都一样（验收 ①）。空白检测、亮度和相邻帧差也在这里算好存进缓存，拼接时不用再解码。
在子进程里跑（Windows 用 spawn，所以入口函数必须能被 import）。
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from . import blank, checks
from . import consts as C
from .canvas import Canvas

_STORES = {}
_UIS = {}
STORE_MAX_BYTES = 800 * 1024 * 1024        # 一个进程里缓存的图最多占这么多内存，超过就清掉重来


def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError("找不到 ffmpeg：请把 ffmpeg 装进 PATH")
    return p


def frame_hash(frame):
    return hashlib.blake2b(frame, digest_size=8).hexdigest()


def init_worker():
    import cv2
    cv2.setNumThreads(1)


def encode_cmd(w, h, mode, out):
    """一个片段的编码命令：每个片段同一套参数、从 IDR 开始、闭合 GOP（x264 默认）→ 拼起来无缝。"""
    return [ffmpeg_path(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-framerate", str(C.FPS), "-i", "-",
            "-an", "-vf", C.RGB2YUV, *C.VENC[mode], *C.COLOR_TAGS, "-threads", str(C.SEG_THREADS), str(out)]


def make_job(plan, sp, cache, mode, chunk=None):
    """计划里的一个镜头 → 渲染片段要的全部输入（都是能 pickle 的普通数据）。chunk = (起帧, 止帧, 块哈希)：只渲这一块；不给 = 整个镜头（测试用）。"""
    c0, c1, ckey = chunk if chunk else (sp.f0, sp.f1, sp.skey)
    def info(s):
        return dict(id=s.id, key=s.key, spec=s.spec, f0=s.f0, f1=s.f1)
    shots = plan.shots
    prev = shots[sp.idx - 1] if sp.trans else None
    nxt = shots[sp.idx + 1] if sp.idx + 1 < len(shots) and shots[sp.idx + 1].trans else None
    return dict(ckey=ckey, c0=c0, c1=c1, cache_dir=str(cache), mode=mode, scale=plan.scale, own=info(sp),
                prev=info(prev) if prev else None, trans_in=_tr(sp.trans),
                next=info(nxt) if nxt else None, trans_out=_tr(nxt.trans) if nxt else None,
                timeline_dir=str(plan.voice), roots=[str(r) for r in plan.roots], fx_dirs=[str(d) for d in plan.fx_dirs],
                sb_ui={k: plan.sb.get(k) for k in ("title", "no", "name", "speakers") if k in plan.sb})


def _tr(t):
    return None if t is None else {"type": t["type"], "params": t["params"], "a": t["a"], "b": t["b"]}


def _context(job):
    """进程里一份的东西：特效插件、时间线、素材仓库（跨片段复用，省得每个镜头重读背景图）、界面。"""
    import fx as fxreg
    from .sprites import AssetStore
    from .timeline import Timeline
    from .ui import UI
    fxreg.load_plugins(job["fx_dirs"])
    tl = Timeline.load(job["timeline_dir"])
    skey = (job["scale"], tuple(job["roots"]))
    store = _STORES.get(skey)
    if store is None:
        store = _STORES[skey] = AssetStore(job["scale"], job["roots"])
    ukey = (job["scale"], json.dumps(job["sb_ui"], sort_keys=True, ensure_ascii=False), job["timeline_dir"], tuple(job["roots"]))
    ui = _UIS.get(ukey)
    if ui is None:
        _UIS.clear()
        ui = _UIS[ukey] = UI(store, tl, job["sb_ui"])
    return fxreg, tl, store, ui


def _scene(info, tl, store, fxreg):
    from .scene import Scene
    sc = Scene(info["spec"], tl, info["f0"] / C.FPS, (info["f1"] - info["f0"]) / C.FPS, store, fxreg.FX)
    sc.f0i = info["f0"]                                # 整数帧号：镜头内时间 = (f − f0i) / 30，和以前一模一样
    return sc


def sample_frames(f0, f1, b_in, a_out):
    """空白检测抽哪几帧：镜头内 BLANK_SAMPLES 这几个位置，躲开转场混合的帧。"""
    lo, hi = f0 + b_in, f1 - a_out
    out = []
    for r in C.BLANK_SAMPLES:
        f = min(max(f0 + int(r * (f1 - f0)), lo), hi - 1)
        if lo <= f < hi and f not in out:
            out.append(f)
    return out


def iter_segment(job, with_ui=True, blank_out=None):
    """逐帧产出这个片段的最终画面 (帧号, BGR 数组)。数组是同一块缓冲，调用的人要保留就自己复制。
    with_ui=False：不加字幕、标题条、水印（测试用）。blank_out 给一个 list：抽到的帧上做空白检测，结果追加进去。"""
    fxreg, tl, store, ui = _context(job)
    S = job["scale"]
    own = _scene(job["own"], tl, store, fxreg)
    prev = _scene(job["prev"], tl, store, fxreg) if job["trans_in"] else None
    nxt = _scene(job["next"], tl, store, fxreg) if job["trans_out"] else None
    f0, f1 = job["own"]["f0"], job["own"]["f1"]
    c0, c1 = job["c0"], job["c1"]                      # 只渲这一块（整个镜头 = [f0, f1)）
    tin, tout = job["trans_in"], job["trans_out"]
    b_in = tin["b"] if tin else 0
    a_out = tout["a"] if tout else 0
    plug_in = fxreg.TRANSITIONS[tin["type"]] if tin else None
    plug_out = fxreg.TRANSITIONS[tout["type"]] if tout else None
    seeds = {id(own): int(job["own"]["key"][:8], 16)}
    if prev:
        seeds[id(prev)] = int(job["prev"]["key"][:8], 16)
    if nxt:
        seeds[id(nxt)] = int(job["next"]["key"][:8], 16)
    cvA = Canvas(store, S, C.FPS, own.dur)
    cvB = Canvas(store, S, C.FPS, own.dur)
    cvS = Canvas(store, S, C.FPS, own.dur)
    tc = Canvas(store, S, C.FPS, 0.0)                  # 转场函数拿到的画布（用它的 assets、尺寸）
    cvU = Canvas(store, S, C.FPS, 0.0)                 # 界面画在它上面
    if with_ui:
        ui.prepare(c0, c1)
    samples = {f for f in sample_frames(f0, f1, b_in, a_out) if c0 <= f < c1} if blank_out is not None else set()

    def draw(cv, sc, f, bare=False):
        cv.rng = np.random.default_rng([seeds[id(sc)], f])        # 每一帧重新播种：同一帧永远拿到同样的随机数，和渲染顺序无关
        sc.draw(cv, (f - sc.f0i) / C.FPS, f / C.FPS, bare=bare)

    for f in range(c0, c1):
        if nxt is not None and f >= f1 - a_out:                     # 快到切点：本镜收尾 + 下一镜开头
            draw(cvA, own, f)
            draw(cvB, nxt, f)
            frame = plug_out.fn(cvA.img, cvB.img, (f - (f1 - a_out) + 0.5) / (a_out + tout["b"]), tout["params"], tc)
        elif prev is not None and f < f0 + b_in:                    # 切点之后：接着混完
            draw(cvA, prev, f)
            draw(cvB, own, f)
            frame = plug_in.fn(cvA.img, cvB.img, (f - (f0 - tin["a"]) + 0.5) / (tin["a"] + b_in), tin["params"], tc)
        else:
            draw(cvA, own, f)
            frame = cvA.img
        frame = np.ascontiguousarray(frame, np.uint8)
        if frame.shape != (cvA.h, cvA.w, 3):
            raise RuntimeError(f"转场返回的画面尺寸 {frame.shape} 不对，应该是 {(cvA.h, cvA.w, 3)}")
        if f in samples:
            draw(cvS, own, f, bare=True)
            for e in blank.detect(cvS.img):
                blank_out.append(dict(e, shot=job["own"]["id"], frame=f, t=round(f / C.FPS, 3)))
        if with_ui:
            cvU.img = frame
            ui.draw(cvU, f)
        yield f, frame


def render_segment(job):
    """渲染并编码一块 → 缓存目录 <cache>/seg/<ckey>/（seg.mp4、meta.json、metrics.npz）。返回 {"ckey", "frames", "sec"}。"""
    init_worker()
    t_start = time.time()
    out = Path(job["cache_dir"]) / "seg" / job["ckey"]
    if (out / "meta.json").exists():
        return {"ckey": job["ckey"], "cached": True}
    tmp = Path(job["cache_dir"]) / "seg" / f".tmp-{job['ckey']}-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    S = job["scale"]
    w, h = round(C.W * S), round(C.H * S)
    enc = subprocess.Popen(encode_cmd(w, h, job["mode"], tmp / "seg.mp4"), stdin=subprocess.PIPE)
    hashes, blanks, metrics = [], [], checks.FrameMetrics()
    try:
        for f, frame in iter_segment(job, True, blanks):
            enc.stdin.write(frame.data)
            hashes.append(frame_hash(frame))
            metrics.push(frame)
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError(f"镜头 {job['own']['id']}：ffmpeg 编码失败")
    except BaseException:
        enc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    finally:
        for st in _STORES.values():
            st.trim(STORE_MAX_BYTES)
    metrics.save(tmp / "metrics.npz")
    meta = {"ckey": job["ckey"], "id": job["own"]["id"], "f0": job["c0"], "f1": job["c1"], "frames": len(hashes), "hashes": hashes,
            "blank": blanks, "mode": job["mode"], "sec": round(time.time() - t_start, 2)}
    (tmp / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    if out.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        os.replace(tmp, out)
    return {"ckey": job["ckey"], "frames": len(hashes), "sec": meta["sec"]}
