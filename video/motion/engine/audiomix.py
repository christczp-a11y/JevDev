"""混音：配音（最响）→ 音效 → 背景音乐（有人说话时自动压低），整集 −16 LUFS、真峰值 ≤ −1.5 dB。全部用 numpy 在绝对时间轴上摆，
再按镜头的帧范围切出来（--shots 只出几镜时，时间线比画面长也不会崩：PITFALLS A6）。响度用 ffmpeg 的 ebur128 量（BS.1770 / EBU R128）。
"""
import re
import shutil
import subprocess

import cv2
import numpy as np

from . import consts as C
from .plan import plan_sfx_path

SR = C.SR
SPF = SR // C.FPS               # 每帧多少个采样（44100 / 30 = 1470，整数）
_dec = {}


def ffmpeg():
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError("找不到 ffmpeg：请把 ffmpeg 装进 PATH")
    return p


def decode(path):
    """任何音频文件 → float32 立体声 44.1 kHz，形状 (n, 2)。"""
    path = str(path)
    if path not in _dec:
        p = subprocess.run([ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"ffmpeg 解不开 {path}：{p.stderr.decode('utf-8', 'replace')[:200]}")
        _dec[path] = np.frombuffer(p.stdout, "<f4").reshape(-1, 2).copy()
    return _dec[path]


def _parse_ebur128(text):
    i = re.findall(r"\bI:\s+(-?[\d.]+|-inf)\s+LUFS", text)
    pk = re.findall(r"\bPeak:\s+(-?[\d.]+|-inf)\s+dBFS", text)
    return (float(i[-1]) if i else float("-inf")), (float(pk[-1]) if pk else float("-inf"))


def measure(pcm):
    """(n, 2) float32 → (整体响度 LUFS, 真峰值 dBFS)。"""
    p = subprocess.run([ffmpeg(), "-nostats", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-af", "ebur128=peak=true", "-f", "null", "-"], input=np.ascontiguousarray(pcm, "<f4").tobytes(), capture_output=True)
    return _parse_ebur128(p.stderr.decode("utf-8", "replace"))


def measure_file(path):
    p = subprocess.run([ffmpeg(), "-nostats", "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True)
    return _parse_ebur128(p.stderr.decode("utf-8", "replace"))


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-9))


def place(dst, clip, t):
    """把 clip 放到 dst 的 t 秒处；越界的部分裁掉（时间线比画面长也不崩）。"""
    i = int(round(t * SR))
    a, b = max(i, 0), min(i + len(clip), len(dst))
    if b > a:
        dst[a:b] += clip[a - i:b - i]


def level_voice(clip):
    """每句配音先调到同一个有声部分 RMS（−21 dBFS），最多调 ±8 dB：不同角色的声音音量拉齐。"""
    m = clip.mean(axis=1)
    act = np.abs(m) > 10 ** (-40 / 20)
    if act.sum() < SR // 50:
        return clip
    g = C.VOICE_TARGET_DB - float(db(np.sqrt(np.mean(m[act] ** 2))))
    g = max(-C.VOICE_GAIN_LIMIT_DB, min(C.VOICE_GAIN_LIMIT_DB, g))
    return clip * 10 ** (g / 20)


def loop_bgm(bgm, n):
    """背景音乐不够长就首尾交叉淡入淡出循环接起来。"""
    if len(bgm) >= n:
        return bgm[:n]
    xf = int(C.BGM_LOOP_XFADE * SR)
    out = bgm.copy()
    ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
    while len(out) < n:
        nxt = bgm
        out[-xf:] = out[-xf:] * (1 - ramp) + nxt[:xf] * ramp
        out = np.concatenate([out, nxt[xf:]])
    return out[:n]


def duck_envelope(voice, n):
    """有人说话 = 1，没人 = 0，平滑过渡（攻击 0.08 秒、释放 0.6 秒，说话前提前 0.06 秒压），返回每个采样的 0..1。"""
    hop = SR // 100
    m = np.abs(voice).max(axis=1) if voice.ndim == 2 else np.abs(voice)
    nf = len(m) // hop
    rms = np.sqrt((m[:nf * hop].reshape(nf, hop) ** 2).mean(axis=1))
    act = (db(rms) > C.VOICE_SILENCE_DB).astype(np.uint8).reshape(1, -1)
    k = max(1, int(C.DUCK_HOLD * 100))
    act = cv2.morphologyEx(act, cv2.MORPH_CLOSE, np.ones((1, k), np.uint8))[0]     # 字与字之间的短停顿不放开音乐
    la = int(C.DUCK_LOOKAHEAD * 100)
    if la:
        act = np.concatenate([act[la:], np.zeros(la, np.uint8)])
    env = np.zeros(nf, np.float32)
    aa, ar = 1 - np.exp(-0.01 / C.DUCK_ATTACK), 1 - np.exp(-0.01 / C.DUCK_RELEASE)
    cur = 0.0
    for i in range(nf):
        tgt = float(act[i])
        cur += (tgt - cur) * (aa if tgt > cur else ar)
        env[i] = cur
    t = (np.arange(n) / SR) * 100 - 0.5
    return np.interp(t, np.arange(nf), env).astype(np.float32)


def limit(x, thr):
    """带前瞻的简单限幅器：先算每个采样需要的衰减，取 ±5 毫秒的最小值再平滑，保证不超过 thr。"""
    peak = np.abs(x).max(axis=1)
    if peak.max() <= thr:
        return x
    g = np.minimum(1.0, thr / np.maximum(peak, 1e-9)).astype(np.float32).reshape(1, -1)
    w = int(0.005 * SR) * 2 + 1
    g = cv2.blur(cv2.erode(g, np.ones((1, w), np.uint8)), (w, 1))
    return x * g.reshape(-1, 1)


def normalize(mix, target=C.LUFS_TARGET, peak_max=C.PEAK_MAX_DB):
    """把 mix 调到目标响度，同时真峰值不超过 peak_max。返回 (pcm, 实测 LUFS, 实测真峰值 dB, 迭代次数)。"""
    lufs, tp = measure(mix)
    if not np.isfinite(lufs):
        return mix, lufs, tp, 0
    g = target - lufs
    thr_db = peak_max - 0.6
    y = mix
    for it in range(1, 8):
        y = limit(mix * 10 ** (g / 20), 10 ** (thr_db / 20))
        lufs2, tp2 = measure(y)
        if abs(lufs2 - target) <= 0.25 and tp2 <= peak_max:
            return y, lufs2, tp2, it
        if tp2 > peak_max:
            thr_db -= (tp2 - peak_max) + 0.2
        g += target - lufs2
    return y, lufs2, tp2, it


def build(plan):
    """按计划里选中的镜头范围混出音频 → (pcm (n,2) float32, 信息 dict)。pcm 长度 = 输出帧数 × 1470。"""
    tl = plan.tl
    n_abs = int(np.ceil(plan.t_end * SR)) + SR
    ranges = _merge(plan.ranges)
    voice = np.zeros((n_abs, 2), np.float32)
    sfx = np.zeros((n_abs, 2), np.float32)

    def in_range(t0, t1):
        return any(t1 > a / C.FPS and t0 < b / C.FPS for a, b in ranges)

    spans = []
    for i, ln in enumerate(tl.lines):
        if tl.is_speech(i) and in_range(ln["t0"], ln["t1"]):
            path = tl.audio_path(i)
            clip = level_voice(decode(path))
            place(voice, clip, ln["t0"])
            spans.append((i, ln["t0"], ln["t1"]))
    for t, name, g, sid in plan.sfx_events:
        if in_range(t - 0.05, t + 0.3):
            clip = decode(plan_sfx_path(plan, name))
            place(sfx, clip * 10 ** ((C.SFX_GAIN_DB + g) / 20), t)
    # 背景音乐：整首调到和配音同样的 RMS，再按（没人说话 −13 dB / 说话时再 −10 dB）压
    raw = decode(C.BGM)
    raw = raw[int(float(plan.sb.get("bgm_start", 0.0)) * SR):]        # 分镜表可以写 bgm_start：从音乐第几秒开始放（样片合集避开音乐里的空拍）
    bgm = loop_bgm(raw, n_abs)
    bgm = bgm * 10 ** ((C.VOICE_TARGET_DB - float(db(np.sqrt(np.mean(raw ** 2))))) / 20)
    env = duck_envelope(voice, n_abs)
    bgm = bgm * (10 ** (C.BGM_OPEN_DB / 20) * 10 ** (C.BGM_DUCK_DB / 20 * env))[:, None]
    # 按镜头范围切出来拼上，接缝处各淡 8 毫秒
    def cut(x):
        parts = []
        for a, b in ranges:
            seg = x[a * SPF:b * SPF].copy()
            if len(seg) < (b - a) * SPF:
                seg = np.concatenate([seg, np.zeros(((b - a) * SPF - len(seg), 2), np.float32)])
            f = int(0.008 * SR)
            seg[:f] *= np.linspace(0, 1, f, dtype=np.float32)[:, None]
            seg[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
            parts.append(seg)
        return np.concatenate(parts)
    v, s, m = cut(voice), cut(sfx), cut(bgm)
    fi, fo = min(int(C.BGM_FADE_IN * SR), len(m)), min(int(C.BGM_FADE_OUT * SR), len(m))
    m[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    m[len(m) - fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    mix = v + s + m
    info = {"voice_spans": spans}
    # 配音轨道有没有声音（每句台词的时段里）
    hop = SR // 100
    chk = []
    vm = np.abs(voice).max(axis=1)
    for i, t0, t1 in spans:
        a, b = int(t0 * SR), min(int(t1 * SR), len(vm))
        seg = vm[a:b]
        nf = len(seg) // hop
        ratio = float((db(np.sqrt((seg[:nf * hop].reshape(nf, hop) ** 2).mean(axis=1))) > C.VOICE_SILENCE_DB).mean()) if nf else 0.0
        chk.append({"line": i, "text": tl.lines[i]["text"], "voiced_ratio": round(ratio, 3)})
    info["voice_lines"] = chk
    y, lufs, tp, it = normalize(mix)
    info.update(lufs_mix=round(lufs, 2), tp_mix=round(tp, 2), norm_iterations=it)
    return np.ascontiguousarray(y, np.float32), info


def _merge(ranges):
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def write_wav(path, pcm):
    import wave
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
