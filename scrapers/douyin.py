"""
抖音抓取模块 — Phase 3
策略：Playwright + RENDER_DATA 解码 + meta 标签

已知限制：
  抖音在服务端通过 isSpider 标记识别自动化请求，
  headless 模式只返回空壳数据，不包含视频详情。
  目前可稳定获取：标题、作者（来自 og:meta 标签）
  无法获取：播放量、点赞、评论（需真实设备 + 移动端 API 签名）
"""
import os
import re
import json
import time
import random
from urllib.parse import unquote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from scrapers import result as scrape_result

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "browser_profiles", "douyin")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def parse_url(url: str) -> tuple[str, str] | None:
    """解析抖音链接，返回 (类型, ID)
    支持混合文本：自动提取其中的抖音 URL
    """
    url = url.strip()
    
    # 从混合文本中提取 douyin.com 链接
    url_match = re.search(r'https?://[^\s]*?douyin\.com[^\s]*', url)
    if url_match:
        url = url_match.group(0).strip()
    
    # 从混合文本中提取 v.douyin.com 短链接
    short_match = re.search(r'(?:https?://)?v\.douyin\.com/[^\s]+', url)
    if short_match:
        return ("shortlink", short_match.group(0).strip())
    
    # modal_id 参数 = 视频 ID（常见于分享链接）
    modal_match = re.search(r'modal_id=(\d+)', url)
    if modal_match:
        return ("video", modal_match.group(1))
    
    url_clean = url.split("?")[0]

    video_match = re.search(r'/video/(\d+)', url_clean)
    if video_match:
        return ("video", video_match.group(1))

    user_match = re.search(r'/user/([a-zA-Z0-9_-]+)', url_clean)
    if user_match:
        return ("user", user_match.group(1))

    if "v.douyin.com" in url_clean:
        return ("shortlink", url)

    return None


