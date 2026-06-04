#!/usr/bin/env python3
"""
小红书手动登录脚本
运行此脚本来完成首次扫码登录，Cookie 将自动保存
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from scrapers.xiaohongshu import _login_and_save_cookies

if __name__ == "__main__":
    print("=" * 50)
    print("  小红书 Cookie 登录工具")
    print("=" * 50)
    cookies = _login_and_save_cookies()
    print(f"已保存 {len(cookies)} 条 Cookie")
    print("现在可以在前端页面中添加小红书链接了!")
