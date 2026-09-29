"""时间线按「真正说完话的时刻」算（第 0 步第 5 项补充）：每句 t1 = 有声部分的结束 + TAIL_KEEP（0.15 秒）；下一句仍是 t1 + 句间停顿；
句首静音只留 HEAD_KEEP（0.08 秒，合成后转 mp3 时裁）；mp3 文件进缓存后不再改；timeline.json 每句记 dur_raw、voiced_end、trim。
离线（假合成 + 真的系列录音）。"""
import re
import subprocess
import unittest

from harness import ROOT, make_case, run_voice, sha1, sha256, timeline, workdir

ASSETS = ROOT / "video" / "assets"
TAIL_KEEP, HEAD_KEEP, GAP = 0.15, 0.08, 0.3


def probe(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def silence_starts_ends(p):
    err = subprocess.run(["ffmpeg", "-i", str(p), "-af", "silencedetect=noise=-50dB:d=0.1", "-f", "null", "-"], capture_output=True, text=True).stderr
    return [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)], [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)], err


class Trim(unittest.TestCase):
    def test_trailing_silence_is_trimmed_and_cache_files_are_untouched(self):
        d = workdir("trim_fake")
        lines = [("旁白", "从前有个小国家。"), ("旁白", "新法写好了！"), ("动作", ""), ("旁白", "那就五十金！")]
        s = make_case(d, lines)
        r = run_voice(s, d / "out", env={"VOICE_TEST_TAIL": "0.8"})     # 每句结尾补 0.8 秒静音
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = timeline(d / "out")["lines"]
        prev = None
        for row in rows:
            if row["audio"]:
                n = len(re.sub(r"[^\w]", "", row["text"]))
                voiced = 0.3 + 0.25 * n                                                 # 假合成的有声部分长度（语速倍数 1.0）
                self.assertAlmostEqual(row["dur_raw"], probe(d / "out" / row["audio"]), delta=0.002)      # dur_raw 就是整段 mp3
                self.assertAlmostEqual(row["dur_raw"], voiced + 0.8, delta=0.12)        # 句首静音已经裁到 HEAD_KEEP 以内，所以 ≈ 有声 + 0.8
                self.assertAlmostEqual(row["voiced_end"], voiced, delta=0.12)           # 有声部分的结束
                self.assertAlmostEqual(row["t1"] - row["t0"], row["voiced_end"] + TAIL_KEEP, delta=0.02)   # t1 = 有声结束 + 尾巴
                self.assertAlmostEqual(row["trim"], row["dur_raw"] - (row["t1"] - row["t0"]), delta=0.011)
                self.assertAlmostEqual(row["trim"], 0.8 - TAIL_KEEP, delta=0.12)        # 裁掉约 0.65 秒
                self.assertEqual(sha1(d / "out" / row["audio"]), sha1(d / "out" / "cache" / f"{row['tts']['key']}.mp3"))   # NN.mp3 就是缓存文件
            if prev is not None:
                self.assertAlmostEqual(row["t0"] - prev["t1"], GAP, delta=0.011)        # 下一句仍按 t1 + 0.3 秒接上
            prev = row

    def test_leading_silence_is_cut_to_head_keep(self):
        """克隆出来的句子开头常有 0.2–1 秒静音：转 mp3 时只留 HEAD_KEEP。"""
        d = workdir("trim_head")
        s = make_case(d, [("旁白", "从前有个小国家。")])
        r = run_voice(s, d / "out", env={"VOICE_TEST_HEAD": "0.9"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = timeline(d / "out")["lines"][0]
        voiced = 0.3 + 0.25 * len(re.sub(r"[^\w]", "", "从前有个小国家。"))
        starts, ends, err = silence_starts_ends(d / "out" / row["audio"])
        lead = ends[0] if starts and starts[0] < 0.01 else 0.0           # 开头那段静音的结束
        self.assertLess(lead, HEAD_KEEP + 0.06, err)
        self.assertAlmostEqual(row["dur_raw"], voiced + HEAD_KEEP, delta=0.15)     # 0.9 秒的静音被裁到 ≈0.08 秒

    def test_no_trailing_silence_means_nothing_trimmed(self):
        d = workdir("trim_none")
        s = make_case(d, [("旁白", "从前有个小国家。")])
        self.assertEqual(run_voice(s, d / "out").returncode, 0)
        row = timeline(d / "out")["lines"][0]
        self.assertLess(row["trim"], 0.02)
        self.assertLessEqual(row["t1"] - row["t0"], row["dur_raw"] + 0.011)

    def test_all_silent_file_is_not_trimmed(self):
        d = workdir("trim_mute")
        s = make_case(d, [("旁白", "从前有个小国家。")])
        self.assertEqual(run_voice(s, d / "out", env={"VOICE_TEST_MUTE": "1", "VOICE_TEST_TAIL": "0.5"}).returncode, 0)
        row = timeline(d / "out")["lines"][0]
        self.assertEqual((row["voiced_end"], row["trim"]), (0.0, 0.0))
        self.assertAlmostEqual(row["t1"] - row["t0"], row["dur_raw"], delta=0.011)

    def test_series_recording_ceremony_line_is_measured_like_any_other(self):
        """真的系列录音「考考你！」「写书的人，来了——」（Qwen 录的，结尾只有一点点静音）：有声结束用 ffmpeg silencedetect 独立核对；
        t1 − t0 = min(整段时长, 有声结束 + 尾巴)；系列录音的 sha256 不变。"""
        d = workdir("trim_ceremony")
        s = make_case(d, [("司马光", "考考你！"), ("旁白", "写书的人，来了——")])
        before = {p.name: sha256(p) for p in (ASSETS / "audio").glob("*") if p.is_file()}
        r = run_voice(s, d / "out", synth="none")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = timeline(d / "out")["lines"]
        for row, rel in zip(rows, ("audio/ceremony_kaokaoni.mp3", "audio/ceremony_xieshu_de_ren_lai_le.mp3")):
            starts, ends, err = silence_starts_ends(ASSETS / rel)
            # 结尾有静音（最后一段静音一直到整段结束）：有声结束 = 它的开始；结尾没有静音：有声一直到整段结束
            dur = probe(ASSETS / rel)
            end = starts[-1] if starts and (len(starts) > len(ends) or ends[-1] >= dur - 0.02) else dur
            self.assertAlmostEqual(row["voiced_end"], end, delta=0.1, msg=err)   # mp3 编码器在开头/结尾各垫了几十毫秒
            self.assertAlmostEqual(row["t1"] - row["t0"], min(row["dur_raw"], row["voiced_end"] + TAIL_KEEP), delta=0.02)
            self.assertEqual(row["dur_raw"], round(probe(ASSETS / rel), 3))
            self.assertLess(row["t1"] - row["t0"], 4.0)
        self.assertEqual(before, {p.name: sha256(p) for p in (ASSETS / "audio").glob("*") if p.is_file()})   # 系列录音的 sha256 不变

    def test_speed_alarm_uses_trimmed_duration(self):
        """30 个字、语速 1.6 倍：有声部分 0.3+0.25×30÷1.6 = 4.99 秒 = 每秒 6 字；整段 mp3（带 1.5 秒静音）算是每秒 4.6 字，裁掉静音以后才是 6 字，要报警。"""
        d = workdir("trim_speed")
        s = make_case(d, [("快嘴", "一二三四五六七八九十" * 3)], cast={"快嘴": "一个七八岁的小男孩，声音清脆明亮，说话很快。"})
        r = run_voice(s, d / "out", env={"VOICE_TEST_TAIL": "1.5", "VOICE_TEST_SPEED": "1.6"})
        self.assertEqual(r.returncode, 0, r.stderr)
        row = timeline(d / "out")["lines"][0]
        self.assertLess(30 / row["dur_raw"], 5)                    # 按整段算不超
        self.assertGreater(30 / (row["t1"] - row["t0"]), 5)        # 按有声部分算超了
        self.assertIn("语速报警：lines[0]（快嘴）", r.stdout)


if __name__ == "__main__":
    unittest.main()
