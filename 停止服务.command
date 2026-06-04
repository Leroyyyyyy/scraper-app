#!/bin/bash
# ==============================================
#  停止服务 — 双击即可安全退出
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="data/server.pid"
PORT=8000

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║    停止数据抓取工具                 ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# 方式1: 通过 PID 文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        sleep 1
        if ! kill -0 "$PID" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo "  ✅ 服务已停止 (PID: $PID)"
        else
            kill -9 "$PID" 2>/dev/null
            rm -f "$PID_FILE"
            echo "  ✅ 服务已强制停止 (PID: $PID)"
        fi
    else
        rm -f "$PID_FILE"
        echo "  ℹ️  PID 文件存在但进程已不存在"
    fi
fi

# 方式2: 通过端口清理残留
if lsof -ti :$PORT &>/dev/null; then
    lsof -ti :$PORT | xargs kill -9 2>/dev/null
    echo "  ✅ 已清理端口 $PORT 残留进程"
fi

# 方式3: 杀所有 main.py
PIDS=$(pgrep -f "main.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null
    echo "  ✅ 已清理所有 main.py 进程"
fi

echo ""
echo "  服务已完全停止"
echo ""
read -p "  按 Enter 关闭窗口..."
