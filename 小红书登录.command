#!/bin/bash
# ==============================================
#  小红书登录 — 双击运行，登录一次后自动复用
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║    小红书登录                        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

if [ ! -d "venv_sys" ]; then
    echo "  ⚠️  请先运行「首次安装.command」完成环境安装"
    read -p "  按 Enter 关闭窗口..."
    exit 1
fi

venv_sys/bin/python3 login_xiaohongshu.py

echo ""
read -p "  按 Enter 关闭窗口..."
