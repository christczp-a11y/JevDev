"""系列固定音效：全部程序合成（numpy + scipy），不用来源不明的素材。全系列同一个特效同一个声音，孩子一听就知道「要来了」。
    .venv/Scripts/python video/motion/sfx/synth.py        重新生成本目录的全部 .wav（结果是固定的，同样代码 → 同样的文件）
    .venv/Scripts/python video/motion/sfx/synth.py pop    只生成一个
加新音效：写一个 def 名字() 返回 float 数组（单声道 44.1 kHz，峰值约 0.5），登记进 SOUNDS，跑一遍这个脚本，把 .wav 一起提交。
分镜表里 "sfx": [{"name": "pop", "at": {...}}] 按名字取 <名字>.wav；特效登记时可以带默认音效名。

声音的样子：儿童节目——木琴、马林巴、钟琴（五声音阶：C D E G A），软软的「啵」「咚」「叮」，噪声都低通在 8 kHz 以下、起收都有淡入淡出，不刺耳、不吓人。
时间对齐：特效的音效在特效的 at 时刻开始（转场的音效在切点开始），所以每个音效都把「重音」按对应特效的动画时间摆好（时间常数在 timing.py，和特效共用）。
"""
import sys
import wave
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import timing as TM   # noqa: E402

SR = 44100

# 五声音阶（Hz）
N = {"C4": 261.63, "D4": 293.66, "E4": 329.63, "G4": 392.0, "A4": 440.0, "C5": 523.25, "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.0,
     "C6": 1046.5, "D6": 1174.66, "E6": 1318.51, "G6": 1567.98, "A6": 1760.0, "C7": 2093.0}
PENTA = ["C5", "D5", "E5", "G5", "A5", "C6", "D6", "E6", "G6", "A6"]


# ============================== 基本零件 ==============================
def _t(d):
    return np.arange(int(round(d * SR))) / SR


def _rng(seed):
    return np.random.default_rng(seed)


def _fade(y, a=0.004, b=0.012):
    y = y.copy()
    na, nb = min(int(a * SR), len(y) // 2), min(int(b * SR), len(y) // 2)
    if na:
        y[:na] *= np.linspace(0, 1, na)
    if nb:
        y[-nb:] *= np.linspace(1, 0, nb)
    return y


def _norm(y, peak=0.5):
    return y / max(np.abs(y).max(), 1e-9) * peak


def lowpass(y, fc, order=3):
    return signal.sosfilt(signal.butter(order, fc / (SR / 2), "low", output="sos"), y)


def highpass(y, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc / (SR / 2), "high", output="sos"), y)


def bandpass(y, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), y)


def place(dst, y, t, gain=1.0):
    i = int(round(t * SR))
    a, b = max(i, 0), min(i + len(y), len(dst))
    if b > a:
        dst[a:b] += y[a - i:b - i] * gain


def buf(d):
    return np.zeros(int(round(d * SR)))


def partials(f, d, ratios, amps, decays, attack=0.002):
    t = _t(d)
    y = np.zeros_like(t)
    for r, a, dc in zip(ratios, amps, decays):
        if f * r < 9000:
            y += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * dc)
    return y * np.minimum(1.0, t / attack)


def glock(f, d=1.1):
    """钟琴：清脆的金属小钟，亮而不刺。"""
    return partials(f, d, (1, 2.76, 5.4), (1.0, 0.30, 0.10), (3.4, 6.0, 10.0))


def marimba(f, d=0.5):
    """马林巴：圆圆的木音，「咚」的一下。"""
    return partials(f, d, (1, 4.0, 9.9), (1.0, 0.32, 0.06), (7.5, 16.0, 30.0), 0.0015)


def xylo(f, d=0.35):
    """木琴：比马林巴脆一点。"""
    return partials(f, d, (1, 3.0, 6.0), (1.0, 0.35, 0.10), (11.0, 20.0, 34.0), 0.001)


def pluck(f0, f1, d=0.16, decay=22.0):
    """「啵」：频率快速滑动的短音。"""
    t = _t(d)
    f = f1 + (f0 - f1) * np.exp(-t * 45)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * decay)
    return y * np.minimum(1.0, t / 0.003)


def thud(f=150.0, f2=55.0, d=0.28, decay=14.0, click=0.25, seed=3):
    """软「咚」：低频下滑 + 一点点木头的「嗒」。"""
    t = _t(d)
    ff = f2 + (f - f2) * np.exp(-t * 28)
    y = np.sin(2 * np.pi * np.cumsum(ff) / SR) * np.exp(-t * decay)
    ck = lowpass(_rng(seed).normal(0, 1, len(t)), 1800) * np.exp(-t * 300) * click
    return (y + ck) * np.minimum(1.0, t / 0.002)


