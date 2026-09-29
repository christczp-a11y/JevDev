#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""史料简报自动核对（工作流第 1 步；对应 PITFALLS S2「没有逐句对原文」、S14「简报里没有注音」）。

用法：
  .venv/Scripts/python video/source_check.py video/stories/tj01/source.md [--refresh] [--check-links]

查什么（简报 source.md 的写法）：
  1. 「…」只用来标古书原文，后面紧跟全角括号的出处短码：「天子之職莫大於禮」（鉴1）；
     多个短码用全角分号：（鉴1；胡1），在任一本里找到就算。短码必须在「来源」一节登记。
     去掉嵌套的『』（原文页面里的引号也一起去掉）后，逐字到下载的维基文库原文里找；
     中间用「……」省略的，每段都要找到。
     逐字找不到时，再去掉标点、按下面的异体字表比一次；这样才找到的算通过，但标「异体匹配」，
     请人看一眼。原文本身就写「歳」的，简报也写「歳」，是逐字通过，不算异体。
     去维基标记时：注文（原始标记里的 {{*|…}}，即胡注、韦昭注、战国策注等小字）保留，
     每条注文单独成段，引文不能跨着正文和注文拼出来，所以（胡1）能引胡注和反切；
     校勘记（<ref>…</ref>）是维基编辑者写的，不是古书原文，去掉，不能拿来核引文。
  2. 每处引文 <= 20 个汉字（只数汉字，不数标点；「……」连接的几段合计；嵌套『』里的字也算）。
     里面一个汉字都没有的（说明文字里提到「」「……」这两个符号本身），不算引文，标「跳过」。
  3. 「来源」一节每行一条：`- 短码：完整URL`。维基文库的短码：鉴N、胡N、史N、国语N、策赵一、
     韩非喻老（下载 action=raw 原文，缓存在 video/out/<集>/source_check/）；其他网页写 网1、网2……
     （只支持事实，不能被「」引用）。每个链接必须是完整的 http(s) URL；加 --check-links 时
     对非维基链接发请求，不是 200 就报错。
  4. 【未核实】只能写成【未核实，不进剧本】（【待查】可以有）。
  5. 第四节下面必须有 `### 注音（人名、地名、生僻字）` 和 `### 多音字（第 4 步配音用）`
     两个小节，各带一张不是空的表格。

