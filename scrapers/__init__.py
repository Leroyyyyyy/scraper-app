import re
from scrapers import bilibili, douyin, xiaohongshu


def detect_platform(url: str) -> str | None:
    """根据 URL 自动识别平台"""
    url_lower = url.strip().lower()
    if "bilibili.com" in url_lower:
        return "bilibili"
    if "xiaohongshu.com" in url_lower or "xhslink.com" in url_lower:
        return "xiaohongshu"
    if "douyin.com" in url_lower:
        return "douyin"
    return None


def get_platform_module(platform: str):
    """获取对应平台的抓取模块"""
    modules = {
        "bilibili": bilibili,
        "xiaohongshu": xiaohongshu,
        "douyin": douyin,
    }
    return modules.get(platform)


def extract_link_info(url: str) -> tuple[str, str] | None:
    """从链接提取 (platform, target_id)"""
    platform = detect_platform(url)
    if not platform:
        return None

    module = get_platform_module(platform)
    if module:
        return module.extract_platform_info(url)
    return (platform, url)
