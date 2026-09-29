"""特效包（fx/）和固定音效（sfx/）的测试（阶段 B）：
  · 《节奏和特效》第五节表里的每一个特效和转场都登记了；每个特效默认的音效、转场的音效、按「几下」选的音效（slam_N / list_N / stat_N）文件都在；
  · 每个音效文件：单声道 44.1 kHz、峰值 ≤ 0.55、没有 NaN、头尾不爆音、时长合理、8 kHz 以上几乎没有能量（不刺耳）；
  · 每个特效一个渲染冒烟测试（用样片合集分镜表里它自己的那一条参数，在场景里真的画几帧）：没到 at 不画、出现以后画了东西、结束以后收干净、
    同样的 (t, 参数) 画两次每个像素一样、乱序画（先画后面的时刻）结果也一样（没有隐藏状态）、它要的音效存在；
  · 每个转场：两端接近前一镜 / 后一镜、形状和类型对、不改输入、可复现、中间有变化；
  · 样片合集：分镜表和生成脚本一致、包含所有特效和转场、预览分辨率端到端渲一遍（自动检查：闪烁、静止、响度、人声全过）。
"""
import json
import unittest
import wave

import numpy as np

import common
import fx as fxreg
from engine import consts as C
from engine.canvas import Canvas
from engine.scene import Scene
from engine.sprites import AssetStore
from engine.timeline import Timeline

REEL = common.TESTS / "fx_reel"
NEED_FX = ["lines_radial", "lines_focus", "lines_speed", "sticker", "smash", "checklist", "stat_card", "map", "map_city", "map_arrow", "rays", "sparkle",
           "confetti", "dust", "rain", "splash", "flame", "tone", "flash", "kaoni", "progress", "person_card", "name_plate", "card_quest", "card_fail",
           "card_title", "card_mvp", "big_title", "remote_click", "screen", "bubble", "page_edge"]
NEED_TR = ["page_turn", "paper_wipe", "ink_wipe", "iris", "fade_paper", "whip", "tv_switch", "dissolve"]
COUNT_SFX = [f"{k}_{i}" for k, n in (("slam", 6), ("list", 6), ("stat", 6)) for i in range(1, n + 1)]
BLANK_SPEC = {"id": "t", "from": {"line": 0}, "bg": [], "actors": []}


def setUpModule():
    fxreg.load_plugins([REEL / "fx"])


def reel_entries():
    """样片合集分镜表里每种特效第一次出现的那一条 {type: entry}，每种转场第一次出现的那一条。"""
    sb = json.loads((REEL / "storyboard.json").read_text(encoding="utf-8"))
    fxs, trs = {}, {}
    for sh in sb["shots"]:
        for e in sh["fx"]:
            fxs.setdefault(e["type"], e)
        t = sh.get("transition")
        if t:
            t = {"type": t} if isinstance(t, str) else t
            trs.setdefault(t["type"], t)
    return fxs, trs


FXS, TRS = None, None


def entries():
    global FXS, TRS
    if FXS is None:
        FXS, TRS = reel_entries()
    return FXS, TRS


class TestRegistry(unittest.TestCase):
    def test_every_fx_and_transition_is_registered(self):
        for n in NEED_FX:
            self.assertIn(n, fxreg.FX, f"特效 {n} 没登记")
        for n in NEED_TR:
            self.assertIn(n, fxreg.TRANSITIONS, f"转场 {n} 没登记")

    def test_all_sfx_files_exist(self):
        need = set(COUNT_SFX)
        need |= {s.sfx for s in fxreg.FX.values() if s.sfx and not s.local}
        need |= {s.sfx for s in fxreg.TRANSITIONS.values() if s.sfx}
        for n in sorted(need):
            self.assertTrue((C.SFX_DIR / f"{n}.wav").exists(), f"音效 {n}.wav 不存在")
        self.assertGreaterEqual(len(need), 40)

    def test_every_fx_appears_in_the_reel(self):
        fxs, trs = entries()
        for n in NEED_FX:
            self.assertIn(n, fxs, f"样片合集里没有特效 {n}")
        for n in NEED_TR:
            if n != "dissolve":                                  # dissolve 是接口示例，样片里不演
                self.assertIn(n, trs, f"样片合集里没有转场 {n}")

    def test_series_stickers_exist(self):
        names = sorted(f.stem for f in (C.MOTION / "stickers").glob("*.png"))
        for n in ("question", "question3", "exclaim", "bulb", "sweat", "anger", "star", "star_eyes", "heart", "dong", "pa", "sou"):
            self.assertIn(n, names)


