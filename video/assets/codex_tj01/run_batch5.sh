#!/usr/bin/env bash
# 整集分镜表要朝左的交领人物（PITFALLS M1：不许翻转）：同一个人、同样姿势和表情，只是朝左，右衽重画。
cd "$(dirname "$0")/../../.."
D=video/assets/codex_tj01
R=../ref/paper_style_ref.png
run() { local n=$1; shift; [ -s "$D/$n.png" ] && { echo "已有 $n"; return; }; bash video/codex_gen.sh $D $n $R "$@" > $D/run_$n.out 2>&1; cat $D/run_$n.out; }
run zxz_no_l ../chars/zxz_no.png &
run hkz_stand_l ../chars/hkz_stand.png ../chars/hkz_stand_hi.png &
run zb_cheer_l ../chars/zb_cheer.png &
run wgh_reins_l ../chars/wgh_reins.png &
wait
