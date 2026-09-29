"""缓存（第 0 步第 5 项第 2 条）：只改一句的文字 → 只重新合成这一句；插句、删句、挪句 → 其余句子命中正确的缓存（不按行号）；
改某几句的语气 → 只重合成这几句（另设计语气变体的参考音）；换参考音 → 用它的句子重新合成。用文件哈希证明，不只看日志。离线（假合成）。"""
import unittest
from pathlib import Path

from harness import AUNT, MALE, count_line, make_case, read_log, run_voice, sha1, timeline, workdir

BASE = [("旁白", "很久很久以前，有一个小国家。"), ("商鞅", "新法写好了！"), ("动作", ""),
        ("大婶", "听说了吗？官府说话算数。"), ("旁白", "说到做到，别人才会信。"), ("商鞅", "那就五十金！")]


class Cache(unittest.TestCase):
    def go(self, d, lines, expect_synth, tone=None):
        s = make_case(d, lines, cast={"商鞅": MALE, "大婶": AUNT}, tone=tone, story_id="S1")
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        synth, hit, _ = count_line(r.stdout)
        self.assertEqual(synth, expect_synth, r.stdout)
        tl = timeline(d / "out")["lines"]
        out = d / "out"
        for row in tl:   # NN.mp3 就是它缓存文件的副本
            if row["audio"]:
                self.assertEqual(sha1(out / row["audio"]), sha1(out / "cache" / f"{row['tts']['key']}.mp3"))
        self.assertEqual(sorted(p.name for p in out.glob("[0-9]*.mp3")), sorted(r["audio"] for r in tl if r["audio"]))   # 没有多余的 NN.mp3
        return tl

    def same_text_same_file(self, tl, seen):
        """同一句话（说话人、文字、语气）的 NN.mp3 哈希，在不同次运行里必须一样：按行号错用录音就会破坏这一条。"""
        for r in tl:
            if r["audio"]:
                k = (r["who"], r["text"], r["tts"]["voice"])
                h = sha1(Path(self.out) / r["audio"])
                self.assertEqual(seen.setdefault(k, h), h, f"lines[{r['i']}]「{r['text']}」用了别的句子的录音")

    def test_eight_steps(self):
        d = workdir("cache")
        self.out, seen = d / "out", {}
        tl = self.go(d, BASE, 5); self.same_text_same_file(tl, seen)                       # 1 冷启动
        tl = self.go(d, BASE, 0); self.same_text_same_file(tl, seen)                       # 2 什么都没改
        b = list(BASE); b[3] = ("大婶", "听说了吗？官府说话真算数！")
        tl = self.go(d, b, 1); self.same_text_same_file(tl, seen)                          # 3 只改一句的文字
        c = list(b); c.insert(2, ("大婶", "真的吗？"))
        tl = self.go(d, c, 1); self.same_text_same_file(tl, seen)                          # 4 在中间插一句
        e = list(c); del e[0]
        tl = self.go(d, e, 0); self.same_text_same_file(tl, seen)                          # 5 删掉第一句（多出来的 NN.mp3 要清掉）
        f = list(e); f[0], f[-1] = f[-1], f[0]
        tl = self.go(d, f, 0); self.same_text_same_file(tl, seen)                          # 6 首尾对调
        tone = {"新法写好了！": "得意、兴奋", "那就五十金！": "得意、兴奋"}
        tl = self.go(d, f, 2, tone=tone)                                                    # 7 只给商鞅的 2 句加语气（语气变体的参考音另设计）
        self.assertTrue(all(r["tts"]["voice"].startswith("商鞅@") and r["tts"]["tone"] == "得意、兴奋" for r in tl if r["who"] == "商鞅"))
        tl = self.go(d, f, 0)                                                               # 8 改回去：旧缓存还在，0 句合成
        self.assertTrue(all(r["tts"]["voice"] == "商鞅" for r in tl if r["who"] == "商鞅"))
        log = [x["text"] for x in read_log(d / "spy.jsonl")]
        self.assertEqual(len(log), 5 + 1 + 1 + 2, log)   # 整个过程发给 TTS 的次数：5 + 1 + 1 + 2
        variants = [x for x in read_log(d / "spy.jsonl", "design") if "@" in x["id"]]
        self.assertEqual(len(variants), 1)                # 语气变体的参考音只设计一次（一次 3 个候选，挑和默认参考音最像的）
        self.assertEqual((variants[0]["n"], variants[0]["anchor"]), (3, "商鞅"))

    def test_same_tone_as_default_uses_default_voice(self):
        """语气和角色的默认语气一样（去掉标点后）：不设计变体，用默认参考音。"""
        d = workdir("cache_default_tone")
        cast = {"商鞅": {"desc": MALE, "tone": "沉稳、自信"}}
        s = make_case(d, [("商鞅", "新法写好了！")], cast=cast, tone={"新法写好了！": "沉稳，自信！"}, story_id="S1")
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x["id"] for x in read_log(d / "spy.jsonl", "design")], ["商鞅"])
        self.assertEqual(timeline(d / "out")["lines"][0]["tts"]["voice"], "商鞅")

    def test_voice_and_reference_are_part_of_the_key(self):
        """文字一样，说话人（声音）不一样，要各合成一次；换了参考音（--redesign），用它的句子要重新合成。"""
        d = workdir("cache_key")
        cast = {"商鞅": MALE, "大婶": AUNT}
        s = make_case(d, [("商鞅", "新法写好了！"), ("大婶", "新法写好了！")], cast=cast, story_id="S1")
        r = run_voice(s, d / "out")
        self.assertEqual(count_line(r.stdout)[0], 2)
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 0)
        r = run_voice(s, d / "out", "--redesign", "商鞅", log=d / "spy.jsonl")
        self.assertEqual(count_line(r.stdout)[:2], (1, 1), r.stdout)     # 商鞅的重新合成，大婶的命中缓存
        self.assertEqual([x["voice"] for x in read_log(d / "spy.jsonl")], ["商鞅"])
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 0)

    def test_same_line_twice_is_synthesized_once(self):
        d = workdir("cache_dup")
        s = make_case(d, [("商鞅", "新法写好了！"), ("大婶", "真的吗？"), ("商鞅", "新法写好了！")], cast={"商鞅": MALE, "大婶": AUNT}, story_id="S1")
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(count_line(r.stdout)[:2], (2, 1), r.stdout)     # 2 句合成，重复的那句记缓存命中
        self.assertEqual(len(read_log(d / "spy.jsonl")), 2)
        tl = timeline(d / "out")["lines"]
        self.assertEqual(tl[0]["tts"]["key"], tl[2]["tts"]["key"])


if __name__ == "__main__":
    unittest.main()
