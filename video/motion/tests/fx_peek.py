"""开发和 reviewer 用：把一个特效（或转场）画在背景上，取几个时刻的帧，拼成一张图，不出片。
    .venv/Scripts/python video/motion/tests/fx_peek.py '{"type":"smash","text":"本事","pos":[540,800]}' --t 0,0.1,0.2,0.4,0.8 --out x.png
    .venv/Scripts/python video/motion/tests/fx_peek.py --transition '{"type":"page_turn"}' --p 0.1,0.3,0.5,0.7,0.9 --out t.png
    --fx-list '[...]' 一次给几个特效（JSON 列表）；--bg sky / study / plain / dark；--actor sgm 加一个人物；--S 0.5 渲染比例；--cols 5 每行几帧
输出的每一格左上角标着时刻。
"""
import argparse
import json
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

BGS = {
    "sky": [{"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080},
            {"img": "sets/jin_land/ridge_far.png", "depth": 0.15, "pos": [0, 430], "w": 1080},
            {"img": "sets/jin_land/ridge_mid.png", "depth": 0.3, "pos": [0, 740], "w": 1080},
            {"img": "sets/jin_land/ridge_near.png", "depth": 0.45, "pos": [0, 830], "w": 1080},
            {"img": "sets/jin_land/ground.png", "depth": 0.9, "pos": [540, 1330], "anchor": [0.5, 0], "w": 1200, "repeat": "x"}],
    "study": [{"img": "sets/study/wall.png", "depth": 0.1, "pos": [-100, 0], "w": 1280}],
    "plain": [],
    "dark": [{"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080, "alpha": 0.4}],
}
ACTORS = {
    "sgm": {"id": "sgm", "img": "chars/sgm_finger.png", "pos": [300, 1585], "h": 520},
    "zb": {"id": "zb", "img": "chars/zb_hi_laugh.png", "pos": [540, 1620], "h": 1000},
}


def peek(fx_list, times, bg="sky", actor=None, S=0.5, cols=5, dur=6.0, grade="normal", label=True):
    fxreg.load_plugins()
    tl = Timeline.load(VOICE)
    store = AssetStore(S, [])
    spec = {"id": "peek", "from": {"line": 0}, "bg": BGS[bg], "actors": [ACTORS[actor]] if actor else [], "fx": fx_list, "grade": grade}
    scene = Scene(spec, tl, 0.0, dur, store, fxreg.FX)
    cv = Canvas(store, S, C.FPS, dur, seed=1)
    tiles = []
    for t in times:
        f = int(round(t * C.FPS))
        cv.rng = np.random.default_rng([1, f])
        scene.draw(cv, t, t)
        im = cv.img.copy()
        if label:
            cv2.putText(im, f"{t:.2f}s", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(im, f"{t:.2f}s", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(im)
    return grid(tiles, cols), scene


def peek_transition(tr, ps, S=0.5, cols=5, bg_a="sky", bg_b="study"):
    fxreg.load_plugins()
    tl = Timeline.load(VOICE)
    store = AssetStore(S, [])
    frames = []
    for bg in (bg_a, bg_b):
        spec = {"id": bg, "from": {"line": 0}, "bg": BGS[bg], "actors": [ACTORS["sgm"]] if bg == bg_a else [ACTORS["zb"]]}
        scene = Scene(spec, tl, 0.0, 3.0, store, fxreg.FX)
        cv = Canvas(store, S, C.FPS, 3.0, seed=1)
        scene.draw(cv, 1.0, 1.0)
        frames.append(cv.img.copy())
    p = dict(tr)
    plug = fxreg.TRANSITIONS[p["type"]]
    cvt = Canvas(store, S, C.FPS, 0.0)
    tiles = []
    for pp in ps:
        im = plug.fn(frames[0], frames[1], pp, p, cvt)
        im = np.ascontiguousarray(im)
        cv2.putText(im, f"p={pp:.2f}", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(im, f"p={pp:.2f}", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(im)
    return grid(tiles, cols)


def grid(tiles, cols):
    h, w = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    out = np.full((rows * (h + 4), cols * (w + 4), 3), 60, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        out[r * (h + 4):r * (h + 4) + h, c * (w + 4):c * (w + 4) + w] = t
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fx", nargs="?", help="一个特效的 JSON")
    ap.add_argument("--fx-list")
    ap.add_argument("--transition")
    ap.add_argument("--t", default="0,0.1,0.2,0.3,0.5")
    ap.add_argument("--p", default="0.05,0.25,0.5,0.75,0.95")
    ap.add_argument("--bg", default="sky")
    ap.add_argument("--actor")
    ap.add_argument("--S", type=float, default=0.5)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--dur", type=float, default=6.0)
    ap.add_argument("--grade", default="normal")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.transition:
        img = peek_transition(json.loads(a.transition), [float(x) for x in a.p.split(",")], a.S, a.cols)
    else:
        lst = json.loads(a.fx_list) if a.fx_list else [json.loads(a.fx)]
        img, _ = peek(lst, [float(x) for x in a.t.split(",")], a.bg, a.actor, a.S, a.cols, a.dur, a.grade)
    ok, buf = cv2.imencode(Path(a.out).suffix or ".png", img)
    Path(a.out).write_bytes(buf.tobytes())
    print("→", a.out, img.shape[1], "x", img.shape[0])


if __name__ == "__main__":
    main()
