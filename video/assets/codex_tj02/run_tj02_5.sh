#!/usr/bin/env bash
# tj02 第 5 步（画面素材）：并行调 Codex 画新图。用法（仓库根目录，Git Bash）：
#   bash video/assets/codex_tj02/run_tj02_5.sh <名字> [<名字> ...]       # 并行跑，已有 <名字>.png 的也会重画（要保留旧图先改名）
# 每个名字读同目录的 <名字>.txt，参考图见下面 refs()（路径相对本目录；第一张永远是画风参考）。
cd "$(dirname "$0")/../../.." || exit 1
D=video/assets/codex_tj02
R=../ref/paper_style_ref.png
C=../chars
P=../props
S=../sets

refs() {
  case "$1" in
    set_sky_rain)    echo "$R $S/jin_land/sky.png $S/jin_land/sky_night.png" ;;
    set_hut)         echo "$R $P/teaser_rain.png $S/jin_land/ground.png $S/jin_land/ridge_near.png" ;;
    set_mud)         echo "$R $S/jin_land/ground.png $P/stove.png $P/paper_bird.png" ;;
    wwh_rain_a)      echo "$R $C/wwh_hi_firm.png $C/wwh_cape.png" ;;
    wwh_rain_b|wwh_rain_c) echo "$R wwh_rain_a.png" ;;
    yr_hi_a)         echo "$R $C/yr_sit.png $C/yr_stand.png" ;;
    yr_hi_b|yr_hi_c) echo "$R yr_hi_a.png" ;;
    yr_l_a)          echo "$R $C/yr_sit.png $C/yr_kneel.png $C/yr_stand.png" ;;
    yr_l_b)          echo "$R $C/yr_helped.png $C/yr_stand.png" ;;
    wdc_run|wdc_pant) echo "$R $C/wdc_a_stand.png $C/wdc_b_stand.png $C/wdc_c_stand.png $C/wdc_a_soaked.png $P/cup_lacquer.png" ;;
    sgm_hi_magnify)  echo "$R $C/sgm_hi_remote.png $C/sgm_hi_point.png" ;;
    wuh_point)       echo "$R $C/wwh_stand.png $C/wgh_stand.png $C/wq_stand.png" ;;
    hands_remote)    echo "$R $P/hands_stack.png $P/douli.png $C/wwh_cape.png $C/sgm_hi_remote.png" ;;
    paperman)        echo "$R" ;;
    flags_pigeon)    echo "$R $P/flag_wei.png $P/paper_bird.png" ;;
    frogs)           echo "$R $P/frog_wait.png $P/frog_wave.png $P/frog_hat.png" ;;
    magnet)          echo "$R $P/medal.png" ;;
    scale_a)         echo "$R $P/token.png $P/stove.png" ;;
    scale_b)         echo "$R scale_a.png" ;;
    magnifier)       echo "$R sgm_hi_magnify.png $P/token.png" ;;
    boat)            echo "$R $P/chariot_front.png" ;;
    bubble_sweeper|bubble_rain_meet|bubble_watch_msg) echo "$R $P/bubble_nickname.png" ;;
    bubble_shoe_mud) echo "$R $P/bubble_nickname.png $C/wwh_help.png" ;;
    bubble_door)     echo "$R $P/bubble_nickname.png $P/frog_wait.png" ;;
    *)               echo "$R" ;;
  esac
}

for n in "$@"; do
  bash video/codex_gen.sh $D "$n" $(refs "$n") > $D/run_$n.out 2>&1 &
done
wait
for n in "$@"; do cat $D/run_$n.out; done
