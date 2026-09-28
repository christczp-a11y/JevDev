"""把我们已经生成的图片素材整理成 MoneyPrinterTurbo 能用的样子（只做最少的处理）：
MPT 会丢掉短边小于 480 像素的图片，而我们的人物、道具图大多只有两三百像素宽，而且是透明底。
所以每张图原样等比放大，居中放在一张纯米色纸底的 1080×1920 竖屏画布上。不拼场景、不摆位置，剩下的交给 MPT。
顺序按故事排（MPT 用本地素材时不会按文案挑图，只按给定的顺序轮流放）。"""
import sys
from pathlib import Path

from PIL import Image

A = Path("video/assets")
ORDER = [   # （素材, 画面里是什么）
    ("sets/qin_gate/far", "远山"), ("sets/qin_gate/gate", "都城城楼"), ("sets/qin_gate/stall", "集市货摊"),
    ("chars/shangyang_stand", "商鞅"), ("props/log", "木头"), ("props/board", "告示牌"),
    ("chars/farmer_doubt", "农夫怀疑"), ("chars/auntie_hands", "大婶叉腰不信"), ("chars/shangyang_point", "商鞅指着喊五十金"),
    ("chars/youth_excited", "小伙：我来"), ("chars/youth_coins", "小伙领赏"), ("chars/farmer_happy", "农夫笑了"),
    ("chars/auntie_happy", "大婶笑了"), ("chars/shangyang_proud", "商鞅得意"), ("props/scroll", "新法竹简"),
]
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for i, (src, what) in enumerate(ORDER, 1):
    im = Image.open(A / f"{src}.png").convert("RGBA")
    k = min(960 / im.width, 1500 / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    canvas = Image.new("RGBA", (1080, 1920), (239, 230, 212, 255))
    canvas.alpha_composite(im, ((1080 - im.width) // 2, (1920 - im.height) // 2))
    canvas.convert("RGB").save(out / f"{i:02d}_{what}.png")
print(len(ORDER), "张 →", out)
