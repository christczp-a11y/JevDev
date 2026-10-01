"""空白检测（M7）：画面中间一大块淡色空白、分层之间露出白缝，出片时自动报出镜头号、秒数、位置，退出码 1；正常的天空、云、气泡、特效不许误报。
  · 合成图的正反例（天空、模糊天空、云、人物挡住一半的空白带、细缝、区域外的空白）；
  · 端到端：故意留一条淡色空白带的分镜表 → 退出码 1，报告里有镜头号、时间、位置；补上图层的 → 过；
  · 固定样本 blank_case/（进 git）：tj01 G 版旧分镜表里 Chris 点名的 0:28、1:50、2:17 三处（只画背景 / 人物 / 前景三层的一帧，缩到 270×480），旧的要报出来、修好的不许报。"""
import json
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


if __name__ == "__main__":
    common.ensure_proto_assets()
    unittest.main()
