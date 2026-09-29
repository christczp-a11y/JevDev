#!/bin/bash
# 一键重跑 video/board.py 的测试（工作流第 5 步的总览图）。用法（仓库根目录）：bash video/tests/board/run_all.sh
# 用合成的登记表和小图，不依赖真实素材；不要网络、不要 Jev key。输出在 video/out/tests/board/。退出码 0 = 全过。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
"$PY" video/tests/board/test_board.py
rc=$?
[ $rc = 0 ] && echo "board：全过" || echo "board：有失败（退出码 $rc）"
exit $rc
