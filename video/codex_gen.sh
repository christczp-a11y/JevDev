#!/usr/bin/env bash
# 系列统一的 Codex 画图脚本（素材引擎：gpt-6.1-sol，reasoning high，Chris 2026-09-29 定）
# 用法：bash video/codex_gen.sh <目录> <名字> [参考图...]
#   在 <目录> 里读 <名字>.txt（提示词），写 <名字>.png；日志写 codex_<名字>.log。
#   每张图的提示词后面自动接上系列统一的出图规矩 video/assets/prompt_rules.txt（手脚数、场面逻辑、假字、交领右衽；PITFALLS R13、P16），不用在每个 .txt 里重写。
#   本地保存失败（could not save）时，按日志里的 session id 到 ~/.codex/generated_images/<id>/ 取最后一张（PITFALLS E4）。并行跑多张也不会拿错。
set -u
RULES="$(cd "$(dirname "$0")" && pwd)/assets/prompt_rules.txt"
[ -s "$RULES" ] || { echo "FAIL 找不到出图规矩 $RULES"; exit 1; }
dir=$1; n=$2; shift 2
cd "$dir" || { echo "FAIL $n（目录不存在：$dir）"; exit 1; }
args=(); for r in "$@"; do args+=(-i "$r"); done
rm -f "$n.png"
codex exec --skip-git-repo-check -s workspace-write -m gpt-6.1-sol -c 'model_reasoning_effort="high"' "${args[@]}" - < <(cat "$n.txt" "$RULES") > "codex_$n.log" 2>&1
if [ ! -s "$n.png" ]; then
  sid=$(grep -m1 '^session id:' "codex_$n.log" | awk '{print $3}')
  p=$(ls -t "$HOME/.codex/generated_images/$sid"/*.png 2>/dev/null | head -1)
  [ -n "$p" ] && cp "$p" "$n.png" && echo "(E4: 从 $sid 取图)"
fi
[ -s "$n.png" ] && echo "OK $n" || { echo "FAIL $n（看 $dir/codex_$n.log）"; exit 1; }
