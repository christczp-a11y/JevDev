#!/usr/bin/env python
"""动态漫画合成器：读 video/stories/<集>/storyboard.json，出片（竖屏 1080×1920，30 帧，带配音、音效、背景音乐）。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  python video/motion/render.py tj01                  整集（默认码率）
  python video/motion/render.py tj01 --preview        半分辨率（540×960），快
  python video/motion/render.py tj01 --final          发布版：高码率、慢编码
  python video/motion/render.py tj01 --shots 1-1,1-2  只渲、拼、混这几镜（时间线按镜头裁）
  python video/motion/render.py path/to/storyboard.json ...
其它：--jobs N 并行进程数；--out 目录；--cache-dir 目录；--no-cache 忽略缓存重渲选中的镜头；--frame-hashes 报告里写每一帧的哈希。
退出码：0 = 出片成功、自动检查全过；1 = 出了片但自动检查没过（闪烁、静止、响度、人声，见报告）；2 = 输入有错（分镜表、素材、字体、音乐），没有出片。
详细说明：video/motion/README.md
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

MOTION = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTION))

import numpy as np                                    # noqa: E402

from engine import audiomix, checks                   # noqa: E402
from engine import consts as C                        # noqa: E402
from engine.canvas import Canvas                      # noqa: E402
from engine.plan import PlanError, build_plan, parse_shot_ids   # noqa: E402
from engine.sprites import AssetStore                 # noqa: E402
from engine.worker import ffmpeg_path, frame_hash, init_worker, render_shot   # noqa: E402


def storyboard_path(arg):
    p = Path(arg)
    if p.suffix == ".json" and p.exists():
        return p
    q = C.VIDEO / "stories" / arg / "storyboard.json"
    if q.exists():
        return q
    sys.exit(f"找不到分镜表：{arg}（也没有 {q}）")


class ShotReader:
    """按顺序读一个缓存镜头的帧（ffmpeg 解成 BGR 原始数据）。first = 文件第一帧的绝对帧号。"""

    def __init__(self, path, first, w, h):
        self.pos, self.w, self.h = first, w, h
        self.n = w * h * 3
        self.p = subprocess.Popen([ffmpeg_path(), "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.n * 2)

    def _read(self):
        buf = np.empty((self.h, self.w, 3), np.uint8)
        mv = memoryview(buf).cast("B")
        got = 0
        while got < self.n:
            k = self.p.stdout.readinto(mv[got:])
            if not k:
                raise RuntimeError("缓存镜头的帧不够（缓存坏了？加 --no-cache 重渲）")
            got += k
        return buf

    def get(self, f):
        if f < self.pos:
            raise RuntimeError(f"读帧顺序错了：要第 {f} 帧，已经读到 {self.pos}")
        while self.pos < f:
            self._read()
            self.pos += 1
        fr = self._read()
        self.pos += 1
        return fr

    def close(self):
        try:
            self.p.stdout.close()
        finally:
            self.p.kill()
            self.p.wait()


def assemble(plan, cache, out_path, wav_path, mode, want_hashes):
    S = plan.scale
    store = AssetStore(S, plan.roots)
    cv = Canvas(store, S, C.FPS, 0.0)
    tc = Canvas(store, S, C.FPS, 0.0)                 # 转场函数拿到的画布（用它的 assets、尺寸）
    w, h = cv.w, cv.h
    plan.ui.prepare(min(a for a, _ in plan.ranges), max(b for _, b in plan.ranges))
    enc = subprocess.Popen([ffmpeg_path(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-framerate", str(C.FPS), "-i", "-",
                            "-i", str(wav_path), "-map", "0:v:0", "-map", "1:a:0", "-vf", C.RGB2YUV, *C.ENC[mode], *C.COLOR_TAGS,
                            "-c:a", "aac", "-movflags", "+faststart", str(out_path)], stdin=subprocess.PIPE)
    metrics, hashes, readers = checks.FrameMetrics(), [], {}
    sel = plan.selected

    def reader(sp):
        if sp.idx not in readers:
            readers[sp.idx] = ShotReader(cache / sp.key / "video.mp4", sp.f0 - sp.pre, w, h)
        return readers[sp.idx]

    def adjacent(a, b):
        return a is not None and b is not None and b.idx == a.idx + 1

    try:
        for si, sp in enumerate(sel):
            prev = sel[si - 1] if si > 0 and adjacent(sel[si - 1], sp) else None
            nxt = sel[si + 1] if si + 1 < len(sel) and adjacent(sp, sel[si + 1]) else None
            for f in range(sp.f0, sp.f1):
                if nxt is not None and nxt.trans and f >= nxt.f0 - nxt.trans["a"]:       # 快到切点：前一镜收尾 + 后一镜开头
                    tr, a, b = nxt.trans, nxt.trans["a"], nxt.trans["b"]
                    A, B = reader(sp).get(f), reader(nxt).get(f)
                    frame = tr["plug"].fn(A, B, (f - (nxt.f0 - a) + 0.5) / (a + b), tr["params"], tc)
                elif prev is not None and sp.trans and f < sp.f0 + sp.trans["b"]:       # 切点之后：接着混完
                    tr, a, b = sp.trans, sp.trans["a"], sp.trans["b"]
                    A, B = reader(prev).get(f), reader(sp).get(f)
                    frame = tr["plug"].fn(A, B, (f - (sp.f0 - a) + 0.5) / (a + b), tr["params"], tc)
                else:
                    frame = reader(sp).get(f)
                frame = np.ascontiguousarray(frame, np.uint8)
                if frame.shape != (h, w, 3):
                    raise RuntimeError(f"转场 {sp.trans and sp.trans['type']} 返回的画面尺寸 {frame.shape} 不对，应该是 {(h, w, 3)}")
                cv.img = frame
                plan.ui.draw(cv, f)
                metrics.push(frame)
                if want_hashes:
                    hashes.append(frame_hash(frame))
                enc.stdin.write(frame.data)
            for k in [k for k in readers if k < sp.idx]:      # 更早的镜头用完了
                readers.pop(k).close()
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError("ffmpeg 出片编码失败")
    except BaseException:
        enc.kill()
        raise
    finally:
        for r in readers.values():
            r.close()
    return metrics, hashes


def main(argv=None):
    ap = argparse.ArgumentParser(description="动态漫画合成器", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("episode", help="集名（video/stories/<集>/storyboard.json）或分镜表路径")
    ap.add_argument("--preview", action="store_true", help="半分辨率")
    ap.add_argument("--final", action="store_true", help="发布版：高码率、慢编码")
    ap.add_argument("--shots", help="只出这几镜，逗号分隔，例如 1-1,1-2")
    ap.add_argument("--jobs", type=int, help="并行进程数（默认 CPU 数 − 1）")
    ap.add_argument("--out", help="输出目录（默认 video/out/motion/<集>/）")
    ap.add_argument("--cache-dir", help="镜头缓存目录（默认 video/out/motion/_cache）")
    ap.add_argument("--no-cache", action="store_true", help="选中的镜头不用缓存，重渲")
    ap.add_argument("--frame-hashes", action="store_true", help="报告里写每一帧的哈希（测试可复现用）")
    a = ap.parse_args(argv)
    if a.preview and a.final:
        sys.exit("--preview 和 --final 不能一起用")
    mode = "preview" if a.preview else "final" if a.final else "normal"
    scale = 0.5 if a.preview else 1.0
    t_all = time.time()

    sb_path = storyboard_path(a.episode)
    try:
        plan = build_plan(sb_path, parse_shot_ids(a.shots), scale)
    except PlanError as e:
        print(f"分镜表有 {len(e.errors)} 处错误，没有出片：")
        for x in e.errors:
            print("  ✗", x)
        return 2
    except FileNotFoundError as e:
        print("找不到文件，没有出片：", e)
        return 2
    for x in plan.warnings:
        print("  ⚠", x)

    name = plan.sb["episode"] + ("_preview" if a.preview else "_final" if a.final else "")
    if a.shots:
        name += "_shots_" + "+".join(sp.id for sp in plan.selected)
    out_dir = Path(a.out) if a.out else C.OUT_ROOT / plan.sb["episode"]
    cache = Path(a.cache_dir) if a.cache_dir else C.OUT_ROOT / "_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"{name}.mp4"
    wav = out_dir / f"{name}.wav"

    # ---------- 渲镜头（多进程，按内容哈希缓存） ----------
    t = time.time()
    todo = []
    for sp in plan.selected:
        d = cache / sp.key
        if a.no_cache and d.exists():
            shutil.rmtree(d, ignore_errors=True)
        if not (d / "meta.json").exists():
            todo.append(sp)
    n_jobs = a.jobs or max(1, (os.cpu_count() or 2) - 1)
    print(f"{plan.sb['episode']}：{len(plan.selected)} 个镜头、{plan.out_frames} 帧（{plan.out_frames / C.FPS:.1f} 秒），"
          f"{len(plan.selected) - len(todo)} 个用缓存，渲 {len(todo)} 个（{min(n_jobs, max(1, len(todo)))} 个进程）", flush=True)
    todo.sort(key=lambda s: -(s.f1 - s.f0 + s.pre + s.post))
    if todo:
        jobs = [dict(key=sp.key, spec=sp.spec, f0=sp.f0, f1=sp.f1, pre=sp.pre, post=sp.post, timeline_dir=str(plan.voice), roots=[str(r) for r in plan.roots],
                     fx_dirs=[str(d) for d in plan.fx_dirs], scale=scale, cache_dir=str(cache)) for sp in todo]
        try:
            if len(jobs) == 1 or n_jobs == 1:
                for j in jobs:
                    render_shot(j)
            else:
                with ProcessPoolExecutor(max_workers=min(n_jobs, len(jobs)), initializer=init_worker) as ex:
                    futs = {ex.submit(render_shot, j): j for j in jobs}
                    for k, fu in enumerate(as_completed(futs), 1):
                        fu.result()
                        if k % 5 == 0 or k == len(jobs):
                            print(f"  镜头 {k}/{len(jobs)}", flush=True)
        except Exception as e:
            print(f"渲染镜头失败：{type(e).__name__}: {e}")
            return 2
    t_render = time.time() - t

    # ---------- 混音 ----------
    t = time.time()
    pcm, ainfo = audiomix.build(plan)
    assert len(pcm) == plan.out_frames * audiomix.SPF, (len(pcm), plan.out_frames)
    audiomix.write_wav(wav, pcm)
    t_audio = time.time() - t

    # ---------- 拼接、转场、界面、编码 ----------
    t = time.time()
    metrics, hashes = assemble(plan, cache, out_mp4, wav, mode, a.frame_hashes)
    t_asm = time.time() - t

    # ---------- 自动检查 ----------
    lufs, peak = audiomix.measure_file(out_mp4)
    report = {
        "episode": plan.sb["episode"], "mode": mode, "shots": [sp.id for sp in plan.selected], "frames": plan.out_frames,
        "duration": round(plan.out_frames / C.FPS, 3), "out": str(out_mp4),
        "checks": {
            "flicker": {"events": checks.flicker(metrics.luma)},
            "static": {"events": checks.static(metrics.diff)},
            "loudness": checks.loudness(lufs, peak) if len(pcm) > 3 * audiomix.SR and ainfo["voice_lines"] else
                        {"lufs": round(lufs, 2), "true_peak_db": round(peak, 2), "ok": True, "skipped": "片段太短或没有台词，不查响度"},
            "voice": checks.voice(ainfo["voice_lines"]),
        },
        "audio": {k: v for k, v in ainfo.items() if k not in ("voice_spans", "voice_lines")},
        "timing": {"render_sec": round(t_render, 1), "audio_sec": round(t_audio, 1), "assemble_sec": round(t_asm, 1),
                   "total_sec": round(time.time() - t_all, 1), "cached_shots": len(plan.selected) - len(todo), "rendered_shots": len(todo),
                   "sec_per_30s_video": round((time.time() - t_all) / max(plan.out_frames / C.FPS / 30, 1e-9), 1)},
        "warnings": plan.warnings,
    }
    for k in ("flicker", "static"):
        report["checks"][k]["ok"] = not report["checks"][k]["events"]
    report["ok"] = all(c["ok"] for c in report["checks"].values())
    if a.frame_hashes:
        report["frame_hashes"] = hashes
    rp = out_dir / f"{name}.report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    ck = report["checks"]
    print(f"→ {out_mp4}（{report['duration']} 秒，总共 {report['timing']['total_sec']} 秒）")
    print(f"  响度 {ck['loudness']['lufs']} LUFS，真峰值 {ck['loudness']['true_peak_db']} dB；"
          f"闪烁 {len(ck['flicker']['events'])} 处；静止 > {C.STATIC_MAX_SEC} 秒 {len(ck['static']['events'])} 处；台词没有人声 {len(ck['voice']['missing'])} 句")
    for k, c in ck.items():
        if not c["ok"]:
            print(f"  ✗ 自动检查不过：{k}：{json.dumps({x: y for x, y in c.items() if x != 'ok'}, ensure_ascii=False)[:400]}")
    print(f"  报告：{rp}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
