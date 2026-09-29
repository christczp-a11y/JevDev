"""不渲染、不花时间的单元测试：锚点、字幕分页、自动检查、混音、特效登记。"""
import unittest

import numpy as np

import common  # noqa: F401  (把 video/motion 放进 sys.path)
import fx as fxreg
from engine import audiomix, checks
from engine import consts as C
from engine.timeline import AnchorError, Timeline
from engine.ui import split_pages, wrap_lines

TL = Timeline.load(common.PROTO / "voice")


class TestAnchors(unittest.TestCase):
    def test_line_start_and_dt(self):
        self.assertAlmostEqual(TL.resolve({"line": 1}), 1.8)
        self.assertAlmostEqual(TL.resolve({"line": 0, "dt": -0.3}), 0.0)
        self.assertAlmostEqual(TL.resolve({"line": 3}, edge="end"), 7.18)

    def test_word_time_is_proportional_to_char_count(self):
        # 第 5 句「宴会上，智伯当众取笑韩康子，羞辱替韩康子出主意的段规！」24 个字，有声段 10.88–16.08 秒，每字 0.2167 秒
        a, b = TL.word_span(5, "羞辱")
        self.assertAlmostEqual(a, 10.88 + 12 * (5.2 / 24), places=3)
        self.assertAlmostEqual(b, 10.88 + 14 * (5.2 / 24), places=3)
        self.assertAlmostEqual(TL.resolve({"line": 5, "word": "羞辱", "dt": -0.28}), 13.2, delta=0.01)
        self.assertAlmostEqual(TL.resolve({"line": 5, "word": "羞辱"}, edge="end"), b, places=6)
        # 第二次出现的「韩康子」
        self.assertGreater(TL.word_span(5, "韩康子", nth=2)[0], TL.word_span(5, "韩康子")[0] + 1)

    def test_shot_relative_anchor(self):
        self.assertAlmostEqual(TL.resolve({"dt": 0.5}, shot_t0=4.0), 4.5)

    def test_bad_anchors_raise(self):
        for bad in ({"line": 99}, {"line": 1, "word": "不存在的词"}, {"line": 1, "secs": 3}, 3.5, {"dt": 1}, {"word": "给"}, {"line": 2, "word": "给"}):
            with self.assertRaises(AnchorError, msg=repr(bad)):
                TL.resolve(bad)

    def test_action_line_has_no_speech(self):
        self.assertFalse(TL.is_speech(2))
        self.assertIsNone(TL.audio_path(2))
        self.assertTrue(TL.audio_path(0).name == "ceremony_kaokaoni.mp3")          # 系列录音路径
        self.assertEqual(TL.audio_path(1).name, "01.mp3")


REAL = common.ROOT / "video" / "out" / "tj01_voice"


@unittest.skipUnless((REAL / "timeline.json").exists(), "没有 video/out/tj01_voice（不进 git，本地才有）")
class TestRealTimeline(unittest.TestCase):
    def test_every_word_of_every_line_resolves_in_order(self):
        """tj01 的旧配音时间线（54 句）：每一句的每个字都能锚到，时间落在这一句里、按字的顺序递增。"""
        tl = Timeline.load(REAL)
        from engine.timeline import core
        n = 0
        for i, ln in enumerate(tl.lines):
            if not tl.is_speech(i):
                continue
            text = core(ln["text"])
            last = ln["t0"] - 1e-9
            for k, ch in enumerate(text):
                a, b = tl.word_span(i, ch, nth=text[:k + 1].count(ch))
                self.assertLess(last, a + 1e-9)
                self.assertLessEqual(a, b)
                self.assertGreaterEqual(a, ln["t0"])
                self.assertLessEqual(b, ln["t1"] + 1e-9)
                last = a
                n += 1
        self.assertGreater(n, 500)
        self.assertAlmostEqual(tl.resolve({"line": 0, "dt": -0.3}), 0.0)


