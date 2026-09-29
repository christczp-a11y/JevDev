"""仪式录音（第 0 步第 6 项第 1 条）：字面完全相同的两句直接用系列录音、不合成；近似写法警告（A5）；系列声音改了录音没重录、
录音文件被改过（sha256）都报错；--make-series-voices、--make-ceremony 不覆盖已有的。离线（假合成，或者干脆禁止合成）。"""
import json
import unittest

from harness import REAL_VOICES, ROOT, copy_series_voices, make_case, read_log, run_voice, sha1, sha256, timeline, workdir

ASSETS = ROOT / "video" / "assets"
SERIES = ROOT / "video" / "series_voice.json"
CFG = json.loads(SERIES.read_text(encoding="utf-8"))
KAO, XIE = "考考你！", "写书的人，来了——"
F_KAO, F_XIE = CFG["ceremony"][0]["file"], CFG["ceremony"][1]["file"]
# 仪式录音用哪个参考音：语气和角色默认语气一样就是角色本身，不一样就是语气变体（09-29 起「考考你」用司马光默认声音）
VARIANTS = [c for c in CFG["ceremony"] if "".join(ch for ch in c["tone"] if ch.isalnum()) != "".join(ch for ch in CFG["characters"][c["who"]]["tone"] if ch.isalnum())]


def tree(p):
    return {x.name: sha256(x) for x in p.rglob("*") if x.is_file()}


