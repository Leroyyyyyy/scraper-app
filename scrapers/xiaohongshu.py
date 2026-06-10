"""
小红书抓取模块
使用 Playwright 持久化浏览器上下文，默认匿名采集；登录一次后复用本机登录态。
"""
import os
import re
import json
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from scrapers import result as scrape_result

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "browser_profiles", "xiaohongshu")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


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


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _extract_network_data(payloads: list[dict]) -> dict | None:
    """从页面 JSON 响应中尽力提取笔记核心字段。"""
    for payload in payloads:
        for item in _walk(payload):
            title = item.get("title") or item.get("display_title") or item.get("desc")
            author_info = item.get("user") or item.get("user_info") or item.get("author")
            interact = item.get("interact_info") or item.get("interactInfo") or item.get("stat") or {}
            if not title and not interact:
                continue

            author = ""
            if isinstance(author_info, dict):
                author = author_info.get("nickname") or author_info.get("name") or ""
            elif author_info:
                author = str(author_info)

            return {
                "title": title or "小红书笔记",
                "author": author,
                "author_id": author,
                "play_count": 0,
                "like_count": _parse_count(str(interact.get("liked_count") or interact.get("like_count") or 0)),
                "favorite_count": _parse_count(str(interact.get("collected_count") or interact.get("collect_count") or 0)),
                "comment_count": _parse_count(str(interact.get("comment_count") or 0)),
                "share_count": _parse_count(str(interact.get("share_count") or 0)),
                "publish_time": item.get("time") or item.get("publish_time") or "",
                "raw_data": json.dumps({"platform": "xiaohongshu", "source": "browser_network"}, ensure_ascii=False),
            }
    return None


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

    if title in ("手机号登录", "登录", "小红书登录") or "登录" in title:
        return None

    if title or author:
        return {
            "title": title or "小红书笔记",
            "author": author,
            "author_id": author,
            "play_count": 0,
            "like_count": like_count,
            "favorite_count": collect_count,
            "comment_count": comment_count,
            "share_count": 0,
            "publish_time": "",
            "raw_data": json.dumps({"platform": "xiaohongshu", "source": "browser_dom"}, ensure_ascii=False),
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


def _fallback_from_url(url: str) -> dict:
    parsed = parse_url(url)
    note_id = parsed[1] if parsed else url.strip().split("?")[0]
    return {
        "title": f"小红书笔记 {note_id}",
        "author": "",
        "author_id": "",
        "play_count": 0,
        "like_count": 0,
        "favorite_count": 0,
        "comment_count": 0,
        "share_count": 0,
        "publish_time": "",
        "raw_data": json.dumps(
            {"platform": "xiaohongshu", "source": "url_fallback", "note": "匿名采集受限，使用链接兜底"},
            ensure_ascii=False,
        ),
    }


def login_profile():
    """打开可见浏览器登录小红书，登录态保存在持久化 profile 中。"""
    with sync_playwright() as p:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="zh-CN",
        )
        page = context.new_page()
        page.goto("https://www.xiaohongshu.com/explore", timeout=30000)

        print("\n请在打开的浏览器里完成小红书登录。")
        print("登录成功后，回到这个窗口按 Enter 保存登录态。\n")
        input(">>> 按 Enter 继续 ")

        context.storage_state(path=os.path.join(PROFILE_DIR, "storage_state.json"))
        context.close()
        print("\n小红书登录态已保存，之后刷新会自动复用。\n")


def fetch(url: str) -> dict:
    """抓取小红书笔记数据"""
    with sync_playwright() as p:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
            ],
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="zh-CN",
        )

        page = context.new_page()
        network_payloads = []

        def capture_response(response):
            if "xiaohongshu.com" not in response.url:
                return
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype:
                return
            try:
                network_payloads.append(response.json())
            except Exception:
                pass

        page.on("response", capture_response)

        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
        except PlaywrightTimeout:
            pass

        page_title = ""
        try:
            page_title = page.title()
        except Exception:
            pass

        # 匿名采集遇到登录墙时直接降级，不保存“手机号登录”这类假标题。
        if (
            "login" in page.url.lower()
            or "passport" in page.url.lower()
            or page_title in ("手机号登录", "登录", "小红书登录")
            or "登录" in page_title
        ):
            context.close()
            fallback = _fallback_from_url(url)
            return scrape_result.partial(
                fallback,
                "manual_unavailable",
                ["author", "publish_time", "play_count", "like_count", "comment_count", "favorite_count", "share_count"],
                "小红书需要登录后才能查看该笔记，请运行 小红书登录.command 后重试",
            )

        data = _extract_network_data(network_payloads)
        source = "browser_network" if data else "browser_dom"
        if not data:
            data = _extract_page_data(page)
        context.close()

        if data:
            return scrape_result.ok(data, source)
        fallback = _fallback_from_url(url)
        return scrape_result.partial(
            fallback,
            "manual_unavailable",
            ["author", "publish_time", "play_count", "like_count", "comment_count", "favorite_count", "share_count"],
            "小红书匿名采集受限，建议运行 小红书登录.command 后重试",
        )


def extract_platform_info(url: str) -> tuple[str, str] | None:
    parsed = parse_url(url)
    if not parsed:
        return None
    return ("xiaohongshu", parsed[1])
