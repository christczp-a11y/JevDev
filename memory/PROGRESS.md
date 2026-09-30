# PROGRESS — 当前进度

> 最后更新：2026-09-29 晚（本地）

## 当前阶段：tj01（三家分晋）第一场样片已发，等 Chris
- 方向：少儿版「古人云」动态漫画（DECISIONS 09-29）。引擎施工 A 合成器、B 特效包（32 特效 + 7 转场）、C 检查工具全部完成，用法见 `video/motion/README.md`。
- **已发 Chris**：特效样片合集（734766f）、第一场样片（975b3dd），都是手机版（≤ 30 MiB）。
- **下一步**：Chris 通过第一场 → 整集：`ep-director` 从第 14 句往后写分镜表（第 4 步）→ 素材清单其余 24 张 + `screen_frame_v2`（4:3 纸屏幕，未拆图登记）用 Codex 画（第 5 步）→ 合成（第 6 步）→ reviewer 查一轮（第 7 步）。Chris 有意见先记 PITFALLS 再改（第 8 步）。
- tj01 现状：台词定稿 `B_段规.json`（73 句台词，旁白 44%，Jev 挑的古今对照 / 考你 / 金句），Qwen 配音 `video/out/tj01_voice_qwen/`（232 秒），素材清单 `video/stories/tj01/素材清单.md`，分镜表 `storyboard.json`（现在只有第一场）。命令见 `video/stories/tj01/status.md`。
- 待补：PITFALLS 待补 14（storyboard_jev 看不到泡泡里的画）、15（去掉镜头运动后的静止检查）；`video/tests/registry/` 4 项旧失败（旧场景目录已删）。

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
