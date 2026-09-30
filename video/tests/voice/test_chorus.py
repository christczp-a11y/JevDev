"""齐声（说话人写成「甲+乙+丙」）和心声（语气里写「心声」）。离线（假合成，正弦波）。
齐声：每个角色各念一遍（各自的声音和语气变体），起点对齐叠在一起、总长按最长的、响度和普通一句差不多；时间线里 who 照写；
缓存照常用；角色没有声音、写法不对都报错。心声：声音用去掉「心声」后的语气，不另外设计；NN.mp3 压低高频，缓存里的原句不动。"""
import re
import subprocess
import unittest

from harness import AUNT, KID, MALE, make_case, read_log, run_voice, sha1, timeline, workdir

CAST = {"甲": MALE, "乙": AUNT, "丙": KID}
CHORUS_TEXT = "今晚联手大反击！"      # 7 个字：假合成念 0.3 + 0.25 × 7 ÷ 语速 秒
TONE = "坚定、干脆"


def volume(path, key="mean_volume", start=None, dur=None):
    """ffmpeg volumedetect 的 mean_volume / max_volume（dBFS）；可以只量从 start 开始的 dur 秒。"""
    cut = (["-ss", str(start)] if start is not None else []) + (["-t", str(dur)] if dur is not None else [])
    err = subprocess.run(["ffmpeg", "-v", "info", *cut, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(key + r": (-?[\d.]+) dB", err).group(1))


def chorus_case(name, who="甲+乙+丙", cast=CAST, tone=TONE, voice_text=None):
    d = workdir(name)
    lines = [("甲", "你好啊，大家。"), (who, CHORUS_TEXT)]
    return d, make_case(d, lines, cast=cast, tone={CHORUS_TEXT: tone} if tone else None, voice_text=voice_text)


class Chorus(unittest.TestCase):
    def test_each_voice_reads_once_and_the_mix_is_as_long_as_the_longest(self):
        d, s = chorus_case("chorus_basic")
        speeds = "甲@坚定干脆=2.0,乙@坚定干脆=1.0,丙@坚定干脆=0.5"          # 念 1.18、2.05、3.80 秒
        r = run_voice(s, d / "out", log=d / "spy.jsonl", env={"VOICE_TEST_SPEED": speeds})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        spoken = [x for x in read_log(d / "spy.jsonl") if x["text"] == CHORUS_TEXT]
        self.assertEqual(sorted(x["voice"] for x in spoken), sorted(["甲@坚定干脆", "乙@坚定干脆", "丙@坚定干脆"]))   # 三个声音各念一遍，每个用自己的语气变体
        row = timeline(d / "out")["lines"][1]
        self.assertEqual(row["who"], "甲+乙+丙")                                         # 说话人照剧本写
        self.assertEqual(row["tts"]["voice"], "甲@坚定干脆+乙@坚定干脆+丙@坚定干脆")
        self.assertEqual([c["voice"] for c in row["tts"]["chorus"]], ["甲@坚定干脆", "乙@坚定干脆", "丙@坚定干脆"])
        self.assertEqual(len(row["tts"]["key"].split("+")), 3)
        self.assertEqual(row["tts"]["from"], "合成")
        longest = 0.3 + 0.25 * 7 / 0.5
        self.assertAlmostEqual(row["voiced_end"], longest, delta=0.12)                     # 总长按最长的那条
        self.assertAlmostEqual(row["dur_raw"], longest, delta=0.12)
        self.assertAlmostEqual(row["t1"] - row["t0"], min(row["dur_raw"], row["voiced_end"] + 0.15), delta=0.02)   # 混音末尾没有静音，就不用再留尾巴
        self.assertTrue((d / "out" / row["audio"]).exists())

    def test_starts_are_aligned_and_loudness_is_like_one_normal_line(self):
        d, s = chorus_case("chorus_loud")
        r = run_voice(s, d / "out", env={"VOICE_TEST_SPEED": "*=1.0"})       # 三条一样长（1.0 × 7 字 = 2.05 秒）
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = timeline(d / "out")["lines"]
        normal, chorus = volume(d / "out" / rows[0]["audio"]), volume(d / "out" / rows[1]["audio"])
        self.assertAlmostEqual(chorus, normal, delta=1.5, msg=f"齐声 {chorus} dB，普通一句 {normal} dB")   # 各自压低，合起来差不多响
        self.assertLess(volume(d / "out" / rows[1]["audio"], start=0, dur=0.5), -10)   # 开头（三个声音都在念的地方）不是静音：起点对齐
        self.assertLess(volume(d / "out" / rows[1]["audio"], "max_volume"), -0.2)      # 不爆音

    def test_second_run_uses_cache_and_remixes_the_same_file(self):
        d, s = chorus_case("chorus_cache")
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = sha1(d / "out" / "01.mp3")
        r = run_voice(s, d / "out", synth="none", log=d / "spy.jsonl")             # 一调用 worker 就报错
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(read_log(d / "spy.jsonl"), [])
        row = timeline(d / "out")["lines"][1]
        self.assertEqual(row["tts"]["from"], "缓存")
        self.assertEqual(sha1(d / "out" / "01.mp3"), first)                          # 同样的缓存，混出来一样的文件

    def test_voice_text_applies_to_every_voice(self):
        d, s = chorus_case("chorus_vt", voice_text={CHORUS_TEXT: "今晚联手大反击。"})
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual({x["text"] for x in read_log(d / "spy.jsonl") if x["voice"].endswith("@坚定干脆")}, {"今晚联手大反击。"})   # 三个声音都念配音用的文字
        row = timeline(d / "out")["lines"][1]
        self.assertEqual(row["text"], CHORUS_TEXT)                                   # 字幕仍是原文
        self.assertEqual(row["voice_text"], "今晚联手大反击。")

    def test_role_without_voice_is_an_error(self):
        d, s = chorus_case("chorus_missing", cast={"甲": MALE, "乙": AUNT})         # 丙没有声音
        r = run_voice(s, d / "out", synth="none")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("丙", r.stderr + r.stdout)
        self.assertIn("没有声音", r.stderr + r.stdout)

    def test_bad_chorus_spellings_are_errors(self):
        for name, who in (("chorus_bad_empty", "甲+"), ("chorus_bad_dup", "甲+甲")):
            d, s = chorus_case(name, who=who)
            r = run_voice(s, d / "out", synth="none")
            self.assertEqual(r.returncode, 1, (who, r.stdout + r.stderr))
            self.assertIn("齐声要写成", r.stderr + r.stdout, who)


class InnerVoice(unittest.TestCase):
    TEXT = "天哪，我家城池旁边也有一条大河。"

    def case(self, name, tone):
        d = workdir(name)
        cast = {"甲": {"desc": MALE, "tone": "平静", "ref_text": "这件事，我们慢慢商量。"}}
        s = make_case(d, [("甲", "你好啊，大家。"), ("甲", self.TEXT)], cast=cast, tone={self.TEXT: tone})
        return d, s

    def test_inner_voice_uses_the_plain_tone_voice_and_filters_the_high_end(self):
        d, s = self.case("inner_basic", "心声、小声、紧张")
        r = run_voice(s, d / "out", log=d / "spy.jsonl", env={"VOICE_TEST_FREQ": "6000"})   # 6 kHz 的正弦波：压高频就该明显变轻
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        designs = {x["id"]: x for x in read_log(d / "spy.jsonl", "design")}
        self.assertIn("甲@小声紧张", designs)                                          # 声音用去掉「心声」后的语气设计
        self.assertIn("小声、紧张", designs["甲@小声紧张"]["instruct"])
        self.assertNotIn("心声", designs["甲@小声紧张"]["instruct"])
        self.assertFalse(any("心声" in k for k in designs))
        row = timeline(d / "out")["lines"][1]
        self.assertEqual(row["tts"]["voice"], "甲@小声紧张")
        self.assertEqual(row["tts"]["tone"], "小声、紧张")
        self.assertEqual(row["tts"]["effect"], "心声")
        cache = d / "out" / "cache" / f"{row['tts']['key']}.mp3"
        self.assertNotEqual(sha1(d / "out" / row["audio"]), sha1(cache))               # NN.mp3 是加了处理的，缓存里的原句不动
        self.assertLess(volume(d / "out" / row["audio"]), volume(cache) - 4, "压低高频以后 6 kHz 的声音应该明显变轻")
        plain = timeline(d / "out")["lines"][0]
        self.assertNotIn("effect", plain["tts"])                                         # 普通句不处理
        self.assertEqual(sha1(d / "out" / plain["audio"]), sha1(d / "out" / "cache" / f"{plain['tts']['key']}.mp3"))

    def test_inner_voice_reuses_the_voice_of_the_same_tone_without_the_marker(self):
        """「心声、小声、紧张」和「小声、紧张」是同一个声音（同一个声音名），只差处理。"""
        d1, s1 = self.case("inner_same_a", "心声、小声、紧张")
        d2, s2 = self.case("inner_same_b", "小声、紧张")
        for d, s in ((d1, s1), (d2, s2)):
            r = run_voice(s, d / "out")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a, b = timeline(d1 / "out")["lines"][1], timeline(d2 / "out")["lines"][1]
        self.assertEqual((a["tts"]["voice"], a["tts"]["text"]), (b["tts"]["voice"], b["tts"]["text"]))
        self.assertNotIn("effect", b["tts"])
        self.assertEqual(a["tts"]["effect"], "心声")

    def test_inner_only_tone_means_default_voice_with_the_effect(self):
        d, s = self.case("inner_only", "心声")
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = timeline(d / "out")["lines"][1]
        self.assertEqual((row["tts"]["voice"], row["tts"]["effect"]), ("甲", "心声"))
        self.assertEqual({x["id"] for x in read_log(d / "spy.jsonl", "design")}, {"甲"})   # 没有另设计语气变体


if __name__ == "__main__":
    unittest.main()
