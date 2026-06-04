"""
数据库模块 —— SQLite 单文件数据库，零配置
"""
import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "scraper.db")


def get_conn():
    """获取数据库连接，自动创建目录和表"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            target_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            title TEXT,
            author TEXT,
            author_id TEXT,
            play_count INTEGER,
            like_count INTEGER,
            comment_count INTEGER,
            favorite_count INTEGER,
            share_count INTEGER,
            follower_count INTEGER,
            publish_time TEXT,
            raw_data TEXT,
            captured_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (link_id) REFERENCES links(id)
        )
    """)
    conn.commit()
    conn.close()


def add_link(url: str, platform: str, target_id: str) -> int:
    """添加一个监控链接，返回 link_id"""
    conn = get_conn()
    try:
        cursor = conn.execute(
            "INSERT INTO links (url, platform, target_id) VALUES (?, ?, ?)",
            (url, platform, target_id)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # 链接已存在，返回已有 ID
        row = conn.execute("SELECT id FROM links WHERE url = ?", (url,)).fetchone()
        conn.close()
        return row["id"]


def get_all_links() -> list:
    """获取所有监控链接"""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM links ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_link(link_id: int):
    """删除链接及其所有快照"""
    conn = get_conn()
    conn.execute("DELETE FROM snapshots WHERE link_id = ?", (link_id,))
    conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()


def save_snapshot(link_id: int, data: dict):
    """保存一条抓取快照"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO snapshots 
        (link_id, title, author, author_id, play_count, like_count, 
         comment_count, favorite_count, share_count, follower_count,
         publish_time, raw_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        link_id,
        data.get("title"),
        data.get("author"),
        data.get("author_id"),
        data.get("play_count"),
        data.get("like_count"),
        data.get("comment_count"),
        data.get("favorite_count"),
        data.get("share_count"),
        data.get("follower_count"),
        data.get("publish_time"),
        data.get("raw_data"),
    ))
    conn.commit()
    conn.close()


def get_latest_snapshots(platform: str = None) -> list:
    """获取每个链接的最新快照，可按平台筛选"""
    conn = get_conn()
    query = """
        SELECT s.*, l.url, l.platform, l.target_id
        FROM snapshots s
        JOIN links l ON s.link_id = l.id
        WHERE s.id IN (
            SELECT MAX(id) FROM snapshots GROUP BY link_id
        )
    """
    params = []
    if platform:
        query += " AND l.platform = ?"
        params.append(platform)

    query += " ORDER BY s.captured_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history(link_id: int, limit: int = 30) -> list:
    """获取某个链接的历史快照"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE link_id = ? ORDER BY captured_at DESC LIMIT ?",
        (link_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    """获取仪表盘统计数据"""
    conn = get_conn()
    now = conn.execute("SELECT datetime('now', 'localtime')").fetchone()[0]

    # 追踪内容总数
    total = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]

    # 各平台数量
    by_platform = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM links GROUP BY platform"
    ).fetchall()

    # T节点统计：有 publish_time 的链接
    t_nodes = conn.execute("""
        SELECT 
            CASE 
                WHEN days <= 1 THEN 'T1'
                WHEN days <= 3 THEN 'T3'
                WHEN days <= 5 THEN 'T5'
                WHEN days <= 7 THEN 'T7'
                WHEN days <= 15 THEN 'T15'
                WHEN days <= 30 THEN 'T30'
                ELSE 'T30+'
            END as t_label,
            COUNT(*) as cnt
        FROM (
            SELECT 
                CAST((julianday(?) - julianday(s.publish_time, 'unixepoch')) AS INTEGER) as days
            FROM snapshots s
            JOIN links l ON s.link_id = l.id
            WHERE s.id IN (SELECT MAX(id) FROM snapshots GROUP BY link_id)
            AND s.publish_time IS NOT NULL AND s.publish_time != ''
        )
        GROUP BY t_label
        ORDER BY 
            CASE t_label
                WHEN 'T1' THEN 1 WHEN 'T3' THEN 2 WHEN 'T5' THEN 3
                WHEN 'T7' THEN 4 WHEN 'T15' THEN 5 WHEN 'T30' THEN 6
                ELSE 7
            END
    """, (now,)).fetchall()

    # 今日待采集数（简化：所有链接都需要采集）
    pending = total

    # 异常数（最近一次抓取失败或有 error 字段的）
    anomalies = conn.execute("""
        SELECT COUNT(DISTINCT s.link_id)
        FROM snapshots s
        JOIN links l ON s.link_id = l.id
        WHERE s.id IN (SELECT MAX(id) FROM snapshots GROUP BY link_id)
        AND (s.title IS NULL OR s.title = '')
    """).fetchone()[0]

    # 快照覆盖率
    links_with_snapshots = conn.execute("""
        SELECT COUNT(DISTINCT link_id) FROM snapshots
    """).fetchone()[0]
    coverage = round(links_with_snapshots / total * 100, 1) if total > 0 else 0

    conn.close()

    return {
        "total": total,
        "pending": pending,
        "anomalies": anomalies,
        "coverage": coverage,
        "by_platform": {r["platform"]: r["cnt"] for r in by_platform},
        "t_nodes": {r["t_label"]: r["cnt"] for r in t_nodes},
    }


