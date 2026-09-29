#!/bin/bash
# 一键重跑 video/script_check.py 的测试（工作流第 2 步；PITFALLS P10、S11、S17、S18、S20）。
# 用法（仓库根目录）：bash video/tests/script_check/run_all.sh
# ok*.json 应该退出 0（没有警告）；bad_*.json 应该退出 1 并报出对应原因（个别会连带别的错，这里只认它该报的那一条）；warn_*.json 退出 0、恰好一条警告（单句 > 8 秒、单句 > 15 字、旁白占比 > 一半，各一份）。
# 样例由 gen_samples.py 生成（改了要重新生成）。不要网络、不要 Jev key。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
T=video/tests/script_check
fail=0

t() {  # t 样例 期望退出码 关键输出 [额外参数...]
  local f=$1 want=$2 key=$3; shift 3
  local out; out=$($PY video/script_check.py "$T/$f" "$@" 2>&1); local got=$?
  if [ "$got" = "$want" ] && grep -qF -- "$key" <<<"$out"; then
    echo "PASS  $f $*  退出码 $got  含「$key」"
  else
    echo "FAIL  $f $*  退出码 $got（期望 $want），关键输出「$key」$(grep -qF -- "$key" <<<"$out" && echo 有 || echo 没有)"
    echo "$out" | sed 's/^/      /'
    fail=1
  fi
}

inputs_sum() { md5sum $T/*.json | md5sum | cut -d' ' -f1; }
before=$(inputs_sum)

echo "---- 合格的 ----"
t ok.json                  0 "script_check：通过，0 条警告"
t ok.json                  0 "（剧本估算秒数）"
t ok.json                  0 "考你 4 次，停顿 [1.0, 1.2, 1.2, 1.8]；「看答案！」4 次"
t ok.json                  0 "金句「好心是队长。」3 次"
t ok.json                  0 "大问题先关一半「答案先揭一半」在"
t ok.json                  0 "（真实时间线）" --timeline $T/ok_timeline.json
t ok.json                  0 "script_check：通过" --timeline $T/ok_timeline.json
t ok_prop_introduced.json  0 "script_check：通过"

echo "---- 大问题念完 ≤ 7 秒（S20）----"
t bad_bigq_late.json       1 "大问题在 9.00s 才念完，超过 7 秒（容差 0.3 秒"
t ok.json                  1 "大问题在 7.50s 才念完，超过 7 秒（容差 0.3 秒" --timeline $T/bad_timeline_bigq_timeline.json
t ok.json                  0 "–7.30s" --timeline $T/ok_timeline_edge_timeline.json   # 7.3 秒念完：在容差边上，算过

echo "---- 结构：仪式句、考你、停顿、揭晓 ----"
t bad_ceremony_first.json  1 "第一句不是 司马光「考考你！」"
t bad_xie_embedded.json    1 "「写书的人，来了——」要由旁白单独成句"
t bad_pauses.json          1 "现在是 [1.0, 1.2, 1.2, 2.5]"
t bad_level_no_ask.json    1 "第 2 关（lines[12] 起）要恰好一次考你（F-1），现在 0 次"
t bad_level_two_asks.json  1 "第 2 关（lines[12] 起）要恰好一次考你（F-1），现在 2 次"
t bad_no_level_starts.json 1 "notes.level_starts 要写成三关各自第一句的下标"
t bad_levelstarts_shifted.json 1 "第 1 关的第一句 lines[7] 的画面里没有「关」或「跟头」"

echo "---- 揭晓要念出答案（S18）----"
t bad_reveal_no_answer.json 1 "揭晓后的 1–2 句里没有念出答案「不听」"
t bad_reveal_no_label.json  1 "揭晓的画面里要写出亮起的按钮"
t bad_reveal_open_second.json 1 "揭晓后的 1–2 句里没有念出答案「不给」"

echo "---- 视角人物每一关都在（S17）----"
t bad_pov_missing.json     1 "视角人物「段规」在第 3 关（lines[24]"
t bad_levelstarts_shifted.json 1 "视角人物「段规」在第 1 关（lines[7]"
t bad_no_pov_note.json     1 "notes.pov（视角人物）没写"

echo "---- 笑点间隔、单句太长 ----"
t bad_gag_gap.json         1 "笑点间隔 99.7s"
t warn_long_line.json      0 "⚠ lines[4]（旁白） 单句 9.0s，超过 8 秒"
t warn_long_line.json      0 "script_check：通过，1 条警告"

echo "---- 单句 > 15 字、旁白占比 > 一半（只是警告，退出码 0）----"
t ok.json                  0 "script_check：通过，0 条警告"                 # 旁白 15 句 / 31 句 = 48%，没有超过 15 字的句子
t warn_long_chars.json     0 "⚠ lines[5]（旁白） 单句 16 字，超过 15 字，孩子跟不上，考虑拆成短句"
t warn_long_chars.json     0 "script_check：通过，1 条警告"
t ok_edge_15chars.json     0 "script_check：通过，0 条警告"                 # 正好 15 字（去掉标点）不警告
t warn_narration_heavy.json 0 "⚠ 旁白 18 句 / 共 31 句台词 = 58%，超过一半"
t warn_narration_heavy.json 0 "script_check：通过，1 条警告"

echo "---- 画面备注残留（S11）----"
t bad_version_residual.json 1 "这种某个版本的残留"
t bad_prop_first.json      1 "道具「毛笔」第一次出现就已经拿在手里"

echo "---- 点题要有白话翻译（S18）、第 3 关的终点 ----"
t bad_dian_no_translation.json 1 "点题之后的 1–2 句里没有白话翻译（金句「好心是队长。」）"
t bad_no_dian_line.json    1 "找不到点题那一句（关键词「德者，才之帅也」）"
t ok_dian_key_custom.json  0 "script_check：通过"
t ok_level_end_default.json 0 "script_check：通过"
t bad_level_end_key.json   1 "视角人物「段规」在第 3 关（lines[24]"

echo "---- 从 check_local 带过来的 ----"
t bad_golden_count.json    1 "金句要恰好 3 次、≤ 12 字，现在 2 次"
t bad_male_run.json        1 "男声连着说了 3 句"
t bad_speaker_no_voice.json 1 "说话人 ['魏桓子'] 在 episode.json 的 cast 里没有声音"
t bad_fast.json            1 "语速超过每秒 5 字"
t bad_then.json            1 "台词里有「然后」"
t bad_stake_late.json      1 "赌注（「智家会没」）要在第 20 秒前念完，现在 30.4–"
t bad_stake_end_late.json  1 "赌注（「智家会没」）要在第 20 秒前念完，现在 "
t bad_no_stake_note.json   1 "notes.stake_line（赌注那句里的关键词）没写"
t bad_ending_order.json    1 "结尾顺序不对"
t bad_half_close_pos.json  1 "大问题先关一半在 89% 处，要在 40%–60%"
t bad_banned.json          1 "台词里有禁用词「知伯」"

echo "---- Qwen 的 cast（没有 voice，只有 desc）：同一个声音按 desc 比 ----"
t qwen/ok_qwen.json        0 "script_check：通过，0 条警告"
t qwen/bad_same_desc/bad_same_desc.json 1 "同一个声音 四十多岁的男性贵族，嗓音洪亮，自信傲慢 给了 ['智伯', '赵襄子']"

after=$(inputs_sum)
[ "$before" = "$after" ] || { echo "FAIL  测试改动了样例文件"; fail=1; }
echo
if [ $fail = 0 ]; then echo "run_all.sh：全过"; else echo "run_all.sh：有失败"; fi
exit $fail
