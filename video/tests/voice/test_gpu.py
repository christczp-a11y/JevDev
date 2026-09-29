"""会真的调用 Qwen3-TTS worker 的测试（要 .venv-tts、显卡、模型；一共约 3–4 分钟）。GPU=0 跳过；找不到 .venv-tts 也跳过。
1. 新角色 + 旁白：设计参考音（wav + json 存进 voices/）、克隆念出来、时长合理，第二次跑全部命中缓存（禁止再调 worker）；
2. 语气变体：同一句话加语气 → 设计变体的参考音（3 个候选挑 1 个）、念出来；
3. 参考音目录是测试自己的（workdir 里的 voices/），不弄脏真的 video/assets/audio/voices/。"""
import json
import os
import unittest
from pathlib import Path

from harness import MALE, REAL_VOICES, ROOT, count_line, make_case, run_voice, sha256, timeline, workdir


def find_tts_python():
    for base in [ROOT, *ROOT.parents]:
        for rel in (".venv-tts/Scripts/python.exe", ".venv-tts/bin/python"):
            if (base / rel).exists():
                return str(base / rel)
    return None


PY = find_tts_python()
RUN = os.environ.get("GPU", "1") != "0" and PY is not None


@unittest.skipUnless(RUN, "GPU=0 或者找不到 .venv-tts：跳过要显卡的测试")
class Gpu(unittest.TestCase):
    def test_design_clone_and_cache(self):
        d = workdir("gpu_basic")
        before = {p.name: sha256(p) for p in REAL_VOICES.iterdir()}
        s = make_case(d, [("旁白", "很久很久以前，有一个小国家。"), ("商鞅", "新法写好了！")], cast={"商鞅": MALE})
        r = run_voice(s, d / "out", synth="real", env={"VOICE_TTS_PYTHON": PY})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = [x for x in timeline(d / "out")["lines"] if x["audio"]]
        self.assertEqual([x["tts"]["from"] for x in rows], ["合成", "合成"])
        for x in rows:
            self.assertTrue(0.5 < x["dur_raw"] < 12, x)                                   # 念出来了，没有撞上限、没有空音频
            self.assertGreater(x["voiced_end"], 0.4, x)
        self.assertTrue((d / "voices" / "商鞅.wav").exists())
        meta = json.loads((d / "voices" / "商鞅.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["desc"], MALE)
        self.assertIn("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", meta["model"])
        r2 = run_voice(s, d / "out", synth="none", env={"VOICE_TTS_PYTHON": PY})           # 全部命中缓存：一调用 worker 就报错
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(count_line(r2.stdout), (0, 2, 0))
        self.assertEqual(before, {p.name: sha256(p) for p in REAL_VOICES.iterdir()})       # 真的参考音没被动

    def test_tone_variant_is_designed_and_used(self):
        d = workdir("gpu_tone")
        line = "这块地，我要了！"
        s = make_case(d, [("旁白", line)], tone={line: "得意、兴奋，声音洪亮"})
        r = run_voice(s, d / "out", synth="real", env={"VOICE_TTS_PYTHON": PY})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = timeline(d / "out")["lines"][0]
        self.assertTrue(row["tts"]["voice"].startswith("旁白@"), row)
        self.assertTrue((d / "voices" / f"{row['tts']['voice']}.wav").exists())
        self.assertTrue(0.4 < row["dur_raw"] < 8, row)
        self.assertIn("候选相似度", r.stdout)                                               # 3 个候选里挑了一个


if __name__ == "__main__":
    unittest.main()
