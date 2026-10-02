"""背景音乐候选的自动筛选（PITFALLS A8 / 待补 21）：开头 5 秒和整首的「电子味」特征、有没有人声（Whisper）、响度归一。
用 .venv-music 跑（里面有 numpy / scipy / torch / transformers；不用显卡也行）：
    export PYTHONIOENCODING=utf-8
    .venv-music/Scripts/python video/music_screen.py video/out/bgm_cands/raw/cand_1.flac ... [--ref video/assets/audio/bgm_main.mp3] [--whisper]
    .venv-music/Scripts/python video/music_screen.py <文件> --normalize video/out/bgm_cands/bgm_cand_1.mp3 --trial video/out/bgm_cands/bgm_cand_1_30s.mp3
特征（每首量「开头 5 秒」和「整首」两份；HARD 里的不过 = 淘汰，SOFT = 嫌疑，阈值和标定依据见下面的 HARD / SOFT 表）：
  sub_db         35–65 Hz 的能量占比（dB）：底鼓 / 低音合成器的基频区，电子的对照组 ≥ −7，干净的拨弦候选 ≤ −20
  steady         持续音比例：150–4000 Hz 里够响的时频格子有多少在 0.5 秒窗口里电平起伏 < 6 dB（合成器垫底 / 风琴大，拨弦小）
  hf_comb        高频泛音梳：4–12 kHz 里既是频谱尖峰又长时间不变的格子占比（锯齿 / 方波持续音留下的一排排横线）
  hf_ratio_db    8 kHz 以上的能量占总能量（dB）；hf_sustain / hf_flux_db：3–10 kHz 包络的平稳程度
  kick_regular   35–110 Hz 低频冲击里「间隔、力度都均匀」的连续脉冲串最长多少个（四拍底鼓）；kick_per_min：每分钟冲击数
  rms_std_db     0.4 秒短时响度的标准差（过于平直的包络很小）；crest_db：峰值 − RMS
  flatness       频谱平坦度均值（噪声感）；centroid_hz：频谱重心
另外：Whisper 查人声（--whisper）、响度（ffmpeg ebur128）、--normalize 归一到 −20 LUFS 并截 30 秒试听版。
对照：旧 video/assets/audio/bgm_main.mp3（Chris 说「开头像电子音乐」）和 3 首故意写成电子音乐的对照组（video/music_gen.py --controls）。
这是第一道筛，不是音色分类器：过了的还要看频谱图（电子的合成器有一排排很规则的高频横线）、最后 Chris 听。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

SR = 44100
ROOT = Path(__file__).resolve().parents[1]


def decode(path, sr=SR, mono=True, start=None, dur=None):
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(path), "-f", "f32le", "-ac", "1" if mono else "2", "-ar", str(sr), "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:300])
    x = np.frombuffer(p.stdout, "<f4")
    return x if mono else x.reshape(-1, 2)


def ebur128(path):
    p = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True)
    t = p.stderr.decode("utf-8", "replace")
    g = lambda pat: (re.findall(pat, t) or [None])[-1]
    return dict(lufs=float(g(r"\bI:\s+(-?[\d.]+)\s+LUFS")), lra=float(g(r"\bLRA:\s+([\d.]+)\s+LU")), true_peak_db=float(g(r"\bPeak:\s+(-?[\d.]+)\s+dBFS")))


def stft_pow(x, n=4096, hop=1024):
    f, t, z = signal.stft(x, SR, nperseg=n, noverlap=n - hop, boundary=None, padded=False)
    return f, t, (np.abs(z) ** 2)


def db(v):
    return 10 * np.log10(np.maximum(v, 1e-12))


def kick_stats(x):
    """35–110 Hz 低频冲击的规律性：返回（最长的「间隔均匀 + 力度均匀」脉冲串个数，每分钟个数）。"""
    sos = signal.butter(4, [35, 110], "bandpass", fs=SR, output="sos")
    y = np.abs(signal.sosfilt(sos, x))
    hop = SR // 200                                                    # 5 ms
    env = y[: len(y) // hop * hop].reshape(-1, hop).max(axis=1)
    env = signal.savgol_filter(env, 5, 2) if len(env) > 7 else env
    base = signal.medfilt(env, 81)                                     # 局部底噪 ≈ 0.4 秒中位数
    thr = np.maximum(base * 2.0, np.percentile(env, 70) * 0.8 + 1e-6)
    pk, prop = signal.find_peaks(env, height=thr, distance=int(0.18 * 200))    # 两次冲击至少隔 0.18 秒
    if len(pk) < 4:
        return 0, len(pk) / (len(x) / SR) * 60
    gaps, amp = np.diff(pk) / 200.0, prop["peak_heights"]
    best = run = 1
    for i in range(1, len(gaps)):
        ok = abs(gaps[i] - gaps[i - 1]) / gaps[i - 1] < 0.06 and abs(amp[i + 1] - amp[i]) / amp[i] < 0.25
        run = run + 1 if ok else 1
        best = max(best, run)
    return best + 1 if best > 1 else 0, len(pk) / (len(x) / SR) * 60


def steady_partials(f, P, hop_s):
    """持续音比例：150–4000 Hz 里「够响的」时频格子（比这一帧最响的格子低不到 35 dB），有多少在前后 0.5 秒的窗口里电平起伏 < 6 dB（先在频率上平均 3 个点、时间上平滑 5 帧）。
    合成器 / 风琴的持续音（垫底、长音）电平不变，这个数大；拨弦、敲击每个音都衰减得很快，这个数小。旧 bgm_main.mp3 约 0.24，第一首拨弦候选 0.002。"""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    band = (f >= 150) & (f <= 4000)
    L = uniform_filter1d(db(uniform_filter1d(P[band], 3, axis=0)), 5, axis=1)
    w = max(3, int(0.5 / hop_s) | 1)
    steady = (maximum_filter1d(L, w, axis=1) - minimum_filter1d(L, w, axis=1)) < 6.0
    strong = (L > (L.max(axis=0, keepdims=True) - 35)) & (L > L.max() - 70)
    return float((steady & strong).sum() / max(strong.sum(), 1))


def hf_comb(f, P, hop_s):
    """高频泛音梳：4–12 kHz 里「够响的」时频格子中，既是频谱尖峰（比左右各 8 个频点的平均高 6 dB 以上）、又在 0.5 秒窗口里电平起伏 < 6 dB 的占比。
    合成器的锯齿 / 方波持续音在高频留下一排排长长的横线，这个数大；拨弦的高频泛音一两百毫秒就没了，噪声（镲、气声）没有尖峰，这两种都小。"""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    band = (f >= 4000) & (f <= 12000)
    L = db(P[band])
    peak = L > (uniform_filter1d(L, 17, axis=0) + 6.0)
    Ls = uniform_filter1d(L, 3, axis=1)
    w = max(3, int(0.5 / hop_s) | 1)
    steady = (maximum_filter1d(Ls, w, axis=1) - minimum_filter1d(Ls, w, axis=1)) < 6.0
    strong = L > (L.max() - 60)
    return float((peak & steady & strong).sum() / max(strong.sum(), 1))


def sub_share_db(x):
    """35–65 Hz 的能量占总能量（dB）。电子底鼓 / 低音合成器的基频就在这里（对照组 −4.5 … −6.8 dB）；拨弦低音基本在 65 Hz 以上（真乐器候选 −8 … −25 dB）。
    注意 ACE-Step 的曲子普遍低频很重（30–100 Hz 占一半左右），所以只看 35–65 Hz，并且在频谱图上确认过：−4 dB 的 cand_4 有一个每拍一下、固定在 57 Hz 的低频冲击（像底鼓）。"""
    n = min(32768, len(x))
    f, P = signal.welch(x, SR, nperseg=n)
    return float(10 * np.log10(P[(f >= 35) & (f < 65)].sum() / P.sum() + 1e-12))


def features(x):
    f, t, P = stft_pow(x)
    tot = P.sum(axis=0) + 1e-12
    hf = P[f > 8000].sum(axis=0)
    hf_ratio_db = float(db(hf.sum() / tot.sum()))
    mid = (f >= 3000) & (f <= 10000)
    e = db(P[mid].sum(axis=0))
    act = e > (e.max() - 50)                                           # 只看有声的帧
    de = np.abs(np.diff(e))
    both = act[1:] & act[:-1]
    hf_flux = float(de[both].mean()) if both.any() else 0.0
    hf_sustain = float((de[both] < 1.0).mean()) if both.any() else 0.0
    band = (f > 200) & (f < 16000)
    S = P[band] + 1e-12
    flat = float(np.mean(np.exp(np.log(S).mean(axis=0)) / S.mean(axis=0)))
    cen = float(np.mean((f[:, None] * P).sum(axis=0) / tot))
    w = int(0.4 * SR)
    r = np.sqrt((x[: len(x) // w * w].reshape(-1, w) ** 2).mean(axis=1))
    rdb = 20 * np.log10(np.maximum(r, 1e-6))
    rdb = rdb[rdb > rdb.max() - 45]
    kr, kpm = kick_stats(x)
    return dict(sub_db=round(sub_share_db(x), 1), steady=round(steady_partials(f, P, 1024 / SR), 3), hf_comb=round(hf_comb(f, P, 1024 / SR), 4), hf_ratio_db=round(hf_ratio_db, 1), hf_sustain=round(hf_sustain, 3), hf_flux_db=round(hf_flux, 2), kick_regular=int(kr), kick_per_min=round(kpm, 1),
                rms_std_db=round(float(rdb.std()), 2), crest_db=round(float(20 * np.log10(np.abs(x).max() / (np.sqrt((x ** 2).mean()) + 1e-9))), 1),
                flatness=round(flat, 4), centroid_hz=round(cen))


# 阈值（拿 3 首故意写成电子音乐的对照组 ctrl_edm / ctrl_synthwave / ctrl_lofi、旧 bgm_main.mp3 和第一批真乐器候选标定；样本很少，所以只是第一道筛：
#  过不了的直接淘汰，过了的还要看频谱图、Chris 再听）。HARD = 淘汰；SOFT = 嫌疑，要人再听。
HARD = [
    # (特征, 比较, 阈值, 只看开头5秒?, 说明)
    ("hf_comb", ">=", 0.0008, False, "高频泛音梳（锯齿 / 方波持续音）：对照 synthwave 开头 0.0013，真乐器候选 ≤ 0.0003"),
    ("steady", ">=", 0.08, False, "持续音（合成器垫底 / 风琴）：旧 bgm_main 0.26、synthwave 开头 0.089，真乐器候选 ≤ 0.065"),
    ("sub_db", ">=", -8.0, False, "35–65 Hz 低频太重（底鼓 / 低音合成器的基频）：对照组 −4.5 … −6.8 dB，cand_4（频谱上有每拍一下固定 57 Hz 的冲击）−4.1 dB，真乐器的干净候选 ≤ −20 dB"),
    ("rms_std_db", "<=", 2.0, True, "开头包络过于平直（压缩过的垫底）：synthwave 开头 1.5，其余 ≥ 4"),
    ("flatness", ">=", 0.12, True, "开头是噪声感很强的宽带声（镲 / 气声 / 噪声扫）：不一定是电子，但不是我们要的纸艺拨弦音色"),
]
SOFT = [
    ("sub_db", ">=", -11.0, False, "35–65 Hz 低频偏重：可能是拨弦低音（cand_2 的低音线音高会变，−8.4 dB），也可能是底鼓，看频谱图确认"),
    ("kick_regular", ">=", 8, False, "35–110 Hz 低频脉冲连续 ≥ 8 个间隔和力度都均匀：可能是四拍底鼓，也可能只是规律的拨弦低音（拨弦低音会误报）"),
]


def verdict(head, whole):
    hard, soft = [], []
    for table, out in ((HARD, hard), (SOFT, soft)):
        for k, op, lim, head_only, why in table:
            for tag, d in (("开头5秒", head), ("整首", whole)):
                if head_only and d is not head:
                    continue
                v = d[k]
                if (op == ">=" and v >= lim) or (op == "<=" and v <= lim):
                    out.append(f"{tag} {k}={v}（{op}{lim}）")
    hard_keys = {h.split("（")[0] for h in hard}
    return hard, [x for x in soft if x.split("（")[0] not in hard_keys]                # 同一特征已经淘汰了就不再列嫌疑


_asr = None
NOSPEECH_MIN = 0.35        # 某一段 Whisper 认为「没有人声」的概率低于这个，就算有人声嫌疑（标定：旧 bgm_main.mp3 纯器乐 0.51–0.85；一句 8 秒的 TTS 配音单独 0.04、压在音乐上 −5 dB 时 0.22，−10 dB 时 0.50 查不出来）


def whisper_check(path, device=None):
    """Whisper(small) 查人声：每 30 秒一段，算「没有人声」token（<|nocaptions|>）的概率，再转写一遍（语种自动）。
    返回 [(段起点秒, P(没有人声), 转写文字)]。Whisper 对纯音乐会乱编短句（"Music"、别的语种），所以主要看 P(没有人声)，文字只作参考；只能抓到比较明显的人声，轻哼 / 和声要人听。"""
    global _asr
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    dev = "cuda" if (device != "cpu" and torch.cuda.is_available()) else "cpu"
    dt = torch.float32                                                  # fp16 在这张卡上会出 NaN（整段转写成一串 "!"），small 模型 fp32 也只要约 1 GB
    if _asr is None:                                                    # 不走 transformers 的 pipeline：它在这个环境里会去加载坏掉的 torchcodec
        _asr = (WhisperProcessor.from_pretrained("openai/whisper-small"), WhisperForConditionalGeneration.from_pretrained("openai/whisper-small", dtype=dt).to(dev).eval())
    proc, model = _asr
    tok = proc.tokenizer
    ns_id, sot = tok.convert_tokens_to_ids("<|nocaptions|>"), tok.convert_tokens_to_ids("<|startoftranscript|>")
    x = decode(path, sr=16000)
    n = 30 * 16000
    res = []
    for i in range(0, len(x), n):
        c = x[i:i + n]
        if len(c) <= 16000:
            continue
        feats = proc([c], sampling_rate=16000, return_tensors="pt").input_features.to(dev, dt)
        with torch.no_grad():
            lg = model(input_features=feats, decoder_input_ids=torch.tensor([[sot]], device=dev)).logits[0, -1].float()
            p_ns = float(torch.softmax(lg, -1)[ns_id])
            ids = model.generate(feats, task="transcribe", max_new_tokens=60)
        res.append((i // 16000, round(p_ns, 3), proc.batch_decode(ids, skip_special_tokens=True)[0].strip()[:60]))
    return res


def normalize(src, dst, lufs=-20.0, tp=-1.5, trial=None, trial_sec=30):
    """整首调到 lufs（积分响度），真峰值超过 tp 就用限幅器压，结尾的数字静音切掉；输出 192k mp3；trial = 从开头截 trial_sec 秒的试听版。"""
    m = ebur128(src)
    gain = lufs - m["lufs"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    # 先把结尾的数字静音切掉（ACE-Step 的曲子结尾会留 3–9 秒的 −68 dB 静音，混音器循环 / 截断时会撞上空拍），再调响度、限幅
    af = f"areverse,silenceremove=start_periods=1:start_threshold=-60dB:start_duration=0.05,areverse,volume={gain:.2f}dB,alimiter=limit={10 ** (tp / 20):.4f}:level=disabled:attack=5:release=60"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", af, "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", "192k", str(dst)], check=True)
    r = {"before": m, "after": ebur128(dst), "gain_db": round(gain, 2)}
    if trial:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-t", str(trial_sec), "-af", "afade=t=out:st=%s:d=1.5" % (trial_sec - 1.5), "-c:a", "libmp3lame", "-b:a", "192k", str(trial)], check=True)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--ref", default=str(ROOT / "video" / "assets" / "audio" / "bgm_main.mp3"), help="对照用的旧背景音乐（'' = 不量）")
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--whisper-device", default="cpu", help="cpu（默认：生成音乐时显卡是满的，Whisper 在 CPU 上跑一首约 1–2 分钟）或 cuda")
    ap.add_argument("--normalize", help="只允许一个输入文件：输出归一后的 mp3")
    ap.add_argument("--trial", help="和 --normalize 一起用：从开头截 30 秒试听版")
    ap.add_argument("--json", help="结果写到这个 json")
    a = ap.parse_args()
    if a.normalize:
        r = normalize(a.files[0], a.normalize, trial=a.trial)
        print(json.dumps(r, ensure_ascii=False))
        return 0
    res = {}
    files = ([a.ref] if a.ref else []) + a.files
    for fp in files:
        x = decode(fp)
        head = features(x[: 5 * SR])
        whole = features(x)
        r = dict(duration=round(len(x) / SR, 1), loud=ebur128(fp), head5=head, whole=whole, flags=list(verdict(head, whole)) if fp != a.ref else [[], []])
        if a.whisper and fp != a.ref:
            r["whisper"] = whisper_check(fp, a.whisper_device)
            r["vocal_suspect_chunks"] = [w[0] for w in r["whisper"] if w[1] < NOSPEECH_MIN]
        res[Path(fp).name] = r
        print(f"== {Path(fp).name}  {r['duration']} 秒  {r['loud']['lufs']} LUFS  LRA {r['loud']['lra']}")
        print("  开头5秒:", json.dumps(head, ensure_ascii=False))
        print("  整首   :", json.dumps(whole, ensure_ascii=False))
        if r["flags"][0]:
            print("  ✗ 淘汰（电子味 / 噪声感）：", "；".join(r["flags"][0]))
        if r["flags"][1]:
            print("  ? 嫌疑（要再听）：", "；".join(r["flags"][1]))
        if "whisper" in r:
            print(f"  Whisper：有人声嫌疑的 30 秒段（P(没有人声) < {NOSPEECH_MIN}）：{r['vocal_suspect_chunks'] or '没有'}；最小 P(没有人声) = {min(w[1] for w in r['whisper'])}")
            for t0, pns, txt in r["whisper"]:
                print(f"    [{t0}s] P(没有人声)={pns}  {txt!r}")
        sys.stdout.flush()
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
