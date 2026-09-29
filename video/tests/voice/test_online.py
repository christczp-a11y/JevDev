"""会真的调用 Edge TTS 的测试（要网络）。ONLINE=0 跳过。
回归：新 voice.py 重配试做集 N6（小伙换声音，不设 NARRATOR_RATE），除小伙以外每句 mp3 时长和 video/out/ep01v2_voice_0929 一样；
真合成时发给 Edge TTS 的确实是配音用的文字。"""
import json
import os
import shutil
import subprocess
import unittest

from harness import MALE, ROOT, make_case, read_log, run_voice, timeline, workdir

ONLINE = os.environ.get("ONLINE", "1") != "0"
OLD = ROOT / "video" / "out" / "ep01v2_voice_0929"
N6 = ROOT / "video" / "stories" / "ep01" / "N6_你搬不搬.json"
PILOT_CAST = {"商鞅": MALE, "小豆子": {"voice": "zh-CN-YunxiaNeural", "rate": "+6%", "pitch": "+0Hz"},
              "农夫": {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-10Hz"},
              "大婶": {"voice": "zh-CN-liaoning-XiaobeiNeural", "rate": "+4%", "pitch": "+0Hz"},
              "小伙": {"voice": "zh-CN-YunyangNeural", "rate": "+6%", "pitch": "+10Hz"},   # 换掉 Yunxi（只给司马光）
              "小孩": {"voice": "zh-CN-YunxiaNeural", "rate": "+8%", "pitch": "+14Hz"},
              "同桌": {"voice": "zh-CN-XiaoyiNeural", "rate": "+4%", "pitch": "+16Hz"}}


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


@unittest.skipUnless(ONLINE, "ONLINE=0：跳过要网络的测试")
class Online(unittest.TestCase):
    @unittest.skipUnless((OLD / "timeline.json").exists(), "本机没有 video/out/ep01v2_voice_0929（改前的 N6 配音）")
    def test_n6_regression_against_old_timeline(self):
        d = workdir("online_n6")
        shutil.copy(N6, d / N6.name)
        ep = json.loads((ROOT / "video" / "stories" / "ep01" / "episode.json").read_text(encoding="utf-8"))
        ep["cast"] = PILOT_CAST
        (d / "episode.json").write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")
        r = run_voice(d / N6.name, d / "out", "2=1.0", "9=1.2", "13=8.6", "22=1.2", "29=3.3", synth="real", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        old = json.loads((OLD / "timeline.json").read_text(encoding="utf-8"))["lines"]
        new = timeline(d / "out")["lines"]
        self.assertEqual(len(old), len(new))
        compared = 0
        for o, n in zip(old, new):
            self.assertEqual((o["who"], o["text"]), (n["who"], n["text"]))
            if o["who"] == "小伙":
                continue
            compared += 1
            # 旧 timeline 的 t1−t0 就是整段 mp3 的时长（当时不裁静音）；新 timeline 的 t1−t0 已经裁掉了句尾静音，整段时长记在 dur_raw。
            # t0、t1 各自四舍五入到 0.01，所以差 0.01 以内算一样；mp3 时长直接量，几乎一样
            if o["audio"]:
                self.assertLessEqual(abs((o["t1"] - o["t0"]) - n["dur_raw"]), 0.01 + 1e-9, o["i"])
                self.assertLessEqual(abs(dur(OLD / o["audio"]) - dur(d / "out" / n["audio"])), 0.001, o["i"])
                self.assertLessEqual(abs(n["dur_raw"] - n["trim"] - (n["t1"] - n["t0"])), 0.011, o["i"])
            else:
                self.assertLessEqual(abs((o["t1"] - o["t0"]) - (n["t1"] - n["t0"])), 0.01 + 1e-9, o["i"])   # 动作行的时长不变
        self.assertEqual(compared, 37)
        self.assertLess(timeline(d / "out")["duration"], json.loads((OLD / "timeline.json").read_text(encoding="utf-8"))["duration"] - 10)   # 裁掉静音以后全片明显变短
        self.assertEqual(new[0]["series_audio"], "audio/ceremony_kaokaoni.mp3")   # 第 0 句「考考你！」用系列录音

    def test_real_synthesis_receives_the_voice_text(self):
        d = workdir("online_vt")
        line = "长子的人来了。"
        s = make_case(d, [("旁白", line)], voice_text={line: "涨子的人来了。"})
        r = run_voice(s, d / "out", synth="real", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x["text"] for x in read_log(d / "spy.jsonl")], ["涨子的人来了。"])
        row = timeline(d / "out")["lines"][0]
        self.assertEqual(row["text"], line)
        self.assertGreater(dur(d / "out" / row["audio"]), 0.5)


if __name__ == "__main__":
    unittest.main()
