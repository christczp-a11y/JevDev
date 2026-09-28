"""用代码合成音乐和音效（版权完全是我们自己的）：五声音阶的拨弦旋律（像古筝），加上跟剧本事件对齐的音效。

音效时间点直接从剧本里读：跳跃、顶方块、气泡弹出、赏金变化、铜钱雨、盖章。
配音（旁白、角色）另外做，见第 4 轮「声音」。
"""
import json
import wave

import numpy as np

SR = 44100
PENTA = [0, 2, 4, 7, 9]           # 宫商角徵羽
BASE = 261.63                      # C4


def note_freq(degree, octave=0):
    o, i = divmod(degree, 5)
    return BASE * 2 ** ((PENTA[i] + 12 * (o + octave)) / 12)


def pluck(freq, dur, amp=0.5, seed=0):
    """Karplus-Strong 拨弦：一段噪声在延迟线里反复平均，听起来像弹拨乐器。"""
    n = int(SR * dur)
    period = max(2, int(SR / freq))
    buf = np.random.default_rng(seed).uniform(-1, 1, period)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = 0.5 * (buf[i % period] + buf[(i + 1) % period]) * 0.996
    return out * amp


def tone(freq, dur, amp, decay=8.0, f_end=None):
    t = np.arange(int(SR * dur)) / SR
    f = freq if f_end is None else np.linspace(freq, f_end, len(t))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * decay) * amp


def add(track, clip, at):
    i = int(at * SR)
    if i >= len(track):
        return
    j = min(len(track), i + len(clip))
    track[i:j] += clip[:j - i]


def music(duration, bpm=100, seed=1):
    track = np.zeros(int(SR * duration))
    beat = 60 / bpm
    rng = np.random.default_rng(seed)
    melody = [4, 5, 7, 5, 4, 2, 4, 0, 2, 4, 5, 4, 2, 0, 1, 2]   # 一段轻快的五声旋律，循环
    t, k = 0.0, 0
    while t < duration:
        deg = melody[k % len(melody)]
        add(track, pluck(note_freq(deg, 1), beat * 1.6, 0.22, seed=k), t)
        if k % 2 == 0:                                            # 低音在强拍
            add(track, pluck(note_freq(melody[k % len(melody)] % 5, -1), beat * 2, 0.28, seed=100 + k), t)
        if rng.random() < 0.25:                                   # 偶尔的装饰音
            add(track, pluck(note_freq(deg + 2, 1), beat * 0.8, 0.1, seed=200 + k), t + beat / 2)
        t += beat
        k += 1
    fade = int(SR * 1.2)
    track[-fade:] *= np.linspace(1, 0, fade)
    track[:int(SR * 0.3)] *= np.linspace(0, 1, int(SR * 0.3))
    return track


def sfx(scene, n):
    track = np.zeros(n)
    for a in scene["actors"].values():
        for t0, t1, _h in a.get("jumps", []):
            add(track, tone(300, 0.25, 0.35, 6, f_end=700), t0)                    # 跳：上扬的「嘣」
        for t0, _t1, _text in a.get("bubbles", []):
            add(track, tone(900, 0.08, 0.25, 30, f_end=1300), t0)                  # 气泡：「啵」
    for p in scene["props"]:
        if p["type"] == "block":
            add(track, tone(150, 0.2, 0.6, 18) + np.pad(np.random.default_rng(1).uniform(-0.3, 0.3, 2000) *
                                                          np.exp(-np.arange(2000) / 300), (0, int(SR * 0.2) - 2000)), p["hitAt"])
            add(track, tone(880, 0.3, 0.25, 6, f_end=1320), p["hitAt"] + 0.1)     # 蹦出奖励
        if p["type"] == "pole":   # 三丈木杆：扛起时木头「咯吱」一声，放下时「咚」地落地、再轻弹一下
            add(track, tone(180, 0.35, 0.3, 9, f_end=140) + tone(420, 0.35, 0.08, 14, f_end=380), p["lift"][0] + 0.35)
            add(track, tone(110, 0.4, 0.7, 11) + tone(70, 0.4, 0.4, 9), p["drop"][0] + 0.75 * (p["drop"][1] - p["drop"][0]))
            add(track, tone(120, 0.2, 0.25, 16), p["drop"][1] - 0.05)
    for steps in scene.get("_steps", {}).values():   # 脚步：跟着纸偶每只脚着地的时刻，走轻跑重
        for i, (t, k) in enumerate(steps):
            thud = tone(95 + 12 * (i % 2), 0.09, 0.18 + 0.22 * k, 38) + np.pad(np.random.default_rng(i).uniform(-0.06, 0.06, 900) *
                                                                              np.exp(-np.arange(900) / 120), (0, int(SR * 0.09) - 900))
            add(track, thud, t)
    for ev in scene["events"]:
        if ev["type"] == "gold":   # 金块一块块落进怀里：清脆的「叮」
            for i in range(ev["n"]):
                add(track, tone(2400 + 180 * (i % 3), 0.25, 0.18, 14) + tone(3600, 0.25, 0.07, 20), ev["t"] + i * 0.2 + 0.45)
    prev = None
    for t, v in ((scene.get("hud") or {}).get("coins") or []):
        if prev is not None and v is not None and prev is not None and v != prev:
            for i, f in enumerate([1318, 1760]):
                add(track, tone(f, 0.35, 0.3, 7), t + i * 0.09)                    # 赏金变化：「叮叮」
        prev = v
    rng = np.random.default_rng(5)
    for ev in scene["events"]:
        if ev["type"] == "coinRain":
            for _ in range(ev["n"]):
                at = ev["t"] + rng.uniform(0.25, 1.3)
                add(track, tone(rng.uniform(2200, 3200), 0.18, 0.12, 20) + tone(rng.uniform(3300, 4200), 0.18, 0.06, 25), at)
        if ev["type"] == "stamp":
            add(track, tone(90, 0.3, 0.8, 12) + tone(60, 0.3, 0.5, 10), ev["t"] + 0.2)   # 盖章：「咚」
            for i, f in enumerate([523, 659, 784, 1046]):
                add(track, pluck(f, 0.8, 0.3, seed=300 + i), ev["t"] + 0.35 + i * 0.1)  # 过关琶音
    extra_sfx(scene, track)
    return track


