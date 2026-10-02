"""每一帧最上面的固定界面：顶部标题条、水印、字幕 + 说话人标签。由合成器按时间线自动加，分镜表里不写。
位置照《版式和画风》：标题条 y 90–330，字幕卡底边贴着平台遮挡区上沿 y 1615（一行、两行都从底边往上长，说话人标签跟着卡片走），水印右上角。字体只有两种：ZCOOL KuaiLe（标题）、Noto Sans SC Bold（字幕、标签、水印）。
界面画在转场之后，转场（翻页、擦过）不会把标题条和字幕一起带走。
"""
import json
import re
from functools import lru_cache

from . import consts as C
from .sprites import rounded_rect, sprite_from_pil, subtitle_boxes, subtitle_image, text_image
from .timeline import core
from PIL import Image, ImageDraw

_CLOSERS = "，。！？；：、）」』”’…—.,!?;:)"
_STOPS = "，。！？；：、…—"


def split_pages(text, per_line=C.SUB_LINE_CHARS, max_lines=C.SUB_MAX_LINES):
    """一句台词 → 若干页字幕，每页最多 max_lines 行、每行最多 per_line 个字；优先在标点处分页。"""
    limit = per_line * max_lines
    clauses = []
    for c in re.split(r"(?<=[，。！？；：、…—])", text):
        if not c:
            continue
        if clauses and not core(c):                   # 「？！」「……！」这种连着的标点归上一个分句，别单独成页（单独成页 = 0 帧，字幕上这个字就没了）
            clauses[-1] += c
        else:
            clauses.append(c)
    pages, cur = [], ""
    for c in clauses:
        while len(c) > limit:                     # 一个分句就超长：硬切
            if cur:
                pages.append(cur)
                cur = ""
            pages.append(c[:limit])
            c = c[limit:]
        if len(cur) + len(c) <= limit:
            cur += c
        else:
            pages.append(cur)
            cur = c
    if cur:
        pages.append(cur)
    return pages


def wrap_lines(page, per_line=C.SUB_LINE_CHARS):
    """一页字幕折成 1–2 行：尽量在标点后、两行差不多长的地方折，行首不放标点。"""
    if len(page) <= per_line:
        return [page]
    best = None
    for i in range(1, len(page)):
        if i > per_line or len(page) - i > per_line or page[i] in _CLOSERS:
            continue
        score = abs(i - len(page) / 2) - (2.0 if page[i - 1] in _STOPS else 0.0)
        if best is None or score < best[0]:
            best = (score, i)
    if best is None:                                  # 满行的下一个字正好是标点：让标点挂在上一行末尾（那一行多一格），不放到下一行行首
        for i in range(per_line + 1, per_line + 3):
            if i < len(page) and page[i - 1] in _CLOSERS and page[i] not in _CLOSERS and len(page) - i <= per_line:
                best = (0, i)
                break
    if best is None:
        best = (0, per_line)
    return [page[:best[1]], page[best[1]:]]


def line_pages(tl, i):
    """第 i 句的字幕页：[(开始秒, 结束秒, [行])]。首页从这句的 t0 起，末页到 t1 止，页与页的分界按字数比例落在有声部分里。"""
    ln = tl.lines[i]
    pgs = split_pages(ln["text"])
    s0, s1 = tl.speech_span(i)
    total = sum(len(core(p)) for p in pgs) or 1
    out, acc = [], 0
    for k, p in enumerate(pgs):
        a = ln["t0"] if k == 0 else s0 + (s1 - s0) * acc / total
        acc += len(core(p))
        b = ln["t1"] if k == len(pgs) - 1 else s0 + (s1 - s0) * acc / total
        out.append((a, b, wrap_lines(p)))
    return out


