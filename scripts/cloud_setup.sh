#!/usr/bin/env bash
# 云端（Claude Code on the web）装机：可重复运行。用法：bash scripts/cloud_setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. 系统包：ffmpeg（合成视频）、中文字体（Google 字体加载失败时兜底）、certutil（导入代理 CA）
apt-get install -y -q ffmpeg fonts-noto-cjk libnss3-tools >/dev/null 2>&1 \
  || { apt-get update -q >/dev/null && apt-get install -y -q ffmpeg fonts-noto-cjk libnss3-tools >/dev/null; }

# 2. Python：云端默认 3.11，numpy 2.5 需要 >= 3.12
[ -x .venv/bin/python ] || uv venv -q -p python3.12 .venv
VIRTUAL_ENV=.venv uv pip install -q -r requirements.txt

# 3. Chromium：Playwright 自带的下载被网络策略拦截，代码会自动改用 /opt/pw-browsers/chromium（见 video/render.py 的 CHROMIUM）
# 4. 浏览器信任代理 CA：出站 HTTPS 被代理重新签名，不导入的话 Chromium 加载 Google 字体会报 ERR_CERT_AUTHORITY_INVALID
NSSDB="sql:$HOME/.pki/nssdb"
mkdir -p "$HOME/.pki/nssdb"
[ -f "$HOME/.pki/nssdb/cert9.db" ] || certutil -N -d "$NSSDB" --empty-password
tmp=$(mktemp -d)
awk -v d="$tmp" '/BEGIN CERT/{n++} {print > sprintf("%s/c%03d.pem", d, n)}' /root/.ccr/ca-bundle.crt
for f in "$tmp"/c*.pem; do
  subj=$(openssl x509 -in "$f" -noout -subject 2>/dev/null) || continue
  case "$subj" in *Anthropic*) certutil -A -d "$NSSDB" -t "C,," -n "ccr-$(basename "$f" .pem)" -i "$f" ;; esac
done
rm -rf "$tmp"

# 5. 自检
.venv/bin/python -c "import typesafe_sdk, playwright, numpy, PIL" && echo "python ok"
command -v ffmpeg >/dev/null && echo "ffmpeg ok"
[ -n "${TYPESAFE_API_KEY:-}" ] && echo "TYPESAFE_API_KEY ok" || echo "!! TYPESAFE_API_KEY 未设置（环境设置 → 环境变量）"
curl -sS -o /dev/null -m 10 https://api.typesafe.ai 2>/dev/null && echo "api.typesafe.ai 可达" || echo "!! api.typesafe.ai 被拦截（环境设置 → 网络放行）"
