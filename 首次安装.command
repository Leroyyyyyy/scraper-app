#!/bin/bash
# ==============================================
#  首次安装脚本 — 双击运行即可完成环境配置
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║    数据抓取工具 - 首次安装          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  正在检查环境..."
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "  ❌ 未找到 Python3，请先安装 Python"
    echo "     下载地址: https://www.python.org/downloads/"
    read -p "  按 Enter 退出..."
    exit 1
fi
echo "  ✅ Python3: $(python3 --version)"

# 创建虚拟环境
if [ ! -d "venv_sys" ]; then
    echo "  📦 创建虚拟环境..."
    python3 -m venv venv_sys
fi

# 安装依赖
echo "  📦 安装 Python 依赖..."
unset HTTP_PROXY HTTPS_PROXY
venv_sys/bin/pip install -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    requests fastapi uvicorn playwright -q 2>&1 | tail -1

echo "  ✅ Python 依赖安装完成"

# 安装 Playwright 浏览器
echo "  🌐 安装浏览器内核（可能需要几分钟）..."
venv_sys/bin/playwright install chromium 2>&1 | tail -3
echo "  ✅ 浏览器内核安装完成"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ✅ 安装完成！                     ║"
echo "  ║   双击「一键启动.command」开始使用   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
read -p "  按 Enter 关闭窗口..."
