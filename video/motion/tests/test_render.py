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

    def test_segment_cache_frame_hashes_identical(self):
        def all_hashes(cache):
            metas = [json.loads(p.read_text()) for p in Path(cache).glob("seg/*/meta.json")]
            return {(m["id"], m["f0"]): m["hashes"] for m in metas}                # 镜头可能切成几块，按（镜头号，起帧）对
        ha, hb = all_hashes(common.OUT / "it_a" / "cache"), all_hashes(common.OUT / "it_b" / "cache")
        self.assertEqual(sorted({k[0] for k in ha}), ["1-1", "1-2", "1-3", "1-4", "1-5", "1-6"])
        self.assertEqual(sum(len(v) for v in ha.values()), 516)
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
        """② 用「成片 − 同样编码的没有字幕的画面」在字幕区域的差来判断字幕有没有出现，和时间线的 t0 比较。"""
        from engine import segment
        from engine.plan import build_plan
        plan = build_plan(common.PROTO / "storyboard.json", scale=0.5, mode="preview")
        d = common.fresh("it_sub_ref")
        ref = subprocess.Popen(segment.encode_cmd(540, 960, "preview", d / "noui.mp4"), stdin=subprocess.PIPE)      # 同样的画面、同样的编码参数，只是没有字幕、标题条、水印
        for sp in plan.shots:
            for f, fr in segment.iter_segment(segment.make_job(plan, sp, common.OUT / "it_a" / "cache", "preview"), with_ui=False):
                ref.stdin.write(fr.data)
        ref.stdin.close()
        self.assertEqual(ref.wait(), 0)
        band = slice(int(1300 * .5), int(1700 * .5))
        scene = [fr[band].copy() for fr in frames(d / "noui.mp4")]           # 只留字幕区那一条（整片原图太占内存）
        tl = Timeline.load(common.PROTO / "voice")
        energy = []
        for n, fr in enumerate(frames(A[2]["out"])):
            dd = np.abs(fr[band].astype(np.int16) - scene[n].astype(np.int16)).max(axis=2)
            energy.append(float(dd.mean()))                   # 字幕区域里「成片和无字幕画面」的平均差
        energy = np.array(energy)
        rise = np.r_[np.zeros(3), energy[3:] - energy[:-3]]      # 和 3 帧前比：字幕淡入的第一帧就会跳上去（淡入 3 帧，第一帧透明度 1/3）
        checked, devs = 0, []
        for i, ln in enumerate(tl.lines):
            if not tl.is_speech(i):
                continue
            f_t0 = ln["t0"] * C.FPS
            first = next(f for f in range(int(f_t0) - 6, len(rise)) if rise[f] > 1.5)
            devs.append(first - f_t0)
            self.assertLessEqual(abs(first - f_t0), 1.0, f"第 {i} 句：字幕第一次出现在第 {first} 帧，时间线 t0 = 第 {f_t0:.1f} 帧")
            checked += 1
        self.assertEqual(checked, 5)
        print("字幕出现帧 − 时间线 t0（帧）：", [round(d, 1) for d in devs])

    def test_subtitle_card_bottom_is_at_1615_for_one_and_two_lines(self):
        """M6：字幕卡底边贴着平台遮挡区上沿 y 1615，一行、两行都从底边往上长（说话人标签跟着卡片走）。"""
        from engine import segment
        from engine.plan import build_plan
        plan = build_plan(common.PROTO / "storyboard.json", scale=0.5, mode="preview")
        cache = common.OUT / "it_a" / "cache"
        boxes = {}
        for sid, f in (("1-1", 90), ("1-4", 350)):            # 第 54–100 帧是一行字幕「要地，给不给？」，第 324 帧起是两行字幕
            sp = next(s for s in plan.shots if s.id == sid)
            job = segment.make_job(plan, sp, cache, "preview")
            ui_frame = scene = None
            for g, fr in segment.iter_segment(job, with_ui=True):
                if g == f:
                    ui_frame = fr.copy()
                    break
            for g, fr in segment.iter_segment(job, with_ui=False):
                if g == f:
                    scene = fr.copy()
                    break
            d = np.abs(ui_frame.astype(np.int16) - scene.astype(np.int16)).max(axis=2)
            d[:int(1250 * .5)] = 0                             # 只看字幕区（标题条、水印在上面）
            ys, xs = np.where(d > 30)
            boxes[sid] = (ys.min() * 2, ys.max() * 2 + 1, xs.min() * 2, xs.max() * 2 + 1)
        for sid, (y0, y1, x0, x1) in boxes.items():
            self.assertAlmostEqual(y1, C.SUB_BOTTOM_Y, delta=6, msg=f"{sid} 字幕卡底边 {y1}")
            self.assertLessEqual(y1, 1620)                      # 不压平台遮挡区
        self.assertLess(boxes["1-4"][0], boxes["1-1"][0] - 40)  # 两行的比一行的往上多长了一截
        self.assertLess(boxes["1-1"][0], boxes["1-1"][1] - 90)


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
    def test_segment_roundtrip_keeps_colors(self):
        """片段（BGR → bt709 YUV420 → 解回 BGR）的颜色误差要小：纸色、印章红、墨色、绿。"""
        from engine.segment import encode_cmd
        d = common.fresh("it_color")
        w, h = 540, 960
        img = np.zeros((h, w, 3), np.uint8)
        img[:, :] = (200, 220, 230)                                  # 纸色（BGR）
        img[100:400, 50:250] = (45, 55, 200)                         # 红
        img[500:800, 300:500] = (32, 35, 42)                         # 墨
        img[100:400, 300:500] = (91, 125, 47)                        # 绿
        enc = subprocess.Popen(encode_cmd(w, h, "normal", d / "c.mp4"), stdin=subprocess.PIPE)
        for _ in range(5):
            enc.stdin.write(img.data)
        enc.stdin.close()
        self.assertEqual(enc.wait(), 0)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(d / "c.mp4"), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        out = np.frombuffer(raw, np.uint8).reshape(h, w, 3)                  # 用 ffmpeg 命令行解码（认 bt709 标签；cv2 自带的解码会按 bt601 算）
        for name, sl in (("纸", (slice(600, 900), slice(20, 200))), ("红", (slice(150, 350), slice(80, 220))), ("墨", (slice(520, 780), slice(320, 480))),
                         ("绿", (slice(150, 350), slice(330, 480)))):
            err = np.abs(out[sl].astype(int) - img[sl].astype(int)).mean()
            self.assertLess(err, 3.0, f"{name} 色平均误差 {err:.2f}")


