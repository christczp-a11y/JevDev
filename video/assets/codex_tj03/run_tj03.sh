#!/usr/bin/env bash
# tj03 第 5 步（提前）：新角色和新姿势，并行调 Codex 画图。用法（仓库根目录，Git Bash）：
#   bash video/assets/codex_tj03/run_tj03.sh <名字> [<名字> ...]       # 并行跑，已有 <名字>.png 的会被重画（要保留旧图先改名）
# 每个名字读同目录的 <名字>.txt；参考图见下面 refs()（路径相对本目录；第一张永远是画风参考）。
cd "$(dirname "$0")/../../.." || exit 1
D=video/assets/codex_tj03
R=../ref/paper_style_ref.png
C=../chars
P=../props

refs() {
  case "$1" in
    wuh_pose_a|wuh_pose_b|wuh_hi_a) echo "$R $C/wuh_point.png" ;;
    wuh_hi_b|wuh_hi_c)              echo "$R wuh_hi_a.png" ;;
    wq_pose)                        echo "$R $C/wq_stand.png $C/wq_hi_point_l.png" ;;
    wq_hi_a)                        echo "$R $C/wq_hi_point_l.png $C/wq_stand.png" ;;
    wq_hi_b|wq_hi_c)                echo "$R wq_hi_a.png" ;;
    rower_row)                      echo "$R $C/zhao_dig.png" ;;
    rower_stop)                     echo "$R rower_row.png" ;;
    preview_chars)                  echo "$R $C/wq_stand.png" ;;
    wuh_pose_c)                     echo "$R $C/wuh_bow_l.png $C/wuh_ponder.png" ;;
    card_sanmiao)                   echo "$R" ;;
    card_xiajie|card_shangzhou)     echo "$R card_sanmiao.png" ;;
    props_a)                        echo "$R" ;;
    mini_mountains)                 echo "$R props_a.png" ;;
    icons_boat)                     echo "$R $P/icon_heart.png $P/icon_look.png ../codex_tj02/boat_crop.png $C/rower_row.png" ;;
    bubble_wall_nap)                echo "$R $P/bubble_nickname.png $P/paperman_wave.png" ;;
    bubble_knight_a)                echo "$R $P/bubble_nickname.png" ;;
    bubble_knight_bc|bubble_knight_d) echo "$R $P/bubble_shoe_mud.png bubble_knight_a.png" ;;
    *)                              echo "$R" ;;
  esac
}

for n in "$@"; do
  bash video/codex_gen.sh $D "$n" $(refs "$n") > $D/run_$n.out 2>&1 &
done
wait
for n in "$@"; do cat $D/run_$n.out; done
