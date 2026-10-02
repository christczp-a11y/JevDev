"""模糊布景图的边（tj03 第一版 s10–s44、tj02 s71：模糊水面左缘的「台阶」）。
根因：AssetStore.image 先把每一份图用 BORDER_REFLECT_101 模糊、再横向拼起来。水波最高的波峰刚好顶到 water.png 的上边，镜像以后模糊后的 alpha 在图的最上一行还很高、
图外面却什么都没有，画出来就是波峰顶被一刀切平的水平台阶（六层水面叠起来是几级台阶；波峰在 pos 140 − 764 + 285 ≈ 屏幕左缘 60 像素处，所以总出现在左边）；横向拼缝两边也是各自镜像、对不上。
  · TestBlurPremult：满铺的边（天空）和以前完全一样；结束的边（水波上沿）往外垫透明边、最外一行 alpha ≈ 0；
  · TestTileSeam：横向重复的图，拼缝两边是真实相邻图（和 5 份拼起来再模糊的中间部分一样）；
  · TestWaterLeftEdge：只画一层模糊水面（water_edge_repro.py），波峰顶在每一列的竖向跳变都不超过自然模糊的水平，左缘和右边一样；原图位置没被垫的透明边挤歪。"""
import unittest

import cv2
import numpy as np

import common  # noqa: F401  (sys.path)
import water_edge_repro as R
from engine import consts as C
from engine.canvas import Canvas
from engine.sprites import AssetStore, blur_premult

PAPER_BGR = np.array(C.PAPER[::-1], np.int32)
WATER = "sets/jin_land/water.png"


def coverage(im):
    """每个像素离纸色有多远（0 = 纸色，布景盖住的地方 > 60）。"""
    return np.abs(im.astype(np.int32) - PAPER_BGR).max(axis=2)


def top_steps(im, y=R.LAYER_Y):
    """水面顶部那一段（波峰上下各一点）每一列里相邻两行的最大跳变。一刀切平的台阶是一行里从纸色跳到 ~80% 的水色。"""
    return np.abs(np.diff(coverage(im)[y - 40:y + 120], axis=0)).max(axis=0)


class TestBlurPremult(unittest.TestCase):
    def test_opaque_edges_unchanged(self):
        """满铺的图（天空）四条边都镜像，和以前的 GaussianBlur 一模一样，不往外长、边上不变透明。"""
        arr = np.full((90, 120, 4), 255, np.uint8)
        arr[..., :3] = np.random.default_rng(1).integers(0, 255, (90, 120, 3), dtype=np.uint8)
        out, pad = blur_premult(arr, 4.0)
        self.assertEqual(pad, (0, 0, 0, 0))
        self.assertTrue(np.array_equal(out, cv2.GaussianBlur(arr, (0, 0), 4.0)))
        sp = AssetStore(1.0).image("sets/jin_land/sky.png", w=1080, blur=6)
        self.assertEqual(sp.pad, (0, 0, 0, 0))
        self.assertEqual(sp.arr[..., 3].min(), 255)

    def test_open_top_grows_transparent(self):
        """波峰顶到图上边：上沿结束（边上只有顶点几列不透明）→ 往上垫透明边，最外一行 alpha ≈ 0；左右、下沿满铺 → 不长。"""
        h, w = 80, 300
        arr = np.zeros((h, w, 4), np.uint8)
        for x in range(w):
            top = int(abs(x - 150) * 0.13)                      # 顶点在 x=150、刚好顶到第 0 行的山；两侧、下面都是实心
            arr[top:, x] = (200, 120, 40, 255)
        out, pad = blur_premult(arr, 5.0)
        r = 16                                                  # ceil(3σ) + 1
        self.assertEqual(pad, (0, r, 0, 0))
        self.assertEqual(out.shape, (h + r, w, 4))
        self.assertLessEqual(int(out[0, :, 3].max()), 3)        # 最外一行：没有一刀切
        self.assertGreater(int(out[r + 8, 150, 3]), 200)        # 原图里的实心部分还是实心

    def test_all_edges_open_keeps_content_position(self):
        """四条边都是透明（道具、人物那类图）：四边各垫 r，图的重心在外圈里的位置 = 原来的位置 + r。"""
        arr = np.zeros((70, 90, 4), np.uint8)
        cv2.circle(arr, (30, 25), 14, (50, 120, 200, 255), -1)
        out, pad = blur_premult(arr, 3.0)
        r = 10                                                  # ceil(3σ) + 1
        self.assertEqual(pad, (r, r, r, r))
        self.assertEqual(out.shape, (70 + 2 * r, 90 + 2 * r, 4))
        yy, xx = np.mgrid[0:70 + 2 * r, 0:90 + 2 * r]
        w = out[..., 3].astype(np.float64)
        self.assertAlmostEqual(float((w * xx).sum() / w.sum()), 30 + r, delta=0.2)
        self.assertAlmostEqual(float((w * yy).sum() / w.sum()), 25 + r, delta=0.2)

    def test_water_png_top_is_open(self):
        st = AssetStore(1.0)
        sp = st.image(WATER, w=1528, blur=6, tile_x=3)
        self.assertGreater(sp.pad[1], 0)                        # 上沿往外垫了
        self.assertLessEqual(int(sp.arr[0, :, 3].max()), 3)
        self.assertEqual(sp.pad[0] + sp.pad[2], 0)              # 左右是接得上的无缝图（大半不透明），不往外长
        self.assertAlmostEqual(sp.k, 1.0, places=6)             # k 只算原图那一块
        self.assertEqual(sp.arr.shape[1], 3 * 1528)


