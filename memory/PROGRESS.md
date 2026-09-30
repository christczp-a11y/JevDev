# PROGRESS — 当前进度

> 最后更新：2026-09-29 晚（本地）

## 当前阶段：tj01 按 Chris 定的新剧本重做整集（09-30）
- 剧本：`video/stories/tj01/Chris定稿_Gemini版.md` 最后一版 + 主会话 9 处红线改法（Chris 否了 4 条，PITFALLS S26）；决定见 DECISIONS 09-30。旧剧本 `B_段规.json` 和旧分镜表停用（第一场样片 Chris 说动效画面可以，故事要换）。
- **进行中**：director 写 `G_尊重.json`（第 2 步）；builder 改 script_check 读 episode.json 的 `structure`；builder 画智伯（名牌）、赵襄子（眼镜）定妆图。
- **然后**：Qwen 配音（第 3 步）→ director 写整集分镜表（第 4 步，复用引擎和素材）→ 按素材清单画缺的图（第 5 步，智伯和赵襄子用到的姿势照定妆图重画）→ 合成（第 6 步）→ reviewer 一轮（第 7 步）→ 发 Chris 整集（手机版 ≤ 30 MiB）。
- 待补：PITFALLS 待补 14、15；`video/tests/registry/` 4 项旧失败。

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
