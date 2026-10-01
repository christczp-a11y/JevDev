"""storyboard_check.py 的测试（不要显卡、不要网络、不要 Jev key）。
数据是合成的（check_case/make_case.py）：素材用 --assets-root 指到测试时生成的纯色小图 + 测试登记表，特效用 --no-plugins，
所以真实素材怎么增减、特效包做到哪一步，这些测试都不受影响。"""
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from types import SimpleNamespace as NS

import common
import faces as facelib
import storyboard_check as SC

TESTS = common.TESTS
CASE = TESTS / "check_case"
OUT = common.OUT / "check_case"
GOOD = TESTS / "good_storyboard.json"
EXPECT = json.loads((TESTS / "check_expect.json").read_text(encoding="utf-8"))
BAD = sorted(TESTS.glob("bad_*.json"))
TAGS = ["格式", "锚点", "长度", "频率", "静止", "特效", "闪烁", "安全区", "素材", "放大", "朝向", "人名牌", "翻转", "压脸", "集中线", "速度线", "字幕", "遮挡", "停留"]

_spec = importlib.util.spec_from_file_location("make_case", CASE / "make_case.py")
make_case = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_case)


def setUpModule():
    make_case.make_assets(OUT)


def check(path, **kw):
    """进程内跑一遍检查：返回 (报告, 统计)。"""
    _, _, rep, stats = SC.run(str(path), registry=OUT / "REGISTRY.md", no_plugins=True, assets_root=OUT / "assets", **kw)
    return rep, stats


def cli(*args):
    p = subprocess.run([sys.executable, str(common.MOTION / "storyboard_check.py"), *[str(a) for a in args]],
                       capture_output=True, text=True, encoding="utf-8", env=common.ENV, cwd=common.ROOT)
    return p.returncode, p.stdout + p.stderr


def text(rep):
    return "\n".join(SC.fmt(f, rep.times) for f in rep.errors)


class TestGood(unittest.TestCase):
    def test_correct_storyboard_passes_clean(self):
        rep, stats = check(GOOD)
        self.assertEqual(rep.errors, [], text(rep))
        self.assertEqual(rep.warnings, [], [SC.fmt(w) for w in rep.warnings])
        self.assertTrue(18 <= stats["rate_per_min"] <= 24, stats)

    def test_cli_exit_code_0(self):
        rc, out = cli(GOOD, "--assets-root", OUT / "assets", "--registry", OUT / "REGISTRY.md", "--no-plugins")
        self.assertEqual(rc, 0, out)
        self.assertIn("结果：通过", out)