def noise_sweep(d, f0, f1, seed=1, width=0.55, peak=0.5, curve=None):
    """噪声「呼」：中心频率从 f0 滑到 f1 的带通噪声，音量是一个钟形。用 STFT 在频域里做，平滑无杂音。"""
    n = int(round(d * SR))
    x = _rng(seed).normal(0, 1, n)
    f, tt, Z = signal.stft(x, SR, nperseg=1024, noverlap=768)
    frac = tt / max(tt[-1], 1e-9)
    if curve is not None:
        frac = curve(frac)
    fc = f0 * (f1 / f0) ** frac
    lf = np.log(np.maximum(f, 20.0))[:, None]
    M = np.exp(-0.5 * ((lf - np.log(fc)[None, :]) / width) ** 2)
    _, y = signal.istft(Z * M, SR, nperseg=1024, noverlap=768)
    y = np.pad(y, (0, max(0, n - len(y))))[:n]
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5 if peak else np.ones(n)
    return _norm(y, 1.0) * env


def swell(d, fc=1200, seed=2, power=2.0):
    """低通噪声的「呼——」涨落（火苗、气流）。"""
    n = int(round(d * SR))
    y = lowpass(_rng(seed).normal(0, 1, n), fc)
    return _norm(y, 1.0) * (np.sin(np.pi * np.linspace(0, 1, n)) ** power)


def arp(notes, gap, timbre=glock, d=0.9, gain=1.0, fall=0.9):
    """一串音符（琶音）：每个比前一个晚 gap 秒，音量逐个略降。"""
    total = gap * (len(notes) - 1) + d
    y = buf(total)
    for i, nt in enumerate(notes):
        place(y, timbre(N[nt], d), gap * i, gain * (fall ** i))
    return y


def chord(notes, timbre=glock, d=1.2, gain=1.0, spread=0.012):
    y = buf(d + spread * len(notes))
    for i, nt in enumerate(notes):
        place(y, timbre(N[nt], d), spread * i, gain)
    return y


def mix(d, parts):
    y = buf(d)
    for t, s, g in parts:
        place(y, s, t, g)
    return y


def _finish(y, peak=0.5, a=0.004, b=0.02):
    y = highpass(y, 40, 1)
    y = lowpass(y, 9000, 2)
    return _fade(_norm(y, peak), a, b)


# ============================== 音效们 ==============================
def pop():
    """弹出：短促的上滑「啵」，贴纸、人物弹出、换表情用。"""
    t = _t(0.18)
    f = 320 + 620 * (1 - np.exp(-t * 38))
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(phase) * np.exp(-t * 20)
    click = np.random.default_rng(7).normal(0, 1, len(t)) * np.exp(-t * 700) * 0.25
    y = y + click
    y *= np.minimum(1.0, t / 0.003)
    return _norm(y)


def whoosh():
    """横向速度线：柔软的一阵风。"""
    y = noise_sweep(0.42, 500, 3200, 11, 0.7)
    return _finish(y, 0.45, 0.02, 0.06)


def burst():
    """放射线：亮亮的「叮铃」上行三个音 + 一口气。"""
    y = mix(0.7, [(0.0, arp(["E6", "G6", "C7"], 0.045, glock, 0.5), 0.8), (0.0, noise_sweep(0.3, 1500, 5500, 12, 0.8) * 0.5, 1.0)])
    return _finish(y, 0.48)


def focus():
    """集中线：「嗖——叮」：一道上行的气流收紧，最后一个清脆的木音。"""
    y = mix(0.7, [(0.0, noise_sweep(0.36, 400, 2600, 13, 0.6) * 0.8, 1.0), (0.0, pluck(360, 1500, 0.34, 4.0) * 0.35, 1.0), (0.32, xylo(N["G6"], 0.3), 0.8)])
    return _finish(y, 0.46)


def slam(n):
    """砸字：第 k 个字在 0.14 + 0.17k 秒落地：落下前一声轻轻的下滑，落地「咚」+ 木音 + 小星星（音阶逐个升高）。"""
    total = TM.SLAM_FALL + TM.SLAM_STAG * (n - 1) + 0.75
    y = buf(total)
    scale = ["C5", "D5", "E5", "G5", "A5", "C6"]
    for k in range(n):
        t0 = TM.SLAM_STAG * k
        place(y, pluck(900, 320, TM.SLAM_FALL, 6.0) * 0.30, t0, 1.0)                              # 落下的口哨
        tl = t0 + TM.SLAM_FALL
        place(y, thud(170, 52, 0.34, 11.0, 0.35, seed=20 + k), tl, 1.0)
        place(y, marimba(N["C4"] * 2 ** (k / 6.0), 0.4), tl, 0.55)
        place(y, glock(N[scale[k]], 0.55), tl + 0.015, 0.34)
    return _finish(y, 0.52)


def list_(n):
    """清单：每条「啵」+ 0.16 秒后一声「叮」（打勾），音阶逐条升高。"""
    total = TM.LIST_GAP * (n - 1) + 0.9
    y = buf(total)
    scale = ["C5", "D5", "E5", "G5", "A5", "C6"]
    for k in range(n):
        t0 = TM.LIST_GAP * k
        place(y, pluck(360, 900, 0.16, 22.0), t0, 0.7)
        place(y, marimba(N[scale[k]], 0.5), t0 + 0.16, 0.9)
        place(y, glock(N[scale[k]] * 2, 0.5), t0 + 0.16, 0.22)
    return _finish(y, 0.5)


