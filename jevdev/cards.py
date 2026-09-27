"""把卡片内容渲染成 1080×1440（3:4）的 PNG，用于小红书图文。

卡片内容是一个 dict：
  kicker      顶部胶囊标签，如「列治文 · 早茶」
  title       大标题，用 [[...]] 标出要强调的词
  subtitle    副标题
  items       列表项 [{"name": ..., "meta": ...}]（可为空）
  footer_left 左下角文字，如「人均 $25–40」
"""
import html
import re
from pathlib import Path
from string import Template

from playwright.sync_api import sync_playwright

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "card.html"
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
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        **THEMES[theme], kicker=esc(card.get("kicker", "")), title_html=title_html,
        subtitle=esc(card.get("subtitle", "")), items_html=items_html,
        footer_left=esc(card.get("footer_left", "")))


def render(cards, out_dir, theme="warm"):
    """渲染多张卡片，返回 PNG 路径列表（路径不含中文，MCP 上传要求）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1440})
        for i, card in enumerate(cards, 1):
            page.set_content(_html(card, theme), wait_until="networkidle")
            path = out_dir / f"card_{i:02d}.png"
            page.screenshot(path=str(path))
            paths.append(str(path))
        browser.close()
    return paths
