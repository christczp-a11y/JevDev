#!/bin/bash
# selfcheck.py 拿老提交当基准也要能跑完（第 3 轮：老 render.open_page 没有 hide_nametags 参数，以前会 TypeError 崩溃）。
# 用法：bash video/tests/selfcheck/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/selfcheck/ 和 video/out/selfcheck_shot5/。
# 说明：拿第 0 步第 19 项（字体本地化）之前的提交当基准时，文字区域（卷号、标签、字幕）都会被标成变化——
#       改前是备用字体，改后是 ZCOOL KuaiLe / Noto Sans SC，这是字体修好的正常结果，不是新问题。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
O=video/out/tests/selfcheck
mkdir -p $O
fail=0
# d99e684：第 19 项之前的提交（老 render.py，没有 hide_nametags 参数）；HEAD：现在的提交（有没有这个参数都要能跑）
for base in d99e684 HEAD; do
  $PY video/selfcheck.py video/scenes/ep01v2/shot5.json --base $base > $O/base_$base.log 2>&1; rc=$?
  if [ $rc = 0 ] && grep -q "个时刻，改前 = $base" $O/base_$base.log && ! grep -q Traceback $O/base_$base.log && [ -f video/out/selfcheck_shot5/summary.json ]; then
    echo "PASS  selfcheck --base $base 在 shot5 上跑完，退出码 0：$(tail -1 $O/base_$base.log)"
  else
    echo "FAIL  selfcheck --base $base 退出码 $rc"; tail -8 $O/base_$base.log; fail=1
  fi
done
[ $fail = 0 ] && echo "全部通过" || echo "有不通过的"
exit $fail
