#!/usr/bin/env bash
# 下载词书所需字体（Noto Serif SC，OFL 开源协议）到本目录 fonts/
set -e
cd "$(dirname "$0")"
mkdir -p fonts
cd fonts
echo "下载 Noto Serif SC…"
curl -sL -o NotoSerifSC-Regular.ttf "https://fonts.gstatic.com/s/notoserifsc/v36/H4cyBXePl9DZ0Xe7gG9cyOj7uK2-n-D2rd4FY7SCqyWv.ttf"
curl -sL -o NotoSerifSC-SemiBold.ttf "https://fonts.gstatic.com/s/notoserifsc/v36/H4cyBXePl9DZ0Xe7gG9cyOj7uK2-n-D2rd4FY7RcrCWv.ttf"
echo "完成："
ls -la
