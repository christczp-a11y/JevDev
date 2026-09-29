"""客观量一量每条音频：时长、有声段、语速、基频（numpy 自相关 + Viterbi）的中位数/起伏、响度起伏。
  .venv-tts/Scripts/python experiments/tts_compare/analyze.py
输出 video/out/tts_compare/metrics.json 和终端表格。基频：8 kHz、40 ms 帧、10 ms 步长的归一化自相关取候选峰（60–400 Hz），
再 Viterbi 平滑（跳八度有代价）。先试过直接取最大峰（男声跳八度，同一个声音两句差 3 倍）和 librosa.pyin（Edge 的低男声整段判成无声），都不稳。
起伏 = 有声帧基频相对中位数的半音数的标准差（st_std），另给 p10–p90 范围（st_range）。
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES, SECOND  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"


def load_mono(p):
    w, sr = sf.read(str(p), dtype="float32", always_2d=True)
    return w.mean(axis=1), sr


def frames(x, n, hop):
    if len(x) < n:
        x = np.pad(x, (0, n - len(x)))
    k = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(k)[:, None]
    return x[idx]


def f0_track(x, sr, fmin=60, fmax=400, hop=0.01, thr_db=-38, K=6):
    """numpy 基频：降到 8 kHz，40 ms 帧的归一化自相关取局部峰，再用 Viterbi 平滑（跳八度有代价）。"""
    from scipy.signal import resample_poly
    y = resample_poly(x, 1, sr // 8000) if sr % 8000 == 0 else x
    sr2 = 8000 if sr % 8000 == 0 else sr
    n, h = int(0.04 * sr2), int(hop * sr2)
    fr = frames(y, n, h) * np.hanning(n)[None, :]
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12) + 1e-12)
    nfft = 1 << (2 * n - 1).bit_length()
    ac = np.fft.irfft(np.abs(np.fft.rfft(fr, nfft, axis=1)) ** 2, nfft, axis=1)[:, :n]
    ac = ac / (ac[:, :1] + 1e-12)
    win_ac = np.fft.irfft(np.abs(np.fft.rfft(np.hanning(n), nfft)) ** 2, nfft)[:n]
    ac = ac / (win_ac / win_ac[0] + 1e-9)[None, :]          # 去掉窗函数造成的随滞后衰减
    lo, hi = int(sr2 / fmax), int(sr2 / fmin)
    T = len(fr)
    cand_f = np.full((T, K), np.nan)
    cand_s = np.zeros((T, K))
    for t in range(T):
        if db[t] < thr_db:
            continue
        seg = ac[t, lo - 1: hi + 2]
        pk = np.where((seg[1:-1] > seg[:-2]) & (seg[1:-1] >= seg[2:]))[0] + 1
        pk = pk[seg[pk] > 0.3]
        pk = pk[np.argsort(-seg[pk])][:K]
        for j, q in enumerate(pk):
            l = q + lo - 1
            a0, b0, c0 = seg[q - 1], seg[q], seg[q + 1]
            d = 0.5 * (a0 - c0) / (a0 - 2 * b0 + c0 + 1e-12)
            cand_f[t, j] = sr2 / (l + d)
            cand_s[t, j] = b0 - 0.01 * np.log2(cand_f[t, j] / fmin)   # 略偏爱低的（防跳到高八度）
    # Viterbi：状态 0..K-1 = 候选，K = 无声
    UV = 0.45
    NEG = -1e9
    score = np.full((T, K + 1), NEG)
    back = np.zeros((T, K + 1), dtype=int)
    loc = np.where(np.isnan(cand_f), NEG, cand_s)
    score[0, :K] = loc[0]
    score[0, K] = UV if db[0] >= thr_db else 0.0
    for t in range(1, T):
        for j in range(K + 1):
            best, arg = NEG, 0
            for i in range(K + 1):
                if score[t - 1, i] <= NEG / 2:
                    continue
                if j < K and i < K:
                    tr = -2.0 * abs(np.log2(cand_f[t, j] / cand_f[t - 1, i]))
                elif j == K and i == K:
                    tr = 0.0
                else:
                    tr = -0.4
                v = score[t - 1, i] + tr
                if v > best:
                    best, arg = v, i
            if j < K:
                if np.isnan(cand_f[t, j]):
                    continue
                score[t, j] = best + loc[t, j]
            else:
                score[t, j] = best + (UV if db[t] >= thr_db else 0.3)
            back[t, j] = arg
    st = int(score[-1].argmax())
    f0 = np.full(T, np.nan)
    for t in range(T - 1, -1, -1):
        if st < K:
            f0[t] = cand_f[t, st]
        st = back[t, st]
    return f0, db, h / sr2


def analyze(p, text):
    x, sr = load_mono(p)
    dur = len(x) / sr
    f0, db, hop = f0_track(x, sr)
    act = db > -40                       # 有声段（相对峰值 -40 dB）
    idx = np.where(act)[0]
    span = (idx[-1] - idx[0] + 1) * hop if len(idx) else 0.0
    lead = idx[0] * hop if len(idx) else dur
    v = f0[~np.isnan(f0)]
    # 句中最长停顿（首尾有声帧之间连续无声的最长一段）；活动段平均响度（dBFS，越小越轻）
    pause = 0.0
    if len(idx) > 1:
        gaps = np.diff(idx) - 1
        pause = float(gaps.max() * hop)
    n_act = min(len(act), len(f0))
    hs = int(sr * hop)
    seg_rms = np.array([np.sqrt((x[i * hs:(i + 1) * hs] ** 2).mean() + 1e-12) for i in range(len(act))])
    level = float(20 * np.log10(np.sqrt((seg_rms[act] ** 2).mean()) + 1e-9)) if act.any() else float("nan")
    if len(v) >= 5:
        med = float(np.median(v))
        st = 12 * np.log2(v / med)
        st_std = float(st.std())
        st_rng = float(np.percentile(st, 90) - np.percentile(st, 10))
    else:
        med = st_std = st_rng = float("nan")
    nchar = len(re.sub(r"[\s，。！？、…,.!?—「」“”]", "", text))
    return dict(dur=round(dur, 2), speech_span=round(span, 2), lead_sil=round(lead, 2),
                chars=nchar, cps=round(nchar / span, 2) if span else None,
                f0_med=round(med, 1), st_std=round(st_std, 2), st_range=round(st_rng, 2),
                voiced_frac=round(len(v) / max(1, act.sum()), 2),
                db_std=round(float(db[act].std()), 2) if act.any() else None,
                pause=round(pause, 2), level=round(level, 1),
                peak=round(float(np.abs(x).max()), 3))


def main():
    rows = {}
    for ln in LINES:
        for tag, pat in [("A", f"A_edge_{ln['id']}_{ln['who']}.wav"), ("B", f"B_design_{ln['id']}_{ln['who']}.wav"),
                         ("Bs1", f"Bs_design_{ln['id']}_{ln['who']}_s1.wav"), ("Bs2", f"Bs_design_{ln['id']}_{ln['who']}_s2.wav"),
                         ("C", f"C_clone_{ln['id']}_{ln['who']}.wav"), ("Cx", f"Cx_xvec_{ln['id']}_{ln['who']}.wav"),
                         ("C06", f"C_clone_0.6B_{ln['id']}_{ln['who']}.wav")]:
            p = OUT / pat
            if p.exists():
                rows[f"{tag}_{ln['id']}_{ln['who']}"] = analyze(p, ln["text"])
        for tag, pat in [("A2", f"A2_edge_{ln['who']}_第二句.wav"), ("B2", f"B2_design_{ln['who']}_第二句.wav"),
                         ("C2", f"C2_clone_{ln['who']}_第二句.wav")]:
            p = OUT / pat
            if p.exists():
                rows[f"{tag}_{ln['who']}"] = analyze(p, SECOND[ln["who"]])
        p = OUT / f"ref_{ln['who']}.wav"
        if p.exists():
            from lines import REF_TEXT
            rows[f"ref_{ln['who']}"] = analyze(p, REF_TEXT[ln["who"]])
    (OUT / "metrics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    hdr = f"{'name':<18}{'dur':>6}{'span':>6}{'lead':>6}{'cps':>6}{'f0med':>7}{'st_std':>7}{'st_rng':>7}{'vfrac':>6}{'db_std':>7}{'pause':>6}{'level':>7}"
    print(hdr)
    for k, r in rows.items():
        print(f"{k:<{18 - sum(1 for c in k if ord(c) > 255)}}{r['dur']:>6}{r['speech_span']:>6}{r['lead_sil']:>6}{r['cps']!s:>6}"
              f"{r['f0_med']:>7}{r['st_std']:>7}{r['st_range']:>7}{r['voiced_frac']:>6}{r['db_std']!s:>7}{r['pause']:>6}{r['level']:>7}")


if __name__ == "__main__":
    main()
