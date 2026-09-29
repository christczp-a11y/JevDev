"""出片的端到端测试（用 17 秒小样的分镜表 proto17 和特性覆盖用例 feature_case，预览分辨率，各渲一两遍）。
验收：① 同样输入渲两次，每一帧的哈希一致；② 字幕出现的时间和时间线差 ≤ 1 帧；④ 速度；还有 --shots 裁剪、缓存、响度和人声检查、编码颜色。"""
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import cv2
import numpy as np

import common
from engine import consts as C
from engine.timeline import Timeline

A = B = FEAT = None


def setUpModule():
    global A, B, FEAT
    common.ensure_proto_assets()
    out_a, out_b = common.fresh("it_a"), common.fresh("it_b")
    A = common.render(common.PROTO / "storyboard.json", out_a, out_a / "cache", "--preview", "--frame-hashes")
    B = common.render(common.PROTO / "storyboard.json", out_b, out_b / "cache", "--preview", "--frame-hashes")
    out_f = common.fresh("it_feat")
    FEAT = common.render(common.FEATURE / "storyboard.json", out_f, out_f / "cache", "--preview", "--frame-hashes")


def frames(path):
    cap = cv2.VideoCapture(str(path))
    while True:
        ok, f = cap.read()
        if not ok:
            return
        yield f


class TestOutput(unittest.TestCase):
    def test_render_succeeds_and_checks_pass(self):
        code, log, rep = A
        self.assertEqual(code, 0, log)
        self.assertTrue(rep["ok"], rep["checks"])
        self.assertEqual(rep["frames"], 516)
        self.assertEqual([len(rep["checks"][k]["events"]) for k in ("flicker", "static")], [0, 0])
        self.assertEqual(rep["checks"]["voice"]["lines"], 5)

    def test_loudness_and_peak(self):
        lo = A[2]["checks"]["loudness"]
        self.assertAlmostEqual(lo["lufs"], C.LUFS_TARGET, delta=C.LUFS_TOL)
        self.assertLessEqual(lo["true_peak_db"], C.PEAK_MAX_DB)

    def test_output_video_format(self):
        mp4 = Path(A[2]["out"])
        cap = cv2.VideoCapture(str(mp4))
        self.assertEqual((int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))), (540, 960))
        self.assertAlmostEqual(cap.get(cv2.CAP_PROP_FPS), 30.0, places=2)
        self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 516)
        self.assertAlmostEqual(common.ffprobe_duration(mp4, "a:0"), 17.2, delta=0.06)

    def test_speed_preview(self):
        """④ 本机预览每 30 秒成片 ≤ 60 秒（从空缓存开始，含渲镜头、混音、拼接、编码、检查）。"""
        t = A[2]["timing"]
        self.assertEqual(t["cached_shots"], 0)
        self.assertLessEqual(t["sec_per_30s_video"], 60, t)


class TestDeterminism(unittest.TestCase):
    def test_frame_hashes_identical_across_two_clean_renders(self):
        """① 两次都从空缓存开始，每一帧（合成完字幕之后）的哈希一致。"""
        ha, hb = A[2]["frame_hashes"], B[2]["frame_hashes"]
        self.assertEqual(len(ha), 516)
        self.assertEqual(ha, hb)

    def test_encoded_files_identical(self):
        def md5(p):
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "framemd5", "-"], capture_output=True, text=True)
            return hashlib.md5(r.stdout.encode()).hexdigest()
        self.assertEqual(md5(A[2]["out"]), md5(B[2]["out"]))

    def test_shot_cache_frame_hashes_identical(self):
        def all_hashes(cache):
            return {json.loads(p.read_text())["id"]: json.loads(p.read_text())["hashes"] for p in Path(cache).glob("*/meta.json")}
        ha, hb = all_hashes(common.OUT / "it_a" / "cache"), all_hashes(common.OUT / "it_b" / "cache")
        self.assertEqual(sorted(ha), ["1-1", "1-2", "1-3", "1-4", "1-5", "1-6"])
        self.assertEqual(ha, hb)

    def test_feature_case_reproducible_too(self):
        code, log, rep = FEAT
        self.assertEqual(code, 0, log)
        out_f = common.fresh("it_feat2")
        code2, log2, rep2 = common.render(common.FEATURE / "storyboard.json", out_f, out_f / "cache", "--preview", "--frame-hashes")
        self.assertEqual(code2, 0, log2)
        self.assertEqual(rep["frame_hashes"], rep2["frame_hashes"])