def stat_open():
    """属性卡滑进来：「唰」+ 「咚」（0.45 秒内）。每行亮起的 `stat_row_N` 和每颗星的 `star_ding` 是单独的音效，
    由 stat_card 出片前按 gap（行间隔）排进镜头的音效表，所以行间隔可以改。"""
    y = buf(0.7)
    place(y, noise_sweep(0.32, 400, 2200, 31, 0.65) * 0.7, 0.0, 1.0)
    place(y, thud(160, 60, 0.25, 15, 0.2, seed=32), 0.36, 0.7)
    return _finish(y, 0.5, 0.004, 0.06)


def stat_row(i):
    """属性卡里第 i 行（从 1 数）亮起：「啵」+ 马林巴，一行比一行高一个音（五声音阶）。"""
    nt = ["C5", "D5", "E5", "G5", "A5", "C6"][i - 1]
    y = buf(0.7)
    place(y, pluck(360, 820, 0.14, 24.0), 0.0, 0.5)
    place(y, marimba(N[nt], 0.5), 0.1, 0.9)
    return _finish(y, 0.42, 0.003, 0.08)


def paper_unfold():
    """纸地图展开：纸的沙沙声 + 最后一声轻「嗒」。"""
    r = _rng(41)
    crackle = lowpass(highpass(r.normal(0, 1, int(0.5 * SR)), 900), 6500)
    env = np.abs(lowpass(r.normal(0, 1, len(crackle)), 30)) * 3
    env = env / env.max() * (np.sin(np.pi * np.linspace(0, 1, len(crackle))) ** 0.8)
    y = mix(0.75, [(0.0, crackle * env, 1.0), (0.0, noise_sweep(0.45, 300, 1800, 42, 0.7) * 0.6, 1.0), (0.42, thud(140, 70, 0.25, 16, 0.4, seed=43), 0.6)])
    return _finish(y, 0.45)


def city_pop():
    """城标落下：「咕咚」+ 一声亮亮的「叮」（落地在 0.16 秒）。"""
    y = mix(0.7, [(0.0, pluck(700, 300, 0.16, 12.0) * 0.5, 1.0), (0.16, thud(190, 70, 0.3, 12, 0.3, seed=51), 0.9), (0.16, marimba(N["G5"], 0.5), 0.8),
                  (0.18, glock(N["D6"], 0.6), 0.32)])
    return _finish(y, 0.5)


def draw():
    """虚线箭头：0.8 秒的铅笔「唰唰」（一段一段），收尾一声木音。"""
    d = TM.DRAW_DUR
    n = int(d * SR)
    t = np.arange(n) / SR
    y = bandpass(_rng(61).normal(0, 1, n), 1800, 4200)
    dash = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 9.5 * t))
    dash = lowpass(dash, 60)
    y = y * dash * np.minimum(1, t / 0.05) * (0.35 + 0.65 * np.linspace(0, 1, n)) * 0.7
    out = buf(d + 0.5)
    place(out, y, 0.0, 1.0)
    place(out, marimba(N["E5"], 0.45), d, 0.85)
    place(out, glock(N["A5"], 0.5), d + 0.02, 0.25)
    return _finish(out, 0.42)


def shine():
    """光芒：暖暖的一个和弦，慢慢亮起来，带一点闪。"""
    t = _t(1.8)
    pad = sum(np.sin(2 * np.pi * N[nt] * t) * a for nt, a in (("C5", 1.0), ("E5", 0.7), ("G5", 0.6), ("C6", 0.5)))
    pad *= (1 - np.exp(-t * 9)) * np.exp(-t * 1.8)
    y = mix(1.9, [(0.0, pad, 0.35), (0.05, glock(N["C6"], 1.4), 0.4), (0.12, glock(N["G6"], 1.2), 0.25), (0.35, glock(N["E6"], 1.0), 0.2)])
    return _finish(y, 0.42, 0.02, 0.1)


def twinkle():
    """闪粉：小星星一颗颗「叮」，高高的、轻轻的。"""
    r = _rng(71)
    y = buf(1.7)
    for i in range(9):
        nt = ["C6", "E6", "G6", "A6", "D6", "C7"][int(r.integers(0, 6))]
        place(y, glock(N[nt], 0.6), 0.12 * i + r.uniform(0, 0.06), 0.3 + 0.2 * r.uniform())
    return _finish(y, 0.36)


def party():
    """纸屑彩带：拉炮「啵」+ 纸屑哗啦 + 一串上行的欢快音。"""
    r = _rng(81)
    crack = highpass(lowpass(r.normal(0, 1, int(0.5 * SR)), 7000), 1200) * np.exp(-_t(0.5) * 9)
    y = mix(1.5, [(0.0, pluck(240, 620, 0.2, 14) * 1.0, 0.9), (0.0, thud(200, 90, 0.2, 20, 0.5, seed=82), 0.5), (0.02, crack, 0.7),
                  (0.12, arp(["C5", "E5", "G5", "C6", "E6"], 0.07, xylo, 0.5), 0.6), (0.4, arp(["G5", "A5", "C6"], 0.09, glock, 0.7), 0.3)])
    return _finish(y, 0.5)


