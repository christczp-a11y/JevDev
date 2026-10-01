# PROGRESS — 当前进度

> 最后更新：2026-09-30 晚（本地）

## 当前阶段：tj01 第 9 步发布包已出（09-30），等 Chris 定时发布
- 发布包 `video/stories/tj01/publish.md`：标题「要地给不给？2400年前的一道选择题」、封面字「本事满分 尊重0分」（Jev 组合胜率 0.889）、正文、话题、置顶评论、发布设置、72 小时复盘和前 2 周冷启动；封面 `video/out/tj01/publish/cover_3x4.png`（脚本 `video/stories/tj01/make_cover.py`）。
- 建议北京时间 10/2（周五）20:00 定时发；发后 2 小时、24 小时、72 小时、7 天的数据记进 `status.md`。
- xiaohongshu-mcp（localhost:18060）这次没连上，对标账号数据没抓；新号冷启动期也不建议用自动化工具登录这个号。

## 上一阶段：tj01 G 版第 2 版已发 Chris，等他看（09-30）
- Chris 看第 1 版给了合格分，提了 7 条（PITFALLS S28、S29、M6–M8、P19）→ 第 2 版已改并发出（b21e28d，手机版上下两段）。
- 成片 `video/out/tj01/full/tj01_full.mp4`（208.0 秒）；剧本 `G_尊重.json`；配音 `video/out/tj01_voice_g/`；分镜表 81 镜。命令见 `video/stories/tj01/status.md`。
- 引擎新能力：截段拼接（改 1 镜约 30 秒）、字幕底边贴 y 1615、出片空白检测；storyboard_check 查字幕区挡脸和特效盖住主角。
- **下一步**：等 Chris。有意见：先记 PITFALLS，截段改；通过了就做第 9 步（Jev 挑标题、封面字，出发布包）。
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