输出：每条引文一行（通过 / 异体匹配 / 错误原因 + 行号），最后一行「N 条引文，M 个错误」
（M 按错误原因数，一条引文可以有两个原因）。
退出码：有任何错误是 1，全过是 0，参数或文件读不了是 2。
只读输入文件，不改简报；只往 video/out/<集>/source_check/ 写下载的原文。
"""
import argparse
import hashlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAX_HAN = 20
UA = "JevDev-source_check/1.0 (children's history animation; local research script)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HAN_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ffff]")
NOTE_EDGE = "\ue000"  # 注文两头的隔断符（私用区字符），引文不会跨过它匹配
ELLIPSIS_RE = re.compile(r"[…⋯]+|\.{3,}")
QUOTE_MARKS = str.maketrans("", "", "「」『』")

# 异体字表：同一个字的不同写法（维基文库各本用字不一，校勘本多用「為」，胡注本多用「爲」）。
# 两边都先按这张表换成同一个字再比；只在逐字找不到时才用，所以只会多放过写法不同的，
# 不会放过错字。要加新的异体字，成对写在这里，并注明哪一本用哪个写法。
VARIANTS = {
    "爲": "為",   # 胡注本、史记、国语 用「爲」，校勘本用「為」
    "歳": "歲",   # 史记「歳餘」
    "眞": "真",   # 史记、战国策 用「眞」
    "竈": "灶",   # 竈 是繁体，灶 是简体 / 俗体
    "臺": "台",
    "鑒": "鑑",   # 資治通鑑 / 資治通鑒
    "於": "于",
    "脣": "唇",
    "緜": "綿",
}


# ---------------------------------------------------------------- 简报里的「来源」一节

def find_heading(lines, pattern):
    """返回 (行下标, 标题级别)；找不到返回 None。"""
    rx = re.compile(pattern)
    fence = False
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s*(.*?)\s*$", ln)
        if m and rx.search(m.group(2)):
            return i, len(m.group(1))
    return None


def section_end(lines, start, level):
    """从 start 的下一行起，到下一个同级或更高级标题之前。"""
    for j in range(start + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s", lines[j])
        if m and len(m.group(1)) <= level:
            return j
    return len(lines)


def family_error(code, url, wiki):
    """维基文库短码：必须是维基文库链接，并指向对应的书和卷；返回错误说明，对得上返回 None。"""
    u = urllib.parse.unquote(url)
    juan = re.findall(r"卷(\d+)", u)
    n = int(juan[-1]) if juan else None
    rules = [
        (r"鉴(\d+)", lambda m: "資治通" in u and "胡三省" not in u and n == int(m[1]), "《資治通鑑》卷{0}"),
        (r"胡(\d+)", lambda m: "胡三省" in u and n == int(m[1]), "《資治通鑒（胡三省音注）》卷{0}"),
        (r"史(\d+)", lambda m: "史記" in u and n == int(m[1]), "《史記》卷{0}"),
        (r"国语(\d+)", lambda m: "國語" in u and n == int(m[1]), "《國語》卷{0}"),
        (r"策赵一", lambda m: "戰國策" in u and "趙" in u, "《戰國策》趙策一"),
        (r"韩非喻老", lambda m: "韓非子" in u and "喻老" in u, "《韓非子·喻老》"),
    ]
    for pat, ok, what in rules:
        m = re.fullmatch(pat, code)
        if m:
            if not wiki:
                return "短码 %s 应指向维基文库，这个链接不是" % code
            if not ok(m):
                return "短码 %s 应指向维基文库%s，这个 URL 对不上" % (code, what.format(*m.groups()))
            return None
    return "未知短码「%s」（维基文库短码是 鉴N、胡N、史N、国语N、策赵一、韩非喻老；其他网页用 网1、网2……）" % code


def parse_sources(lines, out):
    """读「来源」一节，返回 {短码: dict(url, line, kind)}；格式问题写进 out.errors。"""
    sources = {}
    h = find_heading(lines, r"^来源")
    if not h:
        out.err("来源", "找不到「来源」一节（## 来源）")
        return sources
    start, level = h
    for i in range(start + 1, section_end(lines, start, level)):
        ln = lines[i].strip()
        if not ln or not re.match(r"^[-*+]\s", ln):
            continue
        no = i + 1
        m = re.match(r"^[-*+]\s*([^\s：:/]+)\s*[：:]\s*(\S.*?)\s*$", ln)
        if not m or m.group(1).lower() in ("http", "https"):
            out.err("来源", "第%d行 格式应为「- 短码：完整URL」：%s" % (no, ln[:60]))
            continue
        code, url = m.group(1), m.group(2)
        pu = urllib.parse.urlparse(url)
        if not re.fullmatch(r"https?://\S+", url) or not pu.netloc:
            out.err("来源", "第%d行 %s 的链接不是完整的 http(s) URL：%s" % (no, code, url[:60]))
            continue
        if re.search(r"[（）、，；。]", url):
            out.err("来源", "第%d行 %s 的 URL 里混进了中文标点（链接后面别写说明）：%s" % (no, code, url[:60]))
            continue
        if code in sources:
            out.err("来源", "第%d行 短码 %s 重复（第%d行已登记）" % (no, code, sources[code]["line"]))
            continue
        wiki = pu.netloc.endswith("wikisource.org")
        if re.fullmatch(r"网\d+", code):
            kind = "web"
        else:
            bad = family_error(code, url, wiki)
            if bad:
                out.err("来源", "第%d行 %s" % (no, bad))
                continue
            kind = "wiki"
        sources[code] = {"url": url, "line": no, "kind": kind}
    return sources


# ---------------------------------------------------------------- 下载和去维基标记

def http_get(url, ua=UA, timeout=30):
    # 链接里的中文（和空格）按 UTF-8 百分号编码；已经编码过的 %XX 保持不动
    url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def raw_url(url):
    """https://zh.wikisource.org/wiki/<页面名> -> action=raw 地址（中文按 UTF-8 百分号编码）。"""
    pu = urllib.parse.urlparse(url)
    if not pu.path.startswith("/wiki/"):
        raise ValueError("不是 /wiki/ 页面链接")
    title = urllib.parse.unquote(pu.path[len("/wiki/"):])
    return "%s://%s/w/index.php?title=%s&action=raw" % (
        pu.scheme, pu.netloc, urllib.parse.quote(title, safe="/_()"))