class TestStitch(unittest.TestCase):
    """截段拼接（concat 拷贝流）：逐帧和「整片一次编码」对比。拼接点不许跳帧、重复帧、黑帧，音画不许错位。"""

    @classmethod
    def setUpClass(cls):
        from engine import segment
        from engine.plan import build_plan
        cls.plan = build_plan(common.PROTO / "storyboard.json", scale=0.5, mode="preview")
        d = common.fresh("it_stitch")
        w, h = 540, 960
        ref = subprocess.Popen(segment.encode_cmd(w, h, "preview", d / "single.mp4"), stdin=subprocess.PIPE)   # 整片一次编码：同样的参数，同样的画面
        cls.raw = []                                                       # 每一帧的 1/4 缩小图（对比用，整片原图太占内存）
        for sp in cls.plan.shots:
            for f, fr in segment.iter_segment(segment.make_job(cls.plan, sp, common.OUT / "it_a" / "cache", "preview")):
                ref.stdin.write(fr.data)
                cls.raw.append(cv2.resize(fr, (135, 240), interpolation=cv2.INTER_AREA))
        ref.stdin.close()
        assert ref.wait() == 0
        cls.single = d / "single.mp4"

    @staticmethod
    def small(path):
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=135:240:flags=area", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
        return np.frombuffer(p.stdout, np.uint8).reshape(-1, 240, 135, 3)

    def test_frame_by_frame_equal_to_single_pass_encode(self):
        cat = self.small(A[2]["out"])
        one = self.small(self.single)
        n = len(self.raw)
        self.assertEqual((len(cat), len(one)), (n, n))                       # 一帧不多、一帧不少
        raw = np.stack(self.raw).astype(np.float32)
        e_cat = np.abs(cat.astype(np.float32) - raw).mean(axis=(1, 2, 3))     # 每一帧和原始画面差多少
        e_one = np.abs(one.astype(np.float32) - raw).mean(axis=(1, 2, 3))
        d_cat_one = np.abs(cat.astype(np.float32) - one.astype(np.float32)).mean(axis=(1, 2, 3))
        self.assertLess(float(d_cat_one.max()), 3.0, f"拼接和整片编码在第 {int(d_cat_one.argmax())} 帧差 {d_cat_one.max():.2f}")     # 两次独立的有损编码，码率分配不同，帧间差异在 1–2 之间；错帧 / 跳帧会是几十
        self.assertLess(float(d_cat_one.mean()), 1.5)
        self.assertLess(float((e_cat - e_one).max()), 1.0)                    # 拼接的误差不比整片编码大
        for sp in self.plan.shots[1:]:                                       # 拼接点前后各 2 帧：误差没有突然变大（跳帧、错帧会）
            for f in range(sp.f0 - 2, sp.f0 + 2):
                self.assertLess(float(e_cat[f]), float(e_one[f]) + 1.0, f"拼接点第 {f} 帧")
        print(f"\n拼接 vs 整片一次编码：{n} 帧，每帧差 最大 {d_cat_one.max():.2f}、平均 {d_cat_one.mean():.2f}（0–255）；对原始画面的误差：拼接 {e_cat.mean():.2f}、整片 {e_one.mean():.2f}")

    def test_no_black_frames_and_no_duplicates_at_joins(self):
        cat = self.small(A[2]["out"])
        luma = cat.mean(axis=(1, 2, 3))
        raw_luma = np.stack(self.raw).mean(axis=(1, 2, 3))
        self.assertTrue((np.abs(luma - raw_luma) < 6).all(), "有的帧亮度和原始画面差太多（黑帧？）")
        for sp in self.plan.shots[1:]:
            f = sp.f0
            self.assertGreater(float(np.abs(cat[f].astype(int) - cat[f - 1].astype(int)).mean()), 0.0, f"拼接点第 {f} 帧和前一帧一模一样（重复帧）")

    def test_timestamps_continuous_and_av_in_sync(self):
        out = A[2]["out"]
        pk = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.split()
        pts = np.sort(np.array([float(x) for x in pk]))
        self.assertEqual(len(pts), 516)
        self.assertAlmostEqual(float(pts[0]), 0.0, places=3)
        d = np.diff(pts)
        self.assertLess(float(d.max() - d.min()), 0.002)                      # 每帧间隔都是 1/30，没有跳
        v, a = common.ffprobe_duration(out, "v:0"), common.ffprobe_duration(out, "a:0")
        self.assertAlmostEqual(v, 17.2, delta=0.04)
        self.assertAlmostEqual(a, v, delta=0.05)                              # 音轨和画面一样长
        st = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=start_time", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.split()
        self.assertLess(max(abs(float(x)) for x in st), 0.05)                 # 两条流都从 0 开始

    def test_audio_track_is_the_one_mixed_wav(self):
        """音频整条混好再放进去：成片音轨和 .wav 对齐（互相关的偏移只是 AAC 的编码延迟，不到 50 毫秒）。"""
        import wave
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(A[2]["out"]), "-vn", "-f", "s16le", "-ac", "2", "-ar", "44100", "-"], capture_output=True)
        a = np.frombuffer(p.stdout, "<i2").astype(np.float32).reshape(-1, 2)
        with wave.open(str(Path(A[2]["out"]).with_suffix(".wav"))) as w:
            b = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32).reshape(-1, 2)
        seg = slice(44100, 44100 * 6)
        lags = list(range(-2500, 2501, 25))
        score = [float(np.dot(a[seg.start + k:seg.stop + k, 0], b[seg, 0])) for k in lags]
        lag = lags[int(np.argmax(score))]
        self.assertLessEqual(abs(lag), 2200, f"成片音轨和混好的 wav 错开了 {lag} 个采样")


