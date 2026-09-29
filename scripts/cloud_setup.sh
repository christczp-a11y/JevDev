#!/usr/bin/env bash
# 装机检查（本地 Git Bash 和云端都能跑，可以重复运行）：bash scripts/cloud_setup.sh
# 动态漫画技术栈（2026-09-29）：不需要浏览器和显卡；要 Python、ffmpeg、字体、背景音乐、Jev key、Codex 登录。
set -uo pipefail
cd "$(dirname "$0")/.."
ok=1

# 1. ffmpeg（云端用 apt 装；本地用 winget 装的 Gyan.FFmpeg，要在 PATH 里）
if ! command -v ffmpeg >/dev/null; then
  if command -v apt-get >/dev/null; then
    apt-get install -y -q ffmpeg >/dev/null 2>&1 || { apt-get update -q >/dev/null && apt-get install -y -q ffmpeg >/dev/null; }
  fi
fi

# 2. Python 虚拟环境和依赖
if [ -x .venv/Scripts/python ]; then PY=.venv/Scripts/python
else
  [ -x .venv/bin/python ] || uv venv -q -p python3.12 .venv
  PY=.venv/bin/python
fi
"$PY" -m pip install -q -r requirements.txt 2>/dev/null || VIRTUAL_ENV=.venv uv pip install -q -r requirements.txt

# 3. 自检
"$PY" -c "import typesafe_sdk, numpy, scipy, PIL, cv2, edge_tts, fontTools" && echo "python 依赖 ok" || { echo "!! python 依赖不全"; ok=0; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && echo "ffmpeg ok" || { echo "!! ffmpeg / ffprobe 不在 PATH"; ok=0; }
for f in video/vendor/fonts/NotoSansSC-Bold.ttf video/vendor/fonts/ZCOOLKuaiLe-Regular.ttf video/assets/audio/bgm_main.mp3; do
  [ -f "$f" ] && echo "$f ok" || { echo "!! 缺 $f"; ok=0; }
done
if [ -z "${TYPESAFE_API_KEY:-}" ] && command -v powershell >/dev/null; then
  TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r'); export TYPESAFE_API_KEY
fi
[ -n "${TYPESAFE_API_KEY:-}" ] && echo "TYPESAFE_API_KEY ok" || { echo "!! TYPESAFE_API_KEY 未设置"; ok=0; }
curl -sS -o /dev/null -m 10 https://api.typesafe.ai 2>/dev/null && echo "api.typesafe.ai 可达" || { echo "!! api.typesafe.ai 连不上"; ok=0; }
command -v codex >/dev/null && codex login status 2>&1 | grep -q "Logged in" && echo "Codex 已登录" || echo "!! Codex 没登录（第 5 步画素材要用；云端用 codex login --device-auth）"
[ $ok = 1 ] && echo "装机检查：全部通过" || echo "装机检查：有问题，见上面的 !!"
exit $((1 - ok))