def dust_puff():
    """灰尘扬起：软软的「噗」。"""
    y = mix(0.45, [(0.0, swell(0.32, 1100, 91, 1.0) * np.exp(-_t(0.32) * 5), 1.0), (0.0, thud(120, 60, 0.2, 18, 0.2, seed=92), 0.6)])
    return _finish(y, 0.36, 0.006, 0.05)


def rain():
    """雨：柔和的沙沙声 + 稀疏的小水滴，3.6 秒，头尾渐入渐出。"""
    d = 3.6
    n = int(d * SR)
    r = _rng(101)
    y = bandpass(r.normal(0, 1, n), 2200, 7000) * 0.5
    y = y * (0.7 + 0.3 * lowpass(r.normal(0, 1, n), 4) / 0.5 * 0.2)
    for _ in range(22):
        place(y, xylo(float(r.uniform(1400, 3200)), 0.06) * 0.35, float(r.uniform(0.1, d - 0.2)))
    env = np.minimum(1, np.linspace(0, 1, n) / 0.15) * np.minimum(1, (1 - np.linspace(0, 1, n)) / 0.25)
    return _finish(y * env, 0.26, 0.05, 0.3)


def splash():
    """水花：「噗通」（下滑的水泡）+ 溅起的小水滴「叮叮」。"""
    r = _rng(111)
    y = mix(1.0, [(0.0, pluck(180, 520, 0.22, 10) * 1.0, 0.9), (0.0, noise_sweep(0.35, 1200, 5000, 112, 0.8) * 0.7, 0.8),
                  (0.0, thud(150, 60, 0.3, 12, 0.2, seed=113), 0.7)])
    for i in range(5):
        place(y, pluck(float(r.uniform(700, 1200)), float(r.uniform(1500, 2400)), 0.09, 30.0), 0.14 + 0.09 * i, 0.32)
    return _finish(y, 0.5)


def whoomp():
    """纸火焰点着：软软的「呼」，不吓人。"""
    y = mix(0.9, [(0.0, swell(0.7, 700, 121, 1.2), 0.9), (0.0, pluck(70, 150, 0.5, 5.0) * 0.6, 0.6), (0.18, glock(N["G5"], 0.7), 0.2)])
    return _finish(y, 0.44, 0.02, 0.1)


def tone_shift():
    """换色调：一阵柔和的「呜——」，像光扫过。"""
    t = _t(0.9)
    f = 260 * (2.0 ** (t / 0.9 * 1.0))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.9) ** 1.5 * 0.5
    y = y + noise_sweep(0.9, 500, 2500, 131, 0.8) * 0.3
    return _finish(y, 0.34, 0.03, 0.1)


def flash():
    """柔和闪白：极短的一声轻「嘶叮」。"""
    y = mix(0.3, [(0.0, noise_sweep(0.1, 2500, 6000, 141, 0.8) * 0.5, 1.0), (0.02, glock(N["G6"], 0.28), 0.6)])
    return _finish(y, 0.32, 0.003, 0.04)


def kaoni():
    """考你（5.8 秒整段，和 fx/kaoni.py 的时间对齐）：0「考你！」两声（叮咚），选项「啵啵」，3、2、1 每秒一下木鱼，4.1 秒「看答案！」一串上行的欢快音。"""
    d = TM.KAONI_END + 0.4
    y = buf(d)
    place(y, marimba(N["G5"], 0.5), 0.0, 0.9)
    place(y, glock(N["G6"], 0.6), 0.0, 0.25)
    place(y, marimba(N["C6"], 0.7), 0.17, 1.0)
    place(y, glock(N["C7"], 0.8), 0.17, 0.25)
    place(y, thud(150, 60, 0.25, 14, 0.2, seed=151), 0.0, 0.5)
    for i, nt in enumerate(("E5", "G5", "A5")):
        t0 = TM.KAONI_OPT + 0.15 * i
        place(y, pluck(360, 900, 0.14, 22.0), t0, 0.6)
    for i in range(TM.KAONI_COUNT):
        t0 = TM.KAONI_RING + i * 1.0
        place(y, pluck(700, 240, 0.12, 30.0) * 0.8, t0, 0.8)                             # 「嗒」
        place(y, xylo(N["A5"] if i < TM.KAONI_COUNT - 1 else N["C6"], 0.25), t0, 0.55)
    ta = TM.KAONI_ANS
    place(y, arp(["C5", "E5", "G5", "C6", "E6"], 0.07, marimba, 0.6), ta, 0.9)
    place(y, chord(["C6", "E6", "G6"], glock, 1.2), ta + 0.28, 0.4)
    place(y, noise_sweep(0.5, 2000, 6000, 152, 0.8) * 0.3, ta + 0.28, 1.0)
    return _finish(y, 0.5, 0.004, 0.08)


def plate_drop():
    """人名牌落下：木牌「咚、咚、嗒」三下（落地弹跳 0.15 / 0.31 / 0.38 秒）+ 一声轻轻的钟摆「叮」。"""
    y = buf(1.2)
    for t0, g in ((0.153, 1.0), (0.305, 0.55), (0.38, 0.3)):
        place(y, thud(210, 80, 0.2, 18, 0.7, seed=161), t0, g)
        place(y, marimba(N["G4"], 0.3), t0, 0.6 * g)
    place(y, pluck(500, 200, 0.16, 8) * 0.3, 0.0, 1.0)
    place(y, glock(N["C6"], 0.9), 0.44, 0.28)
    return _finish(y, 0.5)