class TestTileSeam(unittest.TestCase):
    def test_seam_uses_real_neighbours(self):
        """拼缝两边 ±24 像素：和「拼 5 份再模糊」的中间部分一样（以前每份各自镜像，缝上波形对不上）。"""
        st = AssetStore(1.0)
        three = st.image(WATER, w=1528, blur=6, tile_x=3)
        five = st.image(WATER, w=1528, blur=6, tile_x=5)
        self.assertEqual(three.pad[1], five.pad[1])
        for s3, s5 in ((1528, 2 * 1528), (2 * 1528, 3 * 1528)):
            a = three.arr[:, s3 - 24:s3 + 24].astype(np.int32)
            b = five.arr[:, s5 - 24:s5 + 24].astype(np.int32)
            self.assertLessEqual(int(np.abs(a - b).max()), 1, f"拼缝 {s3} 两边和真实相邻图对不上")


class TestWaterLeftEdge(unittest.TestCase):
    def test_no_hard_step_at_crest_top(self):
        """每一列的竖向最大跳变：自然模糊 ≈ 9–10，一刀切平 ≈ 25。波峰的屏幕位置 = pos.x − 764 + 285，pos.x = 540 时在左缘 ~60 像素处（tj03 / tj02 实际写法），
        760 时在 ~280，再选 320 / 660 让别的波峰也经过画面。"""
        for x in (540, 760, 320, 660):
            im = R.render_layer(6.0, x)
            d = top_steps(im)
            right = int(d[540:].max())
            self.assertLessEqual(int(d[:200].max()), max(14, int(1.3 * right) + 2), f"pos.x={x}：左缘 0–200 有台阶（最大跳变 {int(d[:200].max())}，右半 {right}）")
            self.assertLessEqual(int(d.max()), 14, f"pos.x={x}：第 {int(d.argmax())} 列有台阶（最大跳变 {int(d.max())}）")

    def test_zoomed_camera(self):
        """镜头推近时（视差缩放）同样没有台阶；和 s21 一样推 + 冲击推。"""
        im = R.render_layer(6.0, 540, camera=[{"move": "push", "amount": 0.03}, {"move": "punch", "at": {"dt": 0.1}, "amount": 0.08}], t=0.5)
        self.assertLessEqual(int(top_steps(im, y=R.LAYER_Y).max()), 14)

    def test_blurred_layer_stays_where_the_sharp_one_is(self):
        """垫出来的透明边不能把图挤歪：模糊和不模糊的波峰上沿（覆盖到 50% 的那一行）差不多在同一行（只差模糊本身带来的几个像素）。"""
        sharp = coverage(R.render_layer(0.0, 540))
        blur = coverage(R.render_layer(6.0, 540))
        lo, hi = 400, 900
        edge = lambda c: np.array([int(np.argmax(c[R.LAYER_Y - 40:R.LAYER_Y + 150, x] >= 60)) for x in range(lo, hi)])
        self.assertLessEqual(float(np.median(np.abs(edge(sharp) - edge(blur)))), 3.0)


class TestPadBlit(unittest.TestCase):
    def test_anchor_ignores_pad(self):
        """Canvas.blit：anchor 是原图那一块的比例，带透明边的 Sprite 和不带的贴在同一个位置。"""
        st = AssetStore(1.0)
        sp = st.image(WATER, w=1528, blur=0.01, tile_x=1)       # 极小的模糊：形状几乎不变，但走带 pad 的路径
        self.assertGreater(sp.pad[1], 0)
        sharp = st.image(WATER, w=1528)
        a, b = Canvas(st, 1.0, 30, 1.0), Canvas(st, 1.0, 30, 1.0)
        a.reset()
        b.reset()
        a.blit(sp, 540, 1180, anchor=(0.5, 0.0))
        b.blit(sharp, 540, 1180, anchor=(0.5, 0.0))
        self.assertLessEqual(float(np.abs(a.img.astype(np.int32) - b.img.astype(np.int32)).mean()), 1.0)


if __name__ == "__main__":
    unittest.main()
