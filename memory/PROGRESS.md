# PROGRESS — 当前进度

> 最后更新：2026-09-30 晚（本地）

## 当前阶段：tj01 做完（第 3 版），Chris 准备 10-01 早上发小红书
- 发布用 `video/out/tj01/full/三家分晋_第一集_v2_高清.mp4`（Chris 选的第 2 版）；`tj01_full.mp4` 和 `三家分晋_第一集_v3_高清.mp4` 是第 3 版（多修了 0:05 学霸泡泡停留，PITFALLS M9）。
- **文案、标题、封面字由 Chris 的另一个会话做**；这个仓库的会话只做动画（第 9 步的发布材料不归这边）。
- 复盘：`video/stories/tj01/复盘.md`（这一集踩过的坑 + 下一集照着做的 6 条）。
- 引擎现状：截段拼接（改 1 镜约 30–60 秒）、字幕底边 y 1615、出片空白检测；storyboard_check 查字幕区挡脸、特效盖主角、交领不许 flip；出图规矩 `video/assets/prompt_rules.txt` 自动接。
- **下一步**：等 Chris 定第 2 集（下集预告是魏文侯雨天打猎之约）；他可能先给剧本。
- 待补：PITFALLS 待补 14（storyboard_jev 看不到泡泡里的画）、15（去掉镜头运动后的静止检查）、16（讲事画面停留 ≥ 2 秒）；`video/tests/registry/` 4 项旧失败；字幕挪进平台遮挡区的事 Chris 说先不做。

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
