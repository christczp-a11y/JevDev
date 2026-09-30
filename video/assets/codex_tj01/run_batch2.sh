#!/usr/bin/env bash
# 第一场追加（PITFALLS M1，交领人物不许翻转）：智果皮影朝左、段规跪坐朝左。
cd "$(dirname "$0")/../../.."
R=../ref/paper_style_ref.png
D=video/assets/codex_tj01
bash video/codex_gen.sh $D zgo_shadow_l $R ../chars/zgo_shadow.png shadow_zgo.png > $D/run_zgo_shadow_l.out 2>&1 &
bash video/codex_gen.sh $D dg_kneel_l $R ../chars/dg_kneel.png ../chars/dg_hi_tight.png > $D/run_dg_kneel_l.out 2>&1 &
wait
cat $D/run_zgo_shadow_l.out $D/run_dg_kneel_l.out