def person_card():
    """人物卡：翻着飞进来「呼」，0.55 秒落稳「啪」+ 收集的一串上行「叮铃」，1.05 秒光扫过「叮」。"""
    y = buf(1.9)
    place(y, noise_sweep(0.55, 400, 2400, 171, 0.6) * 0.8, 0.0, 1.0)
    place(y, thud(170, 60, 0.28, 12, 0.4, seed=172), 0.55, 0.8)
    place(y, arp(["C5", "E5", "G5", "C6", "E6", "G6"], 0.075, glock, 0.7), 0.58, 0.55)
    place(y, marimba(N["C5"], 0.5), 0.58, 0.7)
    place(y, glock(N["C7"], 1.0), 1.05, 0.3)
    return _finish(y, 0.5, 0.004, 0.1)


def card_quest():
    """任务卡：牌子落下「嗒、嗒、嗒」（触地在 0.15 / 0.29 / 0.36 / 0.4 秒），然后「叮——铃」两个亮亮的音。"""
    y = buf(1.5)
    place(y, noise_sweep(0.36, 500, 2200, 181, 0.6) * 0.5, 0.0, 1.0)
    for t0, g in ((0.146, 0.9), (0.29, 0.5), (0.36, 0.3), (0.4, 0.7)):                       # 牌子落下的四次触地（bounce_out）
        place(y, thud(200, 80, 0.22, 18, 0.7, seed=182), t0, g)
    place(y, marimba(N["G5"], 0.5), 0.42, 0.8)
    place(y, glock(N["D6"], 1.0), 0.56, 0.45)
    place(y, glock(N["G6"], 0.9), 0.56, 0.2)
    return _finish(y, 0.5, 0.004, 0.08)


def card_fail():
    """任务失败：软软的「呜呜」下行三个音（不吓人），落下时一声闷闷的「咚」（0.28 秒）。"""
    y = buf(1.5)
    place(y, pluck(420, 140, 0.28, 3.0) * 0.4, 0.0, 1.0)
    place(y, thud(130, 55, 0.35, 10, 0.1, seed=191), 0.28, 0.9)
    for i, nt in enumerate(("E5", "D5", "C5")):
        t = _t(0.42)
        vib = np.sin(2 * np.pi * N[nt] * t + 0.6 * np.sin(2 * np.pi * 5.0 * t)) * np.exp(-t * 3.2)
        place(y, vib * np.minimum(1, t / 0.02), 0.34 + 0.24 * i, 0.5)
    return _finish(y, 0.42, 0.006, 0.12)


def card_title():
    """获得称号：缎带展开「呲——」+ 明亮的号角琶音（钟琴 + 马林巴）+ 闪。"""
    y = buf(1.9)
    place(y, pluck(200, 600, 0.3, 6.0) * 0.3, 0.0, 1.0)
    place(y, noise_sweep(0.4, 500, 3000, 201, 0.6) * 0.5, 0.0, 1.0)
    place(y, arp(["C5", "E5", "G5", "C6"], 0.09, marimba, 0.6), 0.22, 0.9)
    place(y, chord(["G5", "C6", "E6", "G6"], glock, 1.4), 0.55, 0.45)
    place(y, glock(N["C7"], 1.0), 0.7, 0.25)
    return _finish(y, 0.5, 0.004, 0.12)


def card_mvp():
    """本集 MVP：更大的一声——鼓点式的「咚咚」+ 长一点的上行琶音 + 一大阵闪光。"""
    y = buf(2.4)
    place(y, thud(150, 55, 0.3, 10, 0.4, seed=211), 0.0, 0.9)
    place(y, thud(150, 55, 0.3, 10, 0.4, seed=212), 0.14, 0.9)
    place(y, arp(["C5", "E5", "G5", "C6", "E6", "G6"], 0.08, marimba, 0.6), 0.3, 0.85)
    place(y, chord(["C6", "E6", "G6", "C7"], glock, 1.8), 0.85, 0.45)
    place(y, noise_sweep(0.8, 1500, 6000, 213, 0.9) * 0.3, 0.8, 1.0)
    place(y, twinkle(), 0.9, 0.5)
    return _finish(y, 0.52, 0.004, 0.15)


def title_boom():
    """大字标题：重重的「咚」（落地 0.16 秒）+ 光芒「叮铃」，尾音拖一点。"""
    y = buf(1.7)
    place(y, noise_sweep(0.16, 300, 1600, 221, 0.6) * 0.5, 0.0, 1.0)
    place(y, thud(120, 42, 0.5, 8, 0.4, seed=222), 0.16, 1.0)
    place(y, marimba(N["C4"], 0.5), 0.16, 0.8)
    place(y, arp(["C6", "E6", "G6", "C7"], 0.06, glock, 0.9), 0.2, 0.42)
    place(y, chord(["C5", "G5", "C6"], glock, 1.2), 0.2, 0.3)
    return _finish(y, 0.54, 0.004, 0.15)