class TestSubtitles(unittest.TestCase):
    def test_long_line_pages(self):
        text = "他爸爸要选他接班，可智果拦着：不能选他！他对人不好，智家会没！"
        pages = split_pages(text)
        self.assertEqual("".join(pages), text)
        self.assertGreater(len(pages), 1)
        for p in pages:
            self.assertLessEqual(len(p), C.SUB_LINE_CHARS * C.SUB_MAX_LINES)
            lines = wrap_lines(p)
            self.assertLessEqual(len(lines), C.SUB_MAX_LINES)
            for ln in lines:
                self.assertLessEqual(len(ln), C.SUB_LINE_CHARS)
                self.assertNotIn(ln[0], "，。！？；：、）」』”…—")

    def test_short_line_is_one_page_one_line(self):
        self.assertEqual(split_pages("考考你！"), ["考考你！"])
        self.assertEqual(wrap_lines("要地，给不给？"), ["要地，给不给？"])

    def test_wrap_prefers_punctuation(self):
        self.assertEqual(wrap_lines("宴会上，智伯当众取笑韩康子，羞辱替韩康子出主意的段规！"), ["宴会上，智伯当众取笑韩康子，", "羞辱替韩康子出主意的段规！"])


class TestChecks(unittest.TestCase):
    def test_flicker(self):
        fps = 30
        L = np.full(90, 0.3)
        self.assertEqual(checks.flicker(L, fps), [])
        L2 = L.copy()
        L2[10:12] = 0.9                                   # 一次闪白（2 次突变）：不算
        self.assertEqual(checks.flicker(L2, fps), [])
        L3 = L.copy()
        for k in range(4):                                # 1 秒内 4 次闪白（8 次突变）
            L3[10 + 6 * k:12 + 6 * k] = 0.9
        ev = checks.flicker(L3, fps)
        self.assertEqual(len(ev), 1)
        self.assertLess(ev[0]["t0"], 0.5)
        L4 = L.copy()
        L4[10:11], L4[13:14] = 0.9, 0.9                   # 恰好 4 次突变（>3）：报
        self.assertEqual(len(checks.flicker(L4, fps)), 1)
        L5 = L.copy()
        L5[10:11], L5[13:14] = 0.5, 0.5                   # 变化只有 0.2 但 ≥ 0.1：也是突变
        self.assertEqual(len(checks.flicker(L5, fps)), 1)
        L6 = np.linspace(0.1, 0.9, 90)                    # 慢慢变亮：不算
        self.assertEqual(checks.flicker(L6, fps), [])

    def test_static(self):
        self.assertEqual(checks.static([0.0] * 40), [])                 # 1.33 秒：可以
        ev = checks.static([0.3] * 10 + [0.0] * 60 + [0.3] * 10)        # 2 秒：不行
        self.assertEqual(len(ev), 1)
        self.assertGreater(ev[0]["sec"], 1.5)
        self.assertEqual(checks.static([0.3] * 100), [])
        self.assertEqual(checks.static([0.0] * 46)[0]["sec"], round(46 / 30, 3))   # 46 帧 > 1.5 秒

    def test_loudness_verdict(self):
        self.assertTrue(checks.loudness(-16.4, -2.0)["ok"])
        self.assertFalse(checks.loudness(-19.0, -2.0)["ok"])
        self.assertFalse(checks.loudness(-16.0, -1.0)["ok"])

    def test_voice_verdict(self):
        self.assertFalse(checks.voice([{"line": 1, "text": "x", "voiced_ratio": 0.0}])["ok"])
        self.assertTrue(checks.voice([{"line": 1, "text": "x", "voiced_ratio": 0.6}])["ok"])