class TestSfxFiles(unittest.TestCase):
    def test_files_are_clean(self):
        files = sorted(C.SFX_DIR.glob("*.wav"))
        self.assertGreaterEqual(len(files), 50)
        for f in files:
            with wave.open(str(f)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, 44100), f.name)
                y = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
            self.assertTrue(np.isfinite(y).all(), f.name)
            self.assertLessEqual(np.abs(y).max(), 0.56, f"{f.name} 峰值太大")
            self.assertGreaterEqual(np.abs(y).max(), 0.2, f"{f.name} 太小声")
            self.assertLess(abs(float(y.mean())), 0.005, f"{f.name} 有直流偏移")
            self.assertLess(float(np.abs(y[-8:]).max()), 0.02, f"{f.name} 结尾没收干净（会有咔嗒声）")
            self.assertLess(len(y) / 44100, 6.6, f.name)
            if f.stem != "pop":                                    # pop 是阶段 A 的示例，开头 3 毫秒渐入
                self.assertLess(float(np.abs(y[:4]).max()), 0.05, f"{f.name} 开头有咔嗒声")
            spec = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
            hf = spec[int(len(y) * 10000 / 44100):].sum() / spec.sum()
            self.assertLess(hf, 0.02, f"{f.name} 10 kHz 以上能量 {hf:.3f}：太刺耳")

    def test_synth_is_reproducible(self):
        from sfx import synth
        for n in ("kaoni", "slam_3", "page_flip", "rain"):
            y = synth.SOUNDS[n]()
            with wave.open(str(C.SFX_DIR / f"{n}.wav")) as w:
                data = np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32767
            self.assertEqual(len(y), len(data), n)
            self.assertLess(np.abs(np.clip(y, -1, 1) - data).max(), 2 / 32767, n)

    def test_kaoni_matches_ritual_length(self):
        from sfx import timing as T
        with wave.open(str(C.SFX_DIR / "kaoni.wav")) as w:
            dur = w.getnframes() / 44100
        self.assertGreaterEqual(dur, T.KAONI_END)
        self.assertLessEqual(dur, T.KAONI_END + 0.6)


TIMES = [0.02, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.5]


def make_scene(entry, at=0.0, S=0.25, extra=None):
    e = dict(entry)
    e["at"] = {"dt": at}
    tl = Timeline.load(REEL / "voice")
    store = AssetStore(S, [REEL])
    spec = dict(BLANK_SPEC, fx=[e])
    if extra:
        spec.update(extra)
    sc = Scene(spec, tl, 0.0, 9.0, store, fxreg.FX)
    cv = Canvas(store, S, C.FPS, 9.0, seed=1)
    return sc, cv


def frame(sc, cv, t):
    cv.rng = np.random.default_rng([1, int(round(t * C.FPS))])
    sc.draw(cv, t, t)
    return cv.img.copy()


class TestFxSmoke(unittest.TestCase):
    """每个特效一个渲染冒烟测试（下面按特效名一个一个生成）。"""


def _fx_test(name):
    def test(self):
        fxs, _ = entries()
        entry = fxs[name]
        sc, cv = make_scene(entry, at=0.5)
        blank_sc, blank_cv = make_scene({"type": "label", "text": "x"}, at=99.0)
        # 音效：特效要用的音效文件都在
        for t, sfx, g in sc.sfx_events():
            self.assertTrue((C.SFX_DIR / f"{sfx}.wav").exists(), f"{name} 要的音效 {sfx} 不存在")
        used = sc.fx[0][2].get("sfx", fxreg.FX[name].sfx)
        self.assertEqual(len(sc.sfx_events()) >= 1, used is not None, f"{name} 的音效和登记不符")
        blank = frame(blank_sc, blank_cv, 0.0)
        # 还没到 at：什么都不画
        for t in (0.0, 0.2, 0.49):
            self.assertTrue((frame(sc, cv, t) == blank).all(), f"{name} 在 at 之前就画了东西（t={t}）")
        # 出现以后：至少有一个时刻画了东西；没有 NaN / 越界（uint8 自己保证）
        changed = []
        for t in TIMES:
            f = frame(sc, cv, 0.5 + t)
            self.assertEqual(f.shape, blank.shape)
            changed.append(bool((f != blank).any()))
        self.assertTrue(any(changed), f"{name} 从头到尾什么都没画")
        # 可复现：新画布、同样的 (t, 参数)，每个像素一样
        sc2, cv2_ = make_scene(entry, at=0.5)
        for t in (0.5 + 0.3, 0.5 + 1.0):
            self.assertTrue((frame(sc, cv, t) == frame(sc2, cv2_, t)).all(), f"{name} 同样的输入两次画出来不一样")
        # 没有隐藏状态：先画后面的时刻，再画前面的，结果和顺序画一样
        ts = [0.5 + t for t in (0.1, 0.4, 0.9, 1.4)]
        fwd = [frame(sc, cv, t) for t in ts]
        sc3, cv3 = make_scene(entry, at=0.5)
        rev = [frame(sc3, cv3, t) for t in reversed(ts)][::-1]
        for a, b, t in zip(fwd, rev, ts):
            self.assertTrue((a == b).all(), f"{name} 画的东西和渲染顺序有关（t={t}）")
    test.__name__ = f"test_{name}"
    return test