def _random_delay(min_ms=500, max_ms=2000):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def _extract_render_data(html: str) -> dict | None:
    """尝试从 RENDER_DATA 提取视频数据"""
    match = re.search(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', html)
    if not match:
        return None
    
    try:
        decoded = unquote(match.group(1))
        data = json.loads(decoded)
        app = data.get("app", {})
        
        if app.get("isSpider"):
            return None  # 被识别为爬虫，无真实数据
        
        # 尝试在深层找到视频数据
        def find_video(d, depth=0):
            if depth > 5:
                return None
            if isinstance(d, dict):
                if "desc" in d and ("author" in d or "authorInfo" in d):
                    return d
                for v in d.values():
                    r = find_video(v, depth + 1)
                    if r: return r
            elif isinstance(d, list):
                for item in d[:3]:
                    r = find_video(item, depth + 1)
                    if r: return r
            return None
        
        return find_video(app)
    except Exception:
        return None


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _parse_count(value) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(float(text))
    except ValueError:
        return 0


def _fallback_from_share_text(raw_url: str, target_id: str) -> dict:
    """抖音抓不到页面时，至少从用户粘贴的分享文案保留标题。"""
    text = re.sub(r'https?://\S+', '', raw_url).strip()
    text = re.sub(r'复制此链接.*$', '', text).strip()
    text = re.sub(r'^[\d.:\sA-Za-z@/\-]+', '', text).strip()
    title = text or f"抖音内容 {target_id}"
    return {
        "title": title[:120],
        "author": "",
        "author_id": "",
        "play_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "favorite_count": 0,
        "share_count": 0,
        "publish_time": "",
        "raw_data": json.dumps(
            {"platform": "douyin", "source": "share_text", "note": "平台页面采集失败，使用分享文案兜底"},
            ensure_ascii=False,
        ),
    }


def _extract_network_data(payloads: list[dict]) -> dict | None:
    """从抖音 JSON 响应中尽力提取视频核心字段。"""
    for payload in payloads:
        for item in _walk(payload):
            title = item.get("desc") or item.get("title")
            author_info = item.get("author") or item.get("author_info") or item.get("authorInfo")
            stats = item.get("statistics") or item.get("stats") or item.get("stat") or {}
            if not title and not stats:
                continue

            author = ""
            if isinstance(author_info, dict):
                author = author_info.get("nickname") or author_info.get("name") or ""
            elif author_info:
                author = str(author_info)

            publish_time = item.get("create_time") or item.get("createTime") or item.get("publish_time") or ""
            return {
                "title": title or "抖音视频",
                "author": author,
                "author_id": author,
                "play_count": _parse_count(stats.get("play_count") or stats.get("playCount") or 0),
                "like_count": _parse_count(stats.get("digg_count") or stats.get("like_count") or 0),
                "comment_count": _parse_count(stats.get("comment_count") or 0),
                "favorite_count": _parse_count(stats.get("collect_count") or stats.get("favorite_count") or 0),
                "share_count": _parse_count(stats.get("share_count") or 0),
                "publish_time": publish_time,
                "raw_data": json.dumps({"platform": "douyin", "source": "browser_network"}, ensure_ascii=False),
            }
    return None


def _extract_page_data(page) -> dict:
    """从抖音页面提取视频数据"""
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeout:
        pass

    _random_delay(1000, 3000)

    title = ""
    author = ""
    like_count = 0
    publish_time = ""

    # 1. 从 <title> 标签提取（含视频标题 + 作者 + 日期 + 点赞）
    try:
        raw = page.title()
        if raw and " - 抖音" in raw:
            # 格式: "视频标题 - 作者于20260527发布在抖音，已经收获了515.6万个喜欢..."
            parts = raw.rsplit(" - ", 1)
            if len(parts) == 2 and "发布在抖音" in parts[1]:
                title = parts[0].strip()
                info = parts[1].strip()
                am = re.search(r'^(.+?)于(\d{8})发布', info)
                if am:
                    author = am.group(1)
                    d = am.group(2)
                    publish_time = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                lm = re.search(r'([\d.]+)万?个?喜欢', info)
                if lm:
                    val = lm.group(1)
                    like_count = int(float(val) * 10000) if '万' in lm.group(0) else int(val)
            elif parts[1] == "抖音":
                title = parts[0].strip()
    except Exception:
        pass

    # 2. 从 meta description 补充（headless 浏览器 og 标签为空，但 description 有数据）
    if not author or not like_count:
        try:
            el = page.query_selector('meta[name="description"]')
            if el:
                desc = (el.get_attribute("content") or "").strip()
                if not title:
                    parts = desc.rsplit(" - ", 1)
                    if len(parts) == 2: title = parts[0].strip()
                if not author:
                    am = re.search(r'([^-,]+?)于(\d{8})发布', desc)
                    if am:
                        author = am.group(1).strip()
                        if not publish_time:
                            d = am.group(2)
                            publish_time = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                if not like_count:
                    lm = re.search(r'([\d.]+)万?个?喜欢', desc)
                    if lm:
                        val = lm.group(1)
                        like_count = int(float(val) * 10000) if '万' in lm.group(0) else int(val)
        except Exception:
            pass

    # 2. 从 <title> 兜底
    if not title:
        try:
            t = page.title()
            if t:
                title = t.replace(" - 抖音", "").strip()
        except Exception:
            pass

    # 3. 尝试 RENDER_DATA
    try:
        html = page.content()
        rd = _extract_render_data(html)
        if rd:
            if rd.get("desc") and not title:
                title = rd["desc"]
            if rd.get("author"):
                author = rd["author"].get("nickname", "") if isinstance(rd["author"], dict) else str(rd["author"])
    except Exception:
        pass

    if title:
        return {
            "title": title,
            "author": author,
            "author_id": author,
            "play_count": 0,
            "like_count": like_count,
            "comment_count": 0,
            "favorite_count": 0,
            "share_count": 0,
            "publish_time": publish_time,
            "raw_data": json.dumps({"platform": "douyin", "source": "browser_dom", "note": "抖音字段会按页面可见性降级"}, ensure_ascii=False),
        }

    return scrape_result.error(
        "未能提取到任何数据。抖音可能识别到自动化请求或返回空壳页面。",
        "browser_dom",
    )


def fetch(url: str) -> dict:
    """抓取抖音视频数据"""
    parsed = parse_url(url)
    if not parsed:
        return scrape_result.error("无法解析该链接", "browser_dom")

    link_type, target_id = parsed

    # 构造目标 URL
    if link_type == "video":
        fetch_url = f"https://www.douyin.com/video/{target_id}"
    elif link_type == "shortlink":
        # 短链接需要跟随跳转，先请求再拿最终 URL
        fetch_url = target_id if target_id.startswith("http") else f"https://{target_id}"
    else:
        fetch_url = url

    try:
        with sync_playwright() as p:
            os.makedirs(PROFILE_DIR, exist_ok=True)
            context = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                ],
                viewport={"width": 1280, "height": 800},
                user_agent=USER_AGENT,
                locale="zh-CN",
            )

            page = context.new_page()
            network_payloads = []

            def capture_response(response):
                if "douyin.com" not in response.url:
                    return
                ctype = response.headers.get("content-type", "")
                if "json" not in ctype:
                    return
                try:
                    network_payloads.append(response.json())
                except Exception:
                    pass

            page.on("response", capture_response)
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            """)

            try:
                page.goto(fetch_url, timeout=25000, wait_until="domcontentloaded")
            except PlaywrightTimeout:
                pass

            _random_delay(2000, 4000)

            current_page_url = page.url
            if "verify" in current_page_url.lower() or "captcha" in current_page_url.lower():
                context.close()
                return scrape_result.error("抖音触发了验证码，需要人工检查后重试。", "manual_unavailable")

            if "404" in page.title().lower() or "不存在" in page.title():
                context.close()
                return scrape_result.error("页面不存在或已被删除", "browser_dom")

            data = _extract_network_data(network_payloads)
            source = "browser_network" if data else "browser_dom"
            if not data:
                data = _extract_page_data(page)
            context.close()

            if data and data.get("status") == "error":
                fallback = _fallback_from_share_text(url, target_id)
                missing = ["author", "publish_time", "play_count", "like_count", "comment_count", "favorite_count", "share_count"]
                return scrape_result.ok(fallback, "manual_unavailable", missing)

            if data and "error" not in data:
                fallback = _fallback_from_share_text(url, target_id)
                if fallback.get("title") and len(fallback["title"]) > len(data.get("title") or ""):
                    data["title"] = fallback["title"]
                missing = []
                for field in ["play_count", "comment_count", "favorite_count", "share_count"]:
                    if not data.get(field):
                        missing.append(field)
                return scrape_result.ok(data, source, missing)

            fallback = _fallback_from_share_text(url, target_id)
            missing = ["author", "publish_time", "play_count", "like_count", "comment_count", "favorite_count", "share_count"]
            return scrape_result.ok(fallback, "manual_unavailable", missing)

    except Exception as e:
        fallback = _fallback_from_share_text(url, parsed[1] if parsed else url)
        missing = ["author", "publish_time", "play_count", "like_count", "comment_count", "favorite_count", "share_count"]
        fallback["raw_data"] = json.dumps(
            {"platform": "douyin", "source": "share_text", "error": str(e)},
            ensure_ascii=False,
        )
        return scrape_result.ok(fallback, "manual_unavailable", missing)


def extract_platform_info(url: str) -> tuple[str, str] | None:
    parsed = parse_url(url)
    if not parsed:
        return None
    link_type, target_id = parsed
    if link_type == "shortlink":
        # 短链接存储时用完整 URL
        return ("douyin", target_id if target_id.startswith("http") else f"https://{target_id}")
    return ("douyin", target_id)
