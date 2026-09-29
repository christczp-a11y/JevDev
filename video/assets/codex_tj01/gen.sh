#!/usr/bin/env bash
# tj01 用的 Codex 画图脚本（从 codex_ep01/gen.sh 拷来，加了 E4 取图）：gen.sh <名字> <参考图...>
# 在本目录读 <名字>.txt、写 <名字>.png。本地保存失败（could not save）时，按日志里的 session id，
# 到 ~/.codex/generated_images/<session id>/ 里拿最后生成的一张（PITFALLS E4）；并行跑多张也不会拿错。
cd "$(dirname "$0")"
n=$1; shift
args=(); for r in "$@"; do args+=(-i "$r"); done
rm -f "$n.png"
codex exec --skip-git-repo-check -s workspace-write -m gpt-6-astra -c 'model_reasoning_effort="low"' "${args[@]}" - < "$n.txt" > "codex_$n.log" 2>&1
if [ ! -s "$n.png" ]; then
  sid=$(grep -m1 '^session id:' "codex_$n.log" | awk '{print $3}')
  p=$(ls -t "$HOME/.codex/generated_images/$sid"/*.png 2>/dev/null | head -1)
  [ -n "$p" ] && cp "$p" "$n.png" && echo "(E4: 从 $sid 取图)"
fi
[ -s "$n.png" ] && echo "OK $n" || echo "FAIL $n"
