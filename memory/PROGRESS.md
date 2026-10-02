# PROGRESS — 当前进度

> 最后更新：2026-10-01 晚（本地）

## 当前阶段：tj02「魏文侯之约」做完（第 4 版，Chris 10-01：「这一版不用改」）
- 发布用 `video/out/tj02/full/tj02_full.mp4`（高清）/ `魏文侯之约_第二集_v4_手机.mp4`；**文案、标题、封面字由 Chris 的另一个会话做**，这边只做动画。
- 复盘：`video/stories/tj02/复盘.md`（踩过的坑 + 下一集照着做的 6 条，接着 tj01 的 6 条）；进度和重跑命令：`video/stories/tj02/status.md`。
- Chris 给下一集的经验（M6 第二次再犯）：对话框经常挡住司马光 → 规则已改（`docs/规则/版式和画风.md` 最后一节：司马光解说镜头人在画面中部、脸 y 700–1250，不放左下角探头）；待补 20 已做（`[字幕]` 按实际卡片 + 标签算，司马光说话脸进去就报错；tj02 定稿的分镜表按新检查会报 17 镜，是有意留的证据，第 4 版不再重渲）。
- 这一集新加的检查：`[停留]`（M10）、`[速度线]`（M2）、按图脸框 `video/assets/faces.json`（M6）、局部直边露缝 `blank_scan.py --bare`（M7）。
- **下一步**：第 3 集。按通鉴顺序是魏武侯浮西河、吴起「在德不在险」（tj02 预告已讲）；Gemini 储备日志写 ep03 是商鞅，等 Chris 的 Gemini 剧本。
- 待补：PITFALLS 待补 14、15；字幕卡检查认不出「手里的道具」（遥控器画在人物图里），要做就在 faces.json 里加道具框；`fx/_paper.py` 的 `FACE_FRAC` 改用 faces.json；`video/tests/registry/` 4 项旧失败（ep01v2 目录早没了）。

## 第 3 集开工照这个顺序（tj02 实测省时的做法）
1. 读 `memory/README.md`、本文件、`video/stories/tj02/复盘.md`（和 tj01 的）、`docs/自动化工作流-每集生成.md`；跑 `bash scripts/cloud_setup.sh`。
2. 第 2 步：主会话自己对照规则 + 维基文库原文列红线改法（`video/stories/<集>/红线改法.md`），发 Chris 等点头。
3. 点头后**同时**派：researcher 写 source.md（主会话存档、跑 source_check）、director 写剧本 JSON、builder 画新角色定妆（Codex）。
4. 剧本 JSON 过闸门 → builder 配音 → director 先交素材清单 + 镜头大纲 → builder 照清单画图 **同时** director 写 storyboard.json → 素材登记后 storyboard_check 0 错、storyboard_jev 0。
5. builder 合成 + 自检（联系表复述、dwell.md）→ reviewer（Sonnet，30 分钟）**同时** director 改自检问题 → 一次截段重出 → 主会话亲眼看原尺寸抽帧 → 手机版发 Chris。

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
