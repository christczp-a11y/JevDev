#!/usr/bin/env bash
# 用 Codex（Chris 的 ChatGPT 会员，gpt-6-astra + low）画一张素材表：gen.sh <名字> <参考图...>
cd "$(dirname "$0")"
n=$1; shift
args=(); for r in "$@"; do args+=(-i "$r"); done
rm -f "$n.png"
codex exec --skip-git-repo-check -s workspace-write -m gpt-6-astra -c 'model_reasoning_effort="low"' "${args[@]}" - < "$n.txt" > "codex_$n.log" 2>&1
[ -s "$n.png" ] && echo "OK $n" || echo "FAIL $n"
