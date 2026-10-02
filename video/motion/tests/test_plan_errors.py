"""分镜表有错就直接报错、不出片：素材、字体、背景音乐、锚点、拼错的字段、不存在的特效……所有错一次列完。"""
import copy
import json
import shutil
import unittest
from pathlib import Path

import numpy as np

import common
from engine import audiomix
from engine import consts as C
from engine import sprites
from engine.plan import PlanError, build_plan

BASE = json.loads((common.FEATURE / "storyboard.json").read_text(encoding="utf-8"))
DIR = common.OUT / "bad"


def setUpModule():
    common.ensure_proto_assets()


def write(sb, name="bad.json"):
    DIR.mkdir(parents=True, exist_ok=True)
    p = DIR / name
    p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
    return p


def errors_of(sb):
    try:
        build_plan(write(sb))
    except PlanError as e:
        return e.errors
    return []


def mutate(fn):
    sb = copy.deepcopy(BASE)
    fn(sb)
    return errors_of(sb)


class TestBadStoryboards(unittest.TestCase):
    def test_baseline_is_valid(self):
        self.assertEqual(errors_of(BASE), [])

    def expect(self, fn, needle):
        errs = mutate(fn)
        self.assertTrue(any(needle in e for e in errs), f"想看到「{needle}」，实际：{errs}")

    def test_missing_image(self):
        self.expect(lambda sb: sb["shots"][0]["bg"][0].update(img="sets/nope/none.png"), "找不到素材")

    def test_missing_swap_image(self):
        self.expect(lambda sb: sb["shots"][1]["actors"][0]["acts"][0].update(swap="chars/none.png"), "找不到素材")

    def test_unknown_fx_type(self):
        self.expect(lambda sb: sb["shots"][0]["fx"][0].update(type="no_such_fx_zz"), "没有叫 'no_such_fx_zz' 的特效")

    def test_unknown_transition(self):
        self.expect(lambda sb: sb["shots"][1].update(transition="page_flip"), "没有叫 'page_flip' 的转场")

    def test_typo_in_shot_key(self):
        self.expect(lambda sb: sb["shots"][0].update(camara=[]), "不认识的字段")

    def test_typo_in_actor_key(self):
        self.expect(lambda sb: sb["shots"][0]["actors"][0].update(hight=500), "不认识的字段")

    def test_unknown_top_level_key(self):
        self.expect(lambda sb: sb.update(shot=[]), "顶层有不认识的字段")

    def test_anchor_line_out_of_range(self):
        self.expect(lambda sb: sb["shots"][0]["fx"][0].update(at={"line": 99}), "只有 6 句")

    def test_anchor_word_not_found(self):
        self.expect(lambda sb: sb["shots"][1]["actors"][0]["acts"][0].update(at={"line": 1, "word": "根本没有"}), "找不到")

    def test_hardcoded_seconds_rejected(self):
        self.expect(lambda sb: sb["shots"][0]["fx"][0].update(at=3.5), "不能写死秒数")

    def test_from_must_increase(self):
        self.expect(lambda sb: sb["shots"][2].update({"from": {"line": 0}}), "不在")

    def test_sticker_needs_pos(self):
        self.expect(lambda sb: sb["shots"][0]["fx"][0].pop("pos"), "缺 pos")

    def test_unknown_camera_move(self):
        self.expect(lambda sb: sb["shots"][0]["camera"].append({"move": "spin"}), "不认识的镜头运动")

    def test_unknown_grade(self):
        self.expect(lambda sb: sb["shots"][0].update(grade="sepia"), "grade")

    def test_unknown_sfx_name(self):
        self.expect(lambda sb: sb["shots"][0].update(sfx=[{"name": "boom"}]), "找不到音效")

    def test_missing_glyph(self):
        self.expect(lambda sb: sb.update(title=["好😀"]), "两种字体里都没有")

    def test_shot_selection_unknown_id(self):
        with self.assertRaises(PlanError) as cm:
            build_plan(write(BASE), only=["f1", "zz"])
        self.assertIn("zz", str(cm.exception))

    def test_all_errors_listed_at_once(self):
        def three(sb):
            sb["shots"][0]["bg"][0]["img"] = "sets/nope/a.png"
            sb["shots"][1]["actors"][0]["img"] = "chars/none.png"
            sb["shots"][3]["fx"] = [{"type": "no_such_fx_zz"}]
        errs = mutate(three)
        self.assertGreaterEqual(len(errs), 3, errs)

    def test_missing_font_is_an_error_not_a_fallback(self):
        saved = dict(sprites._FONT_FILES)
        try:
            sprites._FONT_FILES["title"] = Path("C:/definitely/not/here/ZCOOL.ttf")
            sprites._pil_fonts.clear()
            errs = errors_of(BASE)
            self.assertTrue(any("找不到字体" in e for e in errs), errs)
        finally:
            sprites._FONT_FILES.update(saved)

    def test_missing_bgm_is_an_error(self):
        saved = C.BGM
        try:
            C.BGM = Path("C:/definitely/not/here/bgm.mp3")
            errs = errors_of(BASE)
            self.assertTrue(any("找不到背景音乐" in e for e in errs), errs)
        finally:
            C.BGM = saved

    def test_missing_voice_timeline(self):
        self.expect(lambda sb: sb.update(voice="video/out/nowhere"), "找不到配音时间线")


