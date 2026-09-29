"""audio.py（第 0 步第 6 项第 2、3 条；A4）：系列固定音效的参数没动（对照第 0 步之前的提交、只把 tone() 换成修好的，逐采样点比）、
tone() 不给 f_end 时是正弦（过零次数、主频）、揭晓/倒计时/进度 +1/过关有音高、司马光弹出音效的 wav、
sha256 核对、--make-sgm-pop 不许覆盖（相对路径也拦）、sgm_pop 事件。离线。"""
import glob
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

from harness import BASE_COMMIT, PY, ROOT, sha256, workdir

VIDEO = ROOT / "video"
WAV = VIDEO / "assets" / "audio" / "sgm_pop.wav"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Audio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = load("audio_new", VIDEO / "audio.py")

    # A4（09-29 Chris 同意）：tone() 不给 f_end 时用 np.full(len(t), freq)。基线 = BASE_COMMIT 的 audio.py 只换这一行，
    # 其余参数（时间点、频率、振幅、衰减）仍然逐采样点比，所以「除了修 tone() 以外没动别的」这条检查还在。
    OLD_F = "    f = freq if f_end is None else np.linspace(freq, f_end, len(t))\n"
    NEW_F = "    f = np.full(len(t), freq) if f_end is None else np.linspace(freq, f_end, len(t))\n"

    def load_base(self, d, fixed):
        old_src = subprocess.run(["git", "show", f"{BASE_COMMIT}:video/audio.py"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
        self.assertEqual(old_src.count(self.OLD_F), 1)   # 基线里 tone() 的老写法还在；不在了说明 BASE_COMMIT 或这条测试要改
        if fixed:
            old_src = old_src.replace(self.OLD_F, self.NEW_F)
        name = "audio_base_fixed" if fixed else "audio_base_buggy"
        (d / f"{name}.py").write_bytes(old_src.encode("utf-8"))
        return load(name, d / f"{name}.py")

    def scene_files(self):
        files = sorted(glob.glob(str(VIDEO / "scenes" / "ep01v2" / "shot*.json"))) + sorted(glob.glob(str(VIDEO / "scenes" / "ep01" / "*.json")))
        if not files:
            self.skipTest("试做集 ep01 的场景 JSON 在 09-29 清理仓库时删掉了（three.js 停用），这条回归测试没有输入")
        self.assertGreaterEqual(len(files), 10)
        return files

    def test_fixed_cues_unchanged_since_before_this_step(self):
        """提问、倒计时、揭晓、过关、进度 +1 的参数是系列固定值：audio.sfx() 对同一批场景 JSON 的输出，
        和「BASE_COMMIT 的 audio.py、只换成修好的 tone()」逐采样点一样。"""
        d = workdir("audio_regress")
        old = self.load_base(d, fixed=True)
        kinds = set()
        for f in self.scene_files():
            sc = json.loads(Path(f).read_text(encoding="utf-8"))
            n = int(old.SR * sc["duration"])
            a, b = old.sfx(sc, n), self.audio.sfx(sc, n)
            self.assertTrue(np.array_equal(a, b), f"{f} 的音效和第 0 步之前（只修 tone()）不一样")
            kinds |= {e["type"] for e in sc["events"]}
        self.assertTrue({"choice", "stamp"} <= kinds)   # 提问/倒计时/揭晓、过关这两类确实被比到了

    def test_tone_fix_really_changes_the_sound(self):
        """修好的 tone() 和老的（直流脉冲）不一样，防止基线换错了、两边其实都是老写法而这条回归白过。"""
        d = workdir("audio_regress_buggy")
        buggy = self.load_base(d, fixed=False)
        sc = {"actors": {}, "props": [], "hud": {}, "duration": 4.0,
              "events": [{"type": "choice", "t0": 0.5, "reveal": 2.5, "options": ["甲", "乙"]}]}
        n = int(self.audio.SR * 4.0)
        self.assertFalse(np.array_equal(buggy.sfx(sc, n), self.audio.sfx(sc, n)))

    @staticmethod
    def zero_crossings(x):
        s = np.signbit(x)
        return int(np.count_nonzero(s[1:] != s[:-1]))

    def test_tone_without_f_end_is_a_sine_at_freq(self):
        """A4 的单元检查：tone(freq, dur, ...) 不给 f_end 时是 freq Hz 的正弦：过零次数 ≈ 2·freq·dur，FFT 主频 = freq；给 f_end 的写法不变。"""
        a = self.audio
        for freq, dur, decay in ((784, 0.3, 8), (1175, 0.45, 6), (1800, 0.05, 60), (90, 0.3, 12), (2400, 0.25, 14)):
            with self.subTest(freq=freq):
                x = a.tone(freq, dur, 0.5, decay)
                self.assertEqual(len(x), int(a.SR * dur))
                zc = self.zero_crossings(x)
                self.assertLessEqual(abs(zc - 2 * freq * dur), 2, (zc, 2 * freq * dur))   # 老写法这里是 0
                if dur >= 0.25:                                                        # 太短的频率分辨率不够，只查过零
                    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)), n=1 << 18))
                    peak = np.argmax(spec) * a.SR / (1 << 18)
                    self.assertLess(abs(peak - freq), 0.03 * freq, (peak, freq))
                self.assertGreater(np.abs(x).max(), 0.3)                                # 不是几乎没声音
        # f_end 写法没变：从 300 扫到 700 Hz，过零次数 ≈ 2·平均频率·时长
        x = a.tone(300, 0.25, 0.35, 6, f_end=700)
        self.assertLessEqual(abs(self.zero_crossings(x) - 2 * 500 * 0.25), 3)
        # f_end == freq 时和不给 f_end 一样（老代码里这两个是不同的声音）
        self.assertTrue(np.allclose(a.tone(880, 0.3, 0.25, 6), a.tone(880, 0.3, 0.25, 6, f_end=880)))

    def test_fixed_series_cues_have_pitch(self):
        """揭晓「叮咚」（784 / 1175 Hz）、倒计时「嘀嗒」（1800 Hz）、进度 +1（988 / 1318 / 1760 Hz）、过关盖章（90 Hz）：
        用 audio.sfx() 出整段声音，看主频都在该有的音高上。老写法下这些声音是衰减的直流脉冲，窗口里的最大值会落在窗口的最低频率上，过不了。"""
        a = self.audio
        SR = a.SR

        def peak_hz(track, t0, t1, lo, hi):
            seg = track[int(t0 * SR):int(t1 * SR)]
            spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n=1 << 18))
            fr = np.fft.rfftfreq(1 << 18, 1 / SR)
            m = (fr >= lo) & (fr <= hi)
            return fr[m][np.argmax(spec[m])]

        def sfx_of(events, dur=4.0, hud=None):
            return a.sfx({"actors": {}, "props": [], "hud": hud or {}, "duration": dur, "events": events}, int(SR * dur))

        tr = sfx_of([{"type": "choice", "t0": 0.2, "reveal": 3.0, "options": ["甲", "乙"]}])
        self.assertLess(abs(peak_hz(tr, 3.0, 3.1, 600, 1000) - 784), 25)      # 揭晓：叮
        self.assertLess(abs(peak_hz(tr, 3.0, 3.1, 1000, 1400) - 1175), 25)    # 揭晓：咚（同时响，分频段看）
        self.assertLess(abs(peak_hz(tr, 0.69, 0.75, 1000, 3000) - 1800), 100)  # 倒计时第一下「嘀」（0.7 秒）
        st = sfx_of([{"type": "stamp", "t": 1.0}])
        self.assertLess(abs(peak_hz(st, 1.2, 1.5, 30, 200) - 90), 10)         # 过关盖章「咚」
        cr = sfx_of([], hud={"credit": [[0.0, 0], [1.0, 1]]})                 # 进度 +1：三个音错开 0.07 秒，1.0 秒起
        for f in (988, 1318, 1760):
            self.assertLess(abs(peak_hz(cr, 1.0 + (f - 988) / 772 * 0.14 + 0.05, 1.0 + (f - 988) / 772 * 0.14 + 0.25, f - 120, f + 120) - f), 40, f)

    def test_fixed_cue_comments_are_there(self):
        src = (VIDEO / "audio.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("系列固定，改动要 Chris 同意"), 4)   # 过关、进度 +1、提问倒计时揭晓、司马光弹出

    def test_sgm_pop_wav_facts(self):
        import wave
        with wave.open(str(WAV), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 44100))
            n = w.getnframes()
            x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32767
        self.assertTrue(0.4 <= n / 44100 <= 0.8, n / 44100)   # 约 0.4–0.8 秒
        self.assertLessEqual(np.abs(x).max(), 0.9)
        self.assertEqual((x[0], x[-1]), (0.0, 0.0))            # 首尾不爆音
        self.assertLess(np.abs(x - self.audio.sgm_pop_clip()).max(), 1e-4)   # 就是 sgm_pop_clip() 的结果（16 位量化误差以内）
        self.assertEqual(sha256(WAV), json.loads((VIDEO / "series_voice.json").read_text(encoding="utf-8"))["files"]["audio/sgm_pop.wav"])

    def test_load_series_wav_checks_sha256(self):
        d = workdir("audio_sha")
        cfg = json.loads((VIDEO / "series_voice.json").read_text(encoding="utf-8"))
        self.audio.load_series_wav("sgm_pop.wav")   # 现在的登记是对的
        old_cfg = self.audio.SERIES_CONFIG
        try:
            bad = json.loads(json.dumps(cfg)); bad["files"]["audio/sgm_pop.wav"] = "0" * 64
            (d / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
            self.audio.SERIES_CONFIG = d / "bad.json"
            with self.assertRaisesRegex(ValueError, "文件被改过"):
                self.audio.load_series_wav("sgm_pop.wav")
            miss = json.loads(json.dumps(cfg)); del miss["files"]["audio/sgm_pop.wav"]
            (d / "miss.json").write_text(json.dumps(miss), encoding="utf-8")
            self.audio.SERIES_CONFIG = d / "miss.json"
            with self.assertRaisesRegex(ValueError, "没有在"):
                self.audio.load_series_wav("sgm_pop.wav")
        finally:
            self.audio.SERIES_CONFIG = old_cfg

    def test_make_sgm_pop_refuses_to_overwrite_series_file_even_by_relative_path(self):
        before = sha256(WAV)
        for arg in ("assets/audio/sgm_pop.wav", "./assets/../assets/audio/sgm_pop.wav", "../video/assets/audio/sgm_pop.wav", None):
            with self.subTest(arg=arg):
                cmd = [PY, "audio.py", "--make-sgm-pop"] + ([arg] if arg else [])
                r = subprocess.run(cmd, cwd=VIDEO, capture_output=True, text=True, encoding="utf-8")   # 在 video/ 目录下用相对路径
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("已有", r.stdout + r.stderr)
        self.assertEqual(sha256(WAV), before)

    def test_make_sgm_pop_to_other_path_is_deterministic(self):
        d = workdir("audio_make")
        outs = []
        for name in ("a.wav", "b.wav"):
            r = subprocess.run([PY, str(VIDEO / "audio.py"), "--make-sgm-pop", str(d / name)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("files", r.stdout)   # 不在系列目录里，不提示登记
            outs.append(sha256(d / name))
        self.assertEqual(outs[0], outs[1])       # 噪声种子固定，每次生成一样
        self.assertEqual(outs[0], sha256(WAV))

    def test_sgm_pop_event_places_the_wav_at_the_time(self):
        a = self.audio
        sc = {"actors": {}, "props": [], "events": [{"type": "sgm_pop", "t": 1.0}], "hud": {}, "duration": 3.0}
        track = a.sfx(sc, int(a.SR * 3))
        wav = a.load_series_wav("sgm_pop.wav")
        i = int(1.0 * a.SR)
        self.assertEqual(np.abs(track[:i]).max(), 0.0)
        self.assertTrue(np.allclose(track[i:i + len(wav)], wav))


if __name__ == "__main__":
    unittest.main()
