#!/bin/bash
# 系列参考帧的检查：自检（8 张的卷号胶囊是不是 ZCOOL KuaiLe、一不一致）+ 用现在的代码重截 8 个时刻带容差对比（约 1.5 分钟）。
# 用法：bash video/tests/ref_frames/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/ref_frames/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
fail=0
.venv/Scripts/python video/tests/ref_frames/check_ref_frames.py --render || fail=1
# 旧参考帧（E1 那批，如果还在）应该被抓出备用字体：证明这个检查确实抓得到
if [ -d video/out/tests/ref_frames/old_refs ]; then
  .venv/Scripts/python video/tests/ref_frames/check_ref_frames.py --dir video/out/tests/ref_frames/old_refs > /dev/null && { echo "FAIL  旧参考帧应该被检查抓出来，却通过了"; fail=1; } || echo "PASS  第一版参考帧（备用字体那批）被检查抓出来了：退出码 1"
fi
[ $fail = 0 ] && echo "全部通过" || echo "有不通过的"
exit $fail
