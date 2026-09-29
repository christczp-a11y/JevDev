#!/bin/bash
# logic_qa.py 的测试（不真跑观察员：观察员要花钱、要 Jev key）。用法：bash video/tests/logic_qa/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/logic_qa/。
# 1 提示词和金标准（改动之前的 logic_qa 导出的）一字不差；2 main 的流程（没有角色的场次、读不到集配置、tj01 的 format）。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
fail=0
$PY video/tests/logic_qa/compare_prompts.py || fail=1
$PY video/tests/logic_qa/check_main.py || fail=1
[ $fail = 0 ] && echo "全部通过" || echo "有不通过的"
exit $fail
