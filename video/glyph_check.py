"""字形覆盖检查（工作流第 0 步第 19 项的补充）：每场场景 JSON 里要上画面的字，都要在字体子集里；缺字就报错退出 1，报出缺哪些字、在哪一场哪一句。

为什么要有它：字体是子集化过的（video/vendor/fonts/），tj01 会大量出现新字（人名、地名、生僻字，比如絺疵）。子集里没有的字，浏览器不报错，
悄悄换成系统备用字体——checkFonts 只验证字体整体生效，验证不了每个字都有。所以第 5 步生成场景 JSON 以后、渲染之前，先查一遍。

查哪些字（engine.html 里每种文字用的字体）：
  ZCOOL KuaiLe：卷号、说话人标签、计分牌标签、人名牌（名字和家名）、气泡、道具上的字（sprite 的 text / say、board 的 texts）、纸鸟字条
  Noto Sans SC：字幕、标题、出处行、横幅、选择题（选项、标题、揭晓后的话）、反例卡、徽章、印章
判断「有没有」按 fonts.css 的实际分工：
  Noto 的字：要在 NotoSansSC-subset.woff2 的 cmap 里；
  ZCOOL 的字：在 ZCOOLKuaiLe-subset.woff2 里；ZCOOL 里没有的字（例如絺）由 fonts.css 的第二条 @font-face 用 Noto 补，
  要在那条的 unicode-range 里、也在 Noto 子集里才算有。cmap 存在 video/vendor/fonts/coverage.json（subset_fonts.py 生成）。
engine.html 代码里写死的字（「赏金」「齐王的宝贝」这类）不在场景 JSON 里；它们在生成字符集时已经被 engine.html 读进去了。

用法（仓库根目录）：python video/glyph_check.py video/scenes/<集>/shot*.json     退出码 0 = 没有缺字；1 = 有缺字
build_stage3d.py 的 qa 和 render、分场脚本模板的渲染前都会自动跑它。
缺字以后怎么办（一条命令）：python video/vendor/fonts/subset_fonts.py
  它会读 video/scenes/ 里所有场景 JSON 的文字，重新生成两个字体子集、fonts.css、coverage.json；跑完再重跑这个检查。
  字库本身就没有的字（报错里会写「字库本身没有」）重新子集化也没用：换字，或者换字体（见 video/vendor/fonts/README.md）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # video/
FONTS = ROOT / "vendor" / "fonts"
FIX = "python video/vendor/fonts/subset_fonts.py"


def load_coverage(fonts_dir=FONTS):
    """{"noto": 字集合, "zcool": 字集合, "zcool_fallback": ZCOOL 缺的字里由 Noto 补的（fonts.css 第二条 @font-face 的 unicode-range），"charset": 请求过的字符集}"""
    fonts_dir = Path(fonts_dir)
    cov = json.loads((fonts_dir / "coverage.json").read_text(encoding="utf-8"))
    css = (fonts_dir / "fonts.css").read_text(encoding="utf-8")
    fallback = set()
    for block in re.findall(r"@font-face\s*\{[^}]*\}", css):
        if 'font-family: "ZCOOL KuaiLe"' in block and "unicode-range" in block:
            for a, b in re.findall(r"U\+([0-9A-Fa-f]+)(?:-([0-9A-Fa-f]+))?", block.split("unicode-range:")[1]):
                fallback |= {chr(c) for c in range(int(a, 16), int(b or a, 16) + 1)}
    charset = set((fonts_dir / "charset.txt").read_text(encoding="utf-8")) if (fonts_dir / "charset.txt").exists() else set()
    return {"noto": set(cov["noto"]), "zcool": set(cov["zcool"]), "zcool_fallback": fallback, "charset": charset}


def screen_texts(sc):
    """场景 JSON 里要上画面的文字：[(位置说明, 文字, 字体 "zcool" 或 "noto"), ...]。"""
    out = []
    add = lambda where, text, font: out.append((where, text, font)) if isinstance(text, str) and text else None
    T = sc.get("title") or {}
    add("卷号（title.kicker）", T.get("kicker"), "zcool")
    for i, ln in enumerate(T.get("lines") or []):
        add(f"标题第 {i + 1} 行", re.sub(r"\[\[|\]\]", "", ln), "noto")
    add("出处行（footer）", sc.get("footer"), "noto")
    for i, s in enumerate(sc.get("subtitles") or []):
        add(f"字幕[{i}]（{s[0]}–{s[1]} 秒）说话人", s[2], "zcool")
        add(f"字幕[{i}]（{s[0]}–{s[1]} 秒）", s[3], "noto")
    add("计分牌标签（hud.label）", (sc.get("hud") or {}).get("label"), "zcool")
    for i, tg in enumerate(sc.get("nametags") or []):
        add(f"人名牌[{i}]（{tg.get('id')}）名字", tg.get("name"), "zcool")
        add(f"人名牌[{i}]（{tg.get('id')}）家名", tg.get("house"), "zcool")
    for id_, a in (sc.get("actors") or {}).items():
        for b in a.get("bubbles") or []:
            add(f"角色 {id_} 的气泡（{b[0]} 秒）", b[2], "zcool")
    for i, p in enumerate(sc.get("props") or []):
        name = p.get("img") or p.get("type")
        for tx in p.get("text") or []:
            add(f"道具[{i}]（{name}）上的字", tx[0], "zcool")
        for sy in p.get("say") or []:
            add(f"道具[{i}]（{name}）的话（{sy[0]} 秒）", sy[2], "zcool")
        for tx in p.get("texts") or []:   # 告示牌：[[时刻, [行, ...]], ...]
            for ln in tx[1]:
                add(f"告示牌[{i}]（{tx[0]} 秒）", ln.lstrip("!"), "zcool")
        add(f"道具[{i}]（{name}）的奖励字", p.get("reward"), "zcool")
    for i, ev in enumerate(sc.get("events") or []):
        ty = ev.get("type")
        where = f"事件[{i}]（{ty}）"
        if ty == "banner":
            add(where, ev.get("text"), "noto")
        elif ty == "choice":
            for j, o in enumerate(ev.get("options") or []):
                add(f"{where}选项 {j + 1}", o, "noto")
            add(f"{where}标题", ev.get("label"), "noto")
            add(f"{where}揭晓后的话", ev.get("after"), "noto")
        elif ty == "nope":
            for it in ev.get("items") or []:
                add(f"{where}（{it[0]} 秒）", it[2], "noto")
        elif ty == "badges":
            for it in ev.get("items") or []:
                add(f"{where}（{it[0]} 秒）", it[1], "noto")
        elif ty == "stamp":
            add(where, ev.get("text"), "noto")
        elif ty == "birds":
            add(where, ev.get("text"), "zcool")
    return out


def missing_chars(text, font, cov):
    """text 里画不出来的字（去重、保持顺序）：[(字, 原因)]。空白不算。"""
    out = {}
    for c in text:
        if c.isspace() or ord(c) < 0x20 or c in out:
            continue
        if font == "noto":
            ok = c in cov["noto"]
        else:
            ok = c in cov["zcool"] or (c in cov["zcool_fallback"] and c in cov["noto"])
        if not ok:
            out[c] = "字库本身没有（在字符集里，却不在字体里）" if c in cov["charset"] else "不在字体子集里"
    return list(out.items())


def check_files(paths, cov=None):
    """返回问题列表 [{scene, shot, where, text, font, missing: [(字, 原因)]}]。paths：场景 JSON。"""
    cov = cov or load_coverage()
    issues = []
    for p in map(Path, paths):
        sc = json.loads(p.read_text(encoding="utf-8"))
        m = re.search(r"shot(\d+)", p.stem)
        for where, text, font in screen_texts(sc):
            miss = missing_chars(text, font, cov)
            if miss:
                issues.append({"scene": str(p), "shot": int(m.group(1)) if m else None, "where": where, "text": text, "font": font, "missing": miss})
    return issues


def print_report(issues, file=None):
    file = file or sys.stderr
    chars = {}
    for it in issues:
        shot = f"第 {it['shot']} 场" if it["shot"] else it["scene"]
        first = it["missing"][0][0]
        i = it["text"].index(first)
        excerpt = ("…" if i > 6 else "") + it["text"][max(0, i - 6): i + 7] + ("…" if i + 7 < len(it["text"]) else "")
        print(f"缺字：{shot} {it['where']}「{excerpt}」（{'ZCOOL KuaiLe' if it['font'] == 'zcool' else 'Noto Sans SC'}）：缺 "
              + "、".join(f"「{c}」（{why}）" for c, why in it["missing"]), file=file)
        chars.update(dict(it["missing"]))
    print(f"共缺 {len(chars)} 个字：{''.join(chars)}。", file=file)
    print(f"重新子集化：{FIX}（读 video/scenes/ 里所有场景 JSON 的文字，重新生成字体子集和 coverage.json），跑完再重跑这个检查；"
          "标了「字库本身没有」的字重新子集化也没用，要换字或者换字体（video/vendor/fonts/README.md）。", file=file)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    paths = (argv if argv is not None else sys.argv[1:])
    if not paths:
        sys.exit("用法：python video/glyph_check.py video/scenes/<集>/shot*.json")
    issues = check_files(paths)
    if issues:
        print_report(issues)
        return 1
    print(f"字形覆盖：{len(paths)} 个场景，要上画面的字都在字体子集里")
    return 0


if __name__ == "__main__":
    sys.exit(main())
