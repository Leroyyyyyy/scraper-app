#!/bin/bash
# ==============================================
#  小红书登录 — 双击运行，扫码即完成
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║    小红书扫码登录                   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  浏览器即将打开，请在浏览器中："
echo "  1. 用手机小红书 App 扫描页面上的二维码"
echo "  2. 登录成功后，回到这里按 Enter"
echo ""

venv_sys/bin/python3 login_xiaohongshu.py

echo ""
read -p "  按 Enter 关闭窗口..."