def get_content_list(platform: str = None, search: str = None) -> list:
    """获取内容列表（带搜索和T节点）"""
    conn = get_conn()
    now = conn.execute("SELECT datetime('now', 'localtime')").fetchone()[0]

    query = """
        SELECT 
            l.id as link_id, l.url, l.platform, l.target_id,
            s.title, s.author, s.play_count, s.like_count,
            s.comment_count, s.favorite_count, s.share_count,
            s.follower_count, s.publish_time, s.captured_at,
            CASE 
                WHEN s.publish_time IS NOT NULL AND s.publish_time != ''
                THEN CAST((julianday(?) - julianday(s.publish_time, 'unixepoch')) AS INTEGER)
                ELSE NULL
            END as days_since_publish
        FROM links l
        LEFT JOIN (
            SELECT * FROM snapshots WHERE id IN (SELECT MAX(id) FROM snapshots GROUP BY link_id)
        ) s ON l.id = s.link_id
        WHERE 1=1
    """
    params = [now]

    if platform:
        query += " AND l.platform = ?"
        params.append(platform)

    if search:
        query += " AND (s.title LIKE ? OR s.author LIKE ? OR l.url LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    query += " ORDER BY s.captured_at DESC, l.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_content_detail(link_id: int) -> dict:
    """获取单个内容详情（含T节点和历史）"""
    conn = get_conn()
    now = conn.execute("SELECT datetime('now', 'localtime')").fetchone()[0]

    # 基本信息
    link = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    if not link:
        conn.close()
        return None

    # 最新快照
    latest = conn.execute(
        "SELECT *, CAST((julianday(?) - julianday(publish_time, 'unixepoch')) AS INTEGER) as days_since_publish FROM snapshots WHERE link_id = ? ORDER BY captured_at DESC LIMIT 1",
        (now, link_id)
    ).fetchone()

    # 历史快照（带 T 节点标签）
    history = conn.execute(
        """SELECT * FROM snapshots WHERE link_id = ? ORDER BY captured_at ASC""",
        (link_id,)
    ).fetchall()

    # 给每条历史快照计算 T 节点
    publish_time = latest["publish_time"] if latest else None
    history_with_t = []
    for h in history:
        hd = dict(h)
        captured = hd.get("captured_at", "")
        if captured and publish_time:
            try:
                days = conn.execute(
                    "SELECT CAST((julianday(?) - julianday(?, 'unixepoch')) AS INTEGER)",
                    (captured, publish_time)
                ).fetchone()[0]
                if days is not None:
                    hd["days_since_publish"] = days
                    if days <= 1: hd["t_label"] = "T1"
                    elif days <= 3: hd["t_label"] = "T3"
                    elif days <= 5: hd["t_label"] = "T5"
                    elif days <= 7: hd["t_label"] = "T7"
                    elif days <= 15: hd["t_label"] = "T15"
                    elif days <= 30: hd["t_label"] = "T30"
                    else: hd["t_label"] = "T30+"
            except Exception:
                pass
        history_with_t.append(hd)

    conn.close()

    result = dict(link)
    if latest:
        result.update(dict(latest))
    
    result["history"] = history_with_t

    # 计算当前T节点标签
    days = result.get("days_since_publish")
    if days is not None:
        if days <= 1: result["t_label"] = "T1"
        elif days <= 3: result["t_label"] = "T3"
        elif days <= 5: result["t_label"] = "T5"
        elif days <= 7: result["t_label"] = "T7"
        elif days <= 15: result["t_label"] = "T15"
        elif days <= 30: result["t_label"] = "T30"
        else: result["t_label"] = "T30+"

    return result
