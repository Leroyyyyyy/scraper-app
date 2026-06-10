#!/usr/bin/env python3
"""
小红书一次登录工具。
登录态会保存在 data/browser_profiles/xiaohongshu，后续后台采集自动复用。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scrapers.xiaohongshu import login_profile


if __name__ == "__main__":
    print("=" * 50)
    print("  小红书登录工具")
    print("=" * 50)
    login_profile()
