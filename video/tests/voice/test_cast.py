"""cast 规则、报错一次列完、同声音警告、NARRATOR_RATE（工作流第 0 步第 5 项第 1 条；PITFALLS P10）。全部离线（假合成）。"""
import json
import re
import unittest

from harness import AUNT, MALE, ROOT, make_case, run_voice, timeline, workdir

N6 = ROOT / "video" / "stories" / "ep01" / "N6_你搬不搬.json"
PILOT_CAST = {   # 试做集原来写在 voice.py 里的声音表（旁白、司马光不在这里）
    "商鞅": MALE, "小豆子": {"voice": "zh-CN-YunxiaNeural", "rate": "+6%", "pitch": "+0Hz"},
    "农夫": {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-10Hz"}, "大婶": AUNT,
    "小伙": {"voice": "zh-CN-YunxiNeural", "rate": "+4%", "pitch": "+0Hz"},
    "小孩": {"voice": "zh-CN-YunxiaNeural", "rate": "+8%", "pitch": "+14Hz"},
    "同桌": {"voice": "zh-CN-XiaoyiNeural", "rate": "+4%", "pitch": "+16Hz"}}
LINES = [("旁白", "从前有个小国家。"), ("商鞅", "新法写好了！"), ("小伙", "我来！")]


class CastRules(unittest.TestCase):
    def test_original_ep01_without_cast_errors(self):
        """原版 ep01/episode.json 没有 cast：所有本集角色都「没有声音」，报错退出 1，不生成输出目录。"""
        d = workdir("cast_orig")
        r = run_voice(N6, d / "out")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("没有声音", r.stderr)
        self.assertIn("小伙", r.stderr)
        self.assertFalse((d / "out").exists())

    def test_yunxi_for_cast_member_errors(self):
        """试做集原来的写法：小伙用 YunxiNeural，报错（YunxiNeural 只给司马光）。"""
        d = workdir("cast_yunxi")
        s = make_case(d, LINES, cast={"商鞅": MALE, "小伙": PILOT_CAST["小伙"]})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("只给司马光用", r.stderr)
        self.assertIn("cast.小伙", r.stderr)

    def test_series_names_in_cast_error(self):
        for who in ("旁白", "司马光"):
            with self.subTest(who=who):
                d = workdir(f"cast_has_{who}")
                s = make_case(d, LINES, cast={"商鞅": MALE, "小伙": MALE, who: {"voice": "zh-CN-YunjianNeural"}})
                r = run_voice(s, d / "out")
                self.assertEqual(r.returncode, 1)
                self.assertIn(f"cast 里不许写「{who}」", r.stderr)

    def test_bad_rate_not_followed_by_missing_voice(self):
        """rate 写错时只报 rate 这一条，不再连带多报「小伙 没有声音」；真正缺的（同桌）照报。"""
        d = workdir("cast_bad_rate")
        lines = LINES + [("同桌", "带漫画书了吗？")]
        s = make_case(d, lines, cast={"商鞅": MALE, "小伙": {"voice": "zh-CN-YunyangNeural", "rate": "4%"}})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cast.小伙：rate '4%'", r.stderr)
        miss = re.search(r"剧本里的说话人 (.*?) 没有声音", r.stderr)
        self.assertIsNotNone(miss, r.stderr)
        self.assertEqual(miss.group(1), "同桌")

    def test_all_kinds_of_errors_listed_together(self):
        """cast 的错误、voice_text 的错误、禁用词一次列完，不是报一类就退出。"""
        d = workdir("cast_all_errors")
        s = make_case(d, LINES + [("旁白", "智伯来了。")], cast={"商鞅": MALE, "小伙": PILOT_CAST["小伙"]},
                      banned={"知伯": "异名，通鉴写智伯"}, voice_text={"智伯来了。": "知伯来了。", "没有这一句": "随便"})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        for want in ("只给司马光用", "禁用词「知伯」", "在剧本台词里找不到"):
            self.assertIn(want, r.stderr)
        self.assertIn("配音前检查没过（3 处）", r.stderr)

    def test_same_voice_warning_and_exit_zero(self):
        """整集里两个说话的角色用同一个声音：打印警告并写进 timeline warnings；退出码 0。"""
        d = workdir("cast_same_voice")
        s = make_case(d, LINES, cast={"商鞅": MALE, "小伙": dict(MALE, rate="+6%", pitch="+10Hz")})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("用了同一个声音 zh-CN-YunyangNeural", r.stdout)
        self.assertEqual(len(timeline(d / "out")["warnings"]["same_voice"]), 1)

    def test_narrator_rate_env_ignored(self):
        """NARRATOR_RATE 还设着：打印「已不用」并忽略，旁白仍是系列配置的 +6%。"""
        d = workdir("cast_env")
        s = make_case(d, [("旁白", "从前有个小国家。")])
        r = run_voice(s, d / "out", env={"NARRATOR_RATE": "+0%"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NARRATOR_RATE 已不用", r.stdout)
        self.assertEqual(timeline(d / "out")["lines"][0]["tts"]["rate"], "+6%")

    def test_series_voices_from_config(self):
        d = workdir("cast_series")
        s = make_case(d, [("旁白", "从前有个小国家。"), ("司马光", "我在书里说。")])
        self.assertEqual(run_voice(s, d / "out").returncode, 0)
        t = timeline(d / "out")["lines"]
        self.assertEqual((t[0]["tts"]["voice"], t[0]["tts"]["rate"], t[0]["tts"]["pitch"]), ("zh-CN-XiaoxiaoNeural", "+6%", "+0Hz"))
        self.assertEqual((t[1]["tts"]["voice"], t[1]["tts"]["rate"], t[1]["tts"]["pitch"]), ("zh-CN-YunxiNeural", "-10%", "-12Hz"))
        cfg = json.loads((ROOT / "video" / "series_voice.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["gap"], 0.3)
        self.assertAlmostEqual(t[1]["t0"] - t[0]["t1"], 0.3, places=2)   # 句间停顿 0.3 秒


if __name__ == "__main__":
    unittest.main()
