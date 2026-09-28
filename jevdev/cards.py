"""把卡片内容渲染成 1080×1440（3:4）的 PNG，用于小红书图文。

卡片内容是一个 dict：
  kicker      顶部胶囊标签，如「列治文 · 早茶」
  title       大标题，用 [[...]] 标出要强调的词
  subtitle    副标题
  items       列表项 [{"name": ..., "meta": ...}]（可为空）
  footer_left 左下角文字，如「人均 $25–40」
  image       （可选）封面主图的本地路径：AI 插画或实拍，见 jevdev/images.py
  image_label （可选）图上的来源标注，如「AI 插画 · 仅示意」「实拍」「示意图」
  cutout      （可选）抠好的实物照片 PNG（透明背景），有它就用抠图封面版式（templates/cover_cutout.html）
"""
import base64
import html
import re
from pathlib import Path
from string import Template

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None   # 云端预装的 Chromium（Playwright 下载被网络策略拦截）；本地为 None，用 Playwright 自带的

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "card.html"
CUTOUT_TEMPLATE = TEMPLATE.with_name("cover_cutout.html")
CUTOUT_COLORS = {"bg": "#ffd84d", "accent": "#d93a14"}  # 抠图封面固定用亮黄底
THEMES = {
    "warm": {"bg": "#f6ead8", "accent": "#d2461e"},
    "fresh": {"bg": "#e3efe6", "accent": "#1f7a4d"},
    "night": {"bg": "#efe3f2", "accent": "#7a2d8c"},
}


def _html(card, theme):
    esc = html.escape
    title_html = re.sub(r"\[\[(.+?)\]\]", lambda m: f"<em>{m.group(1)}</em>", esc(card["title"])).replace("\n", "<br>")
    items_html = "".join(
        f'<div class="item"><span class="no">{i}</span><div><div class="name">{esc(it["name"])}</div>'
        f'<div class="meta">{esc(it.get("meta", ""))}</div></div></div>'
        for i, it in enumerate(card.get("items") or [], 1))
    if card.get("cutout"):  # 抠图封面（jevdev/stock.py）：实物照片抠图 + 亮色背景
        return Template(CUTOUT_TEMPLATE.read_text(encoding="utf-8")).substitute(
            **CUTOUT_COLORS, kicker=esc(card.get("kicker", "")), title_html=title_html,
            subtitle=esc(card.get("subtitle", "")), footer_left=esc(card.get("footer_left", "")),
            cutout_b64=base64.b64encode(Path(card["cutout"]).read_bytes()).decode(),
            label=esc(card.get("image_label", "")))
    hero_html = ""
    if card.get("image"):
        items_html = ""  # 带图封面只放标签、大标题和副标题（单一焦点）；要点留给内页
        # 内嵌成 data URI：set_content 的页面不能直接读本地文件
        data = base64.b64encode(Path(card["image"]).read_bytes()).decode()
        badge = f'<span class="badge">{esc(card["image_label"])}</span>' if card.get("image_label") else ""
        hero_html = f'<div class="hero"><img src="data:image/jpeg;base64,{data}">{badge}</div>'
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        **THEMES[theme], kicker=esc(card.get("kicker", "")), title_html=title_html,
        subtitle=esc(card.get("subtitle", "")), items_html=items_html,
        footer_left=esc(card.get("footer_left", "")),
        body_class="with-image" if hero_html else "", hero_html=hero_html)


# 内容放不下时逐步缩小：先缩大标题，再缩列表字号，最后才去掉末尾的列表项
_FIT_JS = """() => {
  const page = document.querySelector('.page');
  const fits = () => page.scrollHeight <= page.clientHeight;
  const h1 = document.querySelector('h1');
  let fs = parseFloat(getComputedStyle(h1).fontSize);  // 纯文字封面 118，带图封面 96
  const minFs = fs * 0.66;
  while (!fits() && fs > minFs) { fs -= 6; h1.style.fontSize = fs + 'px'; }
  let scale = 1;
  while (!fits() && scale > 0.75) {
    scale -= 0.05;
    document.querySelectorAll('.item .name').forEach(e => e.style.fontSize = (46 * scale) + 'px');
    document.querySelectorAll('.item .meta').forEach(e => e.style.fontSize = (34 * scale) + 'px');
    document.querySelectorAll('.item').forEach(e => e.style.padding = (26 * scale) + 'px 34px');
    const its = document.querySelector('.items');  // 抠图封面没有列表
    if (its) its.style.gap = (26 * scale) + 'px';
  }
  let dropped = 0;
  while (!fits()) {
    const items = document.querySelectorAll('.item');
    if (items.length <= 1) break;
    items[items.length - 1].remove(); dropped++;
  }
  return {title_px: fs, item_scale: Math.round(scale * 100) / 100, dropped, fits: fits()};
}"""


def render(cards, out_dir, theme="warm"):
    """渲染多张卡片，返回 PNG 路径列表（路径不含中文，MCP 上传要求）。
    内容放不下会自动缩小；不得不删掉列表项时打印警告。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 1080, "height": 1440})
        for i, card in enumerate(cards, 1):
            page.set_content(_html(card, theme), wait_until="networkidle")
            fit = page.evaluate(_FIT_JS)
            if fit["dropped"] or not fit["fits"]:
                print(f"  ⚠ 卡片 {i} 内容太多：删掉了 {fit['dropped']} 个列表项（仍放得下：{fit['fits']}）")
            path = out_dir / f"card_{i:02d}.png"
            page.screenshot(path=str(path))
            paths.append(str(path))
        browser.close()
    return paths
