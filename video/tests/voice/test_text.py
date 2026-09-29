"""voice_text（只许换同音字、不许绕过禁用词）、多音字提示、语速报警（第 0 步第 5 项第 3–5 条；reviewer 第 1 轮：voice_text 绕过 banned）。离线（假合成）。"""
import re
import sys
import unittest
from pathlib import Path

from harness import HERE, KID, ROOT, make_case, read_log, run_voice, timeline, workdir

SOURCE = (HERE / "fixtures" / "source_poly.md").read_text(encoding="utf-8")
BANNED = {"知伯": "异名，通鉴写智伯", "豫让": "暴力情节，整段跳过（S13）"}
S_ZHANGZI = "长子的人来了，晋阳之难就在眼前。"


class VoiceText(unittest.TestCase):
    def test_legal_homophone_passes_and_override_is_what_gets_synthesized(self):
        d = workdir("text_legal")
        s = make_case(d, [("旁白", S_ZHANGZI)], voice_text={S_ZHANGZI: "涨子的人来了，晋阳之难就在眼前。"}, source_md=SOURCE)
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x["text"] for x in read_log(d / "spy.jsonl")], ["涨子的人来了，晋阳之难就在眼前。"])   # 发给 TTS 的是配音文字
        row = timeline(d / "out")["lines"][0]
        self.assertEqual(row["text"], S_ZHANGZI)                       # 字幕、timeline 里仍是原文
        self.assertEqual(row["voice_text"], "涨子的人来了，晋阳之难就在眼前。")
        self.assertEqual(row["tts"]["text"], row["voice_text"])
        self.assertNotIn("多音字提示：", r.stdout)                       # 写了配音文字的句子不再提示

    def test_add_or_remove_characters_errors(self):
        d = workdir("text_length")
        for name, new in (("加字", "有个门客叫某某，后来替他报仇。"), ("减字", "有个门客，替他报仇。")):
            with self.subTest(name):
                s = make_case(d, [("旁白", "有个门客，后来替他报仇。")], voice_text={"有个门客，后来替他报仇。": new})
                r = run_voice(s, d / "out")
                self.assertEqual(r.returncode, 1)
                self.assertIn("不许加字、减字", r.stderr)

    def test_change_count_limit(self):
        """改 3 个字过，改 4 个字报错；只改标点算 0 个字，过。"""
        d = workdir("text_changes")
        orig = "一二三四五六七八九十。"
        cases = {"3 个字": ("一二三四五六七八九十。".replace("一二三", "壹贰叁"), 0), "4 个字": (orig.replace("一二三四", "壹贰叁肆"), 1), "只改标点": ("一二三四五六七八九十！", 0)}
        for name, (new, code) in cases.items():
            with self.subTest(name):
                s = make_case(d, [("旁白", orig)], voice_text={orig: new})
                r = run_voice(s, d / "out")
                self.assertEqual(r.returncode, code, r.stdout + r.stderr)
                if code:
                    self.assertIn("超过 3 个", r.stderr)

    def test_banned_word_in_voice_text_is_blocked(self):
        """reviewer 的用例：banned 有「知伯」「豫让」，voice_text 把「智伯」换成「知伯」、又给整句加了「叫豫让」。退出 1，两处都报出来。"""
        d = workdir("text_banned_vt")
        lines = [("司马光", "考考你！"), ("旁白", "智伯来了。"), ("旁白", "有个门客，后来替他报仇。")]
        s = make_case(d, lines, banned=BANNED, voice_text={"智伯来了。": "知伯来了。", "有个门客，后来替他报仇。": "有个门客叫豫让，后来替他报仇。"})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("配音文字里有禁用词「知伯」", r.stderr)
        self.assertIn("配音文字里有禁用词「豫让」", r.stderr)
        self.assertIn("不许加字、减字", r.stderr)          # 第二处同时违反「只许换同音字」
        self.assertFalse((d / "out").exists())            # 没有合成

    def test_banned_word_in_plain_line_is_blocked(self):
        d = workdir("text_banned_line")
        s = make_case(d, [("旁白", "豫让来了。")], banned=BANNED)
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("台词里有禁用词「豫让」", r.stderr)

    def test_banned_wrong_format_errors(self):
        d = workdir("text_banned_format")
        s = make_case(d, [("旁白", "从前。")], banned=["知伯"])
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("banned 要写成字典", r.stderr)

    def test_missing_banned_field_is_said_out_loud(self):
        d = workdir("text_no_banned")
        s = make_case(d, [("旁白", "从前。")])
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0)
        self.assertIn("没有 banned 字段", r.stdout)

    def test_voice_text_key_not_found_and_bad_value(self):
        d = workdir("text_key")
        s = make_case(d, [("旁白", "从前。")], voice_text={"长子来了": "涨子来了", "从前。": ""})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("在剧本台词里找不到", r.stderr)
        self.assertIn("要是非空字符串", r.stderr)


