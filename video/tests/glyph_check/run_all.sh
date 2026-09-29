#!/bin/bash
# 字形覆盖检查的测试。用法：bash video/tests/glyph_check/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/glyph_check/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
.venv/Scripts/python video/tests/glyph_check/check_glyph.py
