#!/usr/bin/env bash
# Codex 额度 17:01 恢复：等到 17:02 再画 bubble_nickname2（大个子表情改成大大咧咧、不凶）。已有图就不画。
cd "$(dirname "$0")/../../.."
export PYTHONIOENCODING=utf-8
while [ "$(date +%H%M)" -lt 1702 ]; do sleep 60; done
[ -s video/assets/codex_tj01/bubble_nickname2.png ] && { echo "已有"; exit 0; }
bash video/codex_gen.sh video/assets/codex_tj01 bubble_nickname2 ../ref/paper_style_ref.png
