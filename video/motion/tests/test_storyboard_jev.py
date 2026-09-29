"""storyboard_jev.py 的测试。
离线（一定跑，不要网络、不要真 key、不花钱）：没有 key 立刻报错（P8）、输入错误、连不上 Jev 报错且 key 不出现在输出里、
  描述怎么拼（画面主体 = 最大的人、说话的人、上一镜台词）、假 Jev 下的阈值 / 放行 / 对照镜头 / 缓存 / 退出码。
带 key 的真跑（有 TYPESAFE_API_KEY 才跑；没有就跳过，跳过的原因会打印）：jev_case 里故意写成「主体不对」「吓人」「网络烂梗」「文言文」的镜头都被标出来、
  好镜头一个都不标、5 个对照镜头都照预期；同样的输入再跑一次 0 次新请求。第一次约 16 次请求、几秒，缓存在 video/out/tests/motion/jev_cache.json。"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
import unittest

import common

sys.path.insert(0, str(common.ROOT))
from jevdev import jev  # noqa: E402
import storyboard_jev as J  # noqa: E402

TESTS = common.TESTS
OUT = common.OUT / "check_case"
CASE = TESTS / "jev_case" / "storyboard.json"
CACHE_DIR = common.OUT
FAKE_KEY = "test-key-not-real-0000"
ARGS = ["--registry", str(OUT / "REGISTRY.md"), "--assets-root", str(OUT / "assets")]

_spec = importlib.util.spec_from_file_location("make_case", TESTS / "check_case" / "make_case.py")
make_case = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_case)


def setUpModule():
    make_case.make_assets(OUT)            # jev_case 用同一套测试图和测试登记表
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cli(*args, key=FAKE_KEY, env=None):
    e = dict(common.ENV, TYPESAFE_API_KEY=key)
    e.update(env or {})
    t = time.time()
    p = subprocess.run([sys.executable, str(common.MOTION / "storyboard_jev.py"), *[str(a) for a in args]], capture_output=True, text=True,
                       encoding="utf-8", env=e, cwd=common.ROOT)
    return p.returncode, p.stdout + p.stderr, time.time() - t


def fake_ask(state, questions):
    """假 Jev：按镜头里的关键字回答。subject：主体的名字在台词里 = 0.9，否则 0.1；kid：文言文 0.9；scary：有「血」0.9；meme：有 yyds 0.9。"""
    shot = state["shot"]
    lines = "".join(shot.get("台词", []))                       # 只看这一镜自己的台词（上一镜台词只是上下文）
    subj = shot.get("画面主体（最大、最靠前）", "")
    here = lines + subj + shot.get("导演备注", "") + "".join(shot.get("贴纸和特效", []))
    name = subj.split("：")[0].split("（")[0]
    p = {"subject": 0.9 if name and name in lines else 0.1, "kid": 0.9 if "夫才与德异" in lines else 0.1,
         "scary": 0.9 if any(w in here for w in ("血", "尸体", "淹死")) else 0.05, "meme": 0.9 if "yyds" in here else 0.05}
    calls.append(state)
    return {q: {"type": "noul", "noul": p[q]} for q in questions}, {"input_tokens": 10, "output_tokens": 1}


calls = []


def run_main(argv, ask=fake_ask, key=FAKE_KEY):
    """在进程内跑 main()：返回 (退出码, 输出)。"""
    old_ask, old_argv, old_key = jev.ask, sys.argv, os.environ.get("TYPESAFE_API_KEY")
    jev.ask, sys.argv = ask, ["storyboard_jev.py", *[str(a) for a in argv]]
    os.environ["TYPESAFE_API_KEY"] = key
    o, e = io.StringIO(), io.StringIO()
    calls.clear()
    try:
        with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
            code = J.main()
    finally:
        jev.ask, sys.argv = old_ask, old_argv
        if old_key is None:
            os.environ.pop("TYPESAFE_API_KEY", None)
        else:
            os.environ["TYPESAFE_API_KEY"] = old_key
    return code, o.getvalue() + e.getvalue()


def result(name, extra=(), **kw):
    cache = CACHE_DIR / f"{name}_cache.json"
    cache.unlink(missing_ok=True)
    out = CACHE_DIR / f"{name}_out.json"
    code, text = run_main([CASE, *ARGS, "--cache", cache, "--out", out, *extra], **kw)
    return code, text, json.loads(out.read_text(encoding="utf-8")) if out.exists() else None, cache


class TestNoKey(unittest.TestCase):
    def test_no_key_fails_immediately(self):
        for key in ("", None):
            e = {"TYPESAFE_API_KEY": key} if key is not None else {}
            env = dict(common.ENV)
            env.pop("TYPESAFE_API_KEY", None)
            env.update(e)
            t = time.time()
            p = subprocess.run([sys.executable, str(common.MOTION / "storyboard_jev.py"), str(CASE), *ARGS], capture_output=True, text=True,
                               encoding="utf-8", env=env, cwd=common.ROOT)
            out = p.stdout + p.stderr
            self.assertEqual(p.returncode, 2, out)
            self.assertIn("TYPESAFE_API_KEY", out)
            self.assertLess(time.time() - t, 8, "没有 key 要立刻报错")

    def test_no_key_even_if_storyboard_is_missing(self):
        rc, out, _ = cli(TESTS / "no_such.json", key="")
        self.assertEqual(rc, 2, out)
        self.assertIn("TYPESAFE_API_KEY", out)

    def test_unreachable_jev_is_error_3_and_key_not_in_output(self):
        cache = CACHE_DIR / "offline_cache.json"
        cache.unlink(missing_ok=True)
        rc, out, _ = cli(CASE, *ARGS, "--cache", cache, env={"TYPESAFE_BASE_URL": "http://127.0.0.1:9"})
        self.assertEqual(rc, 3, out)
        self.assertIn("Jev 调用失败，没有结果", out)
        self.assertNotIn(FAKE_KEY, out)
        cache.unlink(missing_ok=True)

    def test_bad_input_is_2(self):
        rc, out, _ = cli(TESTS / "no_such.json")
        self.assertEqual(rc, 2, out)
        self.assertIn("找不到分镜表", out)
        rc, out, _ = cli(CASE, *ARGS, "--only", "zz")
        self.assertEqual(rc, 2, out)
        self.assertIn("没有这些镜头", out)


class TestDescription(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = J.load(str(CASE), str(OUT / "REGISTRY.md"), str(OUT / "assets"))
        cls.by = {sh.id: sh for sh in cls.ctx.shots}
        cls.prev = {sh.id: (cls.ctx.shots[k - 1] if k else None) for k, sh in enumerate(cls.ctx.shots)}

    def d(self, sid):
        return J.describe_shot(self.ctx, self.by[sid], self.prev[sid])

    def test_subject_is_the_largest_person_and_speaker_is_marked(self):
        g2 = self.d("g2")
        self.assertTrue(g2["画面主体（最大、最靠前）"].startswith("智伯（正在说话）"), g2)
        self.assertTrue(g2["其他人物"][0].startswith("韩康子"), g2)
        b1 = self.d("b1")
        self.assertTrue(b1["画面主体（最大、最靠前）"].startswith("赵襄子"), b1)          # 赵襄子 h 540 比韩康子大
        self.assertIn("台词", b1)
        self.assertEqual(b1["台词"], ["旁白：智伯有五样本事，样样比别人强！"])

    def test_previous_lines_and_notes_and_stickers(self):
        g2 = self.d("g2")
        self.assertEqual(g2["上一镜台词"], ["旁白：宴会上，智伯举着杯子哈哈大笑，当众取笑韩康子。"])
        self.assertNotIn("上一镜台词", self.d("g1"))
        self.assertEqual(self.d("g1")["贴纸和特效"], ["贴纸「哈」"])
        self.assertIn("血", self.d("s1")["导演备注"])

    def test_no_person_shot(self):
        s2 = self.d("s2")
        self.assertTrue(s2["画面主体（最大、最靠前）"].startswith("没有人物"), s2)

    def test_pose_desc_and_set_name(self):
        self.assertEqual(J.pose_desc("**高清半身特写**（607×812）：得意忘形大笑，手举漆耳杯；3/4"), "高清半身特写：得意忘形大笑，手举漆耳杯")
        self.assertEqual(J.pose_desc("跪坐，前倾，伸食指指着人、咧嘴嘲笑（当众取笑段规）；3/4"), "跪坐，前倾，伸食指指着人、咧嘴嘲笑（当众取笑段规）")
        self.assertEqual(J.set_name("布景 lantai（蓝台宴会）", "sets/lantai/x.png"), "蓝台宴会")
        self.assertIsNone(J.set_name("布景 jin_land（共用：天空、山、地面、水）", "sets/jin_land/x.png"))
        self.assertEqual(J.set_name("布景 jinyang", "sets/jinyang/x.png"), "jinyang")

    def test_questions_use_noul_and_rubric_is_consistent(self):
        for q, v in J.QUESTIONS.items():
            self.assertEqual(v["type"], "noul", q)
            self.assertIn("min" if v["good"] else "max", v, q)
        self.assertEqual(set(J.QUESTIONS), {"subject", "kid", "scary", "meme"})
        self.assertIn("ok", J.RUBRIC["controls"])
        self.assertEqual({q for c in J.RUBRIC["controls"].values() for q in c["expect_flag"]}, set(J.QUESTIONS))


class TestLogicWithFakeJev(unittest.TestCase):
    def test_bad_shots_are_flagged_good_are_not(self):
        code, text, r, cache = result("fake1")
        self.assertEqual(code, 1, text)
        flags = {s["id"]: s["flags"] for s in r["shots"]}
        for sid in ("g1", "g2", "g3", "g4", "g5"):
            self.assertEqual(flags[sid], [], sid)
        self.assertIn("subject", flags["b1"])
        self.assertIn("subject", flags["b2"])
        self.assertIn("scary", flags["s1"])
        self.assertIn("scary", flags["s2"])
        self.assertIn("meme", flags["m1"])
        self.assertIn("kid", flags["b3"])
        self.assertEqual(sorted(r["flagged"]), sorted(k for k, v in flags.items() if v))
        for sid in ("b1", "b2", "s1", "m1", "b3"):
            self.assertIn(f"镜头 {sid}", text)
        self.assertIn("没过：", text)
        self.assertTrue(all(c["ok"] for c in r["controls"]), r["controls"])
        self.assertIn("5 / 5 个照预期", text)

    def test_cache_second_run_makes_no_requests(self):
        code, text, r, cache = result("fake2")
        n = len(calls)
        self.assertEqual(n, 11 + 5)
        self.assertEqual(r["calls"]["requests"], n)
        out = CACHE_DIR / "fake2_out.json"
        code, text = run_main([CASE, *ARGS, "--cache", cache, "--out", out])
        self.assertEqual(len(calls), 0, "同样的输入不该再请求")
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["calls"]["cached"], 16)
        # 改一个镜头，只多一次请求
        sb = json.loads(CASE.read_text(encoding="utf-8"))
        sb["shots"][2]["actors"][0]["note"] = "跪坐，抱着地图卷，咬牙为难，快哭了"
        alt = CACHE_DIR / "fake2_alt.json"
        alt.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        run_main([alt, *ARGS, "--cache", cache, "--out", CACHE_DIR / "fake2_alt_out.json"])
        self.assertEqual(len(calls), 1)

    def test_only_and_verbose(self):
        code, text, r, _ = result("fake3", ["--only", "g1,g2", "--verbose"])
        self.assertEqual(code, 0, text)
        self.assertEqual([s["id"] for s in r["shots"]], ["g1", "g2"])
        self.assertIn("镜头 g1", text)
        self.assertIn("这次的结果可信", text)
        self.assertEqual(len(calls), 2 + 5)

    def test_allow_list_in_notes_is_not_a_failure(self):
        sb = json.loads(CASE.read_text(encoding="utf-8"))
        b3 = next(s for s in sb["shots"] if s["id"] == "b3")
        b3["notes"] = {"jev_allow": ["kid", "subject"], "why": "系列固定的金句原文，下一镜马上用白话解释"}
        p = CACHE_DIR / "allow.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        out = CACHE_DIR / "allow_out.json"
        (CACHE_DIR / "allow_cache.json").unlink(missing_ok=True)
        code, text = run_main([p, *ARGS, "--cache", CACHE_DIR / "allow_cache.json", "--out", out, "--only", "b3"])
        self.assertEqual(code, 0, text)
        self.assertIn("放行", text)
        self.assertIn("系列固定的金句原文", text)
        r = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(r["shots"][0]["id"], "b3")
        self.assertEqual(r["shots"][0]["flags"], [])
        self.assertEqual(sorted(r["shots"][0]["allowed"]), ["kid", "subject"])

    def test_untrustworthy_controls_fail(self):
        def always_fine(state, questions):
            calls.append(state)
            return {q: {"type": "noul", "noul": 0.95 if q == "subject" else 0.05} for q in questions}, {}     # 什么都不标：坏的对照镜头没被标出来
        code, text, r, _ = result("fake4", ask=always_fine)
        self.assertEqual(code, 1, text)
        self.assertIn("对照镜头没照预期", text)
        self.assertFalse(all(c["ok"] for c in r["controls"]))

    def test_jev_failure_is_3(self):
        def boom(state, questions):
            raise RuntimeError("连不上 " + os.environ["TYPESAFE_API_KEY"])
        code, text = run_main([CASE, *ARGS, "--cache", CACHE_DIR / "boom_cache.json"], ask=boom)
        self.assertEqual(code, 3, text)
        self.assertIn("Jev 调用失败", text)
        self.assertNotIn(FAKE_KEY, text)


REAL_KEY = os.environ.get("TYPESAFE_API_KEY")


@unittest.skipUnless(REAL_KEY, "没有 TYPESAFE_API_KEY：跳过带 key 的真跑（SKIP，不算通过；用 export TYPESAFE_API_KEY=$(powershell ...) 设好再跑）")
class TestRealJev(unittest.TestCase):
    """真跑：好镜头不标，故意写坏的镜头都被标出来，对照镜头照预期。结果按哈希缓存，第一次约 16 次请求。"""

    @classmethod
    def setUpClass(cls):
        cache = CACHE_DIR / "jev_cache.json"
        out = CACHE_DIR / "jev_real_out.json"
        code, cls.text = run_main([CASE, *ARGS, "--cache", cache, "--out", out, "--verbose"], ask=jev.ask, key=REAL_KEY)
        cls.code = code
        cls.r = json.loads(out.read_text(encoding="utf-8"))
        cls.flags = {s["id"]: s["flags"] for s in cls.r["shots"]}
        cls.calls = cls.r["calls"]

    def test_controls_behave_as_expected(self):
        self.assertTrue(all(c["ok"] for c in self.r["controls"]), self.text)

    def test_wrong_subject_shots_are_flagged(self):
        for sid in ("b1", "b2"):
            self.assertIn("subject", self.flags[sid], f"{sid}：{self.text}")

    def test_scary_shots_are_flagged(self):
        for sid in ("s1", "s2"):
            self.assertIn("scary", self.flags[sid], f"{sid}：{self.text}")

    def test_meme_and_kid_shots_are_flagged(self):
        self.assertIn("meme", self.flags["m1"], self.text)
        self.assertIn("kid", self.flags["b3"], self.text)

    def test_good_shots_are_not_flagged(self):
        for sid in ("g1", "g2", "g3", "g4", "g5"):
            self.assertEqual(self.flags[sid], [], f"{sid}：{self.text}")

    def test_exit_code_is_1_and_second_run_is_free(self):
        self.assertEqual(self.code, 1)
        code, text = run_main([CASE, *ARGS, "--cache", CACHE_DIR / "jev_cache.json", "--out", CACHE_DIR / "jev_real_out2.json"], ask=jev.ask, key=REAL_KEY)
        r2 = json.loads((CACHE_DIR / "jev_real_out2.json").read_text(encoding="utf-8"))
        self.assertEqual(r2["calls"]["requests"], 0, text)
        self.assertEqual(r2["calls"]["cached"], 16)


if __name__ == "__main__":
    unittest.main()
