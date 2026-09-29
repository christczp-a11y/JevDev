"""字体子集化（工作流第 0 步第 19 项）：把 Noto Sans SC 和 ZCOOL KuaiLe 做成放进仓库的 woff2。两种字体都是 SIL OFL 1.1，可以随仓库分发。

为什么要有本地字体：以前 engine.html、stage.html 连 Google Fonts，中文字形按分片首次用到才下载，第一次画字时是备用字体，
截图和成片每一段的第一帧字体不对（E1 再犯）。现在字体在仓库里，加载前先带上要画的字确认真的生效（见 engine.html 的 loadFonts）。

用法（仓库根目录）：
  python video/vendor/fonts/subset_fonts.py [--noto 路径] [--zcool 路径]
  python video/vendor/fonts/subset_fonts.py --coverage-only     只按现有的两个 woff2 重新写 coverage.json（不重新子集化）
    --noto   Noto Sans SC 的可变字体（默认 C:/Windows/Fonts/NotoSansSC-VF.ttf，Windows 自带，Version 2.04，wght 100–900，17.7 MB）
    --zcool  ZCOOLKuaiLe-Regular.ttf（默认 video/out/fonts_src/ZCOOLKuaiLe-Regular.ttf；来源 https://github.com/google/fonts/tree/main/ofl/zcoolkuaile，Version 2.001，1.5 MB）
  需要 fonttools 和 brotli（pip install fonttools brotli，只有重新子集化才要）。
输出（都在本目录）：
  NotoSansSC-subset.woff2        weight 轴只留 500–900（全项目只用 500 / 700 / 900），字符 = 下面「字符集」
  ZCOOLKuaiLe-subset.woff2       字符集同上
  fonts.css                      @font-face（engine.html、stage.html 都 link 它）。ZCOOL KuaiLe 里没有的字（例如絺）
                                 由第二条 @font-face 用 Noto Sans SC 补上，所以画面上不会出现系统备用字体
  coverage.json                  两个 woff2 里实际有哪些字（从 cmap 读出来的）；video/glyph_check.py 用它检查场景里要上画面的字有没有缺字
  charset.txt                    字符集（UTF-8）
字符集：ASCII + GB2312 全部（6763 个常用简体字 + 常用符号）+ 仓库里所有会上画面的文字里出现过的字
  （video/stories/、video/scenes/、video/episodes/、video/engine.html、video/stage3d/stage.html、video/sets/、video/assets/REGISTRY.md、docs/ 里的中文说明不算，只取上面这些）
  + 几个常用标点。第一集新出现了字库里没有的生僻字（简报里的絺之类）：重跑这个脚本就会补进去。
  字库本身没有的字不会报错：所以 stage.html / engine.html 加载时会用 measureText 对着备用字体验证。
"""
import argparse
import sys
import unicodedata
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]   # 仓库根目录
SOURCES = ["video/stories", "video/scenes", "video/episodes", "video/sets", "video/engine.html", "video/stage3d/stage.html", "video/build_ep01_v2.py"]
EXTRA = "“”‘’…—–·《》〈〉「」『』【】、。，！？：；（）→←↑↓×÷±°%&@#*+=<>|~^_-/\'\"`"


def gb2312():
    out = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return out


