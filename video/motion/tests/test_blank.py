"""空白检测（M7）：画面中间一大块淡色空白、分层之间露出白缝，出片时自动报出镜头号、秒数、位置，退出码 1；正常的天空、云、气泡、特效不许误报。
  · 合成图的正反例（天空、模糊天空、云、人物挡住一半的空白带、细缝、区域外的空白）；
  · 端到端：故意留一条淡色空白带的分镜表 → 退出码 1，报告里有镜头号、时间、位置；补上图层的 → 过；
  · 固定样本 blank_case/（进 git）：tj01 G 版旧分镜表里 Chris 点名的 0:28、1:50、2:17 三处（只画背景 / 人物 / 前景三层的一帧，缩到 270×480），旧的要报出来、修好的不许报。
局部直边露缝（M7 再犯，待补 19）见后面四组：TestStripDetector（合成图正反例）、TestStripSamples（strip_case/ 里 tj02 s68 的真实帧）、TestStripEndToEnd（合成器出片）、TestBlankScan（blank_scan.py）。"""
import contextlib
import io
import json
import subprocess
import unittest
from pathlib import Path

import cv2
import numpy as np

import common
from engine import blank
from engine import consts as C

W, H = C.W, C.H
rng = np.random.default_rng(5)


def sky(h=H, w=W, tex=5.0):
    """纸纹的蓝天：饱和的蓝，竖向渐变，带纸纹（标准差 ~tex）。BGR。"""
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    base = np.array([235, 200, 150], np.float32) * (1 - g) + np.array([248, 235, 205], np.float32) * g
    img = np.broadcast_to(base, (h, w, 3)).copy()
    img += rng.normal(0, tex, (h, w, 1)).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def textured(h, w, col=(110, 130, 60)):
    img = np.empty((h, w, 3), np.float32)
    img[:] = col
    img += cv2.resize(rng.normal(0, 28, (h // 8, w // 8, 1)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def flat(h, w, col=(214, 224, 226)):
    img = np.empty((h, w, 3), np.float32)
    img[:] = col
    img += rng.normal(0, 0.8, (h, w, 1)).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def scene(band=None, seam=None, clouds=(), person=None, band_y=(1020, 1330)):
    img = sky()
    img[900:1020] = textured(120, W)                    # 远山
    img[band_y[1]:] = textured(H - band_y[1], W, (60, 120, 150))   # 地面
    img[1020:band_y[1]] = textured(band_y[1] - 1020, W, (150, 170, 70))
    if band:
        y0, y1 = band
        img[y0:y1] = flat(y1 - y0, W)
    if seam:
        y0, y1 = seam
        img[y0:y1] = flat(y1 - y0, W)
    for cx, cy, rx, ry in clouds:
        cv2.ellipse(img, (cx, cy), (rx, ry), 0, 0, 360, (236, 244, 246), -1, cv2.LINE_AA)
    if person:
        x0, x1, y0, y1 = person
        img[y0:y1, x0:x1] = textured(y1 - y0, x1 - x0, (40, 40, 200))
    return img


def kinds(img):
    return sorted(e["kind"] for e in blank.detect(img))


class TestDetector(unittest.TestCase):
    def test_textured_and_blurred_sky_are_not_blank(self):
        self.assertEqual(blank.detect(sky()), [])
        self.assertEqual(blank.detect(sky(tex=1.0)), [])                       # 纸纹很弱的天空：饱和度高，照样不是空白
        self.assertEqual(blank.detect(cv2.GaussianBlur(sky(), (0, 0), 9)), [])   # 特写的模糊背景
        self.assertEqual(blank.detect(scene()), [])                            # 山、地面、天空层层接上

    def test_pale_snow_mountains_are_not_blank(self):
        """淡色的雪山（饱和度 ≈ 28/255）不是空白：空白带（天空图下半截露出来）的饱和度只有 5–12。"""
        img = scene()
        img[812:1028] = flat(216, W, (240, 232, 214))
        self.assertEqual(blank.detect(img), [])

    def test_clouds_are_not_blank(self):
        self.assertEqual(blank.detect(scene(clouds=[(300, 520, 150, 70), (760, 470, 140, 65)])), [])
        self.assertEqual(blank.detect(scene(clouds=[(20, 480, 110, 60), (1060, 500, 110, 60)])), [])      # 被画面边缘切掉一半的云，左右各一朵

    def test_pale_band_between_layers_is_reported_with_position(self):
        found = blank.detect(scene(band=(1030, 1325)))
        self.assertEqual([e["kind"] for e in found], ["block"])
        x0, y0, x1, y1 = found[0]["bbox"]
        self.assertLessEqual(x0, 8)
        self.assertGreaterEqual(x1, W - 8)
        self.assertAlmostEqual(y0, 1030, delta=12)
        self.assertAlmostEqual(y1, 1325, delta=12)

    def test_band_half_hidden_by_a_person_is_still_reported(self):
        self.assertEqual(kinds(scene(band=(1030, 1325), person=(150, 800, 800, 1500))), ["block"])   # 人物挡住中间，左右两边还露着

    def test_thin_straight_seam_across_the_screen_is_reported(self):
        found = blank.detect(scene(seam=(1160, 1196)))
        self.assertEqual([e["kind"] for e in found], ["seam"])
        self.assertAlmostEqual(found[0]["bbox"][1], 1160, delta=12)

    def test_seam_partly_hidden_by_two_people_is_still_reported(self):
        img = scene(seam=(1160, 1196))
        img[700:1500, 90:450] = textured(800, 360, (40, 40, 200))
        img[700:1500, 640:960] = textured(800, 320, (200, 80, 40))
        self.assertEqual(kinds(img), ["seam"])

    def test_outside_the_check_zone_is_ignored(self):
        img = scene()
        img[100:260] = flat(160, W)                                            # 标题条那一带
        img[1450:1900] = flat(450, W)                                          # 字幕区以下（米色纸边）
        self.assertEqual(blank.detect(img), [])

    def test_same_result_at_preview_scale(self):
        full = scene(band=(1030, 1325))
        half = cv2.resize(full, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        a, b = blank.detect(full), blank.detect(half)
        self.assertEqual([e["kind"] for e in a], [e["kind"] for e in b])
        self.assertLessEqual(max(abs(p - q) for p, q in zip(a[0]["bbox"], b[0]["bbox"])), 16)


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = common.fresh("it_blank")
        jl = "sets/jin_land/"
        top = [{"img": jl + "sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080},
               {"img": jl + "ridge_far.png", "depth": 0.15, "pos": [0, 430], "w": 1080},
               {"img": jl + "ridge_mid.png", "depth": 0.3, "pos": [0, 740], "w": 1080}]
        full = json.loads((common.PROTO / "storyboard.json").read_text(encoding="utf-8"))["shots"][0]["bg"]    # 小样第一镜的整套分层：天空、三层山、城墙、城门、地面、两层水
        actor = {"id": "sgm", "who": "司马光", "img": "chars/sgm_finger.png", "pos": [300, 1500], "h": 520}
        good = {"id": "ok", "from": {"line": 0, "dt": -0.3}, "bg": full, "actors": [actor]}
        # 故意漏掉近山、城墙、水、地面：天空图下半截那一大块淡色露出来（真实的失败就是这样，0:28 那一镜）
        bad = {"id": "gap", "from": {"line": 3}, "bg": top, "actors": [actor]}
        sb = {"episode": "blank_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice", "shots": [good, bad]}
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        cls.d = d
        cls.res = common.render(d / "storyboard.json", d / "out", d / "cache", "--preview")

    def test_gap_exits_1_and_reports_shot_time_and_position(self):
        code, log, rep = self.res
        self.assertEqual(code, 1, log)
        blank_check = rep["checks"]["blank"]
        self.assertFalse(blank_check["ok"])
        ev = blank_check["events"]
        self.assertTrue(ev)
        self.assertEqual({e["shot"] for e in ev}, {"gap"})                   # 好的镜头不报，有空白的镜头报
        e = ev[0]
        self.assertGreaterEqual(e["t"], 4.93)                                # 在时间线上的秒数落在这个镜头里
        self.assertLessEqual(e["t"], 17.2)
        self.assertEqual(e["kind"], "block")
        self.assertGreater(e["bbox"][1], 1000)                               # 空白带在远山下面
        self.assertGreaterEqual(e["bbox"][3], 1300)                          # 一直到地面该在的位置（检查区 y 340–1400 之内）
        self.assertIn("空白：镜头 gap", log)                                  # 命令行输出里也写了镜头号和位置
        self.assertEqual([k for k, c in rep["checks"].items() if not c["ok"]], ["blank"])   # 其它检查照常通过

    def test_covering_layers_pass(self):
        d = common.fresh("it_blank_ok")
        sb = json.loads((self.d / "storyboard.json").read_text(encoding="utf-8"))
        sb["shots"] = sb["shots"][:1]
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        code, log, rep = common.render(d / "storyboard.json", d / "out", d / "cache", "--preview")
        self.assertEqual(code, 0, log)
        self.assertEqual(rep["checks"]["blank"]["events"], [])


CASE = Path(__file__).resolve().parent / "blank_case"


class TestTj01Calibration(unittest.TestCase):
    """阈值是拿 tj01 的 G 版成片标定的：Chris 圈的 0:28（远山和地面之间一大块淡色空白）、1:50（同）、2:17（山和水之间一条白缝）都要报出来。
    成片已经补好，所以用固定样本：blank_case/<时间>_<镜头>_old.png 是补之前的旧分镜表渲出来的一帧，_fixed.png 是补完以后同一镜头的一帧
    （都是不含特效 / 字幕 / 调色的场景，缩到 270×480，正好是检测的工作分辨率）。"""

    SPOTS = {"0m28_s11": ("block", 1000, 1330), "1m50_s43": ("block", 1000, 1340), "2m17_s53": ("seam", 1150, 1240)}

    def load(self, name):
        im = cv2.imread(str(CASE / f"{name}.png"))
        self.assertIsNotNone(im, f"没有样本 {name}.png")
        return im

    def test_old_samples_are_flagged(self):
        for key, (kind, y0, y1) in self.SPOTS.items():
            ev = blank.detect(self.load(f"{key}_old"))
            self.assertTrue(ev, f"{key}：旧帧没报出来")
            e = ev[0]
            self.assertEqual(e["kind"], kind, key)
            self.assertLessEqual(abs(e["bbox"][1] - y0), 40, (key, e))
            self.assertLessEqual(abs(e["bbox"][3] - y1), 40, (key, e))
            self.assertEqual((e["bbox"][0], e["bbox"][2]), (0, W), key)          # 横贯整幅画面

    def test_fixed_samples_are_clean(self):
        for key in self.SPOTS:
            self.assertEqual(blank.detect(self.load(f"{key}_fixed")), [], f"{key}：补完的帧不该报")


def _tex(g, h, w, col, amp=28):
    img = np.empty((h, w, 3), np.float32)
    img[:] = col
    img += cv2.resize(g.normal(0, amp, (max(h // 8, 1), max(w // 8, 1), 1)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


def gap_scene(edge_y=1000, x0=600, x1=800, depth=30, col=(231, 227, 215), noise=1.0, tilt=0.0, bottom="zigzag", amp=14, ridge_col=(120, 125, 55), seed=11):
    """局部直边露缝的合成图：远山（平直的图片底边在 edge_y，tilt = 每像素往下滑多少）+ 下面一层近山，山峰之间在 [x0, x1] 露出一小条淡色平条（col，None = 没有露缝）。
    平条厚 depth 左右；bottom = "zigzag"：下沿是山尖的锯齿（厚度在 depth ± amp 之间来回，真实的样子）；"flat"：下沿也是直边（矩形条）。"""
    g = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    edge = edge_y + tilt * (xx - W / 2)
    a = np.clip(edge - yy + 0.5, 0, 1)[..., None]                        # 直边上下各一个像素的抗锯齿（倾斜的边才有亚像素的漂移）
    ridge = a * _tex(g, H, W, ridge_col, 10) + (1 - a) * _tex(g, H, W, (70, 85, 35))      # 远山 → 近山：直边下面整片都是有纹理的近山
    img = np.where((yy >= 700)[..., None], ridge, sky().astype(np.float32))
    if col is not None:
        patch = np.array(col, np.float32) + g.normal(0, noise, (H, W, 1))
        low = depth if bottom == "flat" else depth - amp + 2 * amp * np.abs(((xx - x0) / 35.0) % 2 - 1)
        p = (np.clip(yy - edge + 0.5, 0, 1) * (yy < edge + low) * (xx >= x0) * (xx < x1))[..., None]
        img = img * (1 - p) + patch * p
    return np.clip(img, 0, 255).astype(np.uint8)


def strips(img, **kw):
    return [e for e in blank.detect(img, **kw) if e["kind"] == "strip"]


class TestStripDetector(unittest.TestCase):
    """局部直边露缝（M7 再犯，待补 19）：一段水平直边 + 贴着它的淡色平条，不碰画面边缘、不横贯。"""

    def test_pale_strip_under_a_straight_edge_is_reported_with_position(self):
        found = blank.detect(gap_scene())
        self.assertEqual([e["kind"] for e in found], ["strip"])
        e = found[0]
        x0, y0, x1, y1 = e["bbox"]
        self.assertAlmostEqual(y0, 1000, delta=8)
        self.assertGreaterEqual(x0, 600 - 16)
        self.assertLessEqual(x1, 800 + 16)
        self.assertGreaterEqual(x1 - x0, 150)
        self.assertEqual(blank.detect(gap_scene(), ui=True)[0]["kind"], "strip")      # 成片模式照样报

    def test_same_scene_without_the_pale_patch_is_clean(self):
        self.assertEqual(blank.detect(gap_scene(col=None)), [])              # 一条直边本身不算：下面是有纹理的山

    def test_not_a_strip(self):
        self.assertEqual([e["kind"] for e in blank.detect(gap_scene(depth=16, amp=4))], ["strip"])     # 对照：同样的形状、不是纯白就要报
        for name, img in {
            "有纸纹的平条（灰度标准差 8）": gap_scene(noise=8.0),
            "天空蓝的平条（饱和）": gap_scene(col=(235, 200, 150)),
            "两边都是直边的矩形条（道具上的装饰条）": gap_scene(bottom="flat"),
            "纯白的细条（贴纸描边 / 水波白线）": gap_scene(col=(253, 253, 253), depth=16, amp=4),
            "太窄（45 像素）": gap_scene(x0=700, x1=745),
            "直边倾斜 6%（手绘的线 / 波浪线的斜坡）": gap_scene(tilt=0.06),
            "太厚（100 像素：那是大块平涂，不是缝）": gap_scene(depth=100),
        }.items():
            with self.subTest(name):
                self.assertEqual(blank.detect(img), [])

    def test_strip_is_not_double_reported_inside_a_block_or_seam(self):
        self.assertEqual(kinds(scene(seam=(1160, 1196))), ["seam"])
        self.assertEqual(kinds(scene(band=(1030, 1325))), ["block"])

    def test_card_border_is_excluded_only_in_video_mode(self):
        """成片里卡片 / 气泡的底紧贴在棕色边框（≈ BGR 53, 68, 86）下面：成片模式（ui=True）不报，布景帧里没有卡片，照常报。"""
        img = gap_scene(col=(231, 227, 215), ridge_col=(53, 68, 86))
        self.assertEqual([e["kind"] for e in blank.detect(img)], ["strip"])
        self.assertEqual(blank.detect(img, ui=True), [])

    def test_warm_cream_band_is_not_a_strip_but_paper_colour_is(self):
        """天空图最下面一截的地平线雾（暖色奶油色 RGB 243, 236, 220，tj01 开头 / 小样好镜头里都有）、卡片底不报；颜色就是引擎的纸底色（230, 220, 200，什么都没盖住）要报。"""
        self.assertEqual(blank.detect(gap_scene(col=(220, 236, 243))), [])
        self.assertEqual(blank.detect(gap_scene(col=(212, 230, 244))), [])
        self.assertEqual([e["kind"] for e in blank.detect(gap_scene(col=(200, 220, 230)))], ["strip"])

    def test_same_result_at_preview_scale(self):
        full = gap_scene()
        half = cv2.resize(full, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        a, b = strips(full), strips(half)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertLessEqual(max(abs(p - q) for p, q in zip(a[0]["bbox"], b[0]["bbox"])), 16)


STRIP_CASE = Path(__file__).resolve().parent / "strip_case"


def load_zone(name):
    """strip_case/<name>.png 是 540×960 画面的 y 150–720 那一段（检查区 y 340–1400 → 170–700 行，两头各留余量）；补回整幅画面（上下用边缘行延伸，不造出假的直边）。"""
    im = cv2.imread(str(STRIP_CASE / f"{name}.png"))
    assert im is not None, f"没有样本 {name}.png"
    return cv2.copyMakeBorder(im, 150, 960 - 720, 0, 0, cv2.BORDER_REPLICATE)


class TestStripSamples(unittest.TestCase):
    """真实的帧（缩到 540×960，只留检查区那一段）：
    s68_video_pos     tj02 第 2 版成片 s68 中段（builder 抽的帧，check_v2/s68_2_mid.png）：近山往下挪后中层山的平直底边露出一条浅灰蓝平条，约 x 675–820、y 1000–1025，要报；
    s68_bare_pos      同一个镜头改前的分镜表渲出来的布景帧（只有背景 / 人物 / 前景，没有字幕和调色）：要报；
    s68_bare_fixed    改后（近山 / 中层山重新叠过）同一镜头同一时刻的布景帧：不许报；
    s11_bare_gap      tj02 s11（宴会）：远山的平直底边和平台之间、画面左右两边也露着同样的淡色平条（出片时没人发现，这次检查才报出来）：要报。"""

    def test_s68_video_frame_is_flagged_where_the_builder_saw_it(self):
        found = strips(load_zone("s68_video_pos"), ui=True)
        self.assertEqual(len(found), 1, found)
        x0, y0, x1, y1 = found[0]["bbox"]
        self.assertAlmostEqual(y0, 1000, delta=10)
        self.assertAlmostEqual(y1, 1025, delta=14)
        self.assertAlmostEqual(x0, 675, delta=20)
        self.assertAlmostEqual(x1, 820, delta=20)
        self.assertEqual(len(strips(load_zone("s68_video_pos"))), 1)         # 不按成片模式也报

    def test_s68_bare_frame_before_the_fix_is_flagged_and_after_the_fix_is_clean(self):
        found = strips(load_zone("s68_bare_pos"))
        self.assertEqual(len(found), 1, found)
        self.assertAlmostEqual(found[0]["bbox"][1], 1002, delta=8)
        self.assertEqual(blank.detect(load_zone("s68_bare_fixed")), [])

    def test_s11_side_gaps_are_flagged_on_both_sides(self):
        found = strips(load_zone("s11_bare_gap"))
        self.assertEqual(len(found), 2, found)
        left, right = sorted(found, key=lambda e: e["bbox"][0])
        self.assertLessEqual(left["bbox"][0], 4)
        self.assertGreaterEqual(right["bbox"][2], W - 4)
        for e in found:
            self.assertAlmostEqual(e["bbox"][1], 1004, delta=8)


class TestStripEndToEnd(unittest.TestCase):
    """合成器出片：tj02 s68 改前的分层（近山 y = 870，中层山的平直底边露在近山山峰之间）→ 退出码 1、报「直边平条」带镜头号 / 秒数 / 位置；
    改后的分层（远山 / 中层山 / 近山重新叠过）→ 过。"""

    JL = "sets/jin_land/"

    def bg(self, far, mid, near):
        jl = self.JL
        L = [{"img": jl + "sky.png", "depth": 0.1, "pos": [0, 0], "w": 1080},
             {"img": jl + "ridge_far.png", "depth": 0.2, "pos": far[0], "anchor": [0.5, 0], "w": far[1]},
             {"img": jl + "ridge_mid.png", "depth": 0.3, "pos": mid[0], "anchor": [0.5, 0], "w": mid[1]},
             {"img": jl + "ridge_near.png", "depth": 0.4, "pos": near[0], "anchor": [0.5, 0], "w": near[1]}]
        for i, y in enumerate((1180, 1320, 1460, 1600, 1740, 1880)):
            L.append({"img": jl + "water.png", "depth": 0.7 + 0.05 * i, "pos": [540, y], "anchor": [0.5, 0], "w": 1528, "repeat": "x"})
        return L

    def render(self, name, bg):
        d = common.fresh(name)
        sb = {"episode": "strip_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice", "shots": [{"id": "gap", "from": {"line": 3}, "bg": bg}]}
        (d / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        return d, common.render(d / "storyboard.json", d / "out", d / "cache", "--preview")

    def test_exposed_ridge_bottom_exits_1_and_reports_shot_time_and_position(self):
        _, (code, log, rep) = self.render("it_strip_bad", self.bg(([540, 470], 1100), ([540, 640], 1100), ([540, 870], 1100)))
        self.assertEqual(code, 1, log)
        ev = rep["checks"]["blank"]["events"]
        self.assertTrue(ev)
        self.assertEqual({e["kind"] for e in ev}, {"strip"})
        self.assertEqual({e["shot"] for e in ev}, {"gap"})
        for e in ev:
            self.assertAlmostEqual(e["bbox"][1], 1003, delta=8)              # 直边在 y ≈ 1002
            self.assertGreaterEqual(e["bbox"][2] - e["bbox"][0], 100)
            self.assertGreater(e["t"], 0)
        self.assertGreaterEqual(len(ev), 3)                                  # 每个镜头抽 4 帧，露缝一整个镜头都在
        self.assertIn("直边平条", log)
        self.assertEqual([k for k, c in rep["checks"].items() if not c["ok"]], ["blank"])

    def test_restacked_layers_pass(self):
        _, (code, log, rep) = self.render("it_strip_ok", self.bg(([540, 300], 1250), ([490, 640], 1250), ([470, 830], 1250)))
        self.assertEqual(code, 0, log)
        self.assertEqual(rep["checks"]["blank"]["events"], [])


def synth_video(path, frames, fps=2):
    """把几帧 1080×1920 的画面编码成 mp4（每帧停 1 / fps 秒）。"""
    h, w = frames[0].shape[:2]
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-framerate", str(fps), "-i", "-",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(path)],
                       input=b"".join(f.tobytes() for f in frames), capture_output=True)
    assert p.returncode == 0, p.stderr.decode(errors="replace")


class TestBlankScan(unittest.TestCase):
    """blank_scan.py：成片模式（带 UI 的画面，局部直边要连续两个采样点都在、奶油色卡片底不报）和 --bare 模式（按分镜表只画布景三层）。"""

    @classmethod
    def setUpClass(cls):
        import blank_scan
        cls.bs = blank_scan
        cls.d = common.fresh("it_blank_scan")

    def run_scan(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.bs.main(list(argv))
        return code, buf.getvalue()

    def test_persistence_filter_keeps_only_strips_seen_at_neighbouring_samples(self):
        s = {"kind": "strip", "bbox": [0, 1000, 150, 1040], "area": 0.002, "h": 40, "color": [219, 227, 229]}
        moved = dict(s, bbox=[300, 1000, 450, 1040])                          # 同样的 y 但横向没有重叠
        blk = {"kind": "block", "bbox": [0, 1000, 1080, 1300], "area": 0.1}
        out = self.bs.keep_persistent([[s], [s], [], [s, blk], [moved]])
        self.assertEqual([len(x) for x in out], [1, 1, 0, 1, 0])               # 前两个互相作证；第 4 个的 strip 邻居里没有同位置的（只留 block）；最后一个挪了位置
        self.assertEqual(out[3][0]["kind"], "block")

    def test_video_with_a_gap_exits_1_and_without_exits_0(self):
        bad, good = self.d / "bad.mp4", self.d / "good.mp4"
        synth_video(bad, [gap_scene()] * 6)
        synth_video(good, [gap_scene(col=None)] * 6)
        code, out = self.run_scan(str(bad))
        self.assertEqual(code, 1, out)
        self.assertIn("直边平条", out)
        self.assertRegex(out, r"bbox \[\d+, 100[0-4], ")
        code, out = self.run_scan(str(good))
        self.assertEqual(code, 0, out)

    def test_bare_mode_reads_the_storyboard(self):
        bg = TestStripEndToEnd.bg
        for name, layers, code_want in (("bad", ([540, 470], 1100, [540, 640], 1100, [540, 870], 1100), 1), ("ok", ([540, 300], 1250, [490, 640], 1250, [470, 830], 1250), 0)):
            sb = {"episode": "strip_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice",
                  "shots": [{"id": "gap", "from": {"line": 3}, "bg": bg(TestStripEndToEnd, (layers[0], layers[1]), (layers[2], layers[3]), (layers[4], layers[5]))}]}
            p = self.d / f"bare_{name}.json"
            p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
            code, out = self.run_scan("--bare", str(p), "--every", "3")
            self.assertEqual(code, code_want, out)
            if code_want:
                self.assertIn("gap  直边平条", out)


class TestBareWholeScreen(unittest.TestCase):
    """待补 23（M7 第三次再犯，tj03 第一版书房镜头只铺了 1620 高的 wall.png，最下面 300 像素空米色条）：`blank_scan.py --bare` 扫整屏 y 0–1920，
    认露出来的纸底色（C.PAPER，饱和度 33，不算「淡色」，以前不管扫多大范围都报不出来）。engine/blank.py 本身一个字没动（范围还是 340–1400）。"""

    @classmethod
    def setUpClass(cls):
        import blank_scan
        cls.bs = blank_scan
        cls.d = common.fresh("it_bare_whole")

    def frame(self):
        return textured(H, W)

    def test_bottom_band_of_paper_colour_is_reported_and_the_engine_default_range_never_saw_it(self):
        img = self.frame()
        img[1620:] = self.bs.PAPER_BGR.astype(np.uint8)
        self.assertEqual(blank.detect(img), [])                                         # 以前的检查：y 340–1400，而且纸底色不是淡色
        ev = self.bs.detect_bare(img)
        self.assertEqual([e["kind"] for e in ev], ["paper"], ev)
        self.assertEqual(ev[0]["bbox"], [0, 1620, 1080, 1920])
        self.assertAlmostEqual(ev[0]["area"], 300 / 1920, delta=0.002)

    def test_small_thin_or_off_colour_bits_are_not_reported(self):
        paper = self.bs.PAPER_BGR.astype(np.uint8)
        img = self.frame()
        img[1000:1004, :] = paper                                                       # 4 像素的细线（图边抗锯齿 / 镜头漂移）
        img[500:515, 500:515] = paper                                                   # 15×15 = 225 像素²
        img[1700:1800, 100:300] = paper + np.array([8, 8, 8], np.uint8)                 # 差 8：是图的颜色，不是没盖住
        self.assertEqual(self.bs.uncovered_paper(img), [])
        img[:, :8] = paper                                                              # 贴着屏幕左边的 8 像素宽细条（整个高）：< 10 像素，不报（storyboard_check 的 [铺满] 当警告）
        self.assertEqual(self.bs.uncovered_paper(img), [])
        img[500:530, 500:530] = paper                                                   # 30×30 = 900 像素²：报
        ev = self.bs.uncovered_paper(img)
        self.assertEqual([e["bbox"] for e in ev], [[500, 500, 530, 530]])

    def test_a_pale_flat_band_below_y1400_or_above_y340_is_now_reported(self):
        img = self.frame()
        img[1500:1700] = flat(200, W)
        img[100:300] = flat(200, W)
        self.assertEqual(blank.detect(img), [])                                         # engine 的默认范围看不到
        ev = self.bs.detect_bare(img)
        self.assertEqual(sorted(e["kind"] for e in ev), ["block", "block"], ev)
        for got, want in zip(sorted(e["bbox"][1] for e in ev), (100, 1500)):
            self.assertAlmostEqual(got, want, delta=12)                                 # 5×5 局部标准差在边上多吃几行

    def test_several_bare_bits_in_one_frame_are_merged_into_one_event(self):
        paper = self.bs.PAPER_BGR.astype(np.uint8)
        img = self.frame()
        img[1700:1730, 100:300] = paper
        img[1700:1730, 600:900] = paper
        ev = self.bs.detect_bare(img)
        self.assertEqual(len(ev), 1, ev)
        self.assertEqual((ev[0]["kind"], ev[0]["n"], ev[0]["bbox"]), ("paper", 2, [100, 1700, 900, 1730]))
        self.assertAlmostEqual(ev[0]["area"], (200 + 300) * 30 / (W * H), delta=0.0005)

    def test_wide_range_puts_the_engine_constants_back(self):
        self.bs.detect_bare(self.frame())
        self.assertEqual((C.BLANK_Y0, C.BLANK_Y1), (340, 1400))
        with self.assertRaises(RuntimeError):
            with self.bs.wide_range():
                self.assertEqual((C.BLANK_Y0, C.BLANK_Y1), (self.bs.BARE_Y0, self.bs.BARE_Y1))
                raise RuntimeError
        self.assertEqual((C.BLANK_Y0, C.BLANK_Y1), (340, 1400))

    def run_scan(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.bs.main(list(argv))
        return code, buf.getvalue()

    def test_bare_mode_reports_a_bare_strip_at_the_bottom_and_passes_when_the_last_water_layers_are_there(self):
        full = TestStripEndToEnd.bg(TestStripEndToEnd, ([540, 300], 1250), ([490, 640], 1250), ([470, 830], 1250))      # tj02 s68 改后的分层 + 6 层水（最后一层水在 y 1880）

        def scan(name, layers):
            sb = {"episode": "strip_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice", "shots": [{"id": "gap", "from": {"line": 3}, "bg": layers}]}
            p = self.d / f"{name}.json"
            p.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
            return self.run_scan("--bare", str(p), "--every", "1")
        code, out = scan("water_short", full[:-2])                                      # 少了 y 1740 / 1880 两层水：最下面约 110 像素露出纸底色
        self.assertEqual(code, 1, out)
        self.assertIn("gap  纸底色（没铺满）", out)
        self.assertRegex(out, r"bbox \[0, 18\d\d, 1080, 1920\]")
        code, out = scan("water_full", full)
        self.assertEqual(code, 0, out)


class TestFillModelMatchesTheEngine(unittest.TestCase):
    """storyboard_check 的 [铺满]（不画图，按图层尺寸 / 位置 / 补间 / sway / 视差 / 镜头运动算盖住的范围）和合成器真画出来的一致：
    同一个分镜表（天空 + 三层山 + 三条翻转 / 横向重复的地面、一层带 sway 的模糊水，推 + 摇，故意留着缝）里，每个取样时刻「预测的没盖住」和「真画出来的没盖住」
    （合成器在纸底色和黑底上各画一遍，两张的差 ÷ 纸底色 = 每个像素透出多少底色，> 50% = 没盖住）基本重合。引擎改了画图的办法（blit / 模糊 / 重复）这里会先响。"""

    def test_predicted_uncovered_area_is_what_the_engine_really_leaves_open(self):
        import storyboard_check as SC
        from engine import canvas as engine_canvas
        from engine import segment as S
        from engine.canvas import Canvas
        from engine.plan import build_plan
        jl = "sets/jin_land/"
        bg = [{"img": jl + "sky.png", "depth": 0.1, "pos": [0, 0], "w": 1080, "blur": 3},
              {"img": jl + "ridge_far.png", "depth": 0.2, "pos": [540, 470], "anchor": [0.5, 0], "w": 1100},
              {"img": jl + "ridge_mid.png", "depth": 0.3, "pos": [540, 640], "anchor": [0.5, 0], "w": 1100},
              {"img": jl + "ridge_near.png", "depth": 0.4, "pos": [540, 820], "anchor": [0.5, 0], "w": 1100}]
        for i, (y, w, flip) in enumerate(((1250, 1300, False), (1398, 1500, True), (1570, 1700, False))):                     # 少了最下面一条（y 1764），底下留着空
            bg.append({"img": jl + "ground.png", "depth": 0.9, "pos": [540, y], "anchor": [0.5, 0], "w": w, "repeat": "x", **({"flip": True} if flip else {})})
        bg.append({"img": jl + "water.png", "depth": 0.7, "pos": [540, 1180], "anchor": [0.5, 0], "w": 1528, "repeat": "x", "blur": 3, "sway": {"x": 26, "y": 6, "period": 3.4, "phase": 0.4}})
        sb = {"episode": "strip_case", "no": 1, "title": ["测试"], "voice": "video/motion/tests/proto17/voice",
              "shots": [{"id": "gap", "from": {"line": 3}, "bg": bg, "camera": [{"move": "push", "amount": 0.05}, {"move": "pan", "dx": -40, "dy": 10}]}]}
        d = common.fresh("it_fill_model")
        path = d / "storyboard.json"
        path.write_text(json.dumps(sb, ensure_ascii=False), encoding="utf-8")
        cap = {}
        real = SC.check_fill
        SC.check_fill = lambda sh, out, cam, rep: cap.update(sh=sh, out=out, cam=cam)
        try:
            SC.run(str(path))
        finally:
            SC.check_fill = real
        sh, out, cam = cap["sh"], cap["out"], cap["cam"]
        plan = build_plan(path, None, 1.0, "normal")
        sp = plan.shots[0]
        job = S.make_job(plan, sp, d / "cache", "normal")
        fxreg, tl, store, _ui = S._context(job)
        own = S._scene(job["own"], tl, store, fxreg)
        cv = Canvas(store, 1.0, C.FPS, own.dur)
        paper = engine_canvas._PAPER_BGR
        k = np.ones((3, 3), np.uint8)
        try:
            checked = 0
            for t in (0.3, 0.9, 1.5, 2.1):
                f = sp.f0 + int(round(t * C.FPS))
                if f >= sp.f1:
                    continue
                t = (f - sp.f0) / C.FPS
                shots = []
                for bgc in (paper, (0, 0, 0)):
                    engine_canvas._PAPER_BGR = bgc
                    cv.rng = np.random.default_rng([1, f])
                    own.draw(cv, (f - own.f0i) / C.FPS, f / C.FPS, bare=True)
                    shots.append(cv.img.astype(np.float32).copy())
                engine_canvas._PAPER_BGR = paper
                v_real = (shots[0] - shots[1]).mean(2) / float(np.mean(C.PAPER))
                real_mask = cv2.resize((v_real > 0.5).astype(np.uint8), (540, 960), interpolation=cv2.INTER_AREA) > 0.5
                pred_mask = SC.fill_vis(out["layers"], cam, t, sh.t0, 2) > SC.FILL_VIS_MAX
                real_mask, pred_mask = [cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool) for m in (real_mask, pred_mask)]
                self.assertGreater(real_mask.sum(), 540 * 960 * 0.03, f"t={t}：测试场景应该留着缝（真画出来的没盖住的格子太少，场景失效了）")
                diff = np.logical_xor(real_mask, pred_mask).sum()
                self.assertLess(diff, 0.05 * real_mask.sum(), f"t={t}：预测和真画出来的没盖住的范围对不上（不重合的格子 {diff}，真实 {real_mask.sum()}）")
                checked += 1
            self.assertGreaterEqual(checked, 3)
        finally:
            engine_canvas._PAPER_BGR = paper


if __name__ == "__main__":
    common.ensure_proto_assets()
    unittest.main()
