# PROGRESS — 当前进度

> 最后更新：2026-09-29 晚（本地）

## 当前阶段：tj01 G 版整集已发 Chris，等他看（09-30 晚）
- 剧本 `G_尊重.json`（Chris 定的新剧本），配音 `video/out/tj01_voice_g/`（206.1 秒），分镜表 80 镜，成片 `video/out/tj01/full/tj01_full.mp4`；手机版切上下两段发出（c68f3ed）。命令见 `video/stories/tj01/status.md`。
- 这一轮定下的规矩：出图规矩自动接 `video/assets/prompt_rules.txt`（P16）；成片检查限时 30 分钟（P17）；看图 / 逐帧检查用 Sonnet 5.5 xhigh（P18）；script_check 按 episode.json 的 `structure` 查。
- **下一步**：等 Chris 看整集。他有意见：先记 PITFALLS，再按第 8 步改；通过了就做第 9 步（Jev 挑标题、封面字，出发布包）。
- 待补：PITFALLS 待补 14、15；`video/tests/registry/` 4 项旧失败；旧的非名牌 `zb_*` 智伯图和 B 版剧本 / 配音不再用。

## 装机（09-29 检查通过）
- `bash scripts/cloud_setup.sh` 全部通过：Python 依赖（含 OpenCV 5.0）、ffmpeg、字体（`video/vendor/fonts/` 全量 Noto Sans SC Bold + ZCOOL KuaiLe）、背景音乐 `video/assets/audio/bgm_main.mp3`、Jev key 和连通（实测调用成功）、Codex 已登录。
- Jev：插件 `typesafe@typesafe-ai` 在 `.claude/settings.json` 启用；仓库约定在 `.claude/skills/jev-decisions/SKILL.md`。
- 素材引擎：Codex `gpt-6.1-sol` high（CLI 0.159.0），统一脚本 `video/codex_gen.sh`；系列贴纸已画好 `video/assets/codex_series/stickers_v1.png`。
- 配音：Qwen3-TTS，独立环境 `.venv-tts`（本地显卡），`video/voice.py` 调用。
- tj01 已有的 Codex 素材全部进了 git（09-29，266 个文件）。

## 阻塞 / 待 Chris 处理
- 改掉已经出现在聊天里的凭据：TypeSafe key、Google 小号密码。

## 怎么跑（Git Bash）
`export PYTHONIOENCODING=utf-8; export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`；Python 用 `.venv/Scripts/python`。
