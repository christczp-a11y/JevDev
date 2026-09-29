#!/usr/bin/env bash
# 第一场新图第 1 批（并行）：bash video/assets/codex_tj01/run_batch1.sh
cd "$(dirname "$0")/../../.."
R=../ref/paper_style_ref.png
D=video/assets/codex_tj01
bash video/codex_gen.sh $D stove_flooded $R ../props/stove.png ../sets/jin_land/water.png > $D/run_stove_flooded.out 2>&1 &
bash video/codex_gen.sh $D shadow_screen $R shadow_zgo.png > $D/run_shadow_screen.out 2>&1 &
bash video/codex_gen.sh $D zb_shadow_young $R shadow_zgo.png shadow_zxu.png ../chars/zb_stand_hi.png > $D/run_zb_shadow_young.out 2>&1 &
bash video/codex_gen.sh $D icons_new $R prop_icons.png ../chars/zb_stand_hi.png > $D/run_icons_new.out 2>&1 &
bash video/codex_gen.sh $D bubble_nickname $R > $D/run_bubble_nickname.out 2>&1 &
bash video/codex_gen.sh $D banquet_row $R ../sets/lantai/table.png ../sets/lantai/mat.png ../props/cup_lacquer.png > $D/run_banquet_row.out 2>&1 &
wait
for n in stove_flooded shadow_screen zb_shadow_young icons_new bubble_nickname banquet_row; do cat $D/run_$n.out; done