@lru_cache(maxsize=None)
def subtitle_rects(who, lines):
    """一页字幕（说话人 who、行 lines 是元组）贴在画面上时，卡片和说话人标签各占的方框（设计坐标，含白纸边）：{"card": (l, t, r, b), "tag": (l, t, r, b)}。
    和 UI.draw 一样：图的底边贴 SUB_BOTTOM_Y、横向以 SUB_CENTER_X 居中（不跟镜头动）。storyboard_check 的 [字幕] 用。"""
    w, h, card, tag = subtitle_boxes(who.replace("+", "、"), list(lines), C.SUB_FONT)
    ox, oy = C.SUB_CENTER_X - w / 2, C.SUB_BOTTOM_Y - h
    return {"card": (ox + card[0], oy + card[1], ox + card[2], oy + card[3]), "tag": (ox + tag[0], oy + tag[1], ox + tag[2], oy + tag[3])}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class UI:
    def __init__(self, store, tl, sb):
        self.tl = tl
        self.S = store.S
        self.speakers = sb.get("speakers", {})
        self.houses = {}
        if C.SERIES_STYLE.exists():
            self.houses = json.loads(C.SERIES_STYLE.read_text(encoding="utf-8")).get("houses", {})
        self.title_key = [sb.get("title"), sb.get("no"), sb.get("name")]
        self.title = self._title(sb)
        self.wm = sprite_from_pil(self._watermark(), self.S)
        self._subs = {}       # 句号 → [(帧起, 帧止, Sprite, 是否首页, 是否末页)]

    # ---------- 标题条和水印 ----------
    def _title(self, sb):
        lines = sb.get("title") or []
        if not lines:
            return None
        w, h = 960, C.TITLE_Y1 - C.TITLE_Y0
        kick_text = C.KICKER_FMT.format(no=sb.get("no", ""), name=sb.get("name", "")).rstrip(" ·")          # 没写本集名就只剩「第 N 集」
        kick = text_image(kick_text, "body", 30, C.RED)
        cols = [C.INK, C.RED]
        gap, avail = 8, h - 20 - kick.height - 14
        size = min(84, int(880 // max(len(l) for l in lines)))
        while True:                                   # 字号从大往小试，直到两行装得进标题条
            body = [text_image(l, "title", size, cols[min(i, 1)]) for i, l in enumerate(lines)]
            total = sum(b.height for b in body) + gap * (len(body) - 1)
            if total <= avail or size <= 40:
                break
            size -= 2
        im = rounded_rect(w, h, C.CREAM, 36, (90, 70, 55), 6)
        im.alpha_composite(kick, ((w - kick.width) // 2, 20))
        y = 20 + kick.height + max(0, (h - 20 - kick.height - 14 - total) // 2)
        for b in body:
            im.alpha_composite(b, ((w - b.width) // 2, y))
            y += b.height + gap
        e = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
        ImageDraw.Draw(e).rounded_rectangle((0, 0, w + 15, h + 15), 44, fill=C.WHITE_EDGE + (255,))
        e.alpha_composite(im, (8, 8))
        return sprite_from_pil(e, self.S)

    def _watermark(self):
        return text_image(C.WM_TEXT, "body", 26, (255, 255, 255), stroke=3, stroke_fill=(60, 48, 40), pad=2)

    # ---------- 字幕 ----------
    def _color(self, who):
        if who == "司马光":
            return C.RED
        if who == "旁白":
            return C.NARR
        house = self.speakers.get(who)
        if house and house.startswith("#"):
            return hex_rgb(house)
        if house in self.houses:
            return hex_rgb(self.houses[house]["color"])
        return C.NARR

    def pages(self, i):
        return line_pages(self.tl, i)

    def events(self, i):
        """第 i 句的字幕事件 → [(帧起, 帧止, 行, 首页?, 末页?)]（帧号 = 绝对时间 × 30 取最近的整数）。"""
        pg = self.pages(i)
        return [(round(a * C.FPS), round(b * C.FPS), lines, k == 0, k == len(pg) - 1) for k, (a, b, lines) in enumerate(pg)]

    def _build(self, i):
        if i not in self._subs:
            ln = self.tl.lines[i]
            out = []
            for fa, fb, lines, first, last in self.events(i):
                who = str(ln["who"])
                im, _ = subtitle_image(who.replace("+", "、"), lines, self._color(who.split("+")[0]), C.SUB_FONT)   # 齐声：标签写「甲、乙、丙」，用第一个人的颜色
                out.append((fa, fb, sprite_from_pil(im, self.S), first, last))
            self._subs[i] = out
        return self._subs[i]

    def fingerprint(self, f0, f1):
        """[f0, f1) 这段画面里界面（标题条、字幕）的内容：镜头缓存的哈希要用，改了台词、字幕分页、标题、说话人颜色就重编码这个片段。"""
        subs = []
        for i in self.speech_indices():
            ln = self.tl.lines[i]
            if round(ln["t1"] * C.FPS) >= f0 and round(ln["t0"] * C.FPS) < f1:
                subs.append([str(ln["who"]), list(self._color(str(ln["who"]).split("+")[0])), self.events(i)])
        return {"title": self.title_key, "subs": subs}

    def speech_indices(self):
        return [i for i in range(len(self.tl.lines)) if self.tl.is_speech(i)]

    def prepare(self, f0, f1):
        """先把 [f0, f1) 帧范围内出现的字幕图都画好。"""
        self._active = []
        for i in self.speech_indices():
            ln = self.tl.lines[i]
            if round(ln["t1"] * C.FPS) >= f0 and round(ln["t0"] * C.FPS) < f1:
                self._active += self._build(i)
        self._active.sort(key=lambda e: e[0])

    def draw(self, cv, f):
        if self.title is not None:
            cv.blit(self.title, 60 - 8, C.TITLE_Y0 - 8, anchor=(0, 0))
        cv.blit(self.wm, C.W - 36, 28, anchor=(1.0, 0.0), alpha=0.9)
        fade = max(1, round(C.SUB_FADE * C.FPS))
        for fa, fb, sp, first, last in self._active:
            if fa <= f < fb:
                al = 1.0
                if first:
                    al = min(al, (f - fa + 1) / fade)
                if last:
                    al = min(al, (fb - f) / fade)
                cv.blit(sp, C.SUB_CENTER_X, C.SUB_BOTTOM_Y, alpha=al, anchor=(0.5, 1.0))     # 底边贴 y 1615，往上长
