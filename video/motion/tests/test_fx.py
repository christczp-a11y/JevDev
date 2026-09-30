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
COUNT_SFX = [f"{k}_{i}" for k, n in (("slam", 6), ("list", 6), ("stat_row", 6)) for i in range(1, n + 1)]
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

    def test_unknown_params_are_errors(self):
        """写了特效不认识的参数 = 出片前报错（不许悄悄忽略）：每个系列特效、每个系列转场。"""
        n = 0
        for name, plug in list(fxreg.FX.items()) + list(fxreg.TRANSITIONS.items()):
            if plug.local or plug.check is None:
                continue
            errs = plug.check({"type": name, "no_such_param_zz": 1})
            self.assertTrue(any("no_such_param_zz" in e and "不认识的参数" in e for e in errs), f"{name} 没有拦住不认识的参数：{errs}")
            n += 1
        self.assertGreaterEqual(n, 38)
        self.assertEqual([e for e in fxreg.FX["flash"].check({"type": "flash", "at": {"dt": 1}, "sfx": None, "dur": 1, "layer": "back", "note": "x"})], [])   # 通用参数都认
        self.assertTrue([e for e in fxreg.FX["flash"].check({"layer": "middle"})])                # layer 只能 front / back
        self.assertTrue([e for e in fxreg.TRANSITIONS["iris"].check({"type": "iris", "layer": "back"})])   # 转场没有 layer

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


