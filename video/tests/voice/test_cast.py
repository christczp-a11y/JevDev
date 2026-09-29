"""cast 规则（声音描述）、禁用词、报错一次列完、同描述警告、参考音和描述对不上、--redesign（PITFALLS P10、A4）。全部离线（假合成）。"""
import json
import re
import shutil
import unittest

from harness import AUNT, KID, MALE, ROOT, YOUNG, make_case, read_log, run_voice, timeline, workdir

N6 = ROOT / "video" / "stories" / "ep01" / "N6_你搬不搬.json"
LINES = [("旁白", "从前有个小国家。"), ("商鞅", "新法写好了！"), ("小伙", "我来！")]
CAST = {"商鞅": MALE, "小伙": YOUNG}


class CastRules(unittest.TestCase):
    def test_original_ep01_without_cast_errors(self):
        """原版 ep01/episode.json 没有 cast：所有本集角色都「没有声音」，报错退出 1，不生成输出目录。"""
        d = workdir("cast_orig")
        r = run_voice(N6, d / "out", voices=d / "voices")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("没有声音", r.stderr)
        self.assertIn("小伙", r.stderr)
        self.assertFalse((d / "out").exists())

    def test_old_edge_format_errors(self):
        """Edge TTS 时代的 {"voice", "rate", "pitch"} 写法：报错，并说明已经不用了。"""
        d = workdir("cast_edge")
        s = make_case(d, LINES, cast={"商鞅": {"voice": "zh-CN-YunyangNeural", "rate": "-4%", "pitch": "-6Hz"}, "小伙": YOUNG})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cast.商鞅", r.stderr)
        self.assertIn("Edge TTS 的 voice / rate / pitch 已经不用了", r.stderr)

    def test_series_names_in_cast_error(self):
        for who in ("旁白", "司马光"):
            with self.subTest(who=who):
                d = workdir(f"cast_has_{who}")
                s = make_case(d, LINES, cast=dict(CAST, **{who: KID}))
                r = run_voice(s, d / "out")
                self.assertEqual(r.returncode, 1)
                self.assertIn(f"cast 里不许写「{who}」", r.stderr)

    def test_bad_fields_not_followed_by_missing_voice(self):
        """字段写错时只报字段这一条，不再连带多报「小伙 没有声音」；真正缺的（同桌）照报。"""
        d = workdir("cast_bad_fields")
        lines = LINES + [("同桌", "带漫画书了吗？")]
        s = make_case(d, lines, cast={"商鞅": MALE, "小伙": {"desc": YOUNG, "tone": 3, "pitch": "+3Hz"}})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cast.小伙：tone 3 要是字符串", r.stderr)
        self.assertIn("多了没用的字段 pitch", r.stderr)
        miss = re.search(r"剧本里的说话人 (.*?) 没有声音", r.stderr)
        self.assertIsNotNone(miss, r.stderr)
        self.assertEqual(miss.group(1), "同桌")

    def test_banned_words_in_desc_tone_and_script_tone(self):
        """声音描述、cast 里的默认语气、剧本里的语气：低沉、沙哑、气声、阴森、阴冷、邪恶、恐怖、神秘、阴沉，一律报错（PITFALLS A4）。"""
        d = workdir("cast_banned_desc")
        s = make_case(d, LINES + [("大婶", "别怕。")],
                      cast={"商鞅": "一位嗓音低沉沙哑的老人。", "小伙": {"desc": YOUNG, "tone": "神秘、阴森"}, "大婶": AUNT},
                      tone={"别怕。": "阴冷、邪恶地笑"})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        for want in ("cast.商鞅 的 desc里有「低沉」", "cast.商鞅 的 desc里有「沙哑」", "cast.小伙 的 tone里有「神秘」", "cast.小伙 的 tone里有「阴森」",
                     "tone「别怕。」的语气里有「阴冷」", "有「邪恶」"):
            self.assertIn(want, r.stderr)
        self.assertIn("PITFALLS A4", r.stderr)
        self.assertFalse((d / "out").exists())

    def test_all_kinds_of_errors_listed_together(self):
        """cast 的错误、voice_text 的错误、语气的错误、禁用词一次列完，不是报一类就退出。"""
        d = workdir("cast_all_errors")
        s = make_case(d, LINES + [("旁白", "智伯来了。")], cast={"商鞅": "声音低沉的男人", "小伙": YOUNG},
                      banned={"知伯": "异名，通鉴写智伯"}, voice_text={"智伯来了。": "知伯来了。", "没有这一句": "随便"}, tone={"没有那一句": "开心"})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        for want in ("desc里有「低沉」", "禁用词「知伯」", "voice_text 里的「没有这一句」在剧本台词里找不到", "tone 里的「没有那一句」在剧本台词里找不到"):
            self.assertIn(want, r.stderr)
        self.assertIn("配音前检查没过（4 处）", r.stderr)

    def test_same_desc_warning_and_exit_zero(self):
        """整集里两个说话的角色声音描述一模一样：打印警告并写进 timeline warnings；退出码 0。"""
        d = workdir("cast_same_voice")
        s = make_case(d, LINES, cast={"商鞅": MALE, "小伙": MALE})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("商鞅、小伙 的声音描述一模一样", r.stdout)
        self.assertEqual(len(timeline(d / "out")["warnings"]["same_voice"]), 1)

    def test_series_voices_from_config(self):
        d = workdir("cast_series")
        s = make_case(d, [("旁白", "从前有个小国家。"), ("司马光", "我在书里说。")])
        log = d / "spy.jsonl"
        self.assertEqual(run_voice(s, d / "out", log=log).returncode, 0)
        t = timeline(d / "out")["lines"]
        self.assertEqual((t[0]["tts"]["voice"], t[1]["tts"]["voice"]), ("旁白", "司马光"))     # 系列声音，用默认参考音
        self.assertEqual(read_log(log, "design"), [])                                          # 系列声音的参考音已经在，不再设计
        cfg = json.loads((ROOT / "video" / "series_voice.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["gap"], 0.3)
        self.assertAlmostEqual(t[1]["t0"] - t[0]["t1"], 0.3, places=2)   # 句间停顿 0.3 秒
        self.assertEqual(t[0]["tts"]["tone"], cfg["characters"]["旁白"]["tone"])

    def test_new_cast_voice_is_designed_once_and_saved(self):
        """第一次用到的角色：设计参考音（wav + json 存进 voices/），json 记着描述和参考文字；再跑不再设计。"""
        d = workdir("cast_design_once")
        s = make_case(d, LINES, cast=CAST)
        log = d / "spy.jsonl"
        self.assertEqual(run_voice(s, d / "out", log=log).returncode, 0)
        self.assertEqual(sorted(x["id"] for x in read_log(log, "design")), ["商鞅", "小伙"])
        self.assertEqual({x["n"] for x in read_log(log, "design")}, {1})        # 默认参考音只出一个候选
        for who, desc in CAST.items():
            meta = json.loads((d / "voices" / f"{who}.json").read_text(encoding="utf-8"))
            self.assertEqual((meta["desc"], meta["name"]), (desc, who))
            self.assertTrue((d / "voices" / f"{who}.wav").exists())
        ins = {x["id"]: x["instruct"] for x in read_log(log, "design")}
        self.assertEqual(ins["商鞅"], MALE)                                      # 没写默认语气：指令就是描述
        log2 = d / "spy2.jsonl"
        self.assertEqual(run_voice(s, d / "out", log=log2).returncode, 0)
        self.assertEqual(read_log(log2, "design"), [])

    def test_default_tone_goes_into_the_design_instruction(self):
        d = workdir("cast_default_tone")
        s = make_case(d, [("商鞅", "新法写好了！")], cast={"商鞅": {"desc": MALE, "tone": "沉稳、自信", "ref_text": "我们把新法写好了，大家都来看。"}})
        log = d / "spy.jsonl"
        self.assertEqual(run_voice(s, d / "out", log=log).returncode, 0)
        d0 = read_log(log, "design")[0]
        self.assertEqual(d0["instruct"], MALE.rstrip("。") + "。沉稳、自信。")
        meta = json.loads((d / "voices" / "商鞅.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["tone"], meta["ref_text"]), ("沉稳、自信", "我们把新法写好了，大家都来看。"))

    def test_desc_changed_after_design_errors_and_redesign_fixes_it(self):
        """描述改了、参考音是按旧描述设计的：报错并指路 --redesign；--redesign 以后删掉旧的、重新设计。系列声音的 --redesign 要 --force。"""
        d = workdir("cast_redesign")
        s = make_case(d, LINES, cast=CAST)
        self.assertEqual(run_voice(s, d / "out").returncode, 0)
        old_wav = (d / "voices" / "商鞅.wav").read_bytes()
        s = make_case(d, LINES, cast={"商鞅": KID, "小伙": YOUNG})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("商鞅：参考音是按另一份声音描述设计的", r.stderr)
        self.assertIn("--redesign 商鞅", r.stderr)
        log = d / "spy.jsonl"
        r = run_voice(s, d / "out", "--redesign", "商鞅", log=log)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x["id"] for x in read_log(log, "design")], ["商鞅"])
        meta = json.loads((d / "voices" / "商鞅.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["desc"], KID)
        self.assertNotEqual((d / "voices" / "商鞅.wav").read_bytes(), old_wav)
        r = run_voice(s, d / "out", "--redesign", "旁白")           # 系列声音：不加 --force 不行
        self.assertEqual(r.returncode, 1)
        self.assertIn("系列固定声音", r.stderr)
        self.assertTrue((d / "voices" / "旁白.wav").exists())

    def test_missing_series_reference_errors(self):
        d = workdir("cast_no_series_ref")
        (d / "voices" / "旁白.wav").unlink()
        (d / "voices" / "旁白.json").unlink()
        s = make_case(d, [("旁白", "从前有个小国家。")])
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("先跑 voice.py --make-series-voices", r.stderr)


if __name__ == "__main__":
    unittest.main()
