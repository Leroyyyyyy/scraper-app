"""
定时抓取脚本 —— 供 macOS launchd 调用
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import db
from datetime import datetime
from main import do_scrape


def run():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始定时抓取...")
    db.init_db()
    links = db.get_all_links()
    
    for link in links:
        result = do_scrape(link["id"], link["url"], link["platform"])
        status = result.get("status", "error").upper()
        data = result.get("data") or {}
        if result.get("status") in ("ok", "partial"):
            suffix = f" — 缺失字段: {', '.join(result.get('missing_fields', []))}" if result.get("missing_fields") else ""
            print(f"  [{status}] {link['url']} — {data.get('title', '')[:30]}{suffix}")
        else:
            print(f"  [FAIL] {link['url']} — {result.get('error', '未知错误')}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抓取完成")


if __name__ == "__main__":
    run()
