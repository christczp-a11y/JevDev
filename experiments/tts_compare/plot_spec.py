"""画谱图：6 句 × A/B/C，0–1200 Hz 频谱 + 基频轨迹（青点）。用系统 Python（有 matplotlib）跑：
  python experiments/tts_compare/plot_spec.py
输出 video/out/tts_compare/谱图对比.png。看得出每句的语速、停顿、音高起伏、是不是气声（没有横纹的一团噪声）。
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import f0_track, load_mono  # noqa: E402
from lines import LINES  # noqa: E402

for f in ["Microsoft YaHei", "SimHei", "SimSun"]:
    if any(f in x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [f]
        break
OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"
fig, axes = plt.subplots(6, 3, figsize=(15, 16))
for r, ln in enumerate(LINES):
    for c, (tag, fn) in enumerate([("A Edge", f"A_edge_{ln['id']}_{ln['who']}.wav"), ("B VoiceDesign", f"B_design_{ln['id']}_{ln['who']}.wav"),
                                   ("C 克隆", f"C_clone_{ln['id']}_{ln['who']}.wav")]):
        x, sr = load_mono(OUT / fn)
        ax = axes[r][c]
        ax.specgram(x + 1e-9, NFFT=1024, Fs=sr, noverlap=768, cmap="magma", vmin=-110)
        ax.set_ylim(0, 1200)
        f0, db, hop = f0_track(x, sr)
        ax.plot(np.arange(len(f0)) * hop, f0, "c.", ms=3)
        ax.set_title(f"{tag}  {ln['who']}  {ln['text']}  ({len(x)/sr:.1f}s)", fontsize=9)
plt.tight_layout()
plt.savefig(OUT / "谱图对比.png", dpi=70)
print("ok")