class TestStitchExactOrder(unittest.TestCase):
    """用「每一帧自己写着自己是第几个镜头的第几帧」的方块（frameid 特效）读成片：拼接和分块的每个接缝，帧号一个不错、不重复、不缺。"""

    def test_every_frame_is_the_right_frame_across_all_joins(self):
        d = common.fresh("it_frameid")
        shutil.copytree(common.TESTS / "frameid_case" / "fx", d / "fx")
        full = json.loads((common.PROTO / "storyboard.json").read_text(encoding="utf-8"))["shots"][0]["bg"]      # 整套分层的背景（不触发空白检测）
        froms = [{"line": 0, "dt": -0.3}, {"line": 3}, {"line": 5}]                                            # 0 / 148 / 324 帧起，每个镜头 150 帧以上，各切成 3–4 块
        shots = [{"id": f"k{k}", "from": fr, "bg": full, "fx": [{"type": "frameid", "k": k}]} for k, fr in enumerate(froms)]
        sb = {"episode": "frameid_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice", "shots": shots}
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        code, log, rep = common.render(d / "storyboard.json", d / "out", d / "cache", "--preview")
        self.assertEqual(code, 0, log)
        from engine.plan import build_plan
        plan = build_plan(d / "storyboard.json", scale=0.5, mode="preview")
        self.assertTrue(all(len(sp.chunks) >= 3 for sp in plan.shots), [len(sp.chunks) for sp in plan.shots])
        expect = []
        for k, sp in enumerate(plan.shots):
            expect += [k * 1000 + (f - sp.f0) for f in range(sp.f0, sp.f1)]
        got = []
        for fr in frames(rep["out"]):
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            v = 0
            for i in range(24):
                x = int((60 + i * 40 + 20) * 0.5)
                v = (v << 1) | int(g[int(365 * 0.5), x] > 127)
            got.append(v)
        self.assertEqual(len(got), len(expect))
        bad = [(f, e, g) for f, (e, g) in enumerate(zip(expect, got)) if e != g]
        self.assertEqual(bad[:5], [], f"{len(bad)} 帧不对（帧号, 应该是, 读出来是）")
        joins = sorted({c0 for sp in plan.shots for c0, _, _ in sp.chunks} - {0})
        self.assertGreaterEqual(len(joins), 8)                                    # 至少 8 个接缝（块与块、镜头与镜头）都核对过


