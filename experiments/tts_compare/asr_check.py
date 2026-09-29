"""字念对没有：用 Whisper-small 把每条音频转回文字，和台词比字错率（去掉标点，繁转简）。
  .venv-tts/Scripts/python experiments/tts_compare/asr_check.py
很短的句子（2-3 个字）Whisper 容易幻觉，结果只当参考。输出 video/out/tts_compare/asr.json。
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES, SECOND, REF_TEXT  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"


def norm(s):
    return re.sub(r"[\s，。！？、…,.!?—「」“”：:；;]", "", s)


def edit(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]


def main():
    from transformers import pipeline
    try:
        from opencc import OpenCC
        t2s = OpenCC("t2s").convert
    except Exception:
        t2s = lambda s: s
    asr = pipeline("automatic-speech-recognition", model="openai/whisper-small", device=0, torch_dtype=torch.float32)
    todo = []
    for ln in LINES:
        i, w = ln["id"], ln["who"]
        for tag, pat, text in [("A", f"A_edge_{i}_{w}.wav", ln["text"]), ("B", f"B_design_{i}_{w}.wav", ln["text"]),
                               ("Bs1", f"Bs_design_{i}_{w}_s1.wav", ln["text"]), ("Bs2", f"Bs_design_{i}_{w}_s2.wav", ln["text"]),
                               ("C", f"C_clone_{i}_{w}.wav", ln["text"]), ("Cx", f"Cx_xvec_{i}_{w}.wav", ln["text"]),
                               ("C06", f"C_clone_0.6B_{i}_{w}.wav", ln["text"]),
                               ("A2", f"A2_edge_{w}_第二句.wav", SECOND[w]), ("B2", f"B2_design_{w}_第二句.wav", SECOND[w]),
                               ("C2", f"C2_clone_{w}_第二句.wav", SECOND[w]), ("ref", f"ref_{w}.wav", REF_TEXT[w])]:
            if (OUT / pat).exists():
                todo.append((f"{tag}_{i}_{w}", OUT / pat, text))
    res = {}
    for name, p, text in todo:
        w, sr = sf.read(str(p), dtype="float32")
        if w.ndim > 1:
            w = w.mean(axis=1)
        if sr != 16000:
            import librosa
            w = librosa.resample(w, orig_sr=sr, target_sr=16000)
        w = np.concatenate([np.zeros(8000, np.float32), w, np.zeros(8000, np.float32)])
        out = asr({"raw": w, "sampling_rate": 16000}, generate_kwargs={"language": "zh", "task": "transcribe"})["text"]
        hyp, ref = norm(t2s(out)), norm(text)
        cer = edit(ref, hyp) / max(1, len(ref))
        res[name] = dict(text=text, asr=out.strip(), cer=round(cer, 2))
        print(f"{name:<20} cer={cer:.2f}  期望「{text}」 识别「{out.strip()}」", flush=True)
    (OUT / "asr.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
