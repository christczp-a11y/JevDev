"""特效样片合集专用：在画面下方写一个小标签（特效名），只给样片用，正式的集不用。
分镜表：{"type": "label", "text": "3 / 44  集中线  lines_focus"}   钉在屏幕上，整个镜头都在。"""
from engine import consts as C
from engine.sprites import paper_edge, rounded_rect, sprite_from_pil, text_image
from fx import fx


def _build(text):
    size = 38
    t = text_image(text, "body", size, C.INK)
    while t.width > 960 and size > 20:          # 长名字缩字号，别被画面边缘切掉
        size -= 2
        t = text_image(text, "body", size, C.INK)
    w, h = t.width + 56, t.height + 22
    im = rounded_rect(w, h, C.CREAM, 26, (90, 70, 55), 4)
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
    return paper_edge(im, 7, True)


_memo = {}


@fx("label", layer="front", sfx=None, check=lambda p: [] if isinstance(p.get("text"), str) else ["label 要写 text"])
def label(canvas, t, params, at):
    key = (params["text"], canvas.S)
    if key not in _memo:
        _memo[key] = sprite_from_pil(_build(params["text"]), canvas.S)
    canvas.blit(_memo[key], C.W / 2 - 20, 1712, alpha=1.0, depth=0)