class TestChunks(unittest.TestCase):
    def test_chunked_render_equals_whole_segment_frame_by_frame(self):
        """长镜头切成几块并行渲：每一块的每一帧，和一个进程从头渲到尾的完全一样（含转场混合的帧）。"""
        from engine import segment
        from engine.plan import build_plan
        for sb, shot_ids in ((common.PROTO / "storyboard.json", ["1-1"]), (common.FEATURE / "storyboard.json", ["f2", "f3"])):
            plan = build_plan(sb, scale=0.5, mode="preview")
            for sp in [s for s in plan.shots if s.id in shot_ids]:
                self.assertGreaterEqual(len(sp.chunks), 2, f"{sp.id} 只有 {len(sp.chunks)} 块")
                whole = [segment.frame_hash(fr) for _, fr in segment.iter_segment(segment.make_job(plan, sp, "x", "preview"))]
                parts = []
                for ch in sp.chunks:
                    parts += [segment.frame_hash(fr) for _, fr in segment.iter_segment(segment.make_job(plan, sp, "x", "preview", ch))]
                self.assertEqual(parts, whole, f"{sp.id}：分块渲和整段渲不一样")
                self.assertEqual(sp.chunks[0][0], sp.f0)
                self.assertEqual(sp.chunks[-1][1], sp.f1)
                self.assertTrue(all(a[1] == b[0] for a, b in zip(sp.chunks, sp.chunks[1:])))          # 块与块之间严丝合缝


