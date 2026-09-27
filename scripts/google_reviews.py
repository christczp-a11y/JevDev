"""抓取 Google 地图上某家店最新的约 50 条评价（使用专用 Chrome 配置里的登录态）。

前提：先运行 scripts/open_google_profile.cmd，在弹出的窗口里手动登录 Google 小号并关掉窗口。
规则（DECISIONS 2026-09-27）：每天只抓少量店；遇到验证码或「异常流量」页面就停止，不绕过。

用法：python scripts/google_reviews.py "HK BBQ Master Richmond BC" [--n 50]
"""
import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from jevdev import db  # noqa: E402

PROFILE = r"C:\Users\Chris\jevdev-browser\google-profile"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
    query TEXT PRIMARY KEY, name TEXT, rating REAL, review_count INTEGER, maps_url TEXT, fetched_at TEXT);
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY, query TEXT, source TEXT, author TEXT, stars REAL,
    when_text TEXT, text TEXT, fetched_at TEXT);
"""


class Blocked(Exception):
    """Google 弹出验证码或异常流量页。"""


def pause(lo=0.8, hi=2.0):
    time.sleep(random.uniform(lo, hi))


def check_blocked(page):
    if "/sorry/" in page.url or page.locator("iframe[title*='reCAPTCHA']").count():
        raise Blocked(page.url)


def scrape(query, n=50, headless=False):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE, executable_path=CHROME, headless=headless, locale="en-US",
            viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://www.google.com/maps/search/" + query.replace(" ", "+") + "?hl=en", timeout=60000)
            page.wait_for_timeout(4000)
            check_blocked(page)
            # 搜索结果是列表时，点第一个
            first = page.locator("a.hfpxzc").first
            if first.count():
                first.click()
                page.wait_for_timeout(3000)
            name = page.locator("h1").first.inner_text().strip()
            body = page.locator('div[role="main"]').first.inner_text()
            m = re.search(r"(\d\.\d)\s*\n?.*?\(([\d,]+)\)", body)
            rating = float(m.group(1)) if m else None
            count = int(m.group(2).replace(",", "")) if m else None

            tab = page.locator('button[role="tab"]', has_text=re.compile("Reviews"))
            if not tab.count():
                raise RuntimeError("没有「Reviews」标签：登录态可能失效，请重新运行 open_google_profile.cmd")
            tab.first.click()
            page.wait_for_timeout(2500)
            # 按「最新」排序，避免只看到 Google 挑选的「最相关」评价
            sort_btn = page.locator('button[aria-label*="Sort"]')
            if sort_btn.count():
                sort_btn.first.click()
                pause()
                page.locator('div[role="menuitemradio"]', has_text="Newest").first.click()
                page.wait_for_timeout(2500)

            feed = page.locator("div[data-review-id]").first.locator("xpath=ancestor::div[contains(@class,'m6QErb')][1]")
            seen = 0
            for _ in range(40):
                check_blocked(page)
                cards = page.locator("div.jftiEf[data-review-id]")
                seen = cards.count()
                if seen >= n:
                    break
                (feed if feed.count() else page.locator('div[role="main"]').first).hover()
                page.mouse.wheel(0, random.randint(1800, 2600))
                pause(1.2, 2.5)
            # 展开「More」
            for b in page.locator("button.w8nwRe").all()[: n]:
                try:
                    b.click(timeout=1000)
                except Exception:
                    pass
            out = []
            for c in page.locator("div.jftiEf[data-review-id]").all()[:n]:
                stars_el = c.locator("span[role='img'][aria-label*='star']")
                stars = None
                if stars_el.count():
                    sm = re.search(r"([\d.]+)", stars_el.first.get_attribute("aria-label") or "")
                    stars = float(sm.group(1)) if sm else None
                text_el = c.locator("span.wiI7pd")
                when_el = c.locator("span.rsqaWe")
                out.append({
                    "review_id": c.get_attribute("data-review-id"),
                    "author": c.get_attribute("aria-label"),
                    "stars": stars,
                    "when_text": when_el.first.inner_text() if when_el.count() else None,
                    "text": text_el.first.inner_text() if text_el.count() else "",
                })
            return {"name": name, "rating": rating, "review_count": count, "maps_url": page.url, "reviews": out}
        finally:
            ctx.close()


def save(con, query, result):
    con.executescript(SCHEMA)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con.execute("INSERT OR REPLACE INTO places VALUES (?,?,?,?,?,?)",
                (query, result["name"], result["rating"], result["review_count"], result["maps_url"], ts))
    for r in result["reviews"]:
        con.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?,?,?,?)",
                    (r["review_id"], query, "google", r["author"], r["stars"], r["when_text"], r["text"], ts))
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    try:
        result = scrape(args.query, args.n, args.headless)
    except Blocked as e:
        print(f"遇到验证码或异常流量页，已停止（不绕过）：{e}")
        sys.exit(2)
    save(db.connect(), args.query, result)
    rv = result["reviews"]
    print(json.dumps({k: v for k, v in result.items() if k != "reviews"}, ensure_ascii=False))
    print(f"抓到 {len(rv)} 条评价；有正文 {sum(1 for r in rv if r['text'])} 条")
    for r in rv[:3]:
        print(f"  {r['stars']}★ {r['when_text']} | {r['text'][:80]}")


if __name__ == "__main__":
    main()
