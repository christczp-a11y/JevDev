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
TAGS = ["格式", "锚点", "长度", "频率", "静止", "特效", "闪烁", "安全区", "素材", "放大", "朝向", "人名牌"]

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
