"""
定时抓取脚本 —— 供 macOS launchd 调用
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import db
from datetime import datetime
from scrapers import get_platform_module


def run():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始定时抓取...")
    db.init_db()
    links = db.get_all_links()
    
    for link in links:
        module = get_platform_module(link["platform"])
        if not module:
            print(f"  [SKIP] {link['url']} — 不支持的平台")
            continue

        data = module.fetch(link["url"])
        if data and "error" not in data:
            db.save_snapshot(link["id"], data)
            print(f"  [OK] {link['url']} — {data.get('title', '')[:30]}")
        else:
            error = data.get("error", "未知错误") if data else "无数据"
            print(f"  [FAIL] {link['url']} — {error}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抓取完成")


if __name__ == "__main__":
    run()