class TestSegmentCacheAndTransitions(unittest.TestCase):
    """改一个镜头，只有它自己的片段、和它有转场相邻的片段重编码（feature_case 里有 3 个 dissolve 转场）。"""

    def test_editing_one_shot_rerenders_only_its_segment_and_transition_neighbours(self):
        d = common.fresh("it_seg")
        shutil.copytree(common.FEATURE, d / "fc")
        sb_path = d / "fc" / "storyboard.json"
        sb0 = json.loads(sb_path.read_text(encoding="utf-8"))
        n = len(sb0["shots"])
        cache = d / "cache"
        code, log, rep = common.render(sb_path, d, cache, "--preview")
        self.assertEqual((code, rep["timing"]["rendered_shots"]), (0, n), log)
        has_trans = [i > 0 and sb0["shots"][i].get("transition") not in (None, "cut") for i in range(n)]
        self.assertGreaterEqual(sum(has_trans), 2)
        for i in range(n):
            sb = json.loads(json.dumps(sb0))
            sb["shots"][i]["grade"] = "gold" if sb["shots"][i].get("grade") != "gold" else "cool"
            sb_path.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
            code, log, rep = common.render(sb_path, d, cache, "--preview")
            self.assertEqual(code, 0, log)
            expect = 1 + (1 if has_trans[i] else 0) + (1 if i + 1 < n and has_trans[i + 1] else 0)   # 自己 + 进场转场要用的前一镜 + 下一镜的进场转场要用的它
            self.assertEqual(rep["timing"]["rendered_shots"], expect, f"改了第 {i} 个镜头")
            sb_path.write_text(json.dumps(sb0, ensure_ascii=False), encoding="utf-8")                # 改回去：旧片段还在缓存里，一个都不用重渲
            code, log, rep = common.render(sb_path, d, cache, "--preview")
            self.assertEqual(rep["timing"]["rendered_shots"], 0)

    def test_editing_a_subtitle_rerenders_only_the_segments_it_appears_in(self):
        """改台词（字幕）只影响出现这句字幕的片段：字幕不进场景，但进片段的哈希。"""
        d = common.fresh("it_seg_sub")
        shutil.copytree(common.PROTO, d / "p17", ignore=shutil.ignore_patterns("voice"))
        sb = json.loads((d / "p17" / "storyboard.json").read_text(encoding="utf-8"))
        tl = json.loads((common.PROTO / "voice" / "timeline.json").read_text(encoding="utf-8"))
        (d / "voice").mkdir()
        for f in (common.PROTO / "voice").glob("*.mp3"):
            shutil.copy(f, d / "voice" / f.name)
        (d / "voice" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
        sb["voice"] = str(d / "voice")
        (d / "p17" / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        cache = d / "cache"
        code, log, rep = common.render(d / "p17" / "storyboard.json", d, cache, "--preview")
        self.assertEqual((code, rep["timing"]["rendered_shots"]), (0, 6), log)
        tl["lines"][1]["text"] = "要地，给还是不给？"             # 第 1 句：只出现在第一个镜头（1-1，0–4.93 秒）
        (d / "voice" / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False), encoding="utf-8")
        code, log, rep = common.render(d / "p17" / "storyboard.json", d, cache, "--preview")
        self.assertEqual(rep["timing"]["rendered_shots"], 1, log)


if __name__ == "__main__":
    unittest.main()
