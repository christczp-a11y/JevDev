"""storyboard_check.py 的测试（不要显卡、不要网络、不要 Jev key）。
数据是合成的（check_case/make_case.py）：素材用 --assets-root 指到测试时生成的纯色小图 + 测试登记表，特效用 --no-plugins，
所以真实素材怎么增减、特效包做到哪一步，这些测试都不受影响。"""
import importlib.util
import json
import subprocess
import sys
import unittest

import common
import storyboard_check as SC

TESTS = common.TESTS
CASE = TESTS / "check_case"
OUT = common.OUT / "check_case"
GOOD = TESTS / "good_storyboard.json"
EXPECT = json.loads((TESTS / "check_expect.json").read_text(encoding="utf-8"))
BAD = sorted(TESTS.glob("bad_*.json"))
TAGS = ["格式", "锚点", "长度", "频率", "静止", "特效", "闪烁", "安全区", "素材", "放大", "朝向", "人名牌", "翻转", "压脸", "集中线", "字幕", "遮挡"]

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
