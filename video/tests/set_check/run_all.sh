#!/bin/bash
# set_check.py 和 render.load_scene 缺布景报错的测试。用法：bash video/tests/set_check/run_all.sh    退出码 0 = 全过。样例生成到 video/out/tests/set_check/。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
O=video/out/tests/set_check
fail=0
pass() { echo "PASS  $*"; }
bad() { echo "FAIL  $*"; fail=1; }
$PY video/tests/set_check/make_cases.py || exit 2

$PY video/set_check.py > $O/all.log 2>&1 && pass "现有布景（video/sets/*.json 全部）：退出码 0" || { bad "现有布景没通过 set_check"; cat $O/all.log; }
$PY video/set_check.py $O/ok_copy.json > /dev/null 2>&1 && pass "原样副本：退出码 0" || bad "原样副本没通过"
for f in bad_no_fore bad_missing_image bad_fields bad_wallstrip_name bad_far_too_narrow; do
  $PY video/set_check.py $O/$f.json > $O/$f.log 2>&1; rc=$?
  [ $rc = 1 ] && grep -q "问题" $O/$f.log && pass "$f：退出码 1，报了问题" || bad "$f 应该退出码 1（实际 $rc）"
done
grep -q "缺少「fore」层" $O/bad_no_fore.log && pass "缺 fore 层：报的是「缺少「fore」层」" || bad "缺 fore 层的报错不对"
grep -q "jinyang_tower.png" $O/bad_missing_image.log && pass "缺图：报出缺的是哪张" || bad "缺图的报错没说是哪张"
grep -q "宽高比至少" $O/bad_far_too_narrow.log && pass "远景图太窄：说明白要多宽" || bad "远景图太窄的报错不对"
# 警告：画框层有东西、没写 qa.pine（item 11）：退出码 0，但有警告；写了 0 就没有
$PY video/set_check.py $O/warn_frame_no_pine.json > $O/w1.log 2>&1; rc=$?
[ $rc = 0 ] && grep -q "没写 qa.pine" $O/w1.log && pass "画框层有摆件、没写 qa.pine：退出码 0，有警告" || bad "画框层没写 qa.pine 应该警告（退出码 $rc）"
$PY video/set_check.py $O/ok_frame_pine0.json > $O/w2.log 2>&1
grep -q "没写 qa.pine" $O/w2.log && bad "写了 qa.pine = 0 还警告" || pass "写了 qa.pine = 0：不警告"
# --scenes
$PY video/set_check.py --scenes video/scenes/ep01v2/shot*.json > /dev/null 2>&1 && pass "--scenes：ep01v2 六场用到的布景、镜头范围都没问题" || bad "--scenes 对 ep01v2 报了问题"
$PY video/set_check.py --scenes $O/scene_camera_too_far.json > /dev/null 2>&1 && bad "镜头走太远应该被拦下" || pass "--scenes：镜头走出画布范围：退出码 1"
$PY video/set_check.py --scenes $O/scene_needs_jinyang.json > /dev/null 2>&1 && bad "缺布景的场景应该被拦下" || pass "--scenes：场景要没有的布景：退出码 1"
# render.load_scene 缺布景：中文、无 traceback、退出码 1
out=$($PY video/layout_qa.py --ep ep01v2 $O/scene_needs_jinyang.json 2>&1); rc=$?
if [ $rc = 1 ] && grep -q "找不到 video/sets/jinyang.json" <<<"$out" && grep -q "video/sets/README.md" <<<"$out" && ! grep -q Traceback <<<"$out"; then pass "缺布景：中文错误（哪个场景、要哪个布景、放哪里），无 traceback，退出码 1"; else bad "缺布景的报错不对（退出码 $rc）：$out"; fi
$PY video/tests/set_check/check_assets_for.py > $O/af.log 2>&1 && pass "布景缺图：assets_for 报中文错误（点名缺哪张、让跑 set_check）" || { bad "布景缺图的报错不对"; cat $O/af.log; }
[ $fail = 0 ] && echo "全部通过" || echo "有不通过的"
exit $fail