class TestSubtitleTiming(unittest.TestCase):
    def test_subtitles_appear_within_one_frame_of_timeline(self):
        """② 用「成片 − 没有字幕的场景缓存帧」在字幕区域的差来判断字幕有没有出现，和时间线的 t0 比较。"""
        cache = common.OUT / "it_a" / "cache"
        scene = {}                                     # 绝对帧号 → 场景帧（没有字幕）
        for meta_p in cache.glob("*/meta.json"):
            meta = json.loads(meta_p.read_text())
            for i, fr in enumerate(frames(meta_p.parent / "video.mp4")):
                scene[meta["first_frame"] + i] = fr
        tl = Timeline.load(common.PROTO / "voice")
        energy = []
        for n, fr in enumerate(frames(A[2]["out"])):
            band = slice(int(1280 * .5), int(1700 * .5))
            d = np.abs(fr[band].astype(np.int16) - scene[n][band].astype(np.int16)).max(axis=2)
            energy.append(float(d.mean()))                    # 字幕区域里「成片和无字幕场景」的平均差
        energy = np.array(energy)
        rise = np.r_[np.zeros(3), energy[3:] - energy[:-3]]      # 和 3 帧前比：字幕淡入的第一帧就会跳上去（淡入 3 帧，第一帧透明度 1/3）
        checked = 0
        for i, ln in enumerate(tl.lines):
            if not tl.is_speech(i):
                continue
            f_t0 = ln["t0"] * C.FPS
            first = next(f for f in range(int(f_t0) - 6, len(rise)) if rise[f] > 1.5)
            self.assertLessEqual(abs(first - f_t0), 1.0, f"第 {i} 句：字幕第一次出现在第 {first} 帧，时间线 t0 = 第 {f_t0:.1f} 帧")
            checked += 1
        self.assertEqual(checked, 5)


class TestShotSubset(unittest.TestCase):
    def run_subset(self, shots, name):
        out = common.fresh(name)
        code, log, rep = common.render(common.PROTO / "storyboard.json", out, common.OUT / "it_a" / "cache", "--preview", "--shots", shots)
        return code, log, rep

    def test_straddling_timeline_line(self):
        """PITFALLS A6：只渲 1-4（10.5–13.2 秒），第 5 句台词（10.8–16.2 秒）比画面长，不许崩，音频长度 = 画面长度。"""
        code, log, rep = self.run_subset("1-4", "sub_a")
        self.assertEqual(code, 0, log)
        self.assertEqual(rep["frames"], 396 - 315)
        self.assertEqual(rep["shots"], ["1-4"])
        self.assertAlmostEqual(common.ffprobe_duration(rep["out"], "a:0"), 81 / 30, delta=0.06)
        self.assertEqual(rep["timing"]["rendered_shots"], 0)       # 完全用了缓存

    def test_non_contiguous_shots(self):
        code, log, rep = self.run_subset("1-1,1-3", "sub_b")
        self.assertEqual(code, 0, log)
        self.assertEqual(rep["frames"], 148 + 96)
        self.assertEqual(rep["checks"]["voice"]["lines"], 4)       # 第 0、1、3、4 句在范围里；台词跨在边界上的也算

    def test_first_shot_only_and_last_shot_only(self):
        for shots, frames_ in (("1-1", 148), ("1-6", 57)):
            code, log, rep = self.run_subset(shots, "sub_" + shots)
            self.assertEqual(code, 0, log)
            self.assertEqual(rep["frames"], frames_)

    def test_subset_frames_equal_full_render_frames(self):
        """只渲 1-3 出来的每一帧，和整集里同一时段的每一帧完全一样（缓存、字幕、镜头运动都按绝对时间算）。"""
        out = common.fresh("sub_c")
        code, log, rep = common.render(common.PROTO / "storyboard.json", out, common.OUT / "it_a" / "cache", "--preview", "--shots", "1-3", "--frame-hashes")
        self.assertEqual(code, 0, log)
        self.assertEqual(rep["frame_hashes"], A[2]["frame_hashes"][219:315])