class TestPerEpisodeBgm(unittest.TestCase):
    """分镜表顶层 "bgm"（可选）：每集换背景音乐。不写就用系列默认的 C.BGM（tj01、tj02 不写，输出不变）。"""

    @classmethod
    def setUpClass(cls):
        common.ensure_proto_assets()
        cls.dir = common.OUT / "bgm_case"
        shutil.rmtree(cls.dir, ignore_errors=True)
        shutil.copytree(common.PROTO, cls.dir, ignore=shutil.ignore_patterns("voice"))        # 配音路径写的是仓库根目录相对路径，不用拷
        t = np.arange(25 * audiomix.SR) / audiomix.SR
        for name, f in (("tone_low.wav", 5000.0), ("tone_high.wav", 8000.0)):
            x = (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)
            audiomix.write_wav(cls.dir / name, np.stack([x, x], axis=1))
        cls.sb = json.loads((common.PROTO / "storyboard.json").read_text(encoding="utf-8"))

    def plan_with(self, **top):
        sb = dict(self.sb, **top)
        p = self.dir / "storyboard.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        return build_plan(p)

    def band(self, pcm, f, half=4.0):
        """整条音轨在 f ± half 赫兹里的能量。"""
        x = pcm.mean(axis=1)
        sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
        fr = np.fft.rfftfreq(len(x), 1 / audiomix.SR)
        return float(sp[(fr > f - half) & (fr < f + half)].sum())

    def test_default_when_not_written(self):
        self.assertNotIn("bgm", self.sb)
        self.assertEqual(self.plan_with().bgm, C.BGM)

    def test_relative_to_repo_root_and_to_storyboard_dir_and_absolute(self):
        self.assertEqual(self.plan_with(bgm="video/motion/sfx/pop.wav").bgm, C.ROOT / "video/motion/sfx/pop.wav")
        self.assertEqual(self.plan_with(bgm="tone_high.wav").bgm, self.dir / "tone_high.wav")
        self.assertEqual(self.plan_with(bgm=str(self.dir / "tone_low.wav")).bgm, self.dir / "tone_low.wav")

    def test_missing_file_is_an_error_naming_the_path(self):
        with self.assertRaises(PlanError) as cm:
            self.plan_with(bgm="video/assets/audio/bgm/nope.mp3")
        self.assertTrue(any("找不到背景音乐" in e and "nope.mp3" in e for e in cm.exception.errors), cm.exception.errors)

    def test_directory_or_wrong_type_is_an_error(self):
        for bad in ("video/assets/audio", "", 5, ["a.mp3"]):
            with self.assertRaises(PlanError, msg=repr(bad)):
                self.plan_with(bgm=bad)

    def test_mix_uses_the_chosen_file_and_report_says_which(self):
        low, high = self.plan_with(bgm="tone_low.wav"), self.plan_with(bgm="tone_high.wav")
        (pl, il), (ph, ih) = audiomix.build(low), audiomix.build(high)
        self.assertEqual(il["bgm"], str(self.dir / "tone_low.wav"))
        self.assertEqual(ih["bgm"], str(self.dir / "tone_high.wav"))
        for f, hi_mix in ((8000.0, ph), (5000.0, pl)):                 # 换了音乐，对应频率的能量比另一首高得多（用 5 / 8 kHz 的纯音：人声在这里几乎没有能量）
            other = pl if hi_mix is ph else ph
            self.assertGreater(10 * np.log10(self.band(hi_mix, f) / self.band(other, f)), 10.0, f)
        self.assertEqual(audiomix.build(self.plan_with())[1]["bgm"], str(C.BGM))          # 不写 = 默认那首


class TestPlanShape(unittest.TestCase):
    def test_frame_ranges_and_transitions(self):
        plan = build_plan(common.PROTO / "storyboard.json")
        ranges = [(s.id, s.f0, s.f1) for s in plan.shots]
        # 每镜到下一镜的 from 为止，第一镜从 0 起，最后一镜到时间线结束（17.2 秒 = 516 帧）
        self.assertEqual(ranges, [("1-1", 0, 148), ("1-2", 148, 219), ("1-3", 219, 315), ("1-4", 315, 396), ("1-5", 396, 459), ("1-6", 459, 516)])
        plan = build_plan(common.FEATURE / "storyboard.json")
        f2, f3 = plan.shots[1], plan.shots[2]
        self.assertEqual((f2.trans["a"], f2.trans["b"], f2.pre), (6, 6, 6))            # 0.4 秒 = 12 帧，切点前后各 6
        self.assertEqual(plan.shots[0].post, 6)                                        # 前一镜多渲切点之后的 6 帧
        self.assertEqual((f3.trans["a"], f3.trans["b"]), (4, 5))                       # 0.3 秒 = 9 帧
        self.assertEqual(plan.shots[3].trans, None)                                    # cut

    def test_selection_and_ranges(self):
        plan = build_plan(common.PROTO / "storyboard.json", only=["1-4", "1-2"])
        self.assertEqual([s.id for s in plan.selected], ["1-2", "1-4"])                # 按分镜表顺序
        self.assertEqual(plan.out_frames, (219 - 148) + (396 - 315))

    def test_cache_key_depends_on_content_and_scale(self):
        a = build_plan(common.PROTO / "storyboard.json")
        b = build_plan(common.PROTO / "storyboard.json")
        c = build_plan(common.PROTO / "storyboard.json", scale=0.5)
        self.assertEqual([s.key for s in a.shots], [s.key for s in b.shots])
        self.assertNotEqual(a.shots[0].key, c.shots[0].key)
        sb = json.loads((common.PROTO / "storyboard.json").read_text(encoding="utf-8"))
        sb["shots"][2]["camera"][0]["amount"] = 0.07
        d = common.OUT / "p17copy"
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(common.PROTO, d, ignore=shutil.ignore_patterns("voice"))
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        e = build_plan(d / "storyboard.json")
        self.assertEqual([s.key == t.key for s, t in zip(a.shots, e.shots)], [True, True, False, True, True, True])


if __name__ == "__main__":
    common.ensure_proto_assets()
    unittest.main()