def load_raw(code, url, cache_dir, refresh):
    """返回 (原文, 来自缓存?)。缓存文件名带 URL 的哈希：同一个短码改了链接会重新下载。"""
    f = cache_dir / ("%s.%s.txt" % (code, hashlib.md5(url.encode("utf-8")).hexdigest()[:8]))
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8"), True
    status, body = http_get(raw_url(url))
    if status != 200:
        raise RuntimeError("HTTP %s" % status)
    cache_dir.mkdir(parents=True, exist_ok=True)
    f.write_bytes(body)
    time.sleep(0.5)  # 对维基文库客气一点
    return body.decode("utf-8"), False


def _close_of(s, i):
    """s[i:i+2] == '{{'；返回配对的 '}}' 之后的位置，配不上返回 -1。"""
    depth, k = 0, i
    while k < len(s):
        if s.startswith("{{", k):
            depth += 1
            k += 2
        elif s.startswith("}}", k):
            depth -= 1
            k += 2
            if depth == 0:
                return k
        else:
            k += 1
    return -1


def _drop_templates(s):
    out, i = [], 0
    while i < len(s):
        if s.startswith("{{", i):
            j = _close_of(s, i)
            if j > 0:
                i = j
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _inline(s):
    s = s.replace("-{", "").replace("}-", "")
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"<[^>]+>", "", s)
    return s.translate(QUOTE_MARKS)  # 嵌套的「」『』两边都去掉，不算异体


def wiki_views(raw):
    """去掉维基标记，返回两个文本：只有正文；正文加注文（{{*|…}}，即胡注、韦昭注等小字，每条单独成段）。
    引文在任一个里找到就算，所以胡注本里的胡注也能引，又不会把注文和正文拼在一起。"""
    raw = re.sub(r"<ref[^>]*/>", "", raw)
    raw = re.sub(r"<ref[^>]*>.*?</ref>", "", raw, flags=re.S)
    main, full, i = [], [], 0
    while i < len(raw):
        if raw.startswith("{{", i):
            j = _close_of(raw, i)
            if j > 0:
                body = raw[i + 2:j - 2]
                if body.startswith("*|"):
                    full.append(NOTE_EDGE + _drop_templates(body[2:]) + NOTE_EDGE)
                i = j
                continue
        main.append(raw[i])
        full.append(raw[i])
        i += 1
    return [_inline("".join(main)), _inline("".join(full))]


class View:
    """一个文本，加上只留汉字（异体字换成同一个字）的版本，和汉字到原位置的对照。"""

    def __init__(self, text):
        self.text = text
        han, idx = [], []
        for i, ch in enumerate(text):
            if HAN_RE.match(ch):
                han.append(VARIANTS.get(ch, ch))
                idx.append(i)
            elif ch == NOTE_EDGE:
                han.append(ch)
                idx.append(i)
        self.han, self.idx = "".join(han), idx


def han_key(s):
    return "".join(VARIANTS.get(c, c) for c in s if HAN_RE.match(c))


def find_segment(seg, views):
    """返回 ('exact', 片段) / ('variant', 原文里对应的片段) / None。"""
    for v in views:
        if seg in v.text:
            return "exact", seg
    key = han_key(seg)
    if key:
        for v in views:
            p = v.han.find(key)
            if p >= 0:
                return "variant", v.text[v.idx[p]:v.idx[p + len(key) - 1] + 1].replace("\n", " ")
    return None


# ---------------------------------------------------------------- 引文

def extract_quotes(lines):
    """每个「…」：{line, inner, codes(None=没有短码), unclosed}。嵌套的『』算在引文里面。"""
    quotes, fence = [], False
    for no, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        i = 0
        while i < len(ln):
            if ln[i] != "「":
                i += 1
                continue
            depth, j = 0, i
            while j < len(ln):
                if ln[j] == "「":
                    depth += 1
                elif ln[j] == "」":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= len(ln):
                quotes.append({"line": no, "inner": ln[i + 1:], "codes": None, "unclosed": True})
                break
            inner = ln[i + 1:j]
            m = re.match(r"（([^（）]*)）", ln[j + 1:])
            codes = None
            if m:
                codes = [c.strip() for c in re.split(r"[；;]", m.group(1)) if c.strip()]
            quotes.append({"line": no, "inner": inner, "codes": codes, "unclosed": False})
            i = j + 1
    return quotes