class Polyphone(unittest.TestCase):
    n = 0

    def hints(self, lines, **kw):
        Polyphone.n += 1
        d = workdir(f"poly_{Polyphone.n}")
        s = make_case(d, lines, source_md=SOURCE, **kw)
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0, r.stderr)
        return [x for x in r.stdout.splitlines() if x.startswith("多音字提示")], timeline(d / "out")["warnings"]["polyphone"], r

    def test_table_terms_alias_and_traditional(self):
        h, w, _ = self.hints([("旁白", "长子的人来了。"), ("旁白", "晋阳之难来了。"), ("旁白", "他是中行的人。"), ("旁白", "智伯好利。"), ("旁白", "智伯去看水势。")])
        self.assertEqual(len(h), len(w))
        text = "\n".join(h)
        self.assertIn("lines[0]（旁白）台词里有多音字词「长子」（zhǎng zǐ）", text)
        self.assertIn("lines[1]（旁白）台词里有多音字词「晋阳之难」（nàn）", text)                      # 表里是繁体，台词是简体
        self.assertIn("lines[2]（旁白）台词里有多音字词「中行」（zhōng háng shì，表里的词是「中行氏」）", text)   # 括号里的别名
        self.assertIn("lines[3]（旁白）台词里有多音字词「好利」", text)
        self.assertEqual(len(h), 4)                                                                   # 「智伯去看水势」没有词，不提示；「好利」只提示一次

    def test_parenthetical_notes_are_not_aliases(self):
        h, _, _ = self.hints([("旁白", "这是个地名。"), ("旁白", "他说智伯行水的事。")])
        text = "\n".join(h)
        self.assertNotIn("lines[0]", text)                     # 「长子（地名）」的「地名」不是别名，台词里有「地名」不该提示
        self.assertIn("lines[1]", text)                        # 「行水」是词本身，照提示
        self.assertEqual(len(h), 1)

    def test_only_the_polyphone_table_counts(self):
        h, _, _ = self.hints([("旁白", "不是多音字表。"), ("旁白", "絺疵来了。")])
        self.assertEqual(h, [])

    def test_missing_source_is_skipped_with_a_note(self):
        d = workdir("poly_nosrc")
        s = make_case(d, [("旁白", "长子来了。")])
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 0)
        self.assertIn("source.md 不存在，跳过多音字检查", r.stdout)

    def test_real_tj01_table_parses(self):
        """真的 tj01 简报里的表：读得出来，含「中行氏（中行）」的别名。"""
        sys.path.insert(0, str(ROOT / "video"))
        import importlib.util
        spec = importlib.util.spec_from_file_location("voice_mod", ROOT / "video" / "voice.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        rows = m.read_polyphones(ROOT / "video" / "stories" / "tj01" / "source.md")
        heads = {r[0]: r[1] for r in rows}
        self.assertGreaterEqual(len(rows), 8)
        self.assertEqual(heads.get("中行氏"), ["中行"])
        self.assertEqual(heads.get("长子"), [])


class SpeedAlarm(unittest.TestCase):
    def test_too_fast_line_is_reported_and_normal_lines_are_not(self):
        d = workdir("speed")
        fast = "快点快点再快点快点快点再快点快点快点再快点快点"
        s = make_case(d, [("旁白", "从前有个小国家。"), ("快嘴", fast)], cast={"快嘴": KID})
        r = run_voice(s, d / "out", env={"VOICE_TEST_SPEED": "快嘴=1.8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("语速报警：lines[1]（快嘴）", r.stdout)
        self.assertNotIn("lines[0]（旁白）", "".join(x for x in r.stdout.splitlines() if x.startswith("语速报警")))
        self.assertEqual(len(timeline(d / "out")["warnings"]["too_fast"]), 1)
        self.assertNotIn("导入不了 story.py", r.stderr)   # 用的是 story.py 的 checks()，没走备用实现


if __name__ == "__main__":
    unittest.main()
