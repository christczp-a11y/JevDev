#!/usr/bin/env bash
# 整集其余第 2 批（重画）：inset_yinduo2（尹铎的衣服不能是红色）、city_icons2（墙的颜色太艳）、zxz_expr_a/b（3 张一起画太小，改 2+1）。
cd "$(dirname "$0")/../../.."
D=video/assets/codex_tj01
R=../ref/paper_style_ref.png
run() { local n=$1; shift; [ -s "$D/$n.png" ] && { echo "已有 $n"; return; }; bash video/codex_gen.sh $D $n $R "$@" > $D/run_$n.out 2>&1; cat $D/run_$n.out; }
run inset_yinduo2 ../chars/dg_stand_hi.png ../chars/zxz_stand_hi.png &
run city_icons2 ../props/city_icon1.png &
run zxz_expr_a hr_zxz_hkz_dg.png ../chars/zxz_stand_hi.png &
run zxz_expr_b hr_zxz_hkz_dg.png ../chars/zxz_stand_hi.png &
wait