def check_quote(q, sources, views):
    """返回 (状态, 说明列表)。状态：通过 / 异体匹配 / 错误 / 跳过。"""
    inner = q["inner"]
    if q["unclosed"]:
        return "错误", ["「 没有配对的 」"]
    errs = []
    n = len(HAN_RE.findall(inner))
    if n == 0:  # 「」「……」这样谈符号本身的说明文字，没有古书原文可核，不算引文
        return "跳过", ["没有汉字，不算引文"]
    if n > MAX_HAN:
        errs.append("引文 %d 字，超过 %d 字上限" % (n, MAX_HAN))
    if not q["codes"]:
        errs.append("没有出处短码（「」后要紧跟（鉴1））")
        return "错误", errs
    usable = []
    for c in q["codes"]:
        s = sources.get(c)
        if s is None:
            errs.append("短码「%s」不在来源里" % c)
        elif s["kind"] == "web":
            errs.append("%s 是普通网页，只支持事实，不能被「」引用" % c)
        elif c not in views:
            errs.append("来源 %s 没有下载到原文，没法核对" % c)
        else:
            usable.append(c)
    if not usable:
        return "错误", errs
    segs = [g.strip() for g in ELLIPSIS_RE.split(inner.translate(QUOTE_MARKS))]
    segs = [g for g in segs if g]
    best, miss = None, []
    for c in usable:
        found = [find_segment(g, views[c]) for g in segs]
        if all(found):
            exact = all(f[0] == "exact" for f in found)
            cand = ("通过" if exact else "异体匹配", c,
                    "" if exact else "；".join(f[1] for f in found if f[0] == "variant"))
            if best is None or (cand[0] == "通过" and best[0] != "通过"):
                best = cand
        else:
            miss.append("在 %s 里找不到「%s」" % (c, "」「".join(g for g, f in zip(segs, found) if not f)))
    if best is None:
        return "错误", errs + miss
    if errs:
        return "错误", errs
    if best[0] == "异体匹配":
        return "异体匹配", ["%s 原文作：%s" % (best[1], best[2])]
    return "通过", []


# ---------------------------------------------------------------- 其他检查

def check_unverified(lines, out):
    for no, ln in enumerate(lines, 1):
        for m in re.finditer(r"【未核实[^】]*】", ln):
            if m.group(0) != "【未核实，不进剧本】":
                out.err("未核实", "第%d行 裸的%s，要写成【未核实，不进剧本】" % (no, m.group(0)))


def _table_state(block):
    """block 是小节下面的行。返回 None（没有表格）、'空'（只有表头）、'ok'。"""
    rows = [ln.strip() for ln in block if ln.strip().startswith("|")]
    sep = [i for i, r in enumerate(rows)
           if re.fullmatch(r"\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?", r)]
    if not sep or sep[0] == 0:
        return None
    for r in rows[sep[0] + 1:]:
        cells = [c.strip() for c in r.strip("|").split("|")]
        if any(c and not re.fullmatch(r"[-—–\s]*", c) for c in cells):
            return "ok"
    return "空"


def check_pinyin(lines, out):
    h = find_heading(lines, r"^(第)?四(节|節|[、．.：:\s]|$)")
    if not h:
        out.err("注音", "找不到第四节（## 四、…），注音小节应该在它下面")
        return
    start, level = h
    end = section_end(lines, start, level)
    subs = [("注音（人名、地名、生僻字）", "注音"), ("多音字（第 4 步配音用）", "多音字")]
    heads = []
    for j in range(start + 1, end):
        m = re.match(r"^#{1,6}\s*(.*?)\s*$", lines[j])
        if m:
            heads.append((j, re.sub(r"\s+", "", m.group(1))))
    for title, short in subs:
        pos = [j for j, t in heads if t == re.sub(r"\s+", "", title)]
        if not pos:
            out.err("注音", "第四节下面缺小节「### %s」" % title)
            continue
        nxt = min([j for j, _ in heads if j > pos[0]] + [end])
        st = _table_state(lines[pos[0] + 1:nxt])
        if st is None:
            out.err("注音", "第%d行「%s」下面没有表格" % (pos[0] + 1, short))
        elif st == "空":
            out.err("注音", "第%d行「%s」下面的表格是空的（只有表头）" % (pos[0] + 1, short))
        else:
            out.ok("注音", "「%s」小节和表格都在（第%d行）" % (short, pos[0] + 1))