class TestAudio(unittest.TestCase):
    sr = audiomix.SR

    def tone(self, sec, amp=0.3, f=440):
        t = np.arange(int(sec * self.sr)) / self.sr
        x = (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)
        return np.stack([x, x], axis=1)

    def test_place_clamps_out_of_range(self):
        """PITFALLS A6：时间线比画面长、音频超出范围，不许崩。"""
        dst = np.zeros((self.sr, 2), np.float32)
        audiomix.place(dst, self.tone(2.0), 0.5)          # 超出末尾
        audiomix.place(dst, self.tone(1.0), 5.0)          # 完全在范围外
        audiomix.place(dst, self.tone(1.0), -0.5)         # 起点在范围前
        self.assertGreater(np.abs(dst[:100]).max(), 0)
        self.assertGreater(np.abs(dst[-100:]).max(), 0)

    def test_limiter_respects_threshold(self):
        x = self.tone(1.0, amp=1.8)
        y = audiomix.limit(x, 0.8)
        self.assertLessEqual(np.abs(y).max(), 0.8 + 1e-4)

    def test_duck_envelope(self):
        v = np.zeros((6 * self.sr, 2), np.float32)
        v[2 * self.sr:3 * self.sr] = self.tone(1.0, 0.2)
        env = audiomix.duck_envelope(v, len(v))
        at = lambda t: env[int(t * self.sr)]
        self.assertLess(at(0.5), 0.02)
        self.assertGreater(at(1.98), 0.02)                # 提前 0.06 秒开始压
        self.assertGreater(at(2.5), 0.9)
        self.assertLess(at(5.5), 0.05)                    # 说完 2.5 秒以后音乐回来了

    def test_level_voice_targets_rms_with_limit(self):
        clip = self.tone(1.0, 0.02)                        # 太轻：−37 dB 左右，要补 14 dB，但最多只补 8 dB
        y = audiomix.level_voice(clip)
        gain = 20 * np.log10(np.abs(y).max() / np.abs(clip).max())
        self.assertAlmostEqual(gain, C.VOICE_GAIN_LIMIT_DB, places=1)
        loud = audiomix.level_voice(self.tone(1.0, 0.5))
        self.assertLess(np.abs(loud).max(), 0.5)

    def test_normalize_hits_target_and_peak(self):
        rng = np.random.default_rng(3)
        n = 8 * self.sr
        x = rng.normal(0, 0.05, (n, 2)).astype(np.float32)
        x[3 * self.sr:3 * self.sr + 200] *= 12                # 一小段尖峰，逼限幅器出场
        y, lufs, tp, it = audiomix.normalize(x)
        self.assertAlmostEqual(lufs, C.LUFS_TARGET, delta=0.3)
        self.assertLessEqual(tp, C.PEAK_MAX_DB)
        lufs2, tp2 = audiomix.measure(y)
        self.assertAlmostEqual(lufs2, lufs, delta=0.05)


class TestFxRegistry(unittest.TestCase):
    def setUp(self):
        fxreg.load_plugins()

    def test_examples_registered(self):
        self.assertIn("sticker", fxreg.FX)
        self.assertEqual(fxreg.FX["sticker"].sfx, "pop")
        self.assertIn("dissolve", fxreg.TRANSITIONS)
        self.assertTrue((C.SFX_DIR / "pop.wav").exists())

    def test_duplicate_name_is_an_error(self):
        with self.assertRaises(ValueError):
            fxreg.fx("sticker")(lambda canvas, t, params, at: None)
        with self.assertRaises(ValueError):
            fxreg.transition("dissolve")(lambda a, b, p, params, canvas: a)

    def test_sticker_check_hook(self):
        chk = fxreg.FX["sticker"].check
        self.assertTrue(chk({"pos": [1, 2]}))                            # 既没 name 也没 text
        self.assertTrue(chk({"text": "咚"}))                             # 缺 pos
        self.assertTrue(chk({"name": "a", "text": "b", "pos": [1, 2]}))  # 两个都写
        self.assertEqual(chk({"text": "咚", "pos": [1, 2]}), [])

    def test_sticker_draws_only_inside_its_life(self):
        from engine.canvas import Canvas
        from engine.sprites import AssetStore
        cv = Canvas(AssetStore(0.5), 0.5, C.FPS, 3.0)
        blank = cv.img.copy()
        p = {"type": "sticker", "text": "咚", "pos": [540, 700], "size": 200, "dur": 1.0}
        fn = fxreg.FX["sticker"].fn
        fn(cv, 0.9, p, 1.0)                                              # 还没到 at
        self.assertTrue((cv.img == blank).all())
        fn(cv, 1.3, p, 1.0)                                              # 弹出以后
        self.assertFalse((cv.img == blank).all())
        cv.reset()
        fn(cv, 1.0 + 1.0 + 0.25, p, 1.0)                                 # dur 过了、收尾也结束了
        self.assertTrue((cv.img == blank).all())
        cv.reset()
        fn(cv, 1.0 + 0.0, p, 1.0)                                        # 刚出现的第一刻：大小是 0
        self.assertTrue((cv.img == blank).all())
        first = []
        for u in (0.05, 0.15, 0.25, 0.35):                                # 过冲：中间某一刻比最终大小还大
            cv.reset()
            fn(cv, 1.0 + u, p, 1.0)
            first.append(int((cv.img != blank).any(axis=2).sum()))
        self.assertGreater(max(first[:3]), first[3])

    def test_sfx_synth_is_reproducible(self):
        import wave
        from sfx import synth
        y = synth.pop()
        with wave.open(str(C.SFX_DIR / "pop.wav")) as w:
            data = np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32767
        self.assertEqual(len(y), len(data))
        self.assertLess(np.abs(y - data).max(), 2 / 32767)


if __name__ == "__main__":
    unittest.main()
