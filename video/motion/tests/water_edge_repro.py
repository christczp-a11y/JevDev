"""模糊水面左缘「台阶」的最小复现：只画一层模糊的、横向重复的水面（和分镜表 tj03 s21 里的第一层一模一样的写法），看画面左边。
    .venv/Scripts/python video/motion/tests/water_edge_repro.py --out video/out/tests/motion/water_edge/after.png [--blur 6] [--x 540] [--zoom 0]
出一张图：这层水面画面左侧 360 × 260 像素，放大 2 倍；修之前水波最高的波峰在左缘被一刀切平（几级水平台阶），修之后波峰顶是软的。
test_water_edge.py 用 render_layer / left_strip 做断言。
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

MOTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOTION))

import fx as fxreg                                            # noqa: E402
from engine import consts as C                                # noqa: E402
from engine.canvas import Canvas                              # noqa: E402
from engine.scene import Scene                                # noqa: E402
from engine.sprites import AssetStore                         # noqa: E402
from engine.timeline import Timeline                          # noqa: E402

VOICE = MOTION / "tests" / "proto17" / "voice"
LAYER_Y = 1180


def render_layer(blur=6.0, x=540, y=LAYER_Y, depth=0.7, img="sets/jin_land/water.png", w=1528, repeat="x", camera=None, S=1.0, t=0.0):
    """一个镜头只有一层背景图，返回整幅画面（BGR，纸色底）。"""
    fxreg.load_plugins()
    layer = {"img": img, "depth": depth, "pos": [x, y], "anchor": [0.5, 0], "w": w, "blur": blur}
    if repeat:
        layer["repeat"] = repeat
    spec = {"id": "water_edge", "from": {"line": 0}, "bg": [layer]}
    if camera:
        spec["camera"] = camera
    store = AssetStore(S, [])
    scene = Scene(spec, Timeline.load(VOICE), 0.0, 3.0, store, fxreg.FX)
    cv = Canvas(store, S, C.FPS, 3.0, seed=1)
    scene.draw(cv, t, t)
    return cv.img.copy()


def left_strip(im, y=LAYER_Y, x1=360, rows=260, above=30, S=1.0):
    return im[int((y - above) * S):int((y + rows - above) * S), 0:int(x1 * S)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="模糊水面左缘复现", epilog=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blur", type=float, default=6.0)
    ap.add_argument("--x", type=float, default=540.0, help="这层水面 pos 的 x")
    ap.add_argument("--zoom", type=float, default=0.0, help="镜头推近量（0 = 不动）")
    a = ap.parse_args(argv)
    cam = [{"move": "push", "amount": a.zoom}] if a.zoom else None
    im = render_layer(a.blur, a.x, camera=cam, t=2.0 if a.zoom else 0.0)
    strip = left_strip(im)
    big = cv2.resize(strip, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", big)
    Path(a.out).write_bytes(buf.tobytes())
    print(a.out, big.shape)


if __name__ == "__main__":
    main()
