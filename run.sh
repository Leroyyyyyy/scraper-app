#!/bin/bash
# 
# 数据抓取工具 — 守护启动脚本
# 服务崩溃后自动重启，日志输出到 data/server.log
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/data/server.log"
PYTHON="$SCRIPT_DIR/venv_sys/bin/python3"

mkdir -p "$SCRIPT_DIR/data"

# 清除代理环境变量
unset HTTP_PROXY
unset HTTPS_PROXY
unset ALL_PROXY

echo "==========================================="  >> "$LOG_FILE"
echo "  $(date '+%Y-%m-%d %H:%M:%S') — 守护脚本启动" >> "$LOG_FILE"
echo "==========================================="  >> "$LOG_FILE"

RESTART_COUNT=0

while true; do
    echo "$(date '+%H:%M:%S') 启动服务 (第 $RESTART_COUNT 次重启)" >> "$LOG_FILE"
    
    "$PYTHON" main.py 2>&1 | while IFS= read -r line; do
        echo "[$(date '+%H:%M:%S')] $line" >> "$LOG_FILE"
    done
    
    RESTART_COUNT=$((RESTART_COUNT + 1))
    echo "$(date '+%H:%M:%S') 服务异常退出，3秒后自动重启..." >> "$LOG_FILE"
    sleep 3
done
