#!/usr/bin/env bash
# 兼容旧用法：gen.sh <名字> <参考图...>（在本目录）。实际调用系列统一脚本 video/codex_gen.sh（gpt-6.1-sol high）。
here="$(cd "$(dirname "$0")" && pwd)"
n=$1; shift
exec bash "$here/../../codex_gen.sh" "$here" "$n" "$@"
