#!/usr/bin/env bash
# 一键重跑 voice.py / audio.py 的测试（工作流第 0 步第 5、6 项；PITFALLS P10）。
#   在仓库根目录跑：bash video/tests/voice/run_all.sh
#   不要网络：ONLINE=0 bash video/tests/voice/run_all.sh（跳过 test_online.py：它真的调用 Edge TTS，重配试做集 N6 做回归）
#   只跑一个：bash video/tests/voice/run_all.sh test_text
# 其余测试用假合成（ffmpeg 生成的正弦 mp3，见 fake_run.py），不要网络、不要 Jev key。输出写到 video/out/voice_test/run_all/，退出码 0 = 全过。
set -u
cd "$(dirname "$0")/../../.."
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
mods=("$@")
[ ${#mods[@]} -eq 0 ] && mods=(test_cast test_cache test_text test_ceremony test_audio test_lint test_online)
cd video/tests/voice
"../../../$PY" -m unittest -v "${mods[@]}"
rc=$?
echo
if [ $rc -eq 0 ]; then echo "run_all.sh：全过"; else echo "run_all.sh：有失败（退出码 $rc）"; fi
exit $rc
