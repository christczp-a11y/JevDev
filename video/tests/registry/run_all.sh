#!/bin/bash
# registry_check.py 的反向试验（PITFALLS P10）。用法（仓库根目录或任何地方）：bash video/tests/registry/run_all.sh
#   退出码 0 = 全过。输出写到 video/out/registry_test/（不进 git）：每一项一份 .log，还有故意改坏的登记表副本 reg_*.md。
# 三类：
#   1. 登记表本身：用 mutate.py 从真的 REGISTRY.md 造改坏一处的副本，registry_check.py 必须退出 1 并报出原因；
#   2. 场景 JSON：scenes/tj99（新集）、scenes/ep01（试做集目录）、flat/（不在 scenes/<集>/ 下）里的样例，每个的期望在下面；
#   3. 真的试做集场景 video/scenes/ep01v2：自动对账只该报 auntie_hands（T13），不许报别的。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
T=video/tests/registry
REG=video/assets/REGISTRY.md
OUT=video/out/registry_test
rm -rf "$OUT"; mkdir -p "$OUT"
fail=0; n=0

run() {  # run 标签 期望退出码 关键输出 [不许出现的输出] -- registry_check 的参数...
  local label=$1 want=$2 key=$3 notkey=$4; shift 5
  n=$((n+1))
  local out got; out=$($PY video/registry_check.py "$@" 2>&1); got=$?
  echo "$out" > "$OUT/$(printf '%02d' $n)_${label//[^A-Za-z0-9_]/_}.log"
  local ok=1
  [ "$got" = "$want" ] || ok=0
  grep -qF -- "$key" <<<"$out" || ok=0
  if [ -n "$notkey" ] && grep -qF -- "$notkey" <<<"$out"; then ok=0; fi
  if [ $ok = 1 ]; then
    echo "PASS  $label  退出码 $got  含「$key」${notkey:+  不含「$notkey」}"
  else
    echo "FAIL  $label  退出码 $got（期望 $want），关键输出「$key」$(grep -qF -- "$key" <<<"$out" && echo 有 || echo 没有)${notkey:+，不该有的「$notkey」$(grep -qF -- "$notkey" <<<"$out" && echo 出现了 || echo 没出现)}"
    echo "$out" | sed 's/^/      /'
    fail=1
  fi
}

m() {  # m 改法 期望退出码 关键输出：改坏登记表再查
  local case=$1 want=$2 key=$3
  $PY $T/mutate.py "$case" $REG "$OUT/reg_$case.md" || { echo "FAIL  mutate.py $case 没造出副本"; fail=1; return; }
  run "反向 $case" "$want" "$key" "" -- --registry "$OUT/reg_$case.md"
}

before=$(md5sum $REG | cut -d' ' -f1)

echo "---- 1. 登记表本身"
run "登记表本身" 0 "通过" "" -- 
m delete_row           1 "没登记：chars/kid_give.png"
m delete_coin_row      1 "没登记：props/coin.png"
m bad_facing           1 "朝向必须是 左 / 右 / 正面，写的是「向右」"
m empty_facing         1 "朝向必须是 左 / 右 / 正面，写的是「」"
m bad_size             1 "登记尺寸 395×484，实际 394×484"
m bad_size_format      1 "尺寸要写成 宽×高"
m bad_status           1 "状态必须以 定稿 / 未定稿 / 停用 开头"
m bad_scope            1 "范围必须是 系列 / 试做集 / 宣传图 / tj<集号>"
m bad_baked_cell       1 "「内含别的角色」要写 无 或 有：谁"
m coin_final           1 "props/coin.png 必须是停用（S4）"
m yuanbao_final        1 "chars/d2_gold_yuanbao.png 必须是停用（S4）"
m baked_missing        1 "QA.baked 里有 dad2_grab，登记表里它的「内含别的角色」没写"
m baked_extra          1 "登记表说 chars/kid_give.png 里画着别的角色"
m dup_prefix           1 "前缀 sy2_ 重名"
m prefix_of_other      1 "互为前缀"
m stop_prefix_mismatch 1 "把前缀 douzi_ 标成停用，但 chars/douzi_run.png"
m ghost_outside        1 "chars/ghost.png 写在了「二、素材表」以外的地方"
m ghost_inside         1 "登记了但文件不在：chars/ghost.png"
m dup_row              1 "chars/kid_give.png 登记了两次"
m missing_column       1 "chars/kid_give.png 应该有 8 列，实际 7 列"
m warn_unfinished      0 "通过"      # 状态写「未定稿」是合法的，登记表本身不报错；下面第 2 类用它试警告

