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


_LONG = None


def long_dir():
    """这一轮测试用的 3 分钟分镜表目录：第一次要用时按现在的小样重新生成（不复用上一轮留下的，小样改了就不对了）。"""
    global _LONG
    if _LONG is None:
        common.ensure_proto_assets()
        _LONG = make_long()
    return _LONG


@unittest.skipUnless(os.environ.get("SLOW") == "1", "慢测试：SLOW=1 才跑")
class TestLong(unittest.TestCase):
    def test_three_minutes_hd_within_15_minutes(self):
        d = long_dir()
        code, log, rep = common.render(d / "storyboard.json", d / "out", d / "cache")
        print("\n整集高清：", rep["frames"], "帧，", rep["duration"], "秒；用时", rep["timing"])
        self.assertEqual(code, 0, log)
        self.assertGreaterEqual(rep["duration"], 170)
        self.assertLessEqual(rep["timing"]["total_sec"], 15 * 60, rep["timing"])
        self.assertTrue(rep["checks"]["loudness"]["ok"], rep["checks"]["loudness"])     # 背景音乐（180 秒）循环也稳在 −16 LUFS
        self.edit_and_rerender(d, "", 120)

    def edit_and_rerender(self, d, mode, limit):
        """截段：整集渲完以后改 1 个镜头、再改 2 个镜头，只有这几个片段重编码，总耗时 ≤ limit 秒（不含第一次）。"""
        sb_path = d / "storyboard.json"
        sb0 = json.loads(sb_path.read_text(encoding="utf-8"))
        args = [mode] if mode else []
        out, cache = d / ("out" + mode.replace("--", "_")), d / ("cache" + mode.replace("--", "_"))
        for idx_list in ([30], [12, 45]):
            sb = json.loads(json.dumps(sb0))
            for i in idx_list:
                sb["shots"][i]["grade"] = "gold" if sb["shots"][i].get("grade") != "gold" else "cool"
            sb_path.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
            code, log, rep = common.render(sb_path, out, cache, *args)
            print(f"\n改 {len(idx_list)} 个镜头（{mode or '默认'}）：", rep["timing"])
            self.assertEqual(code, 0, log)
            self.assertEqual(rep["timing"]["rendered_shots"], len(idx_list), rep["timing"])
            self.assertLessEqual(rep["timing"]["total_sec"], limit, rep["timing"])
        sb_path.write_text(json.dumps(sb0, ensure_ascii=False), encoding="utf-8")

    def test_final_edit_one_shot_is_not_a_full_reencode(self):
        """--final 发布版也走截段：第一次整集（慢编码）渲好以后，改 1–2 个镜头重出发布版不再整片重编码。"""
        d = long_dir()
        code, log, rep = common.render(d / "storyboard.json", d / "out_final", d / "cache_final", "--final")
        print("\n整集发布版：", rep["duration"], "秒；用时", rep["timing"])
        self.assertEqual(code, 0, log)
        self.assertLessEqual(rep["timing"]["total_sec"], 15 * 60, rep["timing"])
        self.edit_and_rerender(d, "--final", 150)

    def test_preview_speed_over_30_seconds(self):
        d = long_dir()
        code, log, rep = common.render(d / "storyboard.json", d / "out_prev", d / "cache_prev", "--preview")
        print("\n预览：", rep["duration"], "秒；用时", rep["timing"])
        self.assertEqual(code, 0, log)
        self.assertLessEqual(rep["timing"]["sec_per_30s_video"], 60)


if __name__ == "__main__":
    unittest.main()
