#!/bin/bash
# build_stage3d.py 的退出码、字体失败、初始化重试的测试。用法：bash video/tests/stage3d/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/stage3d/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
.venv/Scripts/python video/tests/stage3d/check_stage3d.py