class TestBad(unittest.TestCase):
    def test_every_bad_file_has_an_expectation(self):
        self.assertEqual({f.name for f in BAD}, set(EXPECT))
        self.assertGreaterEqual(len(BAD), 30)

    def test_each_bad_storyboard_is_rejected_with_the_right_message(self):
        for f in BAD:
            with self.subTest(f.name):
                rep, _ = check(f)
                self.assertTrue(rep.errors, f"{f.name} 应该报错，却通过了")
                self.assertTrue(any(EXPECT[f.name] in SC.fmt(e) for e in rep.errors), f"想看到「{EXPECT[f.name]}」，实际：\n{text(rep)}")

    def test_every_kind_of_check_has_a_bad_example(self):
        tags = set()
        for f in BAD:
            rep, _ = check(f)
            tags |= {e["tag"] for e in rep.errors}
        self.assertEqual(sorted(set(TAGS) - tags), [], "这些检查项没有坏样例")

    def test_a_single_mutation_does_not_cascade_into_unrelated_errors(self):
        """精度：单点改动的坏样例，只该报和这一处有关的错（下面这些是一处改动天然会连带出别的错的，不查）。"""
        chained = {"bad_long_shots_many", "bad_rate_low", "bad_rate_high", "bad_fast_cuts", "bad_shot_too_long", "bad_shot_too_short", "bad_knowledge_fast", "bad_flash_burst"}
        for f in BAD:
            if f.stem in chained:
                continue
            with self.subTest(f.name):
                rep, _ = check(f)
                tags = {e["tag"] for e in rep.errors}
                self.assertLessEqual(len(tags), 1, f"{f.name} 报了不止一类错：\n{text(rep)}")

    def test_cli_exit_code_1_and_lists_shot_ids(self):
        rc, out = cli(TESTS / "bad_static.json", "--assets-root", OUT / "assets", "--registry", OUT / "REGISTRY.md", "--no-plugins")
        self.assertEqual(rc, 1, out)
        self.assertIn("镜头 s10", out)
        self.assertIn("不通过", out)

    def test_all_errors_are_listed_at_once(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        sb["shots"][3]["fx"][0]["at"] = {"line": 99}
        sb["shots"][9]["camera"] = [{"move": "push", "amount": 0}]
        sb["shots"][12]["bg"][0]["img"] = "sets/nope/none.png"
        sb["shots"][5]["fx"][0]["type"] = "sparkel"
        p = OUT / "three_errors.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertGreaterEqual(len(rep.errors), 4, text(rep))
        self.assertEqual({"锚点", "静止", "素材", "特效"} - {e["tag"] for e in rep.errors}, set())


class TestNewRules(unittest.TestCase):
    """PITFALLS M1、M2、M4 那一轮补的检查里，坏样例测不到的例外和边界。"""

    def test_flip_exemptions(self):
        from types import SimpleNamespace as NS

        class Rep:
            errors = []

            def err(self, *a):
                self.errors.append(a)
        ok = [NS(rel="chars/sgm_hi_point.png", file=True, row={"note": "", "owner": "司马光 `sgm_`"}),          # 司马光（圆领）
              NS(rel="chars/zxu_shadow.png", file=True, row={"note": "", "owner": "智宣子 `zxu_`"}),          # 皮影
              NS(rel="chars/zb_stand.png", file=True, row={"note": "侧面立像，可翻转", "owner": "智伯 `zb_`"}),  # 备注写了可翻转
              NS(rel="chars/school_desk.png", file=True, row={"note": "课桌", "owner": "现代课桌（道具）"}),   # 物件
              NS(rel="props/flag_zhi.png", file=True, row={"note": "", "owner": "道具"}),                    # 不在 chars/
              NS(rel="chars/zb_x.png", file=False, row={})]                                                  # 图找不到：素材那一项去报
        for r in ok:
            rp = Rep()
            SC.check_flip(rp, "s1", "actors[0]", r, "谁")
            self.assertEqual(rp.errors, [], r.rel)
        rp = Rep()
        SC.check_flip(rp, "s1", "actors[0]", NS(rel="chars/zb_stand_hi.png", file=True, row={"note": "高清半身", "owner": "智伯 `zb_`"}), "智伯")
        self.assertEqual(len(rp.errors), 1)

    def test_sticker_that_follows_a_person_may_cover_the_face(self):
        rep, _ = check(GOOD)
        self.assertEqual([e for e in rep.errors if e["tag"] == "压脸"], [])       # s12 的 follow 贴纸就在韩康子脸上

    def test_focus_circle_must_cover_the_subject_not_just_any_face(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s09 = next(s for s in sb["shots"] if s["id"] == "s09")                    # 赵襄子（左）+ 智伯（右，比较大）：主体是智伯
        s09["fx"] = [{"type": "lines_focus", "pos": [330, 1180], "clear": 250, "at": {"line": 8, "dt": 0.3}}]      # 圈在赵襄子脸上，没盖住智伯
        p = OUT / "focus_subject.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertTrue(any(e["tag"] == "集中线" and "智伯" in e["msg"] for e in rep.errors), text(rep))
        s09["fx"][0]["pos"] = [760, 1180]
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] == "集中线"], [], text(rep))

    def test_focus_clear_can_be_a_circle_with_its_own_centre(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s21 = next(s for s in sb["shots"] if s["id"] == "s21")
        focus = s21["fx"][-1]
        focus.pop("pos")
        focus["clear"] = [540, 1200, 320]                                           # [x, y, r]
        p = OUT / "focus_circle.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] == "集中线"], [], text(rep))
        focus["clear"] = [540, 300, 320]
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertTrue(any(e["tag"] == "集中线" for e in rep.errors), text(rep))

    def test_plate_time_boundary(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s02 = next(s for s in sb["shots"] if s["id"] == "s02")
        plate = next(f for f in s02["fx"] if f["type"] == "name_plate")
        plate["dur"] = 1.92 + 0.0                                                   # 1.92 - 0.42 = 1.5 秒：刚好够
        p = OUT / "plate_edge.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if "只看得清" in e["msg"]], [], text(rep))
        plate["dur"] = 1.8
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertTrue(any("只看得清" in e["msg"] for e in rep.errors), text(rep))


class TestSubtitleAndCover(unittest.TestCase):
    """M6、M8：没有台词的时段不查字幕区；盖得少 / 盖在后面的不算。"""

    def _case(self, name, feet_y_in_line, extra_fg=None):
        """三个镜头：第 0 句说话、第 1 句是动作（没有台词）、第 2 句说话；智伯站在 feet_y 的位置，只出现在 feet_y_in_line 指定的那一镜里。"""
        vd = OUT / f"{name}_voice"
        vd.mkdir(parents=True, exist_ok=True)
        lines = [{"t0": 0.3, "t1": 2.8, "who": "旁白", "text": "智伯很生气！", "audio": None, "voiced_end": 2.0, "i": 0},
                 {"t0": 3.1, "t1": 5.6, "who": "动作", "text": "", "audio": None, "i": 1},
                 {"t0": 5.9, "t1": 8.4, "who": "旁白", "text": "智伯想了想。", "audio": None, "voiced_end": 2.0, "i": 2}]
        (vd / "timeline.json").write_text(json.dumps({"duration": 8.7, "lines": lines}, ensure_ascii=False), encoding="utf-8")
        bg = [{"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080}]

        def shot(sid, line, low):
            a = [{"id": "zb", "who": "智伯", "img": "chars/zb_angry.png", "pos": [540, 1800 if low else 1560], "h": 446}]
            return {"id": sid, "from": {"line": line}, "bg": bg, "actors": a, "fx": [], **({"fg": extra_fg} if extra_fg and low else {})}
        sb = {"episode": "tj01", "no": 1, "title": ["甲"], "voice": str(vd.relative_to(common.ROOT)).replace("\\", "/"),
              "shots": [shot("a", 0, feet_y_in_line == 0), shot("b", 1, feet_y_in_line == 1), shot("c", 2, feet_y_in_line == 2)]}
        p = OUT / f"{name}.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        return rep

    def test_face_in_subtitle_zone_only_matters_while_a_line_is_spoken(self):
        quiet = self._case("sub_quiet", 1)                                           # 脸低、但这一镜是动作（没有台词）
        self.assertEqual([e for e in quiet.errors if e["tag"] in ("字幕", "安全区")], [], text(quiet))
        loud = self._case("sub_loud", 2)                                             # 同一个位置，第 2 句在说话
        self.assertTrue(any(e["tag"] == "字幕" and e["shot"] == "c" for e in loud.errors), text(loud))
        self.assertFalse(any(e["tag"] == "字幕" and e["shot"] == "b" for e in loud.errors))

    def test_face_below_1620_is_always_an_error(self):
        sb = json.loads((TESTS / "bad_subtitle_covers_face.json").read_text(encoding="utf-8"))
        next(s for s in sb["shots"] if s["id"] == "s10")["actors"][0]["pos"] = [540, 2000]       # 脸框下沿 > 1620：平台遮挡区
        p = OUT / "face_below.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertTrue(any(e["tag"] == "安全区" and "1620" in e["msg"] for e in rep.errors), text(rep))

    def test_small_icon_beside_or_behind_the_lead_is_fine(self):
        rep, _ = check(GOOD)                                                          # good 里 s14、s19 各有一个 props 图标，没盖住主角
        self.assertEqual([e for e in rep.errors if e["tag"] == "遮挡"], [])

    def test_icons_each_small_but_together_over_20_percent(self):
        rep, _ = check(TESTS / "bad_cover_icons_on_lead.json")
        e = next(e for e in rep.errors if e["tag"] == "遮挡")
        self.assertIn("超过 20%", e["msg"])
        self.assertIn("面积最大", e["msg"])

    def test_speaking_person_counts_as_the_lead_even_if_small(self):
        rep, _ = check(TESTS / "bad_cover_speaker.json")
        self.assertTrue(any(e["tag"] == "遮挡" and "正在说话" in e["msg"] and "韩康子" in e["msg"] for e in rep.errors), text(rep))

    def test_big_foreground_prop_is_scenery_not_an_icon(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s10 = next(s for s in sb["shots"] if s["id"] == "s10")
        s10["fg"] = [{"img": "props/map_silk.png", "depth": 1.0, "pos": [540, 1300], "anchor": [0.5, 0.5], "w": 900}]       # 单张就盖住身体一大半：战车、浪、地图卷这类场景大件
        p = OUT / "cover_scenery.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] == "遮挡"], [], text(rep))

    def test_set_front_marked_in_note_or_registry_is_not_an_effect(self):
        sb = json.loads((TESTS / "bad_cover_icons_on_lead.json").read_text(encoding="utf-8"))
        s10 = next(s for s in sb["shots"] if s["id"] == "s10")
        for ic in s10["fg"]:
            ic["note"] = "布景前层：战车前栏"                                          # ② 这一镜里写 note
        p = OUT / "cover_note.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] == "遮挡"], [], text(rep))
        # ① 登记表备注写「布景前层」：整集都认（图层上什么都不用写）
        reg = (OUT / "REGISTRY.md").read_text(encoding="utf-8").replace("`props/cup_lacquer.png` | 道具 | 正面 | 513×257 | 无 | 定稿 | 测试图", "`props/cup_lacquer.png` | 道具 | 正面 | 513×257 | 无 | 定稿 | 布景前层（测试）", 1)
        self.assertIn("布景前层（测试）", reg)
        pr = OUT / "REGISTRY_setfront.md"
        pr.write_text(reg, encoding="utf-8")
        plain = TESTS / "bad_cover_icons_on_lead.json"
        _, _, rp, _ = SC.run(str(plain), registry=pr, no_plugins=True, assets_root=OUT / "assets")
        self.assertEqual([e for e in rp.errors if e["tag"] == "遮挡"], [], text(rp))

    def test_transparent_part_of_an_icon_does_not_count(self):
        from PIL import Image
        f = OUT / "assets" / "props" / "sliver.png"                                   # 230×115，只有左上角一个 20×20 的小方块不透明
        im = Image.new("RGBA", (230, 115), (0, 0, 0, 0))
        im.paste((200, 100, 80, 255), (0, 0, 20, 20))
        im.save(f)
        sb = json.loads((TESTS / "bad_cover_icons_on_lead.json").read_text(encoding="utf-8"))
        s10 = next(s for s in sb["shots"] if s["id"] == "s10")
        for ic in s10["fg"]:
            ic["img"] = "props/sliver.png"                                            # 同样的 6 个位置，同样的框，但几乎全是透明的
        p = OUT / "cover_sliver.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] == "遮挡"], [], text(rep))

    def test_follow_sticker_and_background_prop_do_not_count(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s10 = next(s for s in sb["shots"] if s["id"] == "s10")
        s10["fx"].append({"type": "sticker", "text": "汗", "follow": "zb", "offset": [0, -300], "at": {"line": 9, "dt": 0.5}, "size": 600})     # 挂在人物身上：不算
        s10["bg"] = s10["bg"] + [{"img": "props/cup_lacquer.png", "depth": 1.0, "pos": [540, 1300], "anchor": [0.5, 0.5], "w": 700}]       # bg 在人物后面：不算
        p = OUT / "cover_exempt.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual([e for e in rep.errors if e["tag"] in ("遮挡", "压脸")], [], text(rep))


class TestLineFx(unittest.TestCase):
    """M2 再犯：lines_speed / lines_radial 整屏线条画在人物前面、区域盖住脸 = 错，只盖身体 = 警告；画在人物后面、区域避开的不报。
    用 s10（智伯一个人，脚在 y 1560，脸框约 y 1116–1295，推镜头后约 1123–1312，第 9 句「智伯很生气！」）当试验场。"""
    AT = {"line": 9, "dt": 0.2}

    def _run(self, name, *fxs, shot="s10"):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        next(s for s in sb["shots"] if s["id"] == shot)["fx"] += list(fxs)
        p = OUT / f"{name}.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        return check(p)[0]

    @staticmethod
    def _hits(rep):
        return [e for e in rep.errors if e["tag"] == "速度线"], [w for w in rep.warnings if w["tag"] == "速度线"]

    def test_speed_lines_across_the_face_is_an_error(self):
        rep, _ = check(TESTS / "bad_speed_lines_on_face.json")
        errs, warns = self._hits(rep)
        self.assertEqual([e["shot"] for e in errs], ["s10"], text(rep))
        self.assertIn("智伯", errs[0]["msg"])
        self.assertIn("lines_speed", errs[0]["msg"])
        self.assertIn("layer", errs[0]["msg"])
        self.assertEqual(warns, [])                                                    # 脸错了就不再重复报身体
        self.assertEqual([e for e in rep.errors if e["tag"] != "速度线"], [], text(rep))

    def test_area_that_stays_clear_of_the_people_is_not_reported(self):
        for name, fx in [("speed_above", {"type": "lines_speed", "dir": "left", "y0": 380, "y1": 1000, "at": self.AT}),             # 横带在头顶以上
                         ("speed_below", {"type": "lines_speed", "dir": "left", "y0": 1700, "y1": 1800, "at": self.AT})]:                      # 横带在脚底以下
            with self.subTest(name):
                rep = self._run(name, fx)
                self.assertEqual(self._hits(rep), ([], []), text(rep))
                self.assertEqual(rep.errors, [], text(rep))

    def test_lines_drawn_behind_the_people_are_not_reported(self):
        rep = self._run("speed_back", {"type": "lines_speed", "dir": "left", "layer": "back", "at": self.AT})      # 同 bad_speed_lines_on_face，只多写 layer back
        self.assertEqual(self._hits(rep), ([], []), text(rep))
        self.assertEqual(rep.errors, [], text(rep))
        rep = self._run("speed_front_explicit", {"type": "lines_speed", "dir": "left", "layer": "front", "at": self.AT})   # 写 front 和不写一样
        self.assertEqual(len(self._hits(rep)[0]), 1, text(rep))

    def test_only_the_body_covered_is_a_warning(self):
        rep = self._run("speed_legs", {"type": "lines_speed", "dir": "right", "y0": 1340, "y1": 1500, "at": self.AT})        # 横带在脸框下沿以下、盖住腿
        errs, warns = self._hits(rep)
        self.assertEqual(errs, [], text(rep))
        self.assertEqual(len(warns), 1)
        self.assertIn("身体", warns[0]["msg"])
        self.assertEqual(rep.errors, [], text(rep))

    def test_radial_lines_centred_on_the_face_only_cross_the_body(self):
        rep = self._run("radial_on_face", {"type": "lines_radial", "pos": [540, 1205], "at": self.AT})                       # 脸整个在圆心 210 像素以内
        errs, warns = self._hits(rep)
        self.assertEqual(errs, [], text(rep))
        self.assertEqual(len(warns), 1)
        self.assertIn("lines_radial", warns[0]["msg"])
        rep = self._run("radial_off_face", {"type": "lines_radial", "pos": [540, 300], "at": self.AT})                       # 圆心在头顶上很远的地方：脸在圆外
        errs, _ = self._hits(rep)
        self.assertEqual(len(errs), 1, text(rep))
        self.assertIn("放射速度线", errs[0]["msg"])

    def test_every_person_counts_not_only_the_subject(self):
        rep = self._run("radial_two_people", {"type": "lines_radial", "pos": [760, 1205], "at": {"line": 8, "dt": 0.2}}, shot="s09")    # 圆心在智伯（右，主体）的脸上；赵襄子（左）的脸在圆外
        errs, _ = self._hits(rep)
        self.assertEqual(len(errs), 1, text(rep))
        self.assertIn("赵襄子", errs[0]["msg"])

    def test_focus_lines_keep_their_own_check_and_bad_params_do_not_crash(self):
        rep = self._run("focus_and_bad_params", {"type": "lines_speed", "y0": "高", "at": self.AT}, {"type": "lines_radial", "pos": [540], "at": self.AT})
        self.assertEqual(self._hits(rep), ([], []), text(rep))
        rep, _ = check(GOOD)                                                           # good 里的 lines_focus（有 clear）不归 [速度线] 管
        self.assertEqual(self._hits(rep), ([], []))


class TestFaceBoxes(unittest.TestCase):
    """M6 再犯、待补 18：脸框按图定（faces.json → 自动估 → 旧默认 40%）。用 s10（智伯一个人，说话）当试验场：把他放低，脸的上 40% 还在字幕区上面，但额头到下巴的整张脸进了字幕区。
    阈值：字幕区盖进脸框的高度 ≥ 脸框高的 30% = 错，不到 = 警告；[安全区] 脸框左 / 右出界 ≥ 脸框宽的 10% = 错，不到 = 警告。"""
    BOX = [0.2, 0.8, 0.2, 0.6]                         # 戴斗笠那种：脸在图高的 20%–60%（脸框高约 187 像素）

    @classmethod
    def setUpClass(cls):
        cls.root = OUT / "assets_faces"                # 带 faces.json 的素材目录：从公共的测试素材复制一份，不弄脏别的测试
        if cls.root.exists():
            shutil.rmtree(cls.root)
        shutil.copytree(OUT / "assets", cls.root)

    def _run(self, faces_json=None, x=540, y=1620, flip=False):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s10 = next(s for s in sb["shots"] if s["id"] == "s10")
        s10["actors"][0]["pos"] = [x, y]
        s10.pop("camera", None)
        if flip:
            s10["actors"][0]["flip"] = True
        p = OUT / "face_case.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        fj = self.root / "faces.json"
        if faces_json is None:
            if fj.exists():
                fj.unlink()
        else:
            fj.write_text(json.dumps(faces_json), encoding="utf-8")
        _, _, rep, _ = SC.run(str(p), registry=OUT / "REGISTRY.md", no_plugins=True, assets_root=self.root)
        return rep

    @staticmethod
    def _s10(rep, tag, kind="errors"):
        return [f for f in getattr(rep, kind) if f["tag"] == tag and f["shot"] == "s10"]

    def test_chin_in_the_subtitle_zone_is_caught_only_with_the_real_face_box(self):
        rep = self._run(None, y=1640)                                                  # 旧默认：脸框在字幕区只进去 19% 以内（下巴），不到 30%
        self.assertEqual(self._s10(rep, "字幕"), [], text(rep))
        rep = self._run({"chars/zb_angry.png": self.BOX}, y=1640)                      # 这张图的脸到 60%：字幕区盖进脸框高的 46%，到嘴了
        errs = self._s10(rep, "字幕")
        self.assertEqual(len(errs), 1, text(rep))
        self.assertIn("智伯", errs[0]["msg"])
        self.assertIn("46%", errs[0]["msg"])
        self.assertEqual([e for e in rep.errors if e["tag"] not in ("字幕",)], [], text(rep))
        self.assertTrue(any("faces.json 1" in i for i in rep.info), rep.info)

    def test_subtitle_zone_threshold_is_30_percent_of_the_face_height(self):
        rep = self._run({"chars/zb_angry.png": self.BOX}, y=1600)                      # 盖进 24%：只是下巴 / 胡子尖
        self.assertEqual(self._s10(rep, "字幕"), [], text(rep))
        warns = self._s10(rep, "字幕", "warnings")
        self.assertEqual(len(warns), 1, [SC.fmt(w) for w in rep.warnings])
        self.assertIn("24%", warns[0]["msg"])
        self.assertIn("不到 30%", warns[0]["msg"])
        rep = self._run({"chars/zb_angry.png": self.BOX}, y=1620)                      # 盖进 35%：到嘴了
        self.assertEqual(len(self._s10(rep, "字幕")), 1, text(rep))
        self.assertEqual(self._s10(rep, "字幕", "warnings"), [])                       # 错了就不再重复报警告
        rep = self._run(None, y=1500)                                                  # 完全不进字幕区：什么都不报
        self.assertEqual((self._s10(rep, "字幕"), self._s10(rep, "字幕", "warnings")), ([], []))

    def test_safe_zone_side_overshoot_under_10_percent_of_the_face_width_is_a_warning(self):
        rep = self._run(None, x=175, y=1500)                                           # 脸框左边 69 < 80：出界 11 像素 = 脸框宽的 6%，耳朵擦边
        self.assertEqual(self._s10(rep, "安全区"), [], text(rep))
        warns = self._s10(rep, "安全区", "warnings")
        self.assertEqual(len(warns), 1, [SC.fmt(w) for w in rep.warnings])
        self.assertIn("不到 10%", warns[0]["msg"])
        rep = self._run(None, x=160, y=1500)                                           # 出界 ≥ 10%
        self.assertEqual(len(self._s10(rep, "安全区")), 1, text(rep))
        self.assertEqual(self._s10(rep, "安全区", "warnings"), [])
        rep = self._run(None, x=880, y=1500)                                           # 右边也一样
        errs = self._s10(rep, "安全区")
        self.assertEqual(len(errs), 1, text(rep))
        self.assertIn("右边", errs[0]["msg"])
        rep = self._run(None, x=300, y=1500)
        self.assertEqual((self._s10(rep, "安全区"), self._s10(rep, "安全区", "warnings")), ([], []))

    def test_without_faces_json_and_without_skin_the_old_default_applies(self):
        rep = self._run(None)
        self.assertEqual(rep.errors, [], text(rep))
        self.assertTrue(any("旧默认" in i for i in rep.info), rep.info)

    def test_lookup_order_json_then_auto_then_default(self):
        from PIL import Image, ImageDraw
        root = OUT / "faces_lookup"
        (root / "chars").mkdir(parents=True, exist_ok=True)
        im = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle([60, 160, 140, 400], fill=(40, 60, 90, 255))                      # 深蓝的袍子
        d.ellipse([50, 30, 150, 130], fill=(255, 200, 160, 255))                      # 头：肤色
        d.ellipse([20, 270, 80, 330], fill=(255, 200, 160, 255))                      # 手：肤色，在下面、而且不小
        im.save(root / "chars" / "head.png")
        Image.new("RGBA", (200, 400), (40, 60, 90, 255)).save(root / "chars" / "blue.png")
        (root / "faces.json").write_text(json.dumps({"chars/head.png": [0.1, 0.9, 0.0, 0.5]}), encoding="utf-8")
        t = facelib.FaceTable(root)
        self.assertEqual(t.lookup(root / "chars" / "head.png", "chars/head.png"), ((0.1, 0.9, 0.0, 0.5), "json"))
        (root / "faces.json").unlink()
        box, src = facelib.FaceTable(root).lookup(root / "chars" / "head.png", "chars/head.png")
        self.assertEqual(src, "auto")
        self.assertTrue(0.15 <= box[0] <= 0.30 and 0.70 <= box[1] <= 0.85, box)       # 头在 x 0.25–0.75
        self.assertTrue(box[2] < 0.12 and 0.30 <= box[3] <= 0.45, box)                # 取最上面那团（头），不是手；往下多留一点给下巴
        self.assertEqual(facelib.FaceTable(root).lookup(root / "chars" / "blue.png", "chars/blue.png"), (facelib.DEFAULT, "default"))

    def test_flipped_person_gets_a_mirrored_face_box(self):
        ref = NS(face=(0.1, 0.5, 0.2, 0.6))
        self.assertEqual(SC.face_on_screen(ref, False, 0.0, 0.0, 1000.0, 1000.0), (100.0, 200.0, 500.0, 600.0))
        self.assertEqual(SC.face_on_screen(ref, True, 0.0, 0.0, 1000.0, 1000.0), (500.0, 200.0, 900.0, 600.0))
        self.assertEqual(facelib.mirrored(facelib.DEFAULT), facelib.DEFAULT)           # 旧默认左右对称，翻不翻一样

    def test_face_box_must_be_inside_the_picture(self):
        for bad in ([0.5, 0.2, 0.0, 0.4], [0.1, 0.9, 0.5, 0.4], [0.1, 0.9, 0.0, 1.2], [0.1, 0.9, 0.0], "x"):
            with self.subTest(bad):
                (self.root / "faces.json").write_text(json.dumps({"chars/zb_angry.png": bad}), encoding="utf-8")
                with self.assertRaises(facelib.FaceError):
                    facelib.load(self.root / "faces.json")
        (self.root / "faces.json").write_text(json.dumps({"chars/zb_angry.png": [0.5, 0.2, 0.0, 0.4]}), encoding="utf-8")
        rc, out = cli(GOOD, "--assets-root", self.root, "--registry", OUT / "REGISTRY.md", "--no-plugins")
        self.assertEqual(rc, 2, out)                                                   # 写坏了不当作通过
        (self.root / "faces.json").unlink()

    def test_real_faces_json_parses_and_has_the_hand_measured_hooded_faces(self):
        """真实的 video/assets/faces.json：格式对；戴斗笠的虞人、戴官帽的司马光这几张（M6 再犯的原因）脸框要比旧的 40% 低。图在不在由 `faces.py check` 管（测试不依赖素材增减）。"""
        data = facelib.load(facelib.ASSETS / facelib.FACES_JSON)
        self.assertGreaterEqual(len(data), 90)
        for k in ("chars/yr_hi_cry_l.png", "chars/yr_hi_laugh_l.png", "chars/yr_hi_sigh_l.png", "chars/wwh_hi_rain_firm.png", "chars/sgm_hi_point.png"):
            self.assertGreater(data[k][3], 0.5, k)                                      # 下巴 / 胡子底在图高的 50% 以下
            self.assertGreater(data[k][2], 0.1, k)                                      # 脸从帽檐下面算起，不是从图顶


class TestDwell(unittest.TestCase):
    """M9、M10：讲事的特效出完以后要看得见 ≥ 2 秒；镜头 < 1.5 秒又不在快切连段里 = 警告。用 s13（智伯一个人，3.7 秒，没有特效）当试验场。"""

    def _run(self, name, sb):
        p = OUT / f"{name}.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        return check(p)[0]

    def _s13_dur(self):
        rep, _ = check(GOOD)
        t0, t1 = rep.times["s13"]
        return t1 - t0

    def _with_bubble(self, visible, **extra):
        """s13 里放一个泡泡（出完要 0.15 秒），让它出完以后刚好看得见 visible 秒（再长的话镜头就是 3.7 秒）。"""
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s13 = next(s for s in sb["shots"] if s["id"] == "s13")
        s13["fx"].append({"type": "bubble", "text": "哼", "pos": [700, 1000], "w": 600, "at": make_case.L(12, round(self._s13_dur() - 0.15 - visible, 3)), **extra})
        return self._run(f"dwell_bubble_{visible}", sb)

    @staticmethod
    def _dwell(rep):
        return [e for e in rep.errors if e["tag"] == "停留"]

    def test_bubble_cut_away_after_1_2_seconds_is_an_error(self):
        rep = self._with_bubble(1.2)
        errs = self._dwell(rep)
        self.assertEqual([e["shot"] for e in errs], ["s13"], text(rep))
        self.assertIn("bubble", errs[0]["msg"])
        self.assertIn("只看得见 1.2 秒", errs[0]["msg"])
        self.assertEqual([e for e in rep.errors if e["tag"] != "停留"], [], text(rep))

    def test_bubble_that_stays_2_5_seconds_is_fine(self):
        rep = self._with_bubble(2.5)
        self.assertEqual(rep.errors, [], text(rep))
        self.assertEqual([w for w in rep.warnings if w["tag"] == "停留"], [])

    def test_boundary_is_two_seconds(self):
        self.assertTrue(self._dwell(self._with_bubble(1.8)), "1.8 秒应该报")
        self.assertEqual(self._dwell(self._with_bubble(2.0)), [], "2.0 秒刚好够")

    def test_dur_ends_the_visible_time_and_the_fade_does_not_count(self):
        short = self._with_bubble(3.0, dur=1.5)                       # 镜头里还能再看 3 秒，但自己写了 dur 1.5 秒（弹出 0.15 秒）：只看得见 1.35 秒
        errs = self._dwell(short)
        self.assertEqual(len(errs), 1, text(short))
        self.assertIn("只看得见 1.4 秒", errs[0]["msg"])
        self.assertIn("写了 dur", errs[0]["msg"])
        self.assertEqual(self._dwell(self._with_bubble(3.0, dur=2.2)), [])      # 2.2 − 0.15 = 2.05：够（淡出的 0.3 秒不算也不扣）

    def test_a_slam_waits_for_its_last_letter_to_land(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s13 = next(s for s in sb["shots"] if s["id"] == "s13")
        s13["fx"].append({"type": "smash", "text": "不给不给", "size": 150, "pos": [540, 700], "at": make_case.L(12, 0.0)})
        rep = self._run("dwell_slam", sb)
        row = next(r for r in rep.dwell if r["id"] == "s13")
        self.assertAlmostEqual(row["fx"][0]["enter"], 0.14 + 0.17 * 3, places=3)             # 4 个字：最后一个字比第一个晚 3 × 0.17 秒落地
        self.assertAlmostEqual(row["fx"][0]["visible"], self._s13_dur() - 0.65, places=2)
        self.assertEqual(self._dwell(rep), [])                                               # 3.7 − 0.65 = 3.05 秒，够

    def test_stickers_and_other_non_storytelling_fx_are_not_checked_here(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        s13 = next(s for s in sb["shots"] if s["id"] == "s13")
        s13["fx"].append({"type": "sticker", "text": "！", "pos": [840, 700], "size": 180, "at": make_case.L(12, 3.2)})      # 贴纸 0.5 秒就切走：是反应，不是讲事
        rep = self._run("dwell_sticker", sb)
        self.assertEqual(rep.errors, [], text(rep))

    def _split(self, name, line, cuts):
        """cuts = [(要切的镜头号, 切在这句台词开始后几秒)]：切出来的后半段叫「原镜头号 + b」。"""
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        for sid, dt in cuts:
            make_case.split_shot(sb, sid, line, dt)
        return self._run(name, sb)

    def test_isolated_short_shot_is_a_warning_not_an_error(self):
        dur = self._s13_dur()
        rep = self._split("dwell_short", 12, [("s13", round(dur - 1.3, 3))])               # s13 = 2.4 + 1.3 秒
        self.assertEqual(rep.errors, [], text(rep))
        warns = [w for w in rep.warnings if w["tag"] == "停留"]
        self.assertEqual([w["shot"] for w in warns], ["s13b"], warns)
        self.assertIn("短于 1.5 秒", warns[0]["msg"])

    def test_short_shots_inside_a_fast_run_are_fine(self):
        rep = self._split("dwell_fast_run", 7, [("s08", 0.9), ("s08b", 1.8)])                        # s08 = 0.9 + 0.9 + 0.9 秒：连续 3 个快切镜头
        self.assertEqual([w for w in rep.warnings if w["tag"] == "停留"], [], rep.warnings)
        self.assertEqual([e for e in rep.errors if e["tag"] == "停留"], [])
        rows = {r["id"]: r for r in rep.dwell}
        self.assertTrue(all(rows[k]["fast"] and not rows[k]["short"] for k in ("s08", "s08b", "s08bb")), rows.keys())

    def test_a_single_fast_shot_is_not_a_run(self):
        dur = self._s13_dur()
        rep = self._split("dwell_lone_fast", 12, [("s13", round(dur - 0.9, 3))])           # 前一半 2.8 秒，后一半 0.9 秒：只有它一个快切镜头
        self.assertEqual([w["shot"] for w in rep.warnings if w["tag"] == "停留"], ["s13b"])

    def test_shot_under_0_8_seconds_is_left_to_the_length_check(self):
        dur = self._s13_dur()
        rep = self._split("dwell_too_short", 12, [("s13", round(dur - 0.6, 3))])
        self.assertTrue(any(e["tag"] == "长度" for e in rep.errors))
        self.assertEqual([w for w in rep.warnings if w["tag"] == "停留"], [], "短于 0.8 秒是 [长度] 的错，不再报警告")

    def test_dwell_table_for_review_frames(self):
        import review_frames as RF
        rep = self._with_bubble(1.2)
        ranges = [(sid, 0, round(t0 * 30), round(t1 * 30)) for sid, (t0, t1) in rep.times.items()]
        md, n_bad = RF.dwell_markdown("tj01", ranges, {r["id"]: r for r in rep.dwell}, 30)
        self.assertEqual(n_bad, 1, md)
        self.assertIn("| s13 |", md)
        row = next(l for l in md.splitlines() if l.startswith("| s13 |"))
        self.assertIn("泡泡「哼」：看得见 1.2 秒 ⚠", row)
        self.assertTrue(row.rstrip().endswith("⚠ |"))
        self.assertEqual(sum(1 for l in md.splitlines() if l.startswith("| s") and l.rstrip().endswith("⚠ |")), 1)
        good_rep, _ = check(GOOD)
        ranges = [(sid, 0, round(t0 * 30), round(t1 * 30)) for sid, (t0, t1) in good_rep.times.items()]
        md, n_bad = RF.dwell_markdown("tj01", ranges, {r["id"]: r for r in good_rep.dwell}, 30)
        self.assertEqual(n_bad, 0, md)
        self.assertIn("清单「高大、力气、才艺」", md)                                          # s05 的清单：3 条，等最后一条到位后还有 2 秒以上


class TestWarnings(unittest.TestCase):
    def test_warnings_do_not_fail(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        sb["shots"][0]["actors"][0]["flip"] = True          # 司马光一个人站在左边、脸朝左（朝画面外）
        p = OUT / "warn_only.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertEqual(rep.errors, [], text(rep))
        self.assertTrue(any("背对全场" in w["msg"] for w in rep.warnings), rep.warnings)
        rc, out = cli(p, "--assets-root", OUT / "assets", "--registry", OUT / "REGISTRY.md", "--no-plugins")
        self.assertEqual(rc, 0, out)
        self.assertIn("警告", out)

    def test_unstable_asset_is_a_warning_not_an_error(self):
        reg = (OUT / "REGISTRY.md").read_text(encoding="utf-8").replace("| 定稿 | 测试图 | tj01 |", "| 未定稿 | 测试图 | tj01 |", 1)
        p = OUT / "REGISTRY_unstable.md"
        p.write_text(reg, encoding="utf-8")
        _, _, rep, _ = SC.run(str(GOOD), registry=p, no_plugins=True, assets_root=OUT / "assets")
        self.assertEqual(rep.errors, [], text(rep))
        self.assertTrue(any("未定稿" in w["msg"] for w in rep.warnings), rep.warnings)

    def test_who_that_is_not_in_the_timeline_warns(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        sb["shots"][1]["actors"][0]["who"] = "张三"
        p = OUT / "who_typo.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rep, _ = check(p)
        self.assertTrue(any("张三" in w["msg"] for w in rep.warnings), rep.warnings)


class TestBrokenInputs(unittest.TestCase):
    """输入 / 环境坏了：退出码 2，不是 1。"""

    def test_missing_storyboard(self):
        rc, out = cli(TESTS / "no_such_storyboard.json")
        self.assertEqual(rc, 2, out)

    def test_not_json(self):
        p = OUT / "not_json.json"
        p.write_text("{这不是 JSON", encoding="utf-8")
        rc, out = cli(p)
        self.assertEqual(rc, 2, out)
        self.assertIn("不是 JSON", out)

    def test_missing_voice_timeline(self):
        sb = json.loads(GOOD.read_text(encoding="utf-8"))
        sb["voice"] = "video/out/nowhere"
        p = OUT / "no_voice.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        rc, out = cli(p, "--assets-root", OUT / "assets", "--registry", OUT / "REGISTRY.md", "--no-plugins")
        self.assertEqual(rc, 2, out)
        self.assertIn("找不到配音时间线", out)

    def test_missing_registry(self):
        rc, out = cli(GOOD, "--registry", OUT / "no_registry.md", "--no-plugins")
        self.assertEqual(rc, 2, out)
        self.assertIn("登记表", out)


class TestJsonOutput(unittest.TestCase):
    def test_json_report(self):
        j = OUT / "report.json"
        rc, _ = cli(TESTS / "bad_flash_total.json", "--assets-root", OUT / "assets", "--registry", OUT / "REGISTRY.md", "--no-plugins", "--json", j)
        self.assertEqual(rc, 1)
        d = json.loads(j.read_text(encoding="utf-8"))
        self.assertTrue(any(e["tag"] == "闪烁" for e in d["errors"]))
        self.assertIn("rate_per_min", d["stats"])


if __name__ == "__main__":
    unittest.main()