def repo_chars():
    out = set()
    for s in SOURCES:
        p = ROOT / s
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file() and f.suffix in (".json", ".md", ".py", ".html", ".txt")]
        for f in files:
            try:
                out |= set(f.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                pass
    return out


def wanted(ch):
    if ch in EXTRA:
        return True
    return ord(ch) >= 0x20 and unicodedata.category(ch)[0] != "C" and unicodedata.category(ch) != "So" and ch != "\u3000"   # \u4e0d\u8981\u8868\u60c5\u7b26\u53f7\uff08So\uff09


def build_charset():
    chars = {chr(c) for c in range(0x20, 0x7F)} | gb2312() | repo_chars() | set(EXTRA)
    return "".join(sorted((c for c in chars if wanted(c)), key=ord))


def subset_font(font, text, out, flavor="woff2"):
    opts = subset.Options()
    opts.flavor = flavor
    opts.layout_features = ["kern", "liga", "ccmp", "locl", "mark", "mkmk"]
    opts.notdef_outline = True
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
    opts.drop_tables += ["DSIG"]
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    subset.save_font(font, str(out), opts)


def ranges(chars):
    """字符集合 → CSS unicode-range 写法（连续的合成一段）。"""
    cps = sorted(ord(c) for c in chars)
    out, i = [], 0
    while i < len(cps):
        j = i
        while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1:
            j += 1
        out.append(f"U+{cps[i]:X}" if i == j else f"U+{cps[i]:X}-{cps[j]:X}")
        i = j + 1
    return ", ".join(out)


def write_css(zmissing):
    css = f"""/* 由 subset_fonts.py 生成，不要手改（改字符集或字体就重跑它）。字体都是 SIL OFL 1.1，许可证在同目录。 */
@font-face {{ font-family: "Noto Sans SC"; src: url("NotoSansSC-subset.woff2") format("woff2"); font-weight: 500 900; font-style: normal; font-display: block; }}
@font-face {{ font-family: "ZCOOL KuaiLe"; src: url("ZCOOLKuaiLe-subset.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: block; }}
/* ZCOOL KuaiLe 里没有的字（{len(zmissing)} 个，例如絺）：同一个 font-family 的第二条，后写的优先，用 Noto Sans SC 补，画面上不会跳出系统备用字体 */
@font-face {{ font-family: "ZCOOL KuaiLe"; src: url("NotoSansSC-subset.woff2") format("woff2"); font-weight: 400; font-style: normal; font-display: block;
  unicode-range: {ranges(zmissing)}; }}
"""
    (HERE / "fonts.css").write_text(css, encoding="utf-8")


def write_coverage():
    """coverage.json：两个字体子集里实际有的字（从现有的 woff2 的 cmap 读）。"""
    import json
    noto_font = TTFont(str(HERE / "NotoSansSC-subset.woff2"))
    zcool_font = TTFont(str(HERE / "ZCOOLKuaiLe-subset.woff2"))
    chars = lambda f: "".join(sorted((chr(c) for c in f.getBestCmap() if c >= 0x20), key=ord))
    (HERE / "coverage.json").write_text(json.dumps({"noto": chars(noto_font), "zcool": chars(zcool_font)}, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coverage-only", action="store_true")
    ap.add_argument("--noto", default="C:/Windows/Fonts/NotoSansSC-VF.ttf")
    ap.add_argument("--zcool", default=str(ROOT / "video/out/fonts_src/ZCOOLKuaiLe-Regular.ttf"))
    a = ap.parse_args()
    if a.coverage_only:
        write_coverage()
        print("coverage.json 已按现有的 woff2 重新写出")
        return
    text = build_charset()
    (HERE / "charset.txt").write_text(text, encoding="utf-8")
    print(f"字符集 {len(text)} 个字 → charset.txt")
    noto = TTFont(a.noto)
    noto = instancer.instantiateVariableFont(noto, {"wght": (500, 900)})   # 只留 500–900 的粗细范围
    tmp = ROOT / "video/out/fonts_src/NotoSansSC-500-900.ttf"   # 存盘再读回来：直接拿内存里的对象去子集化，gvar 会对不上（KeyError）
    tmp.parent.mkdir(parents=True, exist_ok=True)
    noto.save(str(tmp))
    noto = TTFont(str(tmp))
    missing = [c for c in text if ord(c) not in noto.getBestCmap() and ord(c) > 0x7F]
    subset_font(noto, text, HERE / "NotoSansSC-subset.woff2")
    print(f"NotoSansSC-subset.woff2：{(HERE / 'NotoSansSC-subset.woff2').stat().st_size / 1024:.0f} KB；字库里没有的字 {len(missing)} 个：{''.join(missing)[:60]}")
    zc = TTFont(a.zcool)
    zmissing = [c for c in text if ord(c) not in zc.getBestCmap() and ord(c) > 0x7F]
    subset_font(zc, text, HERE / "ZCOOLKuaiLe-subset.woff2")
    print(f"ZCOOLKuaiLe-subset.woff2：{(HERE / 'ZCOOLKuaiLe-subset.woff2').stat().st_size / 1024:.0f} KB；字库里没有的字 {len(zmissing)} 个（fonts.css 里用 Noto Sans SC 补）")
    write_css([c for c in zmissing])
    write_coverage()
    print("fonts.css、coverage.json 已生成")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