def noise_burst(dur, amp, decay, seed=0):
    n = int(SR * dur)
    return np.random.default_rng(seed).uniform(-1, 1, n) * np.exp(-np.arange(n) / (SR / decay)) * amp


def extra_sfx(scene, track):
    """第 1 集起新增的画面事件的音效。"""
    hud = scene.get("hud") or {}
    for t, _v in (hud.get("credit") or [])[1:]:      # 爱心变红：上行的「叮～」
        for i, f in enumerate([988, 1318, 1760]):
            add(track, tone(f, 0.4, 0.22, 6), t + i * 0.07)
    for c0, c1 in hud.get("crack") or []:             # 爱心裂开：「咔」；拼回来：亮晶晶的上行音
        if c0 > 0:
            add(track, noise_burst(0.12, 0.5, 40, 3) + tone(200, 0.12, 0.3, 30, f_end=120), c0)
        if c1 < scene["duration"]:
            for i, f in enumerate([1046, 1318, 1568, 2093]):
                add(track, tone(f, 0.35, 0.15, 7), c1 + i * 0.06)
    for p in scene["props"]:
        if p["type"] == "pole" and "appear" in p:     # 木杆「咚」地竖起来
            add(track, tone(90, 0.5, 0.8, 8) + tone(55, 0.5, 0.5, 6), p["appear"] + 0.2)
        if p["type"] == "sprite" and p.get("sfx") == "pop":
            add(track, tone(700, 0.1, 0.2, 25, f_end=1100), p["show"][0])
        if p["type"] == "board":
            add(track, tone(160, 0.25, 0.4, 12, f_end=240), p["show"][0])
    for ev in scene["events"]:
        k = ev["type"]
        if k == "banner":                              # 横幅落下：「嗖——」+ 小鼓
            add(track, noise_burst(0.35, 0.15, 6, 7) * np.linspace(0.2, 1, int(SR * 0.35)), ev["t"])
            add(track, tone(130, 0.25, 0.5, 14), ev["t"] + 0.35)
        if k == "badges":                              # 徽章解锁：「叮」
            for tu, _lab in ev["items"]:
                add(track, tone(1568, 0.5, 0.25, 6) + tone(2349, 0.5, 0.12, 8), tu)
        if k == "boss":                                # BOSS 登场：低沉的两下鼓；血条掉：「砰」
            add(track, tone(70, 0.5, 0.8, 7), ev["t0"])
            add(track, tone(62, 0.5, 0.8, 7), ev["t0"] + 0.35)
            for t, _v in ev["hp"][1:]:
                add(track, tone(110, 0.3, 0.6, 12, f_end=60) + noise_burst(0.2, 0.2, 20, 9), t)
        if k == "shake":
            add(track, tone(80, 0.3, 0.7, 12) + noise_burst(0.15, 0.25, 30, 11), ev["t"])
        if k == "birds":                               # 纸鸟：一串轻快的「扑棱」
            for i in range(ev["n"]):
                add(track, noise_burst(0.08, 0.12, 50, 20 + i), ev["t"] + 0.2 * i)
        if k == "seasons":                             # 四季翻页：翻纸声
            per = (ev["t1"] - ev["t0"]) / (ev.get("loops", 2) * 4)
            t = ev["t0"]
            while t < ev["t1"]:
                add(track, noise_burst(0.09, 0.2, 45, int(t * 10)), t)
                t += per


def build(scene, out_path):
    n = int(SR * scene["duration"])
    mix = music(scene["duration"])[:n] * 0.7 + sfx(scene, n)
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.9
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path


if __name__ == "__main__":
    import sys
    s = json.loads(open(sys.argv[1], encoding="utf-8").read())
    print(build(s, sys.argv[2]))