class TestCache(unittest.TestCase):
    def test_second_run_uses_cache_and_editing_one_shot_rerenders_only_it(self):
        d = common.fresh("it_cache")
        cache = d / "cache"
        shutil.copytree(common.PROTO, d / "p17", ignore=shutil.ignore_patterns("voice"))
        sb_path = d / "p17" / "storyboard.json"
        code, log, rep = common.render(sb_path, d, cache, "--preview")
        self.assertEqual((code, rep["timing"]["rendered_shots"]), (0, 6), log)
        code, log, rep2 = common.render(sb_path, d, cache, "--preview")
        self.assertEqual((rep2["timing"]["rendered_shots"], rep2["timing"]["cached_shots"]), (0, 6))
        self.assertLess(rep2["timing"]["render_sec"], 1.0)
        sb = json.loads(sb_path.read_text(encoding="utf-8"))
        sb["shots"][4]["grade"] = "gold"
        sb_path.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        code, log, rep3 = common.render(sb_path, d, cache, "--preview")
        self.assertEqual((rep3["timing"]["rendered_shots"], rep3["timing"]["cached_shots"]), (1, 5))


class TestErrorsExitCode(unittest.TestCase):
    def test_missing_asset_exits_2_and_writes_no_video(self):
        sb = json.loads((common.FEATURE / "storyboard.json").read_text(encoding="utf-8"))
        sb["shots"][0]["bg"][0]["img"] = "sets/nope/missing.png"
        d = common.fresh("it_bad")
        p = d / "storyboard.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        code, log, rep = common.render(p, d / "out", d / "cache", "--preview")
        self.assertEqual(code, 2)
        self.assertIn("找不到素材", log)
        self.assertEqual(list((d / "out").glob("*.mp4")) if (d / "out").exists() else [], [])

    def test_failing_check_exits_1(self):
        """一个静止的镜头（没有推拉、没有人物、只有天空）→ 静止 > 1.5 秒 → 退出码 1，报告里写明。"""
        d = common.fresh("it_static")
        sb = {"episode": "static_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice",
              "shots": [{"id": "s1", "from": {"line": 0, "dt": -0.3}, "bg": [{"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080}],
                         "camera": [{"move": "push", "amount": 0.0}]}]}
        p = d / "storyboard.json"
        p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        code, log, rep = common.render(p, d / "out", d / "cache", "--preview")
        self.assertEqual(code, 1, log)
        self.assertFalse(rep["ok"])
        self.assertFalse(rep["checks"]["static"]["ok"])
        self.assertGreaterEqual(len(rep["checks"]["static"]["events"]), 1)


class TestEncodeColor(unittest.TestCase):
    def test_cache_roundtrip_keeps_colors(self):
        """缓存镜头（BGR → bt709 YUV420 → 解回 BGR）的颜色误差要小：纸色、印章红、墨色。"""
        from engine.worker import cache_enc_cmd
        d = common.fresh("it_color")
        w, h = 540, 960
        img = np.zeros((h, w, 3), np.uint8)
        img[:, :] = (200, 220, 230)                                  # 纸色（BGR）
        img[100:400, 50:250] = (45, 55, 200)                         # 红
        img[500:800, 300:500] = (32, 35, 42)                         # 墨
        img[100:400, 300:500] = (91, 125, 47)                        # 绿
        enc = subprocess.Popen(cache_enc_cmd(w, h, d / "c.mp4"), stdin=subprocess.PIPE)
        for _ in range(5):
            enc.stdin.write(img.data)
        enc.stdin.close()
        self.assertEqual(enc.wait(), 0)
        from render import ShotReader
        r = ShotReader(d / "c.mp4", 0, w, h)
        out = r.get(2)
        r.close()
        for name, sl in (("纸", (slice(600, 900), slice(20, 200))), ("红", (slice(150, 350), slice(80, 220))), ("墨", (slice(520, 780), slice(320, 480))),
                         ("绿", (slice(150, 350), slice(330, 480)))):
            err = np.abs(out[sl].astype(int) - img[sl].astype(int)).mean()
            self.assertLess(err, 3.0, f"{name} 色平均误差 {err:.2f}")


if __name__ == "__main__":
    unittest.main()
