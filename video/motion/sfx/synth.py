"""系列固定音效：全部程序合成（numpy），不用来源不明的素材。全系列同一个特效用同一个声音。
    .venv/Scripts/python video/motion/sfx/synth.py        重新生成本目录的全部 .wav（结果是固定的，同样代码 → 同样的文件）
加新音效：写一个 def 名字() 返回 float 数组（单声道 44.1 kHz，峰值约 0.5），登记进 SOUNDS，跑一遍这个脚本，把 .wav 一起提交。
分镜表里 "sfx": [{"name": "pop", "at": {...}}] 按名字取 <名字>.wav；特效登记时可以带默认音效名。
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
HERE = Path(__file__).resolve().parent


def _t(d):
    return np.arange(int(d * SR)) / SR


def _norm(y, peak=0.5):
    return y / max(np.abs(y).max(), 1e-9) * peak


def pop():
    """弹出：短促的上滑「啵」，贴纸、人物弹出、换表情用。"""
    t = _t(0.18)
    f = 320 + 620 * (1 - np.exp(-t * 38))                        # 频率从 320 Hz 快速滑到约 940 Hz
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(phase) * np.exp(-t * 20)
    click = np.random.default_rng(7).normal(0, 1, len(t)) * np.exp(-t * 700) * 0.25   # 开头一点点「啪」
    y = y + click
    y *= np.minimum(1.0, t / 0.003)                               # 3 毫秒渐入，避免爆音
    return _norm(y)


SOUNDS = {"pop": pop}


def write(name, y):
    with wave.open(str(HERE / f"{name}.wav"), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    for n, fn in SOUNDS.items():
        write(n, fn())
        print("写好", HERE / f"{n}.wav")
