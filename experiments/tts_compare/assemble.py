"""拼对比.mp3：每个角色依次 A（Edge）→ B（VoiceDesign）→ C（克隆），每段前面一个短提示音。
  .venv-tts/Scripts/python experiments/tts_compare/assemble.py [--c-tag clone|xvec]
提示音：每个角色开头两声高音（1000 Hz）；A = 低音（440 Hz）、B = 中音（660 Hz）、C = 高音（880 Hz），各 0.15 秒。
每条音频先裁掉首尾静音（留 0.12 秒）。响度：A 对齐到有声部分 RMS -23 dBFS；B、C 只对齐一半（保留一半相对 A 的响度差，
「小声」不被抹平），峰值不超过 -1 dBFS。
同时写 对比.txt（每段的起止时间）；另出 对比_B抽三次.mp3（B 版同一句抽三次，看稳不稳）。
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"
SR = 24000


def tone(freq, dur=0.15):
    t = np.arange(int(SR * dur)) / SR
    y = 0.25 * np.sin(2 * np.pi * freq * t)
    fade = int(SR * 0.01)
    y[:fade] *= np.linspace(0, 1, fade)
    y[-fade:] *= np.linspace(1, 0, fade)
    return y.astype(np.float32)


def sil(sec):
    return np.zeros(int(SR * sec), dtype=np.float32)


def load_trim(p, pad=0.12):
    w, sr = sf.read(str(p), dtype="float32")
    if w.ndim > 1:
        w = w.mean(axis=1)
    if sr != SR:
        import librosa
        w = librosa.resample(w, orig_sr=sr, target_sr=SR)
    h = int(SR * 0.01)
    n = len(w) // h
    rms = np.sqrt((w[: n * h].reshape(n, h) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12) + 1e-12)
    idx = np.where(db > -40)[0]
    a, b = (idx[0] * h, (idx[-1] + 1) * h) if len(idx) else (0, len(w))
    a, b = max(0, a - int(pad * SR)), min(len(w), b + int(pad * SR))
    w = w[a:b]
    act = w[np.abs(w) > 0.02 * np.abs(w).max()]
    return w, float(20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9))


def to_level(w, cur, target_db):
    w = w * 10 ** ((target_db - cur) / 20)
    pk = np.abs(w).max()
    if pk > 0.89:
        w = w * (0.89 / pk)
    return w.astype(np.float32)


def main(c_tag="clone"):
    parts, cues, t = [], [], 0.0
    parts2, cues2, t2 = [], [], 0.0

    def add(y, label=None, second=False):
        nonlocal t, t2
        if second:
            if label:
                cues2.append((round(t2, 2), round(t2 + len(y) / SR, 2), label))
            parts2.append(y)
            t2 += len(y) / SR
        else:
            if label:
                cues.append((round(t, 2), round(t + len(y) / SR, 2), label))
            parts.append(y)
            t += len(y) / SR

    TARGET = -23.0
    for ln in LINES:
        i, w = ln["id"], ln["who"]
        for sec in (False, True):
            add(tone(1000, 0.1), second=sec); add(sil(0.08), second=sec); add(tone(1000, 0.1), second=sec); add(sil(0.5), second=sec)
        clips = {}
        for tag, pat in [("A", f"A_edge_{i}_{w}.wav"), ("B", f"B_design_{i}_{w}.wav"),
                         ("C", (f"C_clone_{i}_{w}.wav" if c_tag == "clone" else f"Cx_xvec_{i}_{w}.wav")),
                         ("B抽2", f"Bs_design_{i}_{w}_s1.wav"), ("B抽3", f"Bs_design_{i}_{w}_s2.wav")]:
            clips[tag] = load_trim(OUT / pat)
        la = clips["A"][1]
        def lvl(tag):   # 以 A 为基准，其他版本保留一半的响度差（「小声」不被完全抹平，也不至于听不见）
            return TARGET if tag == "A" else TARGET + 0.5 * (clips[tag][1] - la)
        for tag, freq, name in [("A", 440, "A Edge TTS"), ("B", 660, "B VoiceDesign"), ("C", 880, "C 参考音克隆")]:
            add(tone(freq)); add(sil(0.25))
            add(to_level(clips[tag][0], clips[tag][1], lvl(tag)), f"{i} {w}「{ln['text']}」 {name}")
            add(sil(0.7))
        for tag, name in [("B", "B 第1次"), ("B抽2", "B 第2次"), ("B抽3", "B 第3次")]:
            add(tone(660), second=True); add(sil(0.25), second=True)
            add(to_level(clips[tag][0], clips[tag][1], lvl(tag)), f"{i} {w}「{ln['text']}」 {name}", second=True)
            add(sil(0.7), second=True)
        add(sil(0.8)); add(sil(0.8), second=True)
    for parts_, cues_, name, head in [
        (parts, cues, "对比", "对比.mp3 时间表（秒）。每个角色开头两声高音；每段前一声提示音：低=A Edge TTS，中=B VoiceDesign，高=C 参考音克隆\n"
         "响度：A 对齐到 -23 dBFS，B、C 保留相对 A 的一半响度差（段规「小声」在 C 里比 A 低约 12 dB，这里低约 6 dB）。\n"),
        (parts2, cues2, "对比_B抽三次", "对比_B抽三次.mp3 时间表（秒）。同一段声音描述+同一句台词，换随机种子抽三次（每次一声中音提示）：听音色和语气稳不稳。\n")]:
        y = np.concatenate(parts_)
        wav = OUT / f"{name}.wav"
        sf.write(wav, y, SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "128k", str(OUT / f"{name}.mp3")], check=True)
        wav.unlink()
        (OUT / f"{name}.txt").write_text(head + "\n" + "\n".join(f"{a:7.2f} - {b:7.2f}  {lab}" for a, b, lab in cues_) + "\n", encoding="utf-8")
        print(f"ok {name}.mp3 {sum(len(p) for p in parts_)/SR:.1f}s")


if __name__ == "__main__":
    tag = "clone"
    if "--c-tag" in sys.argv:
        tag = sys.argv[sys.argv.index("--c-tag") + 1]
    main(tag)