def gauge_pop():
    """进度物：弹出「啵」；水位涨起来（0.7 秒起，0.9 秒）「咕噜」的水声；到位时 1.6 秒「咕」一声。"""
    y = buf(2.1)
    place(y, pluck(300, 800, 0.2, 14) * 0.9, 0.0, 0.8)
    place(y, marimba(N["E5"], 0.4), 0.02, 0.5)
    n = int(0.9 * SR)
    sw = lowpass(_rng(231).normal(0, 1, n), 900) * np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    place(y, sw / max(np.abs(sw).max(), 1e-9), 0.7, 0.38)
    for i in range(4):
        place(y, pluck(300 + 90 * i, 700 + 160 * i, 0.09, 26) * 0.4, 0.8 + 0.2 * i, 1.0)
    place(y, pluck(260, 620, 0.16, 12) * 0.8, 1.6, 1.0)
    place(y, glock(N["G5"], 0.6), 1.62, 0.3)
    return _finish(y, 0.46)


def screen_on():
    """纸屏幕亮起：「咔哒」+ 一声上行的「嘟噜」。"""
    y = mix(0.8, [(0.0, thud(320, 120, 0.12, 40, 0.9, seed=241), 0.6), (0.04, pluck(260, 1100, 0.32, 5.0) * 0.5, 1.0), (0.12, glock(N["E6"], 0.6), 0.28),
                  (0.0, noise_sweep(0.35, 700, 3500, 242, 0.8) * 0.3, 1.0)])
    return _finish(y, 0.42)


def click():
    """按遥控器：清脆的「嗒」+ 一声「叮」。"""
    y = mix(0.6, [(0.0, thud(600, 240, 0.08, 60, 1.0, seed=251), 0.7), (0.03, xylo(N["A5"], 0.3), 0.7), (0.05, glock(N["E6"], 0.5), 0.4)])
    return _finish(y, 0.48, 0.002)


def bubble_pop():
    """想象泡泡：大泡泡「啵噜」+ 两个小泡泡「噗、噗」（尾巴上的小圆点）。"""
    y = mix(0.6, [(0.0, pluck(240, 720, 0.22, 11) * 1.0, 0.9), (0.09, pluck(360, 900, 0.1, 22) * 0.6, 0.6), (0.17, pluck(480, 1100, 0.08, 26) * 0.5, 0.5),
                  (0.0, noise_sweep(0.15, 1500, 4000, 261, 0.9) * 0.2, 1.0)])
    return _finish(y, 0.44)


def page_slide():
    """书页边滑上来：纸「唰」+ 一下轻「嗒」。"""
    y = mix(0.7, [(0.0, noise_sweep(0.4, 600, 2600, 271, 0.65) * 0.9, 1.0), (0.3, thud(180, 80, 0.2, 18, 0.5, seed=272), 0.6)])
    return _finish(y, 0.42, 0.01, 0.06)


def page_flip():
    """翻书页（在切点响）：纸「唰啦」——重音在开头，尾巴慢慢散。"""
    r = _rng(281)
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    rustle = highpass(lowpass(r.normal(0, 1, n), 6000), 1500) * np.exp(-t * 6)
    y = mix(0.75, [(0.0, noise_sweep(0.5, 3000, 700, 282, 0.7, curve=lambda f: f) * 1.0, 1.0), (0.0, rustle, 0.35), (0.0, thud(140, 70, 0.15, 25, 0.3, seed=283), 0.3)])
    return _finish(y, 0.42, 0.004, 0.08)


def paper_swipe():
    """纸片擦过：「唰——啪」，纸片一条条扫过去。"""
    y = mix(0.6, [(0.0, noise_sweep(0.36, 900, 3500, 291, 0.7, curve=lambda f: f ** 0.7) * 1.0, 1.0), (0.0, thud(200, 90, 0.14, 26, 0.6, seed=292), 0.5),
                  (0.12, noise_sweep(0.3, 600, 2500, 293, 0.7) * 0.6, 1.0)])
    return _finish(y, 0.44, 0.004, 0.08)


def brush():
    """墨笔刷：一笔「嘶——」（粗糙的沙沙声）。"""
    r = _rng(301)
    n = int(0.65 * SR)
    t = np.arange(n) / SR
    y = bandpass(r.normal(0, 1, n), 700, 4500) * np.exp(-t * 4.5) * np.minimum(1, t / 0.02)
    y = mix(0.7, [(0.0, y, 1.0), (0.0, noise_sweep(0.5, 500, 1800, 302, 0.7) * 0.5, 1.0)])
    return _finish(y, 0.42, 0.004, 0.1)


def iris():
    """圆圈收拢再放开：合拢时「啵」的一声（在切点），然后「哇」一声上滑放开。"""
    y = mix(0.7, [(0.0, pluck(900, 260, 0.14, 20), 0.9), (0.06, pluck(260, 1200, 0.4, 5.0) * 0.6, 0.8), (0.1, glock(N["C6"], 0.5), 0.22)])
    return _finish(y, 0.44)


def fade_soft():
    """淡到纸色：一口气，柔柔的「呜——」（很轻）。"""
    y = mix(0.8, [(0.0, swell(0.7, 900, 311, 1.0), 0.7), (0.1, glock(N["G5"], 0.7), 0.12)])
    return _finish(y, 0.28, 0.02, 0.15)


