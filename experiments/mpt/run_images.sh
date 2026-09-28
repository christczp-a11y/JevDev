#!/usr/bin/env bash
# 对比实验（第二次，按 Chris 的原意）：用我们已经生成的「图片素材」交给 MoneyPrinterTurbo 的 skill，从头生成徙木立信的视频。
# 第一次（run.sh）把我们渲染好的动画切段喂给它，等于只给原版配了音，对比无效。
# 用法（在仓库根目录）：bash experiments/mpt/run_images.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD
MPT=$HOME/MoneyPrinterTurbo
SKILL_DIR=$REPO/experiments/mpt/skill
MAT=$MPT/storage/local_videos/xumu_images

[ -d "$MPT" ] || git clone -q --depth 1 https://github.com/harry0703/MoneyPrinterTurbo.git "$MPT"   # 官方仓库；GitHub 的 zip 下载被网络策略拦截
.venv/bin/python experiments/mpt/prepare_images.py "$MAT"   # 15 张图：只放大、垫米色底（MPT 会丢掉短边 < 480 的图）
MATERIALS=$(ls "$MAT"/*.png | paste -sd, -)
mkdir -p "$SKILL_DIR"
[ -f "$SKILL_DIR/mpt_agent.py" ] || curl -sSL -o "$SKILL_DIR/mpt_agent.py" https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/docs/skill/mpt_agent.py

# 按 skill 的写法运行。只改了三个默认值：本地素材；按顺序拼（默认随机会打乱故事）；每张图最长 2 秒（默认 5 秒，30 秒旁白只放得下前 6 张）
[ -n "${HTTPS_PROXY:-}" ] && export WSS_PROXY="${WSS_PROXY:-$HTTPS_PROXY}"   # Edge TTS 走 wss://，aiohttp 只从 WSS_PROXY 读代理
cd "$SKILL_DIR"
MPT_LLM_PROVIDER=claude_code uv run --no-project --python 3.11 python mpt_agent.py \
  --subject "徙木立信：一根木头，怎么让秦国人开始相信？" -- \
  --video-source local --video-materials "$MATERIALS" --video-concat-mode sequential --video-clip-duration 2 \
  --video-script-prompt "$(cat "$REPO/experiments/mpt/prompt_images.txt")"
