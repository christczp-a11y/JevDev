"""proto17 测试用的界面卡片和音效：程序生成（用引擎自己的字体和卡片函数），写到 gen/ 和 sfx/（两个目录都不进 git）。
    .venv/Scripts/python video/motion/tests/proto17/make_assets.py
卡片本来是阶段 B 的特效（游戏卡片、清单、考你）：A 阶段用普通图层 + 补间 + 出场把它们摆出来，证明引擎不靠特效也能还原小样。"""
import math
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from engine import consts as C                       # noqa: E402
from engine.sprites import card_image, text_image     # noqa: E402

GEN = HERE / "gen"
RED, INK = C.RED, C.INK


def save(im, name):
    (GEN / "cards").mkdir(parents=True, exist_ok=True)
    im.save(GEN / "cards" / name)


def make_cards():
    save(card_image(["有人跟你要地！"], "title", 70, (255, 255, 255), RED, padx=40, pady=18), "ask.png")
    save(card_image(["给"], "title", 76, (255, 255, 255), (47, 125, 91), padx=70, pady=16), "btn_give.png")
    save(card_image(["不给"], "title", 76, (255, 255, 255), RED, padx=56, pady=16), "btn_no.png")
    save(card_image(["第 1 关：忍"], "title", 64, (255, 250, 238), (60, 48, 40), padx=40, pady=16), "level1.png")
    for i, t in enumerate(["高大", "射箭", "才艺", "口才", "果断"]):
        b = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
        d = ImageDraw.Draw(b)
        d.ellipse((4, 4, 185, 185), fill=(255, 252, 244))
        d.ellipse((14, 14, 175, 175), fill=(233, 178, 60), outline=(150, 95, 30), width=5)
        ti = text_image(t, "title", 58, INK)
        b.alpha_composite(ti, ((190 - ti.width) // 2, (190 - ti.height) // 2 - 4))
        save(b, f"badge{i + 1}.png")
    # 书页边（原型里前景那条纸）
    w, h = C.W + 240, 700
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(3)
    top = [18 + 6 * math.sin(x / 37) + rng.normal(0, 1.2) for x in range(w)]
    for x in range(w):
        d.line((x, top[x] - 10, x, top[x]), fill=(80, 60, 40, 60))
        d.line((x, top[x], x, h), fill=(239, 228, 204, 255))
    for i in range(6):
        y = 120 + i * 70
        d.line((140, y, w - 140, y), fill=(220, 205, 178, 255), width=3)
    save(im, "page.png")


def make_sfx():
    (HERE / "sfx").mkdir(exist_ok=True)
    sr = 44100
    tt = lambda d: np.arange(int(d * sr)) / sr
    out = {}
    out["tick"] = np.sin(2 * np.pi * 1800 * tt(0.05)) * np.exp(-tt(0.05) * 60) * 0.5
    for i in range(5):
        f = 880 * 2 ** (i / 12 * 2)
        out[f"ding{i + 1}"] = np.sin(2 * np.pi * f * tt(0.35)) * np.exp(-tt(0.35) * 9) * 0.5
    out["whoosh"] = np.random.default_rng(1).normal(0, 1, len(tt(0.35))) * np.hanning(len(tt(0.35))) * 0.18
    for n, y in out.items():
        with wave.open(str(HERE / "sfx" / f"{n}.wav"), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    make_cards()
    make_sfx()
    print("生成完毕：", GEN, HERE / "sfx")
