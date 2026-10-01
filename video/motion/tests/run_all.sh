#!/usr/bin/env bash
# 动态漫画合成器（video/motion/）的测试。用法（仓库根目录或任何地方）：bash video/motion/tests/run_all.sh
#   只跑一个：bash video/motion/tests/run_all.sh test_units
#   加慢测试（把小样重复成约 3 分钟整集，测整集高清速度，要 5–10 分钟）：SLOW=1 bash video/motion/tests/run_all.sh
# 不要显卡、不要网络；Jev key 只有 test_storyboard_jev 的真跑用（没有就跳过）；输出写到 video/out/tests/motion/（不进 git）。退出码 0 = 全过。
#   test_units        锚点、字幕分页、自动检查（闪烁 / 静止 / 响度 / 人声）、混音、特效登记
#   test_plan_errors  故意写坏的分镜表都要报错（素材、字体、背景音乐、锚点、拼错字段……），所有错一次列完
#   test_render       端到端：可复现（验收 ①）、字幕时间和位置（②、M6）、截段拼接逐帧对比整片一次编码、改一个镜头只重编码相关片段、--shots 裁剪、预览速度（④）、退出码
#   test_blank        空白检测（M7）：合成图正反例、漏图层的分镜表退出码 1 并报镜头号 / 秒数 / 位置、有 tj01 成片时对 0:28 / 1:50 / 2:17；局部直边平条（待补 19）：合成图正反例、tj02 s68 的真实帧（strip_case/）、改前 / 改后的分层端到端、blank_scan.py
#   test_fx           特效包：每个特效和转场登记了、音效文件干净、每个特效一个渲染冒烟测试、转场、样片合集（预览分辨率端到端）
#   test_long         （SLOW=1）3 分钟整集高清速度（④）、整集渲完改 1–2 个镜头 ≤ 2 分钟（普通和 --final）
#   test_storyboard_check  storyboard_check.py：good_storyboard.json 通过，每个 bad_*.json 报出该报的错（check_expect.json），输入 / 环境坏了退出码 2
#   test_storyboard_jev    storyboard_jev.py 的离线部分（没有 key 立刻报错、假 Jev 的阈值 / 对照 / 缓存 / 退出码）；有 TYPESAFE_API_KEY 才再真跑一次（结果按哈希缓存，第一次约 16 次请求）
set -u
cd "$(dirname "$0")/../../.."
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
mods=("$@")
[ ${#mods[@]} -eq 0 ] && mods=(test_units test_plan_errors test_render test_blank test_fx test_long test_storyboard_check test_storyboard_jev)
"$PY" video/motion/tests/proto17/make_assets.py > /dev/null || exit 2      # proto17 的卡片和音效（不进 git，每次重新生成）
cd video/motion/tests
"../../../$PY" -m unittest -v "${mods[@]}"
rc=$?
echo
if [ $rc -eq 0 ]; then echo "motion/tests/run_all.sh：全过"; else echo "motion/tests/run_all.sh：有失败（退出码 $rc）"; fi
exit $rc