class Ceremony(unittest.TestCase):
    def test_exact_lines_use_series_recordings_without_synthesizing(self):
        d = workdir("cer_exact")
        s = make_case(d, [("司马光", KAO), ("动作", ""), ("旁白", XIE)])
        r = run_voice(s, d / "out", synth="none", log=d / "spy.jsonl")     # 一调用 worker 就报错
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(read_log(d / "spy.jsonl"), [])
        rows = [x for x in timeline(d / "out")["lines"] if x["audio"]]
        self.assertEqual([x["series_audio"] for x in rows], [F_KAO, F_XIE])       # timeline 里标出用的是系列录音
        self.assertEqual([x["tts"]["from"] for x in rows], ["系列录音", "系列录音"])
        self.assertEqual([x["tts"]["tone"] for x in rows], [c["tone"] for c in CFG["ceremony"]])   # 记着录音用的语气
        self.assertEqual([x["tts"]["voice"].startswith(c["who"] + "@") for x, c in zip(rows, CFG["ceremony"])], [c in VARIANTS for c in CFG["ceremony"]])   # 语气不同才用语气变体的参考音
        self.assertEqual(sha1(d / "out" / rows[0]["audio"]), sha1(ASSETS / F_KAO))  # NN.mp3 就是系列录音
        self.assertEqual(sha1(d / "out" / rows[1]["audio"]), sha1(ASSETS / F_XIE))
        self.assertEqual(list((d / "out" / "cache").glob("*.mp3")), [])              # 不进缓存
        self.assertEqual(timeline(d / "out")["warnings"]["ceremony_near"], [])       # 一字不差，不警告

    def test_near_miss_warns_and_is_synthesized(self):
        d = workdir("cer_near")
        lines = [("司马光", KAO), ("旁白", "写书的人，来了。"), ("旁白", "这个故事，写在《资治通鉴》里。" + XIE),
                 ("旁白", KAO), ("司马光", "考考你"), ("旁白", "考你：商鞅会怎么办？"), ("旁白", XIE)]
        s = make_case(d, lines)
        r = run_voice(s, d / "out", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stderr)
        warns = timeline(d / "out")["warnings"]["ceremony_near"]
        self.assertEqual(len(warns), 4, warns)
        joined = "\n".join(warns)
        self.assertIn("lines[1]（旁白）「写书的人，来了。」", joined)
        self.assertIn("去掉标点后和仪式句一样", joined)
        self.assertIn("lines[2]（旁白）", joined)
        self.assertIn("这句话里含有仪式句", joined)
        self.assertIn("lines[3]（旁白）「考考你！」", joined)
        self.assertIn("说话人是旁白，仪式句是司马光说的", joined)
        self.assertIn("lines[4]（司马光）「考考你」", joined)
        self.assertNotIn("lines[0]", joined)                   # 一字不差的不警告
        self.assertNotIn("lines[5]", joined)                   # 「考你」不是「考考你」
        self.assertNotIn("lines[6]", joined)
        self.assertEqual(r.stdout.count("很像："), 4)
        log = read_log(d / "spy.jsonl")                        # 近似写法照常合成，真仪式句不合成
        synthesized = {x["text"] for x in log}
        self.assertIn("写书的人，来了。", synthesized)
        self.assertNotIn(KAO, {x["text"] for x in log if x["voice"].startswith("司马光")})
        self.assertNotIn(XIE, {x["text"] for x in log if x["voice"] == "旁白"} - {"这个故事，写在《资治通鉴》里。" + XIE})

    def test_voice_text_or_tone_on_ceremony_line_errors(self):
        d = workdir("cer_vt")
        s = make_case(d, [("司马光", KAO)], voice_text={KAO: "考考你"}, tone={KAO: "开心"})
        r = run_voice(s, d / "out")
        self.assertEqual(r.returncode, 1)
        self.assertIn("不许写配音用的文字", r.stderr)
        self.assertIn("不许写语气", r.stderr)

    def test_series_voice_changed_but_recording_not_remade_errors(self):
        """系列声音的描述改了：已存的参考音对不上，报错（要先问 Chris）。"""
        d = workdir("cer_stale")
        cfg = json.loads(SERIES.read_text(encoding="utf-8"))
        cfg["characters"]["旁白"]["desc"] += "语速稍快。"
        (d / "series.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        s = make_case(d, [("旁白", "从前。")])
        r = run_voice(s, d / "out", series=d / "series.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("参考音是按另一份声音描述设计的", r.stderr)
        self.assertIn("系列声音（旁白、司马光）要先问 Chris", r.stderr)

    def test_reference_replaced_but_recording_not_remade_errors(self):
        """仪式录音是用另一段参考音录的（ref_sha256 对不上）：报错，要先问 Chris、重录。"""
        d = workdir("cer_ref_sha")
        cfg = json.loads(SERIES.read_text(encoding="utf-8"))
        cfg["ceremony"][0]["ref_sha256"] = "0" * 64
        (d / "series.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        s = make_case(d, [("旁白", "从前。")])
        r = run_voice(s, d / "out", series=d / "series.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("是用 sha256 为", r.stderr)
        self.assertIn("先问 Chris", r.stderr)

    def test_recording_file_changed_sha256_errors(self):
        """series_voice.json 的 files 里登记的 sha256 和文件对不上（文件被改过）→ 报错；没登记 → 也报错。参考音也在登记表里。"""
        d = workdir("cer_sha")
        cfg = json.loads(SERIES.read_text(encoding="utf-8"))
        self.assertEqual(cfg["files"][F_KAO], sha256(ASSETS / F_KAO))            # 现在登记的和文件一致
        self.assertEqual(cfg["files"]["audio/sgm_pop.wav"], sha256(ASSETS / "audio" / "sgm_pop.wav"))
        for who in ("旁白", "司马光"):
            self.assertEqual(cfg["files"][f"audio/voices/{who}.wav"], sha256(REAL_VOICES / f"{who}.wav"))
        s = make_case(d, [("旁白", "从前。")])
        bad = json.loads(json.dumps(cfg)); bad["files"][F_KAO] = "0" * 64
        (d / "series_bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        r = run_voice(s, d / "out", series=d / "series_bad.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("文件被改过", r.stderr)
        self.assertIn(F_KAO.split("/")[-1], r.stderr)
        miss = json.loads(json.dumps(cfg)); del miss["files"][F_XIE]
        (d / "series_miss.json").write_text(json.dumps(miss, ensure_ascii=False), encoding="utf-8")
        r = run_voice(s, d / "out", series=d / "series_miss.json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("没有登记", r.stderr)

    def test_make_ceremony_never_overwrites_without_force(self):
        """--make-ceremony 在临时 assets 目录里：第一次录、打印要登记的 sha256；再跑不覆盖；--force 才重录。不动真的系列录音。"""
        d = workdir("cer_make")
        before = tree(ASSETS / "audio")
        voices = copy_series_voices(d / "assets" / "audio" / "voices")
        # 1. 空的 assets：录两段（假合成），打印的 sha256 就是文件的
        r = run_voice("--make-ceremony", assets=d / "assets", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(read_log(d / "spy.jsonl")), 2)
        files = {}
        for c in CFG["ceremony"]:
            files[c["file"]] = sha256(d / "assets" / c["file"])
            self.assertIn(f'"{c["file"]}": "{files[c["file"]]}"', r.stdout)
            self.assertIn(f'"{c["ref_sha256"]}"', r.stdout)                      # 参考音没变，ref_sha256 就是登记的那个
        # 2. 已有：不覆盖，不合成
        r = run_voice("--make-ceremony", assets=d / "assets", log=d / "spy2.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("不重录"), 2)
        self.assertEqual(read_log(d / "spy2.jsonl"), [])
        # 3. --force：重录
        r = run_voice("--make-ceremony", "--force", assets=d / "assets", log=d / "spy3.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(read_log(d / "spy3.jsonl")), 2)
        # 4. 录音文件被改过（多了一个字节）：正常配音报错；--make-ceremony 只说「不重录」
        with open(d / "assets" / F_KAO, "ab") as f:
            f.write(b"\x00")
        cfg = json.loads(SERIES.read_text(encoding="utf-8"))
        cfg["files"].update(files)
        (d / "series.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        s = make_case(d, [("旁白", "从前。")])
        r = run_voice(s, d / "out", series=d / "series.json", assets=d / "assets", voices=voices)
        self.assertEqual(r.returncode, 1)
        self.assertIn("文件被改过", r.stderr)
        r = run_voice("--make-ceremony", assets=d / "assets")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count("不重录"), 2)
        # 真的系列录音、参考音一个字节都没动
        self.assertEqual(before, tree(ASSETS / "audio"))

    def test_make_series_voices_designs_missing_and_never_overwrites_without_force(self):
        """--make-series-voices：空的参考音目录 → 设计旁白、司马光的默认参考音（各 1 个候选）和仪式录音用的语气变体（各 3 个候选，基准是默认参考音）；
        打印要登记的 sha256；再跑不覆盖；描述对不上就报错；--force 才重做。"""
        d = workdir("cer_series_voices")
        before = tree(REAL_VOICES)
        empty = d / "assets" / "audio" / "voices"
        empty.mkdir(parents=True)
        r = run_voice("--make-series-voices", assets=d / "assets", log=d / "spy.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        design = read_log(d / "spy.jsonl", "design")
        self.assertEqual(sorted(x["id"] for x in design if "@" not in x["id"]), ["司马光", "旁白"])
        variants = [x for x in design if "@" in x["id"]]
        self.assertEqual(len(variants), len(VARIANTS))
        self.assertEqual({(x["n"], x["anchor"][0] if x["anchor"] else None) for x in variants}, {(3, c["who"][0]) for c in VARIANTS})
        self.assertLess(min(i for i, x in enumerate(design) if "@" not in x["id"]), min(i for i, x in enumerate(design) if "@" in x["id"]))   # 默认参考音先于变体
        for x in design:
            self.assertIn(f'"audio/voices/{x["id"]}.wav": "{sha256(empty / (x["id"] + ".wav"))}"', r.stdout)
        # 已有：不覆盖
        r = run_voice("--make-series-voices", assets=d / "assets", log=d / "spy2.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("不重做", r.stdout)
        self.assertEqual(read_log(d / "spy2.jsonl", "design"), [])
        # 描述和已存的对不上：报错，不动
        meta = json.loads((empty / "旁白.json").read_text(encoding="utf-8"))
        meta["desc"] = "别的描述"
        (empty / "旁白.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        r = run_voice("--make-series-voices", assets=d / "assets")
        self.assertEqual(r.returncode, 1)
        self.assertIn("对不上", r.stderr)
        # --force：全部重做
        r = run_voice("--make-series-voices", "--force", assets=d / "assets", log=d / "spy3.jsonl")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(read_log(d / "spy3.jsonl", "design")), 2 + len(VARIANTS))   # 两个默认参考音 + 语气变体
        self.assertEqual(before, tree(REAL_VOICES))              # 真的参考音一个字节都没动


if __name__ == "__main__":
    unittest.main()
