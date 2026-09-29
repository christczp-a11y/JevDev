#!/bin/bash
# 跑 video/tests/ 下所有的 run_all.sh，最后汇总。用法：bash video/tests/run_all.sh    退出码 0 = 全过。
# 每个目录的输出在 video/out/tests/<目录名>/。除了 jev_pick 的「带 key 的真跑」（有 TYPESAFE_API_KEY 才跑；结果按哈希缓存，第一次约 130 次请求，之后 0 次）都不带 Jev、不花钱。
cd "$(dirname "$0")/../.." || exit 2
fail=0
for d in video/tests/*/; do
  n=$(basename "$d")
  [ -f "$d/run_all.sh" ] || continue
  echo "================ $n"
  bash "$d/run_all.sh"; rc=$?
  [ $rc = 0 ] && echo ">>>> $n：通过" || { echo ">>>> $n：不通过（退出码 $rc）"; fail=1; }
done
echo
[ $fail = 0 ] && echo "video/tests 全部通过" || echo "video/tests 有不通过的"
exit $fail
