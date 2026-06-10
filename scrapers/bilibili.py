"""
B站抓取模块 —— 通过官方 API 获取视频/作者数据
"""
import re
import requests
import json
from scrapers import result as scrape_result

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def parse_url(url: str) -> tuple[str, str] | None:
    """解析 B站链接，返回 (类型, ID)
    
    支持：
    - 视频: https://www.bilibili.com/video/BV1xx411c7mD
    - 用户空间: https://space.bilibili.com/123456
    """
    url = url.strip().split("?")[0]  # 去掉查询参数

    # 视频链接
    bv_match = re.search(r'/video/(BV[a-zA-Z0-9]+)', url)
    if bv_match:
        return ("video", bv_match.group(1))

    # 用户空间链接
    mid_match = re.search(r'space\.bilibili\.com/(\d+)', url)
    if mid_match:
        return ("space", mid_match.group(1))

    return None


def fetch_video(bvid: str) -> dict | None:
    """获取 B站视频信息"""
    try:
        resp = requests.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()

        if data["code"] != 0:
            return {"error": data.get("message", "unknown error")}

        video = data["data"]
        owner = video.get("owner", {})
        stat = video.get("stat", {})

        result = {
            "title": video.get("title", ""),
            "author": owner.get("name", ""),
            "author_id": str(owner.get("mid", "")),
            "play_count": stat.get("view", 0),
            "like_count": stat.get("like", 0),
            "comment_count": stat.get("reply", 0),
            "favorite_count": stat.get("favorite", 0),
            "share_count": stat.get("share", 0),
            "publish_time": video.get("pubdate", ""),
            "raw_data": json.dumps({"type": "video", "bvid": bvid}, ensure_ascii=False),
        }

        # 顺便获取作者粉丝数
        author_info = fetch_author(str(owner.get("mid", "")))
        if author_info and "error" not in author_info:
            result["follower_count"] = author_info.get("follower_count", 0)

        return result

    except Exception as e:
        return {"error": str(e)}


def fetch_author(mid: str) -> dict | None:
    """获取 B站用户信息"""
    try:
        resp = requests.get(
            f"https://api.bilibili.com/x/space/acc/info?mid={mid}",
            headers=HEADERS,
            timeout=10,
        )
        data = resp.json()

        if data["code"] != 0:
            return {"error": data.get("message", "unknown error")}

        user = data["data"]
        return {
            "author": user.get("name", ""),
            "author_id": str(user.get("mid", "")),
            "follower_count": user.get("follower", 0),
            "publish_time": "",
            "title": f"[用户主页] {user.get('name', '')}",
            "raw_data": json.dumps({"type": "space", "mid": mid}, ensure_ascii=False),
        }

    except Exception as e:
        return {"error": str(e)}


def fetch(url: str) -> dict | None:
    """统一入口：根据链接抓取 B站数据"""
    parsed = parse_url(url)
    if not parsed:
        return scrape_result.error("无法识别该链接，请提供 B站视频或用户主页链接", "api")

    link_type, target_id = parsed
    if link_type == "video":
        data = fetch_video(target_id)
    else:
        data = fetch_author(target_id)

    return scrape_result.normalize(data, "api")


def extract_platform_info(url: str) -> tuple[str, str] | None:
    """从 URL 提取平台名和目标 ID（用于存储到 links 表）"""
    parsed = parse_url(url)
    if not parsed:
        return None
    return ("bilibili", parsed[1])
