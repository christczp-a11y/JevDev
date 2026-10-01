#!/usr/bin/env python
"""动态漫画合成器：读 video/stories/<集>/storyboard.json，出片（竖屏 1080×1920，30 帧，带配音、音效、背景音乐）。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  python video/motion/render.py tj01                  整集（默认码率）
  python video/motion/render.py tj01 --preview        半分辨率（540×960），快
  python video/motion/render.py tj01 --final          发布版：高码率、慢编码（片段也用发布码率，不再整片重编码）
  python video/motion/render.py tj01 --shots 1-1,1-2  只渲、拼、混这几镜（时间线按镜头裁）
  python video/motion/render.py path/to/storyboard.json ...
其它：--jobs N 并行进程数；--out 目录；--cache-dir 目录；--no-cache 忽略缓存重渲选中的镜头；--frame-hashes 报告里写每一帧的哈希。
截段：每个镜头（含它的转场、字幕）单独编码成一个片段，按输入哈希缓存；整集 = 片段 concat 拷贝流拼起来（不重编码）+ 整条音轨。改一两个镜头只重编码这一两个片段。
退出码：0 = 出片成功、自动检查全过；1 = 出了片但自动检查没过（闪烁、静止、响度、人声、空白，见报告）；2 = 输入有错（分镜表、素材、字体、音乐），没有出片。
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
from engine.plan import PlanError, build_plan, parse_shot_ids   # noqa: E402
from engine.segment import ffmpeg_path, init_worker, make_job, render_segment   # noqa: E402


def storyboard_path(arg):
    p = Path(arg)
    if p.suffix == ".json" and p.exists():
        return p
    q = C.VIDEO / "stories" / arg / "storyboard.json"
    if q.exists():
        return q
    sys.exit(f"找不到分镜表：{arg}（也没有 {q}）")


def mux(plan, seg_root, wav_path, out_path, mode, list_path):
    """把选中的片段按顺序 concat 拷贝流拼起来，和整条音轨一起写成成片（视频不重编码，音频编码一次 aac）。返回成片里的视频帧数。"""
    with open(list_path, "w", encoding="utf-8") as f:
        for sp in plan.selected:
            for _, _, ck in sp.chunks:
                f.write("file '" + str((seg_root / ck / "seg.mp4").resolve()).replace("\\", "/") + "'\n")
    p = subprocess.run([ffmpeg_path(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(list_path), "-i", str(wav_path),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", C.ABITRATE[mode], "-movflags", "+faststart", str(out_path)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg 拼接失败：{p.stderr.strip()[:400]}")
    q = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out_path)],
                       capture_output=True, text=True)
    return int(q.stdout.strip().split(",")[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description="动态漫画合成器", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("episode", help="集名（video/stories/<集>/storyboard.json）或分镜表路径")
    ap.add_argument("--preview", action="store_true", help="半分辨率")
    ap.add_argument("--final", action="store_true", help="发布版：高码率、慢编码（片段也用发布码率，不再整片重编码）")
    ap.add_argument("--shots", help="只出这几镜，逗号分隔，例如 1-1,1-2")
    ap.add_argument("--jobs", type=int, help="并行进程数（默认 CPU 数 − 1）")
    ap.add_argument("--out", help="输出目录（默认 video/out/motion/<集>/）")
    ap.add_argument("--cache-dir", help="片段缓存目录（默认 video/out/motion/_cache）")
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
        plan = build_plan(sb_path, parse_shot_ids(a.shots), scale, mode)
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
    seg_root = cache / "seg"
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_root.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / f"{name}.mp4"
    wav = out_dir / f"{name}.wav"

    # ---------- 渲片段（多进程，按输入哈希缓存；片段 = 一个镜头的最终画面，已经编码好） ----------
    t = time.time()
    todo = []                                           # [(镜头, 块)]：缓存里没有的块
    for sp in plan.selected:
        for ch in sp.chunks:
            d = seg_root / ch[2]
            if a.no_cache and d.exists():
                shutil.rmtree(d, ignore_errors=True)
            if not (d / "meta.json").exists():
                todo.append((sp, ch))
    n_jobs = a.jobs or max(1, (os.cpu_count() or 2) - 1)
    todo_shots = {sp.id for sp, _ in todo}
    n_chunks = sum(len(sp.chunks) for sp in plan.selected)
    print(f"{plan.sb['episode']}：{len(plan.selected)} 个镜头、{plan.out_frames} 帧（{plan.out_frames / C.FPS:.1f} 秒），"
          f"{len(plan.selected) - len(todo_shots)} 个镜头的片段全部用缓存，重渲 {len(todo_shots)} 个镜头（{len(todo)}/{n_chunks} 块，{min(n_jobs, max(1, len(todo)))} 个进程）", flush=True)
    todo.sort(key=lambda t: (-(t[0].f1 - t[0].f0), t[0].idx, t[1][0]))      # 长镜头先开工；同一个镜头的几块挨着排（同一个进程连着渲，素材不用重读）
    if todo:
        jobs = [make_job(plan, sp, cache, mode, ch) for sp, ch in todo]
        try:
            if len(jobs) == 1 or n_jobs == 1:
                for j in jobs:
                    render_segment(j)
            else:
                with ProcessPoolExecutor(max_workers=min(n_jobs, len(jobs)), initializer=init_worker) as ex:
                    futs = {ex.submit(render_segment, j): j for j in jobs}
                    for k, fu in enumerate(as_completed(futs), 1):
                        fu.result()
                        if k % 5 == 0 or k == len(jobs):
                            print(f"  块 {k}/{len(jobs)}", flush=True)
        except Exception as e:
            print(f"渲染镜头失败：{type(e).__name__}: {e}")
            return 2
    t_render = time.time() - t

    # ---------- 混音（整条音轨单独混好） ----------
    t = time.time()
    pcm, ainfo = audiomix.build(plan)
    assert len(pcm) == plan.out_frames * audiomix.SPF, (len(pcm), plan.out_frames)
    audiomix.write_wav(wav, pcm)
    t_audio = time.time() - t

    # ---------- 拼接（拷贝流）+ 音轨 ----------
    t = time.time()
    try:
        n_video = mux(plan, seg_root, wav, out_mp4, mode, out_dir / f"{name}.concat.txt")
    except RuntimeError as e:
        print(e)
        return 2
    if n_video != plan.out_frames:
        print(f"拼接出来 {n_video} 帧，应该是 {plan.out_frames} 帧：片段缓存坏了？加 --no-cache 重渲")
        return 2
    t_asm = time.time() - t

    # ---------- 自动检查（逐片段的结果都在缓存里，不用再解码成片） ----------
    metas, parts = [], []
    for sp in plan.selected:
        for _, _, ck in sp.chunks:
            metas.append(json.loads((seg_root / ck / "meta.json").read_text(encoding="utf-8")))
            z = np.load(seg_root / ck / "metrics.npz")
            parts.append({k: z[k] for k in z.files})
    luma, diff = checks.merge_metrics(parts)
    blanks = [e for m in metas for e in m["blank"]]
    lufs, peak = audiomix.measure_file(out_mp4)
    report = {
        "episode": plan.sb["episode"], "mode": mode, "shots": [sp.id for sp in plan.selected], "frames": plan.out_frames,
        "duration": round(plan.out_frames / C.FPS, 3), "out": str(out_mp4),
        "checks": {
            "flicker": {"events": checks.flicker(luma)},
            "static": {"events": checks.static(diff)},
            "loudness": checks.loudness(lufs, peak) if len(pcm) > 3 * audiomix.SR and ainfo["voice_lines"] else
                        {"lufs": round(lufs, 2), "true_peak_db": round(peak, 2), "ok": True, "skipped": "片段太短或没有台词，不查响度"},
            "voice": checks.voice(ainfo["voice_lines"]),
            "blank": {"events": blanks, "samples_per_shot": len(C.BLANK_SAMPLES)},
        },
        "audio": {k: v for k, v in ainfo.items() if k not in ("voice_spans", "voice_lines")},
        "timing": {"render_sec": round(t_render, 1), "audio_sec": round(t_audio, 1), "assemble_sec": round(t_asm, 1),
                   "total_sec": round(time.time() - t_all, 1), "cached_shots": len(plan.selected) - len(todo_shots), "rendered_shots": len(todo_shots),
                   "rendered_chunks": len(todo), "chunks": n_chunks,
                   "sec_per_30s_video": round((time.time() - t_all) / max(plan.out_frames / C.FPS / 30, 1e-9), 1)},
        "warnings": plan.warnings,
    }
    for k in ("flicker", "static", "blank"):
        report["checks"][k]["ok"] = not report["checks"][k]["events"]
    report["ok"] = all(c["ok"] for c in report["checks"].values())
    if a.frame_hashes:
        report["frame_hashes"] = [h for m in metas for h in m["hashes"]]
    rp = out_dir / f"{name}.report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    ck = report["checks"]
    print(f"→ {out_mp4}（{report['duration']} 秒，总共 {report['timing']['total_sec']} 秒）")
    print(f"  响度 {ck['loudness']['lufs']} LUFS，真峰值 {ck['loudness']['true_peak_db']} dB；"
          f"闪烁 {len(ck['flicker']['events'])} 处；静止 > {C.STATIC_MAX_SEC} 秒 {len(ck['static']['events'])} 处；台词没有人声 {len(ck['voice']['missing'])} 句；"
          f"空白 {len(blanks)} 处")
    for k, c in ck.items():
        if not c["ok"]:
            if k == "blank":
                for e in blanks[:30]:
                    print(f"  ✗ 空白：镜头 {e['shot']}，{int(e['t'] // 60)}:{e['t'] % 60:04.1f}，{'大块' if e['kind'] == 'block' else '白缝'}，位置 {e['bbox']}，占画面 {e['area']:.1%}")
                if len(blanks) > 30:
                    print(f"  ……还有 {len(blanks) - 30} 处，见报告")
            else:
                print(f"  ✗ 自动检查不过：{k}：{json.dumps({x: y for x, y in c.items() if x != 'ok'}, ensure_ascii=False)[:400]}")
    print(f"  报告：{rp}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
