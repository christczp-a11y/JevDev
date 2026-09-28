#!/usr/bin/env bash
# 对比实验：用 MoneyPrinterTurbo 的 skill（docs/skill/SKILL.md）把 demo 的同一个故事重做一遍，
# 看「有 skill」和「没 skill（我们自己的纸偶流水线）」的区别。Chris 2026-09-28 的要求：不是在原版上优化，是重做。
#
# 用法（在仓库根目录）：bash experiments/mpt/run.sh
# 需要：网络放行 speech.platform.bing.com（MPT 默认的 Edge TTS 配音）；claude 命令行已登录（MPT 用 claude_code 写文案）
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD
MPT=$HOME/MoneyPrinterTurbo
SKILL_DIR=$REPO/experiments/mpt/skill
MAT=$MPT/storage/local_videos/xumu

# 1. 素材：demo 同一套动画（video/scenes/mpt_source_youth.json = test_puppet_youth 去掉测试标题、页脚、烧进画面的字幕，
#    标题换成已确认的「一根木头，怎么让秦国人开始相信？」），按镜头切成 8 段
[ -f video/out/mpt_source_youth.mp4 ] || .venv/bin/python video/render.py video/scenes/mpt_source_youth.json
[ -d "$MPT" ] || git clone -q --depth 1 https://github.com/harry0703/MoneyPrinterTurbo.git "$MPT"   # 官方仓库；GitHub 的 zip 下载被网络策略拦截，改用 git
mkdir -p "$MAT"
i=0
for seg in "0.0 2.5" "2.5 6.0" "6.0 8.0" "8.0 9.0" "9.0 12.7" "12.7 14.4" "14.4 17.0" "17.0 19.0"; do
  set -- $seg; i=$((i + 1))
  ffmpeg -loglevel error -y -ss "$1" -to "$2" -i video/out/mpt_source_youth.mp4 -an -c:v libx264 -crf 18 -pix_fmt yuv420p "$MAT/shot$(printf %02d $i).mp4"
done
MATERIALS=$(ls "$MAT"/shot*.mp4 | paste -sd, -)

# 2. skill 的 helper（skill 要求在它所在的目录用相对路径运行）
mkdir -p "$SKILL_DIR"
[ -f "$SKILL_DIR/mpt_agent.py" ] || curl -sSL -o "$SKILL_DIR/mpt_agent.py" https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/docs/skill/mpt_agent.py

# 3. 按 skill 的写法运行：一条前台命令。LLM 用 claude_code（本机已登录的 claude 命令行，不需要 API key）；
#    素材用本地的 8 段镜头，按顺序拼（默认随机会打乱故事顺序）；其余都用 skill 的默认值（中文 9:16、Edge TTS 晓晓、字幕、随机背景音乐）
cd "$SKILL_DIR"
MPT_LLM_PROVIDER=claude_code uv run --no-project --python 3.11 python mpt_agent.py \
  --subject "徙木立信：一根木头，怎么让秦国人开始相信？" -- \
  --video-source local --video-materials "$MATERIALS" --video-concat-mode sequential \
  --video-script-prompt "$(cat "$REPO/experiments/mpt/prompt.txt")"
