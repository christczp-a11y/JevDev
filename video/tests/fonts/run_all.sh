#!/bin/bash
# 字体本地化的测试。用法：bash video/tests/fonts/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/fonts/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
.venv/Scripts/python video/tests/fonts/check_fonts.py
