"""配音时间线（voice.py 写的 timeline.json）和锚点解析。

锚点 = {"line": 第几句, "word": "这句里的字", "nth": 第几次出现（默认 1）, "dt": 偏移秒}。
- 没有 word：这一句的开头（t0）。有 word：这个词第一个字开口的时刻。
- 每个字的时间 = 这一句「有声部分」按字数（去掉标点）比例分配。Qwen3-TTS 不给字级时间，误差约 0.1–0.2 秒。
- edge="end"（只有「to」这种表示结束的地方用）：没有 word = 这一句的结尾（t1）；有 word = 这个词最后一个字说完的时刻。
- 没有 line、只有 dt：相对本镜头开头。
"""
import json
import re
from pathlib import Path

from .consts import ASSETS, HEAD_KEEP, TAIL_KEEP

ANCHOR_KEYS = {"line", "word", "nth", "dt"}
ACTION = "动作"


class AnchorError(ValueError):
    pass


def core(s):
    """去掉标点和空白，只留字（和 voice.py、story.py 数字数的规则一样）。"""
    return re.sub(r"[^\w]", "", s)


class Timeline:
    def __init__(self, data, folder):
        self.folder = Path(folder)
        self.lines = data["lines"]
        self.duration = float(data["duration"])

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        p = folder / "timeline.json"
        if not p.exists():
            raise AnchorError(f"找不到配音时间线 {p}（先跑第 3 步 voice.py）")
        return cls(json.loads(p.read_text(encoding="utf-8")), folder)

    # ---------- 一句话 ----------
    def line(self, i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(self.lines):
            raise AnchorError(f"锚点里的 line={i!r} 不对：时间线只有 {len(self.lines)} 句（从 0 数）")
        return self.lines[i]

    def is_speech(self, i):
        ln = self.lines[i]
        return ln["who"] != ACTION and bool(core(ln.get("text", "")))

    def speech_span(self, i):
        """这一句真正有声音的时间段（秒）。"""
        ln = self.line(i)
        t0, t1 = float(ln["t0"]), float(ln["t1"])
        s0 = t0 + HEAD_KEEP
        s1 = t0 + float(ln["voiced_end"]) if ln.get("voiced_end") else t1 - TAIL_KEEP
        return (s0, s1) if s1 - s0 > 0.05 else (t0, t1)

    def word_span(self, i, word, nth=1):
        ln = self.line(i)
        text = core(ln.get("text", ""))
        w = core(word)
        if not w:
            raise AnchorError(f"line {i} 的 word={word!r} 去掉标点后是空的")
        pos, start = -1, 0
        for _ in range(int(nth)):
            pos = text.find(w, start)
            if pos < 0:
                break
            start = pos + 1
        if pos < 0:
            raise AnchorError(f"line {i}（{ln.get('text', '')!r}）里找不到第 {nth} 个 {word!r}")
        s0, s1 = self.speech_span(i)
        per = (s1 - s0) / len(text)
        return s0 + pos * per, s0 + (pos + len(w)) * per

    # ---------- 锚点 ----------
    def resolve(self, anchor, shot_t0=None, edge="start"):
        if not isinstance(anchor, dict):
            raise AnchorError(f"锚点必须写成 {{\"line\": 第几句, \"word\": \"字\", \"dt\": 秒}}，不能写死秒数：{anchor!r}")
        bad = set(anchor) - ANCHOR_KEYS
        if bad:
            raise AnchorError(f"锚点里有不认识的字段 {sorted(bad)}：{anchor!r}（只认 line、word、nth、dt）")
        dt = float(anchor.get("dt", 0.0))
        if "line" not in anchor:
            if shot_t0 is None:
                raise AnchorError(f"这里的锚点必须写 line：{anchor!r}")
            if "word" in anchor:
                raise AnchorError(f"锚点有 word 就必须有 line：{anchor!r}")
            return shot_t0 + dt
        i = anchor["line"]
        ln = self.line(i)
        if "word" in anchor:
            a, b = self.word_span(i, anchor["word"], anchor.get("nth", 1))
            return (a if edge == "start" else b) + dt
        return (float(ln["t0"]) if edge == "start" else float(ln["t1"])) + dt

    # ---------- 音频文件 ----------
    def audio_path(self, i):
        """这一句的配音文件；动作行和没有台词的返回 None；台词有、文件找不到返回 False。"""
        ln = self.line(i)
        if ln["who"] == ACTION or not core(ln.get("text", "")):
            return None
        for cand in (self.folder / ln["audio"] if ln.get("audio") else None,
                     ASSETS / ln["series_audio"] if ln.get("series_audio") else None):
            if cand is not None and cand.exists():
                return cand
        return False
