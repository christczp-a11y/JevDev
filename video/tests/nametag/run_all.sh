#!/bin/bash
# 人名牌的测试（3D 舞台 + 2D 引擎；约 3 分钟，3D 页面初始化要扫每张牌的入画时刻）。用法：bash video/tests/nametag/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/nametag/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
.venv/Scripts/python video/tests/nametag/check_nametags.py