class TestReviewFixes(unittest.TestCase):
    """样片合集 reviewer 提出的问题，每一条一个测试（以后每集都会用到的特效不许再犯）。"""

    def scene_with(self, fx_entry, actors=(), bg=None, S=0.5, at=0.0):
        tl = Timeline.load(REEL / "voice")
        store = AssetStore(S, [REEL])
        spec = dict(BLANK_SPEC, bg=bg or [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}], actors=list(actors), fx=[dict(fx_entry, at={"dt": at})])
        sc = Scene(spec, tl, 0.0, 9.0, store, fxreg.FX)
        return sc, Canvas(store, S, C.FPS, 9.0, seed=1)

    def test_flame_must_not_overlap_a_person(self):
        """火焰和人物的框重叠 = 报错（儿童安全：不能像人站在火里）；放在画面两边、不重叠就过。"""
        person = {"id": "zxz", "img": "chars/zxz_stand.png", "pos": [540, 1610], "h": 560}
        with self.assertRaises(ValueError) as cm:
            self.scene_with({"type": "flame", "pos": [540, 1640], "w": 600, "height": 300}, [person])
        self.assertIn("重叠", str(cm.exception))
        with self.assertRaises(ValueError):
            self.scene_with({"type": "flame", "pos": [450, 1640], "w": 240, "height": 340}, [person])
        self.scene_with({"type": "flame", "pos": [150, 1640], "w": 240, "height": 340}, [person])         # 左边，不挡人
        self.scene_with({"type": "flame", "pos": [540, 1640], "w": 600, "height": 300}, [])                # 没有人物
        self.assertTrue(fxreg.FX["flame"].check({"pos": [540, 1640], "w": 600}, {"actors": [person]}))    # check(params, shot) 直接调

    def test_bubble_fits_safe_area_and_tail_stays(self):
        from fx.desk import bubble_width, BUB_AR
        for pos, flip in (([345, 1050], False), ([900, 900], False), ([200, 700], True), ([600, 500], False)):
            w = bubble_width(820, pos[0], pos[1], flip)
            ax = 0.96 if flip else 0.04
            left, right = pos[0] - ax * w, pos[0] + (1 - ax) * w
            top, bottom = pos[1] - 0.92 * w * BUB_AR, pos[1] + 0.08 * w * BUB_AR
            self.assertGreaterEqual(left, 80 - 1e-6)
            self.assertLessEqual(right, 1000 + 1e-6)
            self.assertGreaterEqual(top, 360 - 1e-6)
            self.assertLessEqual(bottom, 1400 + 1e-6)
        self.assertEqual(bubble_width(820, 200, 1300, False), 820)                                          # 放得下就不缩
        self.assertLess(bubble_width(820, 345, 1050, False), 820)                                          # 右边放不下就缩
        self.assertTrue(fxreg.FX["bubble"].check({"pos": [990, 500]}))                                      # 放不下：报错
        self.assertEqual(fxreg.FX["bubble"].check({"pos": [345, 1050], "img": "props/bulb.png"}), [])

    def test_stat_card_draws_only_as_many_slots_as_rows(self):
        from fx.lists import _card_pil, _layout
        cv = Canvas(AssetStore(0.25, []), 0.25, C.FPS, 3.0)
        lay = _layout(cv)
        hs = {n: _card_pil(cv, lay, n)[1] for n in range(1, 7)}
        self.assertEqual(hs[5], hs[6])
        self.assertEqual(hs[3], hs[4])
        self.assertEqual(hs[1], hs[2])
        self.assertLess(hs[1], hs[3])
        self.assertLess(hs[3], hs[5])
        # 奇数行最后一格的凹槽和横条被抹掉了：那一块的颜色变化（标准差）比留着凹槽的小
        cx, cy, r = lay["slots"][1]["circle"]
        sl = (slice(int(cy) - 60, int(cy) + 60), slice(int(cx) - 60, int(cx) + 60))
        erased = np.array(_card_pil(cv, lay, 1)[0])[..., :3].astype(np.float32)[sl]
        kept = np.array(_card_pil(cv, lay, 6)[0])[..., :3].astype(np.float32)[sl]
        self.assertLess(float(erased.std(axis=(0, 1)).mean()) + 2.0, float(kept.std(axis=(0, 1)).mean()))

    def test_confetti_and_sparkle_avoid_faces(self):
        from fx import _paper as P
        person = {"id": "sgm", "img": "chars/sgm_finger.png", "pos": [270, 1600], "h": 540}
        face = P.actor_boxes({"actors": [person]})[0]["face"]
        for entry in ({"type": "confetti", "mode": "burst", "count": 300}, {"type": "sparkle", "area": [60, 1000, 500, 1400], "count": 60}):
            sc, cv = self.scene_with(entry, [person], at=0.0)
            sc0, cv0 = self.scene_with({"type": "label", "text": "x"}, [person], at=99.0)
            sx = cv.S
            box = (int(face[0] * sx), int(face[1] * sx), int(face[2] * sx), int(face[3] * sx))
            seen = 0
            for t in (0.4, 0.6, 0.8, 1.0, 1.3):
                f, f0 = frame(sc, cv, t), frame(sc0, cv0, t)
                d = (f != f0).any(axis=2)
                seen += int(d.sum())
                self.assertEqual(int(d[box[1]:box[3], box[0]:box[2]].sum()), 0, f"{entry['type']} 在脸框里画了东西（t={t}）")
            self.assertGreater(seen, 50, f"{entry['type']} 什么都没画")

    def test_page_edge_hides_the_cut_bottom_of_the_bust(self):
        """探出来的半身像平切的下沿一直藏在书页后面：书页没升起来 / 已经落下去的时候半身像完全不可见，书页在的时候半身像只出现在书页上沿以上。"""
        entry = {"type": "page_edge", "y": 1200, "peek": "chars/sgm_hi_remote.png", "peek_h": 880, "dur": 1.7}
        plain = dict(entry)
        plain.pop("peek")
        S = 0.5
        bg = [{"img": "sets/study/wall.png", "depth": 0.0, "pos": [-100, 0], "w": 1280}]
        sc, cv = self.scene_with(entry, bg=bg, S=S)
        sc0, cv0 = self.scene_with(plain, bg=bg, S=S)
        for t in (0.02, 0.1, 0.2, 0.3):
            self.assertTrue((frame(sc, cv, t) == frame(sc0, cv0, t)).all(), f"书页还没升起来，半身像就露出来了（t={t}）")
        for t in (1.0, 1.4):
            d = (frame(sc, cv, t) != frame(sc0, cv0, t)).any(axis=2)
            rows = np.nonzero(d.any(axis=1))[0]
            self.assertGreater(len(rows), 0)
            self.assertLess(rows.max() / S, 1200 + 24 + 79 + 6, f"半身像的下沿露在书页纸面的最低处以下（t={t}）")   # 书页上沿是弧形：纸面最高点 y+24+55，最低点 y+24+79
        self.assertTrue((frame(sc, cv, 2.35) == frame(sc0, cv0, 2.35)).all())                                 # 落下去以后完全没有半身像

    def test_tone_night_is_blue_and_sweep_ends_smoothly(self):
        entry = {"type": "tone", "tone": "night", "delay": 0.0, "ramp": 0.9}
        sc, cv = self.scene_with(entry, S=0.25)
        last = frame(sc, cv, 2.5).astype(np.float32)
        b, r = last[..., 0].mean(), last[..., 2].mean()
        self.assertGreater(b, 1.6 * r, "夜色不够蓝")
        self.assertGreater(b, 100, "夜色太暗")
        seq = [frame(sc, cv, i / 30.0).astype(np.float32).mean() for i in range(20, 34)]            # 扫色在 0.9 秒（第 27 帧）结束：结束前后逐帧亮度没有跳
        self.assertLess(max(abs(seq[i + 1] - seq[i]) for i in range(7, 13)), 2.0)
        self.assertLess(abs(seq[-1] - seq[-2]), 0.5)

    def test_tone_from_replaces_previous_tone(self):
        """from → to：换色以前是 from 的样子，被 to 扫掉；结束以后和只用 to 的结果一样（不叠成灰雾）。"""
        a = {"type": "tone", "tone": "night", "from": "gold", "delay": 0.2, "ramp": 0.6}
        b = {"type": "tone", "tone": "night", "delay": 0.0, "ramp": 0.0}
        sa, ca = self.scene_with(a, S=0.25)
        sb, cb = self.scene_with(b, S=0.25)
        self.assertTrue((frame(sa, ca, 1.5) == frame(sb, cb, 1.5)).all())
        self.assertFalse((frame(sa, ca, 0.1) == frame(sb, cb, 0.1)).all())

    def test_smash_exit_keeps_edge_until_it_fades_together(self):
        entry = {"type": "smash", "text": "本事", "pos": [540, 600], "dur": 1.0}
        sc, cv = self.scene_with(entry, S=0.5)

        def white(t):
            f = frame(sc, cv, t)
            return int(((f > 236).all(axis=2)[150:450]).sum())
        w0 = white(1.0)
        self.assertGreater(w0, 200)
        self.assertGreaterEqual(white(1.06), 0.7 * w0, "退场刚开始白纸边就没了")
        self.assertLess(white(1.31), 0.1 * w0)

    def test_iris_luma_changes_gradually(self):
        a, b, cv = TestTransitions().frames()
        plug = fxreg.TRANSITIONS["iris"]
        lum = [float(plug.fn(a, b, (i + 0.5) / 21, {"type": "iris", "pos": [540, 1150]}, cv).mean()) for i in range(21)]
        self.assertLess(max(abs(lum[i + 1] - lum[i]) for i in range(20)), 0.09 * 255)
        self.assertLess(abs(lum[2] - lum[0]), 6.0)                                     # 前两帧几乎没变（前慢）

    def test_tv_switch_starts_inside_the_screen(self):
        """前一镜放着纸屏幕：转场第一帧和前一镜几乎一样（小窗口从屏幕纸面上长出来，不是从空墙上冒出来）。"""
        a, b, cv = TestTransitions().frames()
        plug = fxreg.TRANSITIONS["tv_switch"]
        o = plug.fn(a, b, 0.02, {"type": "tv_switch", "pos": [789, 678], "w": 414}, cv)
        self.assertLess(float(np.abs(o.astype(int) - a).mean()), 1.0)
        o2 = plug.fn(a, b, 0.6, {"type": "tv_switch", "pos": [789, 678], "w": 414}, cv)
        self.assertGreater(float(np.abs(o2.astype(int) - a).mean()), 20.0)

    def test_reel_terrain_has_no_gaps(self):
        """样片合集的晋地外景：从 y=1250 一直到画面底，每一行都被地面盖住（不露出奶油色的纸底 / 天空的空带）。"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_reel_t", REEL / "build_reel.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        S = 0.5
        for name in ("SKY", "WATER"):
            sc, cv = self.scene_with({"type": "label", "text": "x"}, bg=getattr(mod, name), S=S)
            for t in (0.0, 1.5, 3.0):
                f = frame(sc, cv, t)
                creamy = ((np.abs(f[..., 2].astype(int) - 230) < 14) & (np.abs(f[..., 1].astype(int) - 220) < 14) & (np.abs(f[..., 0].astype(int) - 200) < 16))
                rows = creamy[int(1250 * S):].mean(axis=1) > 0.3                     # 每条草土带的上沿有一圈白纸边（约 14 像素）是画风；空带是连续几十像素
                run = mx = 0
                for v in rows:
                    run = run + 1 if v else 0
                    mx = max(mx, run)
                self.assertLessEqual(mx / S, 24, f"{name}：y≥1250 有一段连续 {mx / S:.0f} 像素是纸底色（空带）")


class TestNewFxParams(unittest.TestCase):
    """第一场样片 reviewer 提的特效层需求（lines_focus.clear、sticker.follow / exit、dust 柔和颗粒、新音效、name_plate 停留、kaoni.end_stamp、bubble.inner_sway、标题条本集名）。"""

    def scene_with(self, fx_entry, actors=(), bg=None, S=0.5, at=0.0, extra=None):
        tl = Timeline.load(REEL / "voice")
        store = AssetStore(S, [REEL])
        spec = dict(BLANK_SPEC, bg=bg or [{"img": "sets/jin_land/sky.png", "depth": 0.0, "pos": [0, 0], "w": 1080}], actors=list(actors), fx=[dict(fx_entry, at={"dt": at})])
        if extra:
            spec.update(extra)
        sc = Scene(spec, tl, 0.0, 9.0, store, fxreg.FX)
        return sc, Canvas(store, S, C.FPS, 9.0, seed=1), spec

    def test_lines_focus_clear_circle_stays_clean(self):
        e = {"type": "lines_focus", "pos": [540, 900], "clear": [300, 1100, 300]}
        sc, cv, _ = self.scene_with(e)
        sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, at=99.0)
        S = cv.S
        yy, xx = np.mgrid[0:cv.h, 0:cv.w]
        inside = np.hypot(xx - 300 * S, yy - 1100 * S) < 300 * S
        for t in (0.3, 0.8, 1.5):
            f, f0 = frame(sc, cv, t), frame(sc0, cv0, t)
            d = (f != f0).any(axis=2)
            self.assertEqual(int((d & inside).sum()), 0, "clear 圆里画了线")
            self.assertGreater(int(d.sum()), 500)
            self.assertLess(float(d.mean()), 0.25, "线铺得太满（要只在画面边上）")
        self.assertTrue(fxreg.FX["lines_focus"].check({"clear": [1, 2]}))                     # clear 要写 [x, y, r]
        self.assertEqual(fxreg.FX["lines_focus"].check({"clear": 400, "center": [540, 900]}), [])

    def test_lines_focus_only_on_the_outer_part(self):
        sc, cv, _ = self.scene_with({"type": "lines_focus", "pos": [540, 900], "clear": 0})
        sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, at=99.0)
        d = (frame(sc, cv, 1.0) != frame(sc0, cv0, 1.0)).any(axis=2)
        cx, cy = 270, 450
        self.assertEqual(int(d[cy - 80:cy + 80, cx - 80:cx + 80].sum()), 0, "画面中间不该有线")

    def test_sticker_follows_actor_and_tears(self):
        person = {"id": "zb", "img": "chars/zb_hi_laugh.png", "pos": [700, 1500], "h": 820, "enter": "pop",
                  "acts": [{"at": {"dt": 1.0}, "do": "jump"}]}
        e = {"type": "sticker", "name": "anger", "follow": "zb", "attach": "head", "size": 250, "dur": 1.6, "exit": "tear"}
        sc, cv, spec = self.scene_with(e, [person], at=0.6)
        sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, [person], at=99.0)

        def centroid(t):
            d = (frame(sc, cv, t) != frame(sc0, cv0, t)).any(axis=2)
            ys, xs = np.nonzero(d)
            return (xs.mean() / cv.S, ys.mean() / cv.S, int(d.sum())) if len(xs) else None
        c_still, c_jump = centroid(0.9), centroid(1.25)                                       # 跳起来的那一刻贴纸跟着往上
        self.assertLess(c_jump[1], c_still[1] - 20)
        self.assertIsNotNone(centroid(2.35))                                                   # 撕开的两半还在往下落
        self.assertIsNone(centroid(2.9))                                                       # 落完了
        names = [x["name"] for x in spec.get("sfx", [])]
        self.assertEqual(names.count("tear"), 1)                                               # 撕的那一刻的 tear 音效自动排进音效表
        self.assertAlmostEqual(spec["sfx"][0]["at"]["dt"], 0.6 + 1.6, places=3)
        sc.__class__(spec, sc.tl, 0.0, 9.0, sc.store, fxreg.FX)                                # 再建一遍（渲染进程会再跑一次 check）：不重复加
        self.assertEqual([x["name"] for x in spec["sfx"]].count("tear"), 1)
        # 错误：follow 的人物不存在 / 没写 offset / exit 没写 dur
        with self.assertRaises(ValueError):
            self.scene_with(dict(e, follow="nobody"), [person])
        with self.assertRaises(ValueError):
            self.scene_with({"type": "sticker", "name": "anger", "follow": "zb"}, [person])
        with self.assertRaises(ValueError):
            self.scene_with({"type": "sticker", "name": "anger", "pos": [500, 500], "exit": "tear"}, [person])

    def test_sticker_mirrors_with_flipped_actor(self):
        base = {"id": "zb", "img": "chars/zb_hi_laugh.png", "pos": [540, 1500], "h": 820}
        e = {"type": "sticker", "name": "sweat", "follow": "zb", "offset": [200, -600], "size": 200}
        xs = []
        for flip in (False, True):
            sc, cv, _ = self.scene_with(e, [dict(base, flip=flip)])
            sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, [dict(base, flip=flip)], at=99.0)
            d = (frame(sc, cv, 1.0) != frame(sc0, cv0, 1.0)).any(axis=2)
            xs.append(np.nonzero(d)[1].mean() / cv.S)
        self.assertGreater(xs[0], 540 + 100)
        self.assertLess(xs[1], 540 - 100)

    def test_dust_puff_is_a_soft_cloud_that_fades(self):
        e = {"type": "dust", "mode": "puff", "pos": [540, 1400], "size": 200}
        sc, cv, _ = self.scene_with(e)
        sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, at=99.0)
        f, f0 = frame(sc, cv, 0.45).astype(np.int16), frame(sc0, cv0, 0.45).astype(np.int16)
        d = np.abs(f - f0).max(axis=2)
        self.assertGreater(int((d > 8).sum()), 300)
        vals = d[d > 8]
        self.assertGreater(len(np.unique(vals)), 25)                                           # 颜色有很多层次（柔和的颗粒和雾），不是一两块平涂
        self.assertTrue((frame(sc, cv, 1.6) == frame(sc0, cv0, 1.6)).all())                     # 淡没了

    def test_new_sfx_exist_and_stat_star_ding_per_star(self):
        for n in ("frog_croak", "hmph", "tear", "light_up", "star_ding"):
            self.assertTrue((C.SFX_DIR / f"{n}.wav").exists(), n)
        e = {"type": "stat_card", "name": "智伯", "rows": [{"label": "本事", "stars": 5}, {"label": "口才", "stars": 4}, {"label": "好心", "stars": 1}]}
        sc, cv, spec = self.scene_with(e, at=0.5)
        evs = [x for x in spec["sfx"] if x["name"] == "star_ding"]
        self.assertEqual(len(evs), 10)                                                         # 一颗星一声：5 + 4 + 1
        times = sorted(x["at"]["dt"] for x in evs)
        self.assertAlmostEqual(times[0], 0.5 + 0.45 + 0.22, places=3)
        self.assertTrue(all(b > a for a, b in zip(times, times[1:])) or len(set(times)) < len(times))
        sc2, _, spec2 = self.scene_with(dict(e, star_ding=False), at=0.5)
        self.assertEqual([x for x in spec2.get("sfx", []) if x["name"] == "star_ding"], [])

    def test_stat_card_gap_moves_rows_and_their_sounds(self):
        e = {"type": "stat_card", "name": "智伯", "rows": [{"label": "本事", "stars": 5}, {"label": "口才", "stars": 4}, {"label": "好心", "stars": 1}], "gap": 0.3}
        sc, cv, spec = self.scene_with(e, at=1.0)
        rows = sorted((x["at"]["dt"], x["name"]) for x in spec["sfx"] if x["name"].startswith("stat_row"))
        self.assertEqual([n for _, n in rows], ["stat_row_1", "stat_row_2", "stat_row_3"])
        self.assertAlmostEqual(rows[1][0] - rows[0][0], 0.3, places=3)
        sc2, cv2_, spec2 = self.scene_with(dict(e, gap=0.75), at=1.0)
        r2 = sorted(x["at"]["dt"] for x in spec2["sfx"] if x["name"].startswith("stat_row"))
        self.assertAlmostEqual(r2[1] - r2[0], 0.75, places=3)
        # 画面上：gap 小，第三行早早亮起来
        sc3, cv3, _ = self.scene_with(dict(e, gap=0.3, rows=e["rows"]), at=0.0)
        sc4, cv4, _ = self.scene_with(dict(e, gap=0.75, rows=e["rows"]), at=0.0)
        t = 1.5
        self.assertFalse((frame(sc3, cv3, t) == frame(sc4, cv4, t)).all())
        self.assertTrue(fxreg.FX["stat_card"].check(dict(e, gap=0.01)))
        self.assertTrue((C.SFX_DIR / "stat_open.wav").exists())

    def test_splash_layer_back_draws_behind_the_person(self):
        person = {"id": "zb", "img": "chars/zb_hi_laugh.png", "pos": [540, 1700], "h": 900}
        e = {"type": "splash", "pos": [540, 1250], "size": 1.4}
        outs = {}
        for layer in ("front", "back"):
            sc, cv, _ = self.scene_with(dict(e, layer=layer), [person], at=0.0)
            outs[layer] = frame(sc, cv, 0.3)
        sc0, cv0, _ = self.scene_with({"type": "label", "text": "x"}, [person], at=99.0)
        base = frame(sc0, cv0, 0.3)
        self.assertFalse((outs["front"] == outs["back"]).all())
        # 人物挡住的地方：back 保持人物原样，front 被水盖了
        person_area = (outs["front"] != base).any(axis=2) & (outs["back"] == base).all(axis=2)
        self.assertGreater(int(person_area.sum()), 50)
        with self.assertRaises(ValueError):
            self.scene_with(dict(e, layer="middle"), [person])

    def test_name_plate_visible_time_check(self):
        base = {"name": "智伯", "role": "智家老大", "house": "智家", "pos": [150, 380]}
        chk = fxreg.FX["name_plate"].check
        self.assertEqual(chk(dict(base)), [])                                                  # 默认 2.4 秒：落下 0.42 + 能看清 2.0
        self.assertEqual(chk(dict(base, dur=1.95)), [])
        self.assertTrue(chk(dict(base, dur=1.8)))                                              # 能看清 < 1.5 秒：报错
        from fx.cards import PLATE_DUR, PLATE_FALL
        self.assertGreaterEqual(PLATE_DUR - PLATE_FALL, 1.9)

    def test_kaoni_end_stamp(self):
        e = {"type": "kaoni", "options": ["给", "不给"], "answer": 1, "end_stamp": "揭晓"}
        sc, cv, spec = self.scene_with(e)
        sc0, cv0, _ = self.scene_with(dict(e, end_stamp=None))
        d = (frame(sc, cv, 3.9) != frame(sc0, cv0, 3.9)).any(axis=2)
        self.assertGreater(int(d.sum()), 300)                                                  # 盖章那一拍画面里多了个章
        self.assertEqual(int((frame(sc, cv, 3.6) != frame(sc0, cv0, 3.6)).any(axis=2).sum()), 0)   # 章在最后一拍以前不出现
        self.assertTrue([x for x in spec["sfx"] if x["name"] == "pop"])
        self.assertTrue(fxreg.FX["kaoni"].check({"options": ["给"], "end_stamp": "一二三四五六七"}))

    def test_bubble_inner_sways_and_bubble_breathes(self):
        e = {"type": "bubble", "img": "props/bulb.png", "pos": [345, 1050], "w": 820}
        sc, cv, _ = self.scene_with(e)
        sc0, cv0, _ = self.scene_with(dict(e, inner_sway=0))
        a, b = frame(sc, cv, 1.5), frame(sc, cv, 2.4)
        self.assertGreater(int((a != b).any(axis=2).sum()), 300)                               # 泡泡和里面的画不冻住
        a0, b0 = frame(sc0, cv0, 1.5), frame(sc0, cv0, 2.4)
        self.assertLess(int((a0 != b0).any(axis=2).sum()), int((a != b).any(axis=2).sum()) // 2)   # inner_sway=0 基本不动

    def test_title_kicker_uses_episode_name(self):
        self.assertEqual(C.KICKER_FMT.format(no=1, name="三家分晋").rstrip(" ·"), "第 1 集 · 三家分晋")
        self.assertEqual(C.KICKER_FMT.format(no=1, name="").rstrip(" ·"), "第 1 集")
        self.assertNotIn("光爷爷讲通鉴", C.KICKER_FMT)
        from engine.plan import TOP_KEYS, build_plan, PlanError
        self.assertIn("name", TOP_KEYS)
        d = common.fresh("name_glyph")
        sb = json.loads((REEL / "storyboard.json").read_text(encoding="utf-8"))
        sb["name"] = "𠮷𠮷"
        sb["shots"] = [{"id": "a", "from": {"line": 0}, "bg": [{"img": "sets/jin_land/sky.png", "pos": [0, 0], "w": 1080}]}]
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(PlanError) as cm:
            build_plan(d / "storyboard.json")
        self.assertIn("𠮷", str(cm.exception))


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