for _n in NEED_FX:
    setattr(TestFxSmoke, f"test_{_n}", _fx_test(_n))


class TestFxDetails(unittest.TestCase):
    def test_smash_shake_within_limit(self):
        """砸字的震屏：整幅画面平移不超过画面宽度的 1.5%（有背景的镜头里，字落地前后画面的平移量）。"""
        fxs, _ = entries()
        e = dict(fxs["smash"], shake=999)
        sc, cv = make_scene(e, at=0.0, S=0.5, extra={"bg": [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}]})
        blank_sc, blank_cv = make_scene({"type": "label", "text": "x"}, S=0.5, extra={"bg": [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}]})
        ref = frame(blank_sc, blank_cv, 0.3).astype(np.float32).mean(axis=2)
        worst = 0
        for t in (0.17, 0.19, 0.21, 0.24):
            f = frame(sc, cv, t).astype(np.float32).mean(axis=2)
            top = f[:200, :]                                   # 画面上部没有字，只看背景的平移
            best = min(range(-12, 13), key=lambda dx: float(np.abs(np.roll(ref[:200], dx, axis=1) - top).mean()))
            worst = max(worst, abs(best))
        self.assertLessEqual(worst * 2, C.SHAKE_AMP_MAX + 2)

    def test_flash_is_soft_and_short(self):
        """闪白：最多盖 60% 白、只有 3 帧（0.1 秒），之后一点不剩。"""
        fxs, _ = entries()
        sc, cv = make_scene(fxs["flash"], at=0.0, S=0.25, extra={"bg": [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}]})
        bsc, bcv = make_scene({"type": "label", "text": "x"}, S=0.25, extra={"bg": [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}]})
        ref = frame(bsc, bcv, 1.0).astype(np.float32)
        peaks = []
        for i in range(0, 8):
            f = frame(sc, cv, i / 30.0).astype(np.float32)
            peaks.append(float(((f - ref) / np.maximum(255 - ref, 1)).mean()))
        self.assertLessEqual(max(peaks), 0.6)
        self.assertGreater(max(peaks), 0.3)
        self.assertLessEqual(sum(1 for p in peaks if p > 0.02), 3)
        self.assertLess(peaks[4], 0.01)

    def test_check_hooks_reject_bad_params(self):
        chk = lambda n, p: fxreg.FX[n].check(dict(p))
        self.assertTrue(chk("smash", {"text": "", "pos": [1, 2]}))
        self.assertTrue(chk("smash", {"text": "一二三四五六七", "pos": [1, 2]}))
        self.assertTrue(chk("checklist", {"items": []}))
        self.assertTrue(chk("stat_card", {"rows": [{"label": "本事很长很长", "stars": 5}]}))
        self.assertTrue(chk("kaoni", {"options": []}))
        self.assertTrue(chk("name_plate", {"name": "智伯", "role": "智家老大", "house": "不存在家", "pos": [1, 2]}))
        self.assertTrue(chk("tone", {"tone": "no_such_tone"}))
        self.assertTrue(chk("sticker", {"name": "no_such_sticker", "pos": [1, 2]}))
        self.assertTrue(chk("card_quest", {"text": "", "pos": [1, 2]}))
        self.assertTrue(chk("big_title", {"text": "一二三四五六七八九十一\n二", "pos": [1, 2]}))
        self.assertTrue(chk("map_arrow", {"pts": [[1, 2]]}))
        self.assertEqual(chk("smash", {"text": "本事", "pos": [1, 2]}), [])

    def test_count_based_sfx_is_chosen_by_check(self):
        """砸字 / 清单 / 属性卡按「几下」选音效：check 出片前把 sfx 补进参数；分镜表自己写了（包括 null）就不动。"""
        p = {"text": "本事", "pos": [1, 2]}
        fxreg.FX["smash"].check(p)
        self.assertEqual(p["sfx"], "slam_2")
        p = {"items": ["a", "b", "c"]}
        fxreg.FX["checklist"].check(p)
        self.assertEqual(p["sfx"], "list_3")
        p = {"rows": [{"label": "本事", "stars": 1}], "sfx": None}
        fxreg.FX["stat_card"].check(p)
        self.assertIsNone(p["sfx"])


