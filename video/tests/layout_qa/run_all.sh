#!/bin/bash
# layout_qa.py 的测试（第 0 步第 8 项：PINE 按布景、BAKED 按集配置；第 2 轮：读不到集配置退出 1）。
# 用法：bash video/tests/layout_qa/run_all.sh    退出码 0 = 全过。输出在 video/out/tests/layout_qa/。
# 和改动前（d589a8a）的 layout_qa 输出逐行比较的那一次性测试在第 1 轮做过（新旧输出一致），不在这里。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
T=video/tests/layout_qa
O=video/out/tests/layout_qa
fail=0
pass() { echo "PASS  $*"; }
bad() { echo "FAIL  $*"; fail=1; }
norm() { sed 's/^== .*：/== X：/' | tr -d '\r'; }
$PY $T/make_bad.py || exit 2

$PY video/layout_qa.py video/scenes/ep01v2/shot*.json > $O/ep01v2.log 2>&1; rc=$?
[ $rc = 0 ] && diff <(norm < $O/ep01v2.log) $T/expected_ep01v2.txt > /dev/null && pass "ep01v2 六场：退出码 0，都是「没有站位错误」（和第 0 步基线一致）" || { bad "ep01v2 六场（退出码 $rc）"; cat $O/ep01v2.log; }
$PY video/layout_qa.py --ep ep01v2 $O/bad_shot1.json > $O/bad1.log 2>&1; rc=$?
[ $rc = 1 ] && diff <(norm < $O/bad1.log) $T/expected_bad_shot1.txt > /dev/null && pass "故意有站位错误的场景：退出码 1，4 类错误（被松树挡、重叠、重影、说话时出画）一条不少、一字不差" || { bad "站位错误场景（退出码 $rc）"; cat $O/bad1.log; }
$PY video/layout_qa.py --ep ep01v2 $O/classroom_left.json > $O/cl.log 2>&1; rc=$?
[ $rc = 0 ] && diff <(norm < $O/cl.log) $T/expected_classroom_left.txt > /dev/null && pass "教室布景没写 qa.pine：人站在 x=100 不报「被松树挡」（松树规则只对写了 qa.pine 的布景）" || { bad "教室场景（退出码 $rc）"; cat $O/cl.log; }
# tj01 的配置没有 baked：重影这一项查不出来（配置就是这样配的），但读得到配置，不报错
$PY video/layout_qa.py --ep tj01 $O/bad_shot1.json > $O/tj.log 2>&1; rc=$?
[ $rc = 1 ] && ! grep -q "重影" $O/tj.log && grep -q "被松树挡" $O/tj.log && pass "--ep tj01（QA.baked 是空的）：重影不查，别的照查" || bad "--ep tj01（退出码 $rc）"
# 第 2 轮：读不到集配置 = 退出 1，不往下查（以前只警告，R11 重影会被悄悄跳过）
out=$($PY video/layout_qa.py $O/bad_shot1.json 2>&1); rc=$?
[ $rc = 1 ] && grep -q "没有读到这一集的配置" <<<"$out" && ! grep -q "个站位错误" <<<"$out" && pass "场景不在 video/scenes/<集>/ 下又没写 --ep：退出码 1，说清楚怎么办，没有往下查" || bad "没有集名应该退出码 1（实际 $rc）：$out"
out=$($PY video/layout_qa.py --ep no_such_ep $O/bad_shot1.json 2>&1); rc=$?
[ $rc = 1 ] && grep -q "找不到这一集的配置" <<<"$out" && pass "--ep 写了不存在的集：退出码 1" || bad "不存在的集应该退出码 1（实际 $rc）：$out"
[ $fail = 0 ] && echo "全部通过" || echo "有不通过的"
exit $fail
