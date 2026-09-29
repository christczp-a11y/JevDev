#!/usr/bin/env bash
# 补画：2026-09-29 Codex 额度用完（"You've hit your usage limit ... try again at 12:00 PM"，本机时间），下面这些素材表的提示词已经写好、还没画出来。
# 额度恢复后（12:00 PM 以后）跑这个；已经有 <名字>.png 的会跳过，失败的可以直接重跑。全部约 20 分钟、20 次调用（并行 6 张；周威烈王姿势和课堂小孩两张已按主会话决定不画）。
#   bash video/assets/codex_tj01/run_pending.sh
# 跑完接着（仓库根目录，Git Bash，PYTHONIOENCODING=utf-8）：
#   .venv/Scripts/python video/assets/codex_tj01/split_tj01.py --list    # 先看每张表切出几件、数量对不对
#   .venv/Scripts/python video/assets/codex_tj01/split_tj01.py           # 拆图放进 chars/ props/ sets/
#   .venv/Scripts/python video/assets/codex_tj01/register_tj01.py        # 登记 REGISTRY.md（朝向默认右，逐张看图后到 register_tj01.py 的 CH/PROP/SETS 里改）
#   .venv/Scripts/python video/board_tj01.py all                         # 重出阵容图、剪影图、布景总览
#   .venv/Scripts/python video/registry_check.py                         # 退出码 0
# 拆完的姿势表：先看联系表（video/assets/codex_tj01/contact_tj01.py），再改 tj01_meta.py 里 zgo / zgu / zwl 的「姿势表里站着的图高」，
# 并把这三个人的 *_stand.png 按它缩放（同 zb_ 等：原图另存 *_stand_hi.png），PX 才算定下来。
cd "$(dirname "$0")"
R=../ref/paper_style_ref.png
C=../chars
export PYTHONIOENCODING=utf-8

run() {   # run <名字> <参考图...>
  local n=$1; shift
  if [ -s "$n.png" ]; then echo "已有 $n"; return; fi
  bash gen.sh "$n" "$@" > "run_$n.out" 2>&1
  cat "run_$n.out"
  if grep -q "usage limit" "codex_$n.log" 2>/dev/null; then echo "额度还没恢复：$n"; fi
}

# 第 1 批：人物（姿势图和高清特写）
run pose_zg_zgu $R $C/zgo_stand.png $C/zgu_stand.png $C/sy2_stand.png &
run pose_sgm2 $R $C/sgm_finger.png &
run pose_crowd $R $C/sy2_stand.png &
run hr_zxz_hkz_dg $R $C/zxz_stand_hi.png $C/hkz_stand.png $C/dg_stand.png &
wait
# 第 2 批
run hr_zmt_wgh $R $C/zmt_stand.png $C/wgh_stand.png &
run hr_sgm $R $C/sgm_finger.png &
run shadow_zxu $R &
run shadow_zgo $R &
run prop_hands $R &
run prop_frogs $R &
wait
# 第 3 批：道具和布景
run prop_gauge_hi $R &
run prop_gauge_kit $R &
run prop_icons $R &
run prop_boat $R &
run teaser_rain $R &
run patches $R &
wait
# 第 4 批：书房、小剧场
run set_study_wall $R &
run set_study_items $R &
run set_theater $R &
run set_audience $R ../codex_ep01/ref_v2_douzi.png &
wait
for n in pose_zg_zgu pose_sgm2 pose_crowd hr_zxz_hkz_dg hr_zmt_wgh hr_sgm shadow_zxu shadow_zgo prop_hands prop_frogs prop_gauge_hi prop_gauge_kit prop_icons prop_boat teaser_rain patches set_study_wall set_study_items set_theater set_audience; do
  [ -s "$n.png" ] && echo "OK   $n" || echo "缺   $n"
done