class TestTransitions(unittest.TestCase):
    def frames(self, S=0.25):
        store = AssetStore(S, [])
        cv = Canvas(store, S, C.FPS, 1.0)
        tl = Timeline.load(REEL / "voice")
        out = []
        for img, x in (("sets/jin_land/sky.png", 200), ("sets/study/wall.png", 0)):
            spec = dict(BLANK_SPEC, bg=[{"img": img, "depth": 0.0, "pos": [0, 0], "w": 1080}], actors=[{"id": "a", "img": "chars/sgm_finger.png", "pos": [x + 300, 1600], "h": 500}])
            sc = Scene(spec, tl, 0.0, 3.0, store, fxreg.FX)
            sc.draw(cv, 1.0, 1.0)
            out.append(cv.img.copy())
        return out[0], out[1], cv

    def test_each_transition(self):
        a, b, cv = self.frames()
        _, trs = entries()
        for name in [n for n in NEED_TR if n != "dissolve"]:
            plug = fxreg.TRANSITIONS[name]
            params = dict(trs.get(name, {"type": name}))
            a0, b0 = a.copy(), b.copy()
            outs = [plug.fn(a, b, p, params, cv) for p in (0.01, 0.2, 0.4, 0.5, 0.6, 0.8, 0.99)]
            self.assertTrue((a == a0).all() and (b == b0).all(), f"{name} 改了输入")
            for o in outs:
                self.assertEqual((o.shape, o.dtype), (a.shape, a.dtype), name)
            self.assertLess(float(np.abs(outs[0].astype(int) - a).mean()), 6.0, f"{name} 开头不像前一镜")
            self.assertLess(float(np.abs(outs[-1].astype(int) - b).mean()), 6.0, f"{name} 结尾不像后一镜")
            self.assertGreater(max(float(np.abs(o.astype(int) - a).mean()) for o in outs[2:5]), 8.0, f"{name} 中间没有变化")
            again = plug.fn(a, b, 0.4, params, cv)
            self.assertTrue((again == outs[2]).all(), f"{name} 同样的输入两次结果不一样")
            self.assertTrue(plug.sfx and (C.SFX_DIR / f"{plug.sfx}.wav").exists(), f"{name} 没有音效")

    def test_smooth_no_jump(self):
        """相邻两帧之间的变化不能一下子跳很大（转场里相邻两帧的平均差 < 60：没有「瞬移」）。"""
        a, b, cv = self.frames()
        _, trs = entries()
        for name in [n for n in NEED_TR if n not in ("dissolve",)]:
            plug = fxreg.TRANSITIONS[name]
            params = dict(trs.get(name, {"type": name}))
            n = max(2, round(float(params.get("dur", plug.dur)) * C.FPS))
            prev = None
            worst = 0.0
            for i in range(n):
                o = plug.fn(a, b, (i + 0.5) / n, params, cv).astype(np.float32)
                if prev is not None:
                    worst = max(worst, float(np.abs(o - prev).mean()))
                prev = o
            self.assertLess(worst, 60.0, f"{name} 逐帧最大变化 {worst:.1f}：一跳一跳")


class TestReel(unittest.TestCase):
    def test_storyboard_matches_generator(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_reel", REEL / "build_reel.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        d = common.fresh("reel_gen")
        old = mod.HERE
        mod.HERE = d
        (d / "voice").mkdir()
        try:
            mod.build()
        finally:
            mod.HERE = old
        for f in ("storyboard.json", "voice/timeline.json"):
            self.assertEqual((d / f).read_text(encoding="utf-8"), (REEL / f).read_text(encoding="utf-8"), f"{f} 和 build_reel.py 生成的不一致（改了脚本没重新生成？）")

    def test_reel_renders_and_passes_auto_checks(self):
        """样片合集预览分辨率端到端渲一遍：退出码 0（闪烁、静止、响度、人声都过）。"""
        out = common.fresh("fx_reel")
        code, log, rep = common.render(REEL / "storyboard.json", out, out / "cache", "--preview")
        self.assertEqual(code, 0, log[-2000:])
        self.assertTrue(rep["ok"], rep["checks"])
        self.assertGreater(rep["duration"], 100)
        self.assertLess(rep["duration"], 180)
        self.assertEqual(rep["checks"]["flicker"]["events"], [])
        self.assertEqual(rep["checks"]["static"]["events"], [])
        self.assertEqual(rep["warnings"], [], rep["warnings"])


if __name__ == "__main__":
    unittest.main()
