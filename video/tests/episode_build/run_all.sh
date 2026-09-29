#!/bin/bash
# 分场脚本模板的测试。用法：bash video/tests/episode_build/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/episode_build/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
.venv/Scripts/python video/tests/episode_build/check_episode_build.py
