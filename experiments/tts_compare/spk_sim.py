"""音色稳不稳：用 Qwen3-TTS-Base 自带的说话人编码器给每条音频取向量，量余弦相似度。
  .venv-tts/Scripts/python experiments/tts_compare/spk_sim.py
同一角色两句（第 N 句 vs 第二句）越接近 1 越像同一个人；不同角色之间的相似度是参照（应该明显更低）。
向量先减去全体均值再算余弦（原始向量余弦全在 0.92 以上，没有区分度）。
Edge 的同一个声音两句也量一下，当作「同一个人」的上限参照。输出 video/out/tts_compare/spk_sim.json。
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"


def main(size="1.7B"):
    from qwen_tts import Qwen3TTSModel
    m = Qwen3TTSModel.from_pretrained(f"Qwen/Qwen3-TTS-12Hz-{size}-Base", device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa")
    tsr = m.model.speaker_encoder_sample_rate

    def emb(p):
        w, sr = sf.read(str(p), dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        if sr != tsr:
            w = librosa.resample(w, orig_sr=sr, target_sr=tsr)
        e = m.model.extract_speaker_embedding(audio=w, sr=tsr).float().flatten().cpu().numpy()
        return e / (np.linalg.norm(e) + 1e-9)

    roles = [ln["who"] for ln in LINES]
    files = {}
    for ln in LINES:
        w, i = ln["who"], ln["id"]
        files[("A", w, 1)] = OUT / f"A_edge_{i}_{w}.wav"
        files[("A", w, 2)] = OUT / f"A2_edge_{w}_第二句.wav"
        files[("B", w, 1)] = OUT / f"B_design_{i}_{w}.wav"
        files[("B", w, 2)] = OUT / f"B2_design_{w}_第二句.wav"
        files[("Bs1", w, 1)] = OUT / f"Bs_design_{i}_{w}_s1.wav"
        files[("Bs2", w, 1)] = OUT / f"Bs_design_{i}_{w}_s2.wav"
        files[("C", w, 1)] = OUT / f"C_clone_{i}_{w}.wav"
        files[("C", w, 2)] = OUT / f"C2_clone_{w}_第二句.wav"
        files[("Cx", w, 1)] = OUT / f"Cx_xvec_{i}_{w}.wav"
        files[("ref", w, 0)] = OUT / f"ref_{w}.wav"
    E = {k: emb(p) for k, p in files.items() if p.exists()}
    # 原始向量的余弦全在 0.92 以上（含不同角色），没有区分度；减去全体均值再比（去掉所有声音共有的成分）
    mu = np.mean(list(E.values()), axis=0)
    E = {k: (v - mu) / (np.linalg.norm(v - mu) + 1e-9) for k, v in E.items()}
    cos = lambda a, b: float(np.dot(a, b))
    res = {"per_role": {}, "cross_role_mean": {}}
    for w in roles:
        r = {}
        for v in ["A", "B", "C"]:
            if (v, w, 1) in E and (v, w, 2) in E:
                r[f"{v}_1_vs_2"] = round(cos(E[(v, w, 1)], E[(v, w, 2)]), 3)
        draws = [E[(v, w, 1)] for v in ("B", "Bs1", "Bs2") if (v, w, 1) in E]
        if len(draws) == 3:
            r["B_same_text_3seeds_mean"] = round(float(np.mean([cos(draws[0], draws[1]), cos(draws[0], draws[2]), cos(draws[1], draws[2])])), 3)
        if ("ref", w, 0) in E:
            for v in ["B", "C", "Cx"]:
                for n in (1, 2):
                    if (v, w, n) in E:
                        r[f"{v}{n}_vs_ref"] = round(cos(E[(v, w, n)], E[("ref", w, 0)]), 3)
        res["per_role"][w] = r
    for v in ["A", "B", "C"]:
        vals = []
        for w1 in roles:
            for w2 in roles:
                if w1 < w2 and (v, w1, 1) in E and (v, w2, 1) in E:
                    vals.append(cos(E[(v, w1, 1)], E[(v, w2, 1)]))
        if vals:
            res["cross_role_mean"][v] = round(float(np.mean(vals)), 3)
    (OUT / "spk_sim.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "1.7B")
