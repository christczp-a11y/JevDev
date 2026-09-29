#!/usr/bin/env bash
# 一键重跑 voice.py / audio.py 的测试（工作流第 0 步第 5、6 项；PITFALLS P10）。
#   在仓库根目录跑：bash video/tests/voice/run_all.sh
#   不要显卡：GPU=0 bash video/tests/voice/run_all.sh（跳过 test_gpu.py：它真的调用 Qwen3-TTS worker，要 .venv-tts、显卡、模型，约 3–4 分钟）
#   只跑一个：bash video/tests/voice/run_all.sh test_text
# 其余测试用假 worker（fake_run.py 里生成正弦波 wav，不要显卡、不要网络、不要 Jev key）。输出写到 video/out/voice_test/run_all/，退出码 0 = 全过。
set -u
cd "$(dirname "$0")/../../.."
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
mods=("$@")
[ ${#mods[@]} -eq 0 ] && mods=(test_cast test_cache test_text test_ceremony test_trim test_audio test_lint test_gpu)
cd video/tests/voice
"../../../$PY" -m unittest -v "${mods[@]}"
rc=$?
echo
if [ $rc -eq 0 ]; then echo "run_all.sh：全过"; else echo "run_all.sh：有失败（退出码 $rc）"; fi
exit $rc
