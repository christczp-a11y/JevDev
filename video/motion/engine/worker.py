"""渲染一个镜头 → 缓存目录（video.mp4 + meta.json）。在子进程里跑（Windows 用 spawn，所以入口函数必须能被 import）。
缓存里存的是「场景」（没有字幕、标题条、水印），用几乎无损的 x264 编码；字幕等界面和转场在合成阶段统一加。
每一帧算一个哈希记在 meta.json 里：同样的输入，每一帧的哈希都一样（验收 ①）。
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from . import consts as C


def ffmpeg_path():
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError("找不到 ffmpeg：请把 ffmpeg 装进 PATH")
    return p


def cache_enc_cmd(w, h, out):
    return [ffmpeg_path(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-framerate", str(C.FPS), "-i", "-",
            "-an", "-vf", C.RGB2YUV, *C.CACHE_ENC, *C.COLOR_TAGS, str(out)]


def frame_hash(frame):
    return hashlib.blake2b(frame, digest_size=8).hexdigest()


def init_worker():
    import cv2
    cv2.setNumThreads(1)


def render_shot(job):
    """job：spec、f0/f1/pre/post、时间线目录、素材根目录、fx 目录、比例、缓存目录、key。返回 {"key", "frames", "sec"}。"""
    import fx as fxreg
    from .canvas import Canvas
    from .scene import Scene
    from .sprites import AssetStore
    from .timeline import Timeline
    init_worker()
    t_start = time.time()
    out = Path(job["cache_dir"]) / job["key"]
    if (out / "meta.json").exists():
        return {"key": job["key"], "cached": True}
    fxreg.load_plugins(job["fx_dirs"])
    tl = Timeline.load(job["timeline_dir"])
    store = AssetStore(job["scale"], job["roots"])
    f0, f1, pre, post = job["f0"], job["f1"], job["pre"], job["post"]
    t0 = f0 / C.FPS
    scene = Scene(job["spec"], tl, t0, (f1 - f0) / C.FPS, store, fxreg.FX)
    seed = int(job["key"][:8], 16)
    cv = Canvas(store, job["scale"], C.FPS, (f1 - f0) / C.FPS, seed=seed)
    tmp = Path(job["cache_dir"]) / f".tmp-{job['key']}-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    enc = subprocess.Popen(cache_enc_cmd(cv.w, cv.h, tmp / "video.mp4"), stdin=subprocess.PIPE)
    hashes = []
    try:
        for f in range(f0 - pre, f1 + post):
            cv.rng = np.random.default_rng([seed, f])         # 每一帧重新播种：同一帧永远拿到同样的随机数，和渲染顺序无关
            scene.draw(cv, (f - f0) / C.FPS, f / C.FPS)
            enc.stdin.write(cv.img.data)
            hashes.append(frame_hash(cv.img))
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError(f"镜头 {scene.id}：ffmpeg 编码失败")
    except BaseException:
        enc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    meta = {"key": job["key"], "id": scene.id, "first_frame": f0 - pre, "frames": len(hashes), "hashes": hashes,
            "sec": round(time.time() - t_start, 2), "warnings": scene.warnings}
    (tmp / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if out.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        os.replace(tmp, out)
    return {"key": job["key"], "frames": len(hashes), "sec": meta["sec"]}
