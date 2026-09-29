"""缓存（第 0 步第 5 项第 2 条）：只改一句的文字 → 只重新合成这一句；插句、删句、挪句 → 其余句子命中正确的缓存（不按行号）；
改 cast 的语速 → 只重合成这个角色的句子。用文件哈希证明，不只看日志。离线（假合成）。"""
import unittest
from pathlib import Path

from harness import MALE, AUNT, count_line, make_case, read_log, run_voice, sha1, timeline, workdir

BASE = [("旁白", "很久很久以前，有一个小国家。"), ("商鞅", "新法写好了！"), ("动作", ""),
        ("大婶", "听说了吗？官府说话算数。"), ("旁白", "说到做到，别人才会信。"), ("商鞅", "那就五十金！")]


class Cache(unittest.TestCase):
    def go(self, d, lines, expect_synth, shangyang_rate="-4%"):
        cast = {"商鞅": dict(MALE, rate=shangyang_rate), "大婶": AUNT}
        s = make_case(d, lines, cast=cast, story_id="S1")
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
        """同一句话（说话人、文字、语速）的 NN.mp3 哈希，在不同次运行里必须一样：按行号错用录音就会破坏这一条。"""
        for r in tl:
            if r["audio"]:
                k = (r["who"], r["text"], r["tts"]["rate"])
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
        tl = self.go(d, f, 2, shangyang_rate="-5%")                                        # 7 只改商鞅的语速（商鞅 2 句）
        self.assertTrue(all(r["tts"]["rate"] == "-5%" for r in tl if r["who"] == "商鞅"))
        tl = self.go(d, f, 0, shangyang_rate="-4%"); self.same_text_same_file(tl, seen)    # 8 改回去：旧缓存还在，0 句合成
        log = [x["text"] for x in read_log(d / "spy.jsonl")]
        self.assertEqual(len(log), 5 + 1 + 1 + 2, log)   # 整个过程发给 TTS 的次数：5 + 1 + 1 + 2

    def test_pitch_and_voice_are_part_of_the_key(self):
        """文字一样，声音或音高变了，也要重新合成。"""
        d = workdir("cache_key")
        s = make_case(d, [("商鞅", "新法写好了！")], cast={"商鞅": MALE}, story_id="S1")
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 1)
        s = make_case(d, [("商鞅", "新法写好了！")], cast={"商鞅": dict(MALE, pitch="+0Hz")}, story_id="S1")
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 1)
        s = make_case(d, [("商鞅", "新法写好了！")], cast={"商鞅": dict(MALE, voice="zh-CN-YunjianNeural")}, story_id="S1")
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 1)
        self.assertEqual(count_line(run_voice(s, d / "out").stdout)[0], 0)


if __name__ == "__main__":
    unittest.main()
