"""audio.py（第 0 步第 6 项第 2、3 条）：系列固定音效的参数没动（对照第 0 步之前的提交逐采样点比）、司马光弹出音效的 wav、
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

    def test_fixed_cues_unchanged_since_before_this_step(self):
        """提问、倒计时、揭晓、过关、进度 +1 的参数是系列固定值：audio.sfx() 对同一批场景 JSON 的输出，和 BASE_COMMIT 的 audio.py 逐采样点一样。"""
        d = workdir("audio_regress")
        old_src = subprocess.run(["git", "show", f"{BASE_COMMIT}:video/audio.py"], cwd=ROOT, capture_output=True, check=True).stdout
        (d / "audio_old.py").write_bytes(old_src)
        old = load("audio_old", d / "audio_old.py")
        files = sorted(glob.glob(str(VIDEO / "scenes" / "ep01v2" / "shot*.json"))) + sorted(glob.glob(str(VIDEO / "scenes" / "ep01" / "*.json")))
        self.assertGreaterEqual(len(files), 10)
        kinds = set()
        for f in files:
            sc = json.loads(Path(f).read_text(encoding="utf-8"))
            n = int(old.SR * sc["duration"])
            a, b = old.sfx(sc, n), self.audio.sfx(sc, n)
            self.assertTrue(np.array_equal(a, b), f"{f} 的音效和第 0 步之前不一样")
            kinds |= {e["type"] for e in sc["events"]}
        self.assertTrue({"choice", "stamp"} <= kinds)   # 提问/倒计时/揭晓、过关这两类确实被比到了

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
