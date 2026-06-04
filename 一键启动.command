#!/bin/bash
# ==============================================
#  一键启动 — 启动后台服务 + 打开网页
#  双击此文件即可使用
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="data/server.pid"
PORT=8000

# 检查是否已运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  ✅ 服务已在运行中"
        open "http://localhost:$PORT"
        exit 0
    fi
fi

# 检查端口
if lsof -i :$PORT &>/dev/null; then
    echo "  ⚠️  端口 $PORT 已被占用，尝试关闭旧进程..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null
    sleep 1
fi

# 确保环境就绪
mkdir -p data

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY

# 检查依赖
if [ ! -d "venv_sys" ]; then
    echo "  ⚠️  首次使用需要安装环境，正在打开安装向导..."
    open "首次安装.command"
    exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║    数据抓取工具  v1.0               ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  🚀 正在启动后台服务..."
echo ""

# 启动服务
venv_sys/bin/python3 main.py > data/server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PID_FILE"

# 等待服务就绪
echo "  等待服务就绪..."
for i in {1..15}; do
    if curl -s --max-time 1 "http://localhost:$PORT/api/snapshots" &>/dev/null; then
        echo "  ✅ 服务启动成功!"
        echo ""
        echo "  🌐 正在打开浏览器..."
        open "http://localhost:$PORT"
        echo ""
        echo "  ┌─────────────────────────────────────┐"
        echo "  │  后台服务已启动，请勿关闭此窗口    │"
        echo "  │  关闭此窗口将停止服务             │"
        echo "  │  双击「停止服务.command」安全退出  │"
        echo "  └─────────────────────────────────────┘"
        echo ""

        # 保持窗口打开，等待用户手动关闭
        echo "  按 Ctrl+C 或关闭此窗口停止服务"
        trap "kill $SERVER_PID 2>/dev/null; rm -f $PID_FILE; echo '  服务已停止'; exit 0" INT TERM
        
        # 守护循环：监控进程状态
        while kill -0 $SERVER_PID 2>/dev/null; do
            sleep 2
        done
        
        # 进程异常退出，自动重启
        echo ""
        echo "  ⚠️  服务异常退出，3秒后自动重启..."
        sleep 3
        
        venv_sys/bin/python3 main.py > data/server.log 2>&1 &
        SERVER_PID=$!
        echo $SERVER_PID > "$PID_FILE"
        echo "  🔄 服务已重启"
        
        # 继续守护
        while kill -0 $SERVER_PID 2>/dev/null; do
            sleep 2
        done
    fi
    sleep 1
done

echo "  ❌ 服务启动失败，请检查 data/server.log"
read -p "  按 Enter 关闭窗口..."
