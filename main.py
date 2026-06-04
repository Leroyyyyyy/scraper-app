"""
主入口 —— FastAPI 后端服务 + 定时抓取
启动: python main.py
"""
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import db
from scrapers import detect_platform, get_platform_module, extract_link_info

app = FastAPI(title="多平台数据抓取工具", version="1.0")

# 启动时初始化数据库
db.init_db()


class AddLinkRequest(BaseModel):
    url: str


class ScrapeAllRequest(BaseModel):
    pass


def do_scrape(link_id: int, url: str, platform: str):
    """执行单条链接的抓取"""
    module = get_platform_module(platform)
    if not module:
        return {"error": f"不支持的平台: {platform}"}

    data = module.fetch(url)
    if data and "error" not in data:
        db.save_snapshot(link_id, data)
        return {"status": "ok", "data": data}
    else:
        return {"status": "error", "error": data.get("error", "抓取失败") if data else "无数据返回"}


@app.post("/api/links")
def api_add_link(req: AddLinkRequest):
    """添加一个监控链接并立即抓取一次"""
    url = req.url.strip()
    platform = detect_platform(url)
    if not platform:
        raise HTTPException(
            status_code=400,
            detail="无法识别链接平台，请提供 B站 / 小红书 / 抖音 的有效链接",
        )

    info = extract_link_info(url)
    if not info:
        raise HTTPException(status_code=400, detail="无法解析该链接")

    platform_name, target_id = info
    link_id = db.add_link(url, platform_name, target_id)

    result = do_scrape(link_id, url, platform_name)
    return {"link_id": link_id, "platform": platform_name, "result": result}


@app.get("/api/links")
def api_list_links():
    """获取所有监控链接"""
    return db.get_all_links()


@app.delete("/api/links/{link_id}")
def api_delete_link(link_id: int):
    """删除链接"""
    db.delete_link(link_id)
    return {"status": "ok"}


@app.get("/api/snapshots")
def api_latest_snapshots(platform: str = None):
    """获取最新快照，可按平台筛选"""
    return db.get_latest_snapshots(platform)


@app.get("/api/snapshots/{link_id}/history")
def api_history(link_id: int, limit: int = 30):
    """获取某链接的历史快照"""
    return db.get_history(link_id, limit)


@app.post("/api/scrape-all")
def api_scrape_all():
    """手动触发所有链接的抓取"""
    links = db.get_all_links()
    results = []
    for link in links:
        res = do_scrape(link["id"], link["url"], link["platform"])
        results.append({
            "url": link["url"],
            "platform": link["platform"],
            "result": res,
        })
    return {"total": len(links), "results": results}


@app.get("/api/stats")
def api_stats():
    """仪表盘统计数据"""
    return db.get_stats()


@app.get("/api/content")
def api_content_list(platform: str = None, search: str = None):
    """内容列表（带搜索和T节点）"""
    return db.get_content_list(platform, search)


@app.get("/api/content/{link_id}")
def api_content_detail(link_id: int):
    """单个内容详情"""
    detail = db.get_content_detail(link_id)
    if not detail:
        raise HTTPException(status_code=404, detail="内容不存在")
    return detail


# 挂载前端静态文件
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    # 写入 PID 文件
    pid_file = os.path.join(os.path.dirname(__file__), "data", "server.pid")
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    print("\n   多平台数据抓取工具 v1.0")
    print("   打开浏览器访问: http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