def whip():
    """甩镜：又短又快的「呼」。"""
    y = noise_sweep(0.3, 400, 4200, 321, 0.75, curve=lambda f: f ** 0.6)
    return _finish(y, 0.46, 0.004, 0.06)


def tv_click():
    """解说台切进故事：「咔」一声按下，屏幕「嗡」地展开（上滑的一阵），落定时一声「叮」。"""
    y = mix(1.0, [(0.0, thud(400, 150, 0.1, 50, 1.0, seed=331), 0.7), (0.04, pluck(250, 1300, 0.5, 4.0) * 0.5, 1.0), (0.05, noise_sweep(0.5, 500, 3800, 332, 0.8) * 0.5, 1.0),
                  (0.5, glock(N["C6"], 0.7), 0.35), (0.5, marimba(N["G5"], 0.5), 0.5)])
    return _finish(y, 0.46, 0.003, 0.1)


def star_ding():
    """属性卡里星星亮一颗：清脆短促的一声钟琴「叮」（一颗一声，全系列同一个声音）。"""
    y = mix(0.55, [(0.0, glock(N["E6"], 0.5), 0.9), (0.0, glock(N["E6"] * 2, 0.3), 0.18), (0.0, pluck(1500, 2200, 0.05, 60) * 0.2, 1.0)])
    return _finish(y, 0.36, 0.002, 0.06)


def light_up():
    """一样东西亮起来：一道往上滑的柔和「呜~」+ 钟琴「叮」+ 一点闪粉，越到后面越亮。"""
    t = _t(0.8)
    f = 330 * (2.0 ** (1.3 * (1 - np.exp(-t * 4.0)) / (1 - np.exp(-3.2))))
    sw = np.sin(2 * np.pi * np.cumsum(f) / SR) * (1 - np.exp(-t * 20)) * np.exp(-t * 2.6)
    y = mix(1.0, [(0.0, sw, 0.5), (0.22, glock(N["G6"], 0.7), 0.5), (0.3, glock(N["C7"], 0.6), 0.3), (0.34, twinkle_bits(0.5, 7), 0.5)])
    return _finish(y, 0.42, 0.004, 0.1)


def twinkle_bits(d, seed):
    r = _rng(seed)
    y = buf(d)
    for i in range(4):
        place(y, glock(N[["E6", "G6", "A6", "C7"][int(r.integers(0, 4))]], 0.3), 0.07 * i + r.uniform(0, 0.03), 0.3)
    return y


def frog_croak():
    """可爱的蛙叫「呱」：两下短促的、圆圆的，带一点上滑的喉音（脉冲串 + 共振峰），不吓人。"""
    def gua(d, f0, f1):
        t = _t(d)
        f = f0 + (f1 - f0) * np.sin(np.pi * np.minimum(t / d, 1.0) * 0.5) ** 1.0
        ph = 2 * np.pi * np.cumsum(f) / SR
        pulse = np.sin(ph) + 0.55 * np.sin(2 * ph + 0.4) + 0.3 * np.sin(3 * ph + 1.1)
        am = 0.6 + 0.4 * np.sin(2 * np.pi * 34 * t)                                        # 喉部的颤动
        y = np.tanh(1.6 * pulse) * am
        y = bandpass(y, 500, 1500, 2) + 0.35 * lowpass(y, 500, 2)
        env = np.sin(np.pi * np.minimum(t / d, 1.0)) ** 0.7
        return y * env
    y = mix(0.75, [(0.0, gua(0.2, 210, 300), 1.0), (0.24, gua(0.24, 190, 330), 0.85)])
    return _finish(y, 0.46, 0.004, 0.06)


def hmph():
    """「哼」（不用人声）：短促下滑的一声，像小低音管——方波加低通、音高从 330 滑到 190 Hz，开头一小口气。"""
    t = _t(0.28)
    f = 190 + 140 * np.exp(-t * 11)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = (np.sign(np.sin(ph)) * 0.5 + np.sin(ph)) * np.exp(-t * 9.0) * np.minimum(1.0, t / 0.006)
    y = lowpass(y, 1100, 3)
    breath = lowpass(_rng(401).normal(0, 1, len(t)), 1800) * np.exp(-t * 90) * 0.5
    return _finish(y + breath, 0.44, 0.003, 0.05)


def tear():
    """撕纸：一阵「嘶啦」——带纤维颗粒的噪声，音量一段一段地起伏（一点一点撕开），开头有一下「嗤」，低通在 7 kHz，不刺耳。"""
    d = 0.55
    n = int(d * SR)
    t = np.arange(n) / SR
    r = _rng(411)
    base = bandpass(r.normal(0, 1, n), 1200, 6500, 2)
    rip = np.abs(lowpass(r.normal(0, 1, n), 38)) * 2.6                                 # 撕的一抖一抖
    rip = rip / rip.max()
    env = np.minimum(1.0, t / 0.012) * np.exp(-t * 4.2) * (0.35 + 0.65 * rip)
    grain = (r.random(n) < 0.010).astype(np.float64)                                    # 纸纤维断掉的小「噼」
    grain = lowpass(np.convolve(grain, np.hanning(9), "same"), 6000) * 5.0 * np.exp(-t * 5.0)
    y = base * env + grain * 0.35
    return _finish(y, 0.44, 0.004, 0.09)


