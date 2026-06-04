"""
小红书抓取模块 — Phase 2
使用 Playwright 模拟浏览器，Cookie 持久化

首次使用流程：
1. 运行时会打开一个可见浏览器窗口
2. 手动扫码登录小红书
3. Cookie 自动保存到 data/xiaohongshu_cookies.json
4. 之后自动使用已保存的 Cookie 抓取
"""
import os
import re
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "xiaohongshu_cookies.json")


def parse_url(url: str) -> tuple[str, str] | None:
    """解析小红书链接，返回 (类型, ID)
    
    支持：
    - 笔记: https://www.xiaohongshu.com/explore/64a1b2c3000000001e03abcd
    - 短链接: https://xhslink.com/xxxxx
    """
    url = url.strip().split("?")[0]

    # 笔记链接
    note_match = re.search(r'/explore/([a-zA-Z0-9]+)', url)
    if note_match:
        return ("note", note_match.group(1))

    # 短链接
    if "xhslink.com" in url:
        return ("shortlink", url)

    return None


def _load_cookies() -> list | None:
    """加载已保存的 Cookie"""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
                if cookies:
                    return cookies
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _save_cookies(cookies: list):
    """保存 Cookie 到文件"""
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f)


def _extract_page_data(page) -> dict | None:
    """从小红书页面 DOM 中提取数据"""
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        pass

    time.sleep(2)

    title = ""
    author = ""
    like_count = 0
    collect_count = 0
    comment_count = 0

    try:
        title_el = page.query_selector("#detail-title, .title, [class*='title']")
        if title_el:
            title = title_el.inner_text().strip()
    except Exception:
        pass

    try:
        author_el = page.query_selector(".username, [class*='username'], .author-name, [class*='author']")
        if author_el:
            author = author_el.inner_text().strip()
    except Exception:
        pass

    try:
        like_el = page.query_selector(".like-wrapper .count, [class*='like'] [class*='count'], #note-page-like")
        if like_el:
            like_text = like_el.inner_text().strip()
            like_count = _parse_count(like_text)
    except Exception:
        pass

    try:
        collect_el = page.query_selector(".collect-wrapper .count, [class*='collect'] [class*='count']")
        if collect_el:
            collect_text = collect_el.inner_text().strip()
            collect_count = _parse_count(collect_text)
    except Exception:
        pass

    try:
        comment_el = page.query_selector(".chat-wrapper .count, [class*='comment'] [class*='count']")
        if comment_el:
            comment_text = comment_el.inner_text().strip()
            comment_count = _parse_count(comment_text)
    except Exception:
        pass

    if not title:
        title = page.title().replace(" - 小红书", "").strip()

    if title or author:
        return {
            "title": title or "小红书笔记",
            "author": author,
            "author_id": author,
            "like_count": like_count,
            "favorite_count": collect_count,
            "comment_count": comment_count,
            "publish_time": "",
            "raw_data": json.dumps({"platform": "xiaohongshu"}, ensure_ascii=False),
        }

    return None


def _parse_count(text: str) -> int:
    """解析可能包含 '万' 的计数文本"""
    text = text.strip().replace(",", "")
    if not text:
        return 0
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(float(text))
    except ValueError:
        return 0


def _login_and_save_cookies() -> list:
    """打开浏览器让用户手动扫码登录，保存并返回 Cookie"""
    print("\n" + "=" * 50)
    print("  小红书登录 — 请在打开的浏览器中扫码登录")
    print("=" * 50 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.goto("https://www.xiaohongshu.com/explore", timeout=30000)

        print("请在浏览器中扫码登录小红书...")
        print("登录成功后，回到这里按 Enter 继续...\n")
        input(">>> 按 Enter 继续 ")

        cookies = context.cookies()
        _save_cookies(cookies)
        browser.close()

    print("Cookie 已保存!\n")
    return cookies


def fetch(url: str) -> dict:
    """抓取小红书笔记数据"""
    cookies = _load_cookies()
    need_login = not cookies

    close_on_done = False
    if need_login:
        print("[小红书] 需要登录...")
        return {
            "error": "小红书需要首次登录。请在终端运行: python3 scrapers/xiaohongshu_login.py"
        }
        # 后台模式下不能交互，所以提示用户手动运行登录脚本

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        )

        context.add_cookies(cookies)
        page = context.new_page()

        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
        except PlaywrightTimeout:
            pass

        # 检查是否需要重新登录
        if "login" in page.url.lower() or "passport" in page.url.lower():
            browser.close()
            # Cookie 过期，删除旧文件
            if os.path.exists(COOKIE_FILE):
                os.remove(COOKIE_FILE)
            return {
                "error": "小红书 Cookie 已过期，请在终端运行: python3 scrapers/xiaohongshu_login.py"
            }

        data = _extract_page_data(page)
        browser.close()

        if data:
            return data
        else:
            return {"error": "未能提取到数据，小红书页面结构可能已变更"}


def extract_platform_info(url: str) -> tuple[str, str] | None:
    parsed = parse_url(url)
    if not parsed:
        return None
    return ("xiaohongshu", parsed[1])
