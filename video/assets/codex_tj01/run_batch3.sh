#!/usr/bin/env bash
# 整集其余（素材清单第二节 12–35 号，系列插画除外）：第 1 批并行；已有 <名字>.png 的跳过。
cd "$(dirname "$0")/../../.."
D=video/assets/codex_tj01
R=../ref/paper_style_ref.png
run() { local n=$1; shift; [ -s "$D/$n.png" ] && { echo "已有 $n"; return; }; bash video/codex_gen.sh $D $n $R "$@" > $D/run_$n.out 2>&1; cat $D/run_$n.out; }
run bubble_checkers ../props/bubble_nickname.png &
run bubble_shot ../props/bubble_nickname.png &
run screen_cups ../props/bubble_nickname.png prop_hands.png &
run inset_yinduo ../chars/dg_stand_hi.png ../chars/zxz_stand_hi.png &
run chariot_full ../props/chariot.png &
run hands_douli prop_hands.png prop_frogs.png &
run city_icons ../props/city_icon1.png &
wait
run book_page_hi &
run sky_night ../sets/jin_land/sky.png &
run zb_expr_a ../chars/zb_hi_laugh.png ../chars/zb_stand_hi.png &
run zb_expr_b ../chars/zb_hi_laugh.png ../chars/zb_stand_hi.png &
run zxz_expr hr_zxz_hkz_dg.png ../chars/zxz_stand_hi.png &
wait
for n in bubble_checkers bubble_shot screen_cups inset_yinduo chariot_full hands_douli city_icons book_page_hi sky_night zb_expr_a zb_expr_b zxz_expr; do [ -s $D/$n.png ] && echo "OK   $n" || echo "缺   $n"; done