def danmaku_whoosh():
    """弹幕纸条飞过：轻快的「嗖」——一小阵从高到中的气流 + 一点纸的颤动，0.3 秒，很轻（一屏十几条，每条都响，所以不能吵）。"""
    y = mix(0.32, [(0.0, noise_sweep(0.26, 3400, 1100, 501, 0.7, curve=lambda f: f ** 0.7), 1.0), (0.02, pluck(1500, 700, 0.12, 26) * 0.35, 1.0)])
    return _finish(y, 0.36, 0.004, 0.06)


def calendar_flip():
    """翻日历（0.8 秒，和 timing.py 的翻页时刻对齐，从第一张翻起的那一刻开始）：7 张纸页「刷、刷、刷……」——一张比一张慢，每张是一小阵纸的沙沙声 + 尾巴上一点「啪」；
    翻停那一下「嗒」+ 一声马林巴。翻页开始在 CAL_START（p）、每张间隔见 cal_starts，音效里以第一张为 0 秒。"""
    dur = TM.CAL_DUR
    st = TM.cal_starts()
    y = buf(0.95)
    t_first = st[0] * dur
    for i, s0 in enumerate(st):
        t0 = s0 * dur - t_first
        fd = TM.cal_flip_dur(i) * dur
        n = int(fd * SR * 1.1)
        r = _rng(600 + i)
        noise = bandpass(r.normal(0, 1, n), 1500, 6500, 2)
        env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.4 * (1.0 - 0.25 * np.linspace(0, 1, n))
        place(y, noise * env, t0 + 0.005, 0.85 - 0.04 * i)
        place(y, thud(520 - 25 * i, 240, 0.06, 55, 0.6, seed=610 + i), t0 + fd * 0.82, 0.30)          # 翻到底「啪」
    t_end = (st[-1] + TM.cal_flip_dur(len(st) - 1)) * dur - t_first
    place(y, thud(210, 80, 0.2, 18, 0.7, seed=620), t_end, 0.8)
    place(y, marimba(N["G5"], 0.5), t_end, 0.7)
    place(y, glock(N["D6"], 0.6), t_end + 0.02, 0.2)
    return _finish(y, 0.46, 0.004, 0.1)


def freeze():
    """定格「咔哒」：两下干脆的机械快门——「咔」（高一点）、0.07 秒后「哒」（低一点），再加一声很轻的下滑「嗡」（画面停住、纸框合上）。"""
    y = mix(0.6, [(0.0, thud(900, 380, 0.05, 90, 1.0, seed=701), 0.9), (0.0, xylo(N["E6"], 0.12), 0.25), (0.07, thud(520, 210, 0.07, 60, 0.9, seed=702), 1.0),
                  (0.07, marimba(N["A4"], 0.25), 0.35), (0.1, pluck(420, 160, 0.3, 9.0) * 0.3, 1.0)])
    return _finish(y, 0.46, 0.002, 0.08)


SOUNDS = {"pop": pop, "whoosh": whoosh, "burst": burst, "focus": focus, "paper_unfold": paper_unfold, "city_pop": city_pop, "draw": draw, "shine": shine,
          "twinkle": twinkle, "party": party, "dust_puff": dust_puff, "rain": rain, "splash": splash, "whoomp": whoomp, "tone_shift": tone_shift, "flash": flash,
          "kaoni": kaoni, "plate_drop": plate_drop, "person_card": person_card, "card_quest": card_quest, "card_fail": card_fail, "card_title": card_title,
          "card_mvp": card_mvp, "title_boom": title_boom, "gauge_pop": gauge_pop, "screen_on": screen_on, "click": click, "bubble_pop": bubble_pop,
          "page_slide": page_slide, "page_flip": page_flip, "paper_swipe": paper_swipe, "brush": brush, "iris": iris, "fade_soft": fade_soft, "whip": whip,
          "tv_click": tv_click,
          "danmaku_whoosh": danmaku_whoosh, "calendar_flip": calendar_flip, "freeze": freeze, "star_ding": star_ding, "light_up": light_up, "frog_croak": frog_croak, "hmph": hmph, "tear": tear}
for _k in range(1, TM.SLAM_MAX + 1):
    SOUNDS[f"slam_{_k}"] = (lambda k=_k: slam(k))
for _k in range(1, TM.LIST_MAX + 1):
    SOUNDS[f"list_{_k}"] = (lambda k=_k: list_(k))
SOUNDS["stat_open"] = stat_open
for _k in range(1, TM.STAT_MAX + 1):
    SOUNDS[f"stat_row_{_k}"] = (lambda k=_k: stat_row(k))


def write(name, y):
    with wave.open(str(HERE / f"{name}.wav"), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    names = sys.argv[1:] or list(SOUNDS)
    for n in names:
        y = SOUNDS[n]()
        write(n, y)
        print(f"{n}.wav  {len(y) / SR:.2f} 秒  峰值 {np.abs(y).max():.2f}")