def check_links(sources, out):
    for code, s in sources.items():
        if s["kind"] != "web":
            continue
        try:
            status, _ = http_get(s["url"], ua=BROWSER_UA, timeout=20)
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:  # 连不上、超时、证书问题都算失败
            out.err("链接", "%s 请求失败（%s）：%s" % (code, type(e).__name__, s["url"]))
            continue
        if status == 200:
            out.ok("链接", "%s 200 %s" % (code, s["url"]))
        else:
            out.err("链接", "%s 返回 HTTP %s：%s" % (code, status, s["url"]))


# ---------------------------------------------------------------- 输出

class Out:
    def __init__(self):
        self.lines, self.errors = [], 0

    def ok(self, kind, msg):
        self.lines.append("[通过] %s：%s" % (kind, msg))

    def err(self, kind, msg):
        self.errors += 1
        self.lines.append("[错误] %s：%s" % (kind, msg))

    def note(self, msg):
        self.lines.append(msg)


def episode_of(md):
    parts = md.resolve().parts
    if "stories" in parts[:-1]:
        i = parts.index("stories")
        if i + 1 < len(parts) - 1:
            return parts[i + 1]
    return md.resolve().parent.name


def show_quote(q):
    t = q["inner"]
    if len(t) > 40:
        t = t[:38] + "……"
    return "「%s」%s" % (t, "（%s）" % "；".join(q["codes"]) if q["codes"] else "")


def main():
    ap = argparse.ArgumentParser(description="史料简报自动核对（PITFALLS S2、S14）")
    ap.add_argument("md", help="简报，如 video/stories/tj01/source.md")
    ap.add_argument("--refresh", action="store_true", help="重新下载维基文库原文（默认用缓存）")
    ap.add_argument("--check-links", action="store_true", help="对非维基链接发请求，不是 200 就报错")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    md = Path(a.md)
    if not md.is_file():
        print("找不到简报：%s" % md)
        return 2
    lines = md.read_text(encoding="utf-8").splitlines()
    ep = episode_of(md)
    cache_dir = Path(__file__).resolve().parent / "out" / ep / "source_check"
    out = Out()

    out.note("== 来源（%s）==" % md)
    sources = parse_sources(lines, out)
    views = {}
    for code, s in sources.items():
        if s["kind"] != "wiki":
            continue
        try:
            raw, cached = load_raw(code, s["url"], cache_dir, a.refresh)
        except Exception as e:
            out.err("来源", "%s 下载失败（%s: %s）：%s" % (code, type(e).__name__, e, s["url"]))
            continue
        views[code] = [View(t) for t in wiki_views(raw)]
        out.ok("来源", "%s %s，%d 字：%s" % (code, "用缓存" if cached else "已下载", len(views[code][0].text), s["url"]))
    web = sum(1 for s in sources.values() if s["kind"] == "web")
    if web and not a.check_links:
        out.note("（普通网页 %d 个，没检查链接是否打得开；加 --check-links 才查）" % web)

    out.note("== 引文 ==")
    quotes = extract_quotes(lines)
    variant = skipped = 0
    for q in quotes:
        status, notes = check_quote(q, sources, views)
        if status == "错误":
            out.errors += len(notes)
        elif status == "异体匹配":
            variant += 1
        elif status == "跳过":
            skipped += 1
        tail = ("  <- " + "；".join(notes)) if notes else ""
        out.note("[%s] 第%d行 %s%s" % (status, q["line"], show_quote(q), tail))

    out.note("== 其他检查 ==")
    check_unverified(lines, out)
    check_pinyin(lines, out)
    if a.check_links:
        check_links(sources, out)

    out.note("（异体匹配 %d 条：字面上和原文不完全一样，请人看一眼）" % variant)
    print("\n".join(out.lines))
    print("%d 条引文，%d 个错误" % (len(quotes) - skipped, out.errors))
    return 1 if out.errors else 0


if __name__ == "__main__":
    sys.exit(main())