echo "---- 2. 场景 JSON：新集 tj99"
S=$T/scenes/tj99
run "ok 只用系列素材"            0 "通过" "警告" -- $S/ok.json
run "ok 正面不查 native"         0 "通过" "错误" -- $S/ok_native_front.json
run "未定稿只警告"               0 "警告：$S/ok_warn.json：用了未定稿的素材 chars/sgm_frown.png" "错误" -- --registry "$OUT/reg_warn_unfinished.md" $S/ok_warn.json
run "未定稿的警告在真登记表里没有" 0 "通过" "警告" -- $S/ok_warn.json
run "native 朝右写成 -1"         1 "actor sgm 的 native=-1，但姿势图 sgm_finger 原图朝右，应该 native=1" "" -- $S/bad_native_right.json
run "native 朝左写成 1"          1 "actor desk 的 native=1，但姿势图 desk_wait 原图朝左，应该 native=-1" "" -- $S/bad_native_left.json
run "姿势图没登记"               1 "姿势图 nobody_stand 登记表里没有" "" -- $S/bad_unregistered.json
run "新集用试做集人物"           1 "新集 tj99 用了试做集的素材 chars/d2_run.png" "" -- $S/bad_pilot_char.json
run "新集用试做集道具"           1 "新集 tj99 用了试做集的素材 props/crow.png" "" -- $S/bad_pilot_prop.json
run "新集用 qin_gate"            1 "新集 tj99 用了试做集的布景 qin_gate" "" -- $S/bad_pilot_set.json
run "新集用 classroom"           1 "新集 tj99 用了试做集的布景 classroom" "" -- $S/bad_pilot_set_classroom.json
run "新集用试做集纸偶"           1 "新集 tj99 的 actor youth 用了试做集的纸偶 rig/youth" "" -- $S/bad_pilot_rig.json
run "用停用的素材"               1 "用了停用的素材 chars/dad_grab.png" "" -- $S/bad_stopped.json
run "coinRain 事件"              1 "用了事件 coinRain" "" -- $S/bad_coinrain.json
run "yuanbao 字符串"             1 "含 yuanbao" "" -- $S/bad_yuanbao.json
run "整个 tj99 目录一起查"       1 "场景 JSON：查了 $(ls $S/*.json | wc -l) 个文件" "" -- $S

echo "---- 3. 场景 JSON：试做集目录 ep01 和不在 scenes/<集>/ 下的"
run "试做集目录可以用试做集素材" 0 "通过" "T19" -- $T/scenes/ep01/pilot_ok.json
run "试做集里 native 也要对"     1 "actor auntie 的 native=1，但姿势图 auntie_hands 原图朝左" "试做集的" -- $T/scenes/ep01/pilot_bad_native.json
run "试做集也不许用停用素材"     1 "用了停用的素材 chars/dad_grab.png" "" -- $T/scenes/ep01/pilot_stopped.json
run "不在 scenes/<集>/ 下不写 --ep" 0 "T19（试做集素材、试做集布景）这一项没查" "错误" -- $T/flat/flat_set.json
run "不在 scenes/<集>/ 下写 --ep tj95" 1 "新集 tj95 用了试做集的布景 qin_gate" "" -- --ep tj95 $T/flat/flat_set.json
run "--ep ep01v2 当试做集"       0 "通过" "错误" -- --ep ep01v2 $T/flat/flat_set.json

echo "---- 4. 真的试做集场景 video/scenes/ep01v2：只该报 auntie_hands（T13）"
run "ep01v2 自动对账" 1 "姿势图 auntie_hands 原图朝左，应该 native=-1" "teachers" -- video/scenes/ep01v2
run "ep01v2 只有 2 个问题" 1 "不通过：2 个问题" "停用的素材" -- video/scenes/ep01v2

echo "----"
after=$(md5sum $REG | cut -d' ' -f1)
[ "$before" = "$after" ] || { echo "FAIL  测试改动了真的登记表"; fail=1; }
if [ $fail = 0 ]; then echo "run_all.sh：$n 项全过"; else echo "run_all.sh：有失败"; fi
exit $fail
