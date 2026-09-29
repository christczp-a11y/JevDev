"""慢测试（SLOW=1 才跑）：把 17 秒小样的镜头重复 10 遍拼成约 3 分钟的整集，测整集高清的速度（验收 ④：≤ 15 分钟），同时检查长片的响度和背景音乐循环。
    SLOW=1 bash video/motion/tests/run_all.sh          （只跑这个：SLOW=1 bash video/motion/tests/run_all.sh test_long）"""
import copy
import json
import os
import shutil
import unittest

import common

REPEAT = 10


def walk(o, shift):
    if isinstance(o, dict):
        if "line" in o and isinstance(o["line"], int):
            o["line"] += shift
        for v in o.values():
            walk(v, shift)
    elif isinstance(o, list):
        for v in o:
            walk(v, shift)


def make_long():
    d = common.fresh("long")
    src = common.PROTO
    for sub in ("gen", "fx", "sfx"):
        shutil.copytree(src / sub, d / sub)
    (d / "voice").mkdir()
    tl = json.loads((src / "voice" / "timeline.json").read_text(encoding="utf-8"))
    for f in (src / "voice").glob("*.mp3"):
        shutil.copy(f, d / "voice" / f.name)
    n, dur = len(tl["lines"]), tl["duration"]
    lines = []
    for k in range(REPEAT):
        for ln in tl["lines"]:
            x = copy.deepcopy(ln)
            x["t0"], x["t1"] = round(x["t0"] + dur * k, 3), round(x["t1"] + dur * k, 3)
            lines.append(x)
    for i, ln in enumerate(lines):
        ln["i"] = i
    (d / "voice" / "timeline.json").write_text(json.dumps({"duration": round(dur * REPEAT, 3), "lines": lines}, ensure_ascii=False), encoding="utf-8")
    sb = json.loads((src / "storyboard.json").read_text(encoding="utf-8"))
    shots = []
    for k in range(REPEAT):
        for s in sb["shots"]:
            s2 = copy.deepcopy(s)
            s2["id"] = f"{k}-{s['id']}"
            walk(s2, n * k)
            shots.append(s2)
    sb["shots"], sb["voice"], sb["episode"] = shots, str(d / "voice"), "long3min"
    (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
    return d


@unittest.skipUnless(os.environ.get("SLOW") == "1", "慢测试：SLOW=1 才跑")
class TestLong(unittest.TestCase):
    def test_three_minutes_hd_within_15_minutes(self):
        common.ensure_proto_assets()
        d = make_long()
        code, log, rep = common.render(d / "storyboard.json", d / "out", d / "cache")
        print("\n整集高清：", rep["frames"], "帧，", rep["duration"], "秒；用时", rep["timing"])
        self.assertEqual(code, 0, log)
        self.assertGreaterEqual(rep["duration"], 170)
        self.assertLessEqual(rep["timing"]["total_sec"], 15 * 60, rep["timing"])
        self.assertTrue(rep["checks"]["loudness"]["ok"], rep["checks"]["loudness"])     # 背景音乐（180 秒）循环也稳在 −16 LUFS

    def test_preview_speed_over_30_seconds(self):
        d = common.OUT / "long"
        if not (d / "storyboard.json").exists():
            common.ensure_proto_assets()
            d = make_long()
        code, log, rep = common.render(d / "storyboard.json", d / "out_prev", d / "cache_prev", "--preview")
        print("\n预览：", rep["duration"], "秒；用时", rep["timing"])
        self.assertEqual(code, 0, log)
        self.assertLessEqual(rep["timing"]["sec_per_30s_video"], 60)


if __name__ == "__main__":
    unittest.main()
