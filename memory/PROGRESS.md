# PROGRESS — 当前进度

> 最后更新：2026-09-29（本地）

## 当前阶段：施工「动态漫画引擎」，然后做 tj01（三家分晋）
- 方向：少儿版「古人云」动态漫画（DECISIONS 09-29 最后一条）。three.js 已停用、已删除。
- **下一步**：按 `docs/施工计划-动态漫画引擎.md`：
  1. A 合成器核心（`ep-builder`）；
  2. B 特效包 + C 检查工具（两个 `ep-builder`，同时做）；B 的特效样片合集发给 Chris 看；
  3. D 之前：`ep-director` 先按新的台词风格改一遍 tj01 的台词（见 `video/stories/tj01/要点.md`），再复核素材。
  4. D：tj01 第一场。`ep-director` 写分镜表，走第 4–7 步，出第一场样片给 Chris。
- tj01 已有、继续有效：史料 `source.md`、定稿剧本 `B_段规.json`、配音 `video/out/tj01_voice/`、人物和场景素材。见 `video/stories/tj01/status.md`。
- 参考：17 秒动态漫画小样的原型 `video/motion/_prototype_mc.py`。

## 装机（09-29 检查通过）
- `bash scripts/cloud_setup.sh` 全部通过：Python 依赖（含 OpenCV 5.0）、ffmpeg、字体（`video/vendor/fonts/` 全量 Noto Sans SC Bold + ZCOOL KuaiLe）、背景音乐 `video/assets/audio/bgm_main.mp3`、Jev key 和连通（实测调用成功）、Codex 已登录。
- Jev：插件 `typesafe@typesafe-ai` 在 `.claude/settings.json` 启用；仓库约定在 `.claude/skills/jev-decisions/SKILL.md`。
- tj01 已有的 Codex 素材全部进了 git（09-29，266 个文件）。

## 阻塞 / 待 Chris 处理
- 配音授权（Edge TTS 能不能商用）还没确认，第一集公开前要定。
- 改掉已经出现在聊天里的凭据：TypeSafe key、Google 小号密码。

## 怎么跑（Git Bash）
`export PYTHONIOENCODING=utf-8; export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`；Python 用 `.venv/Scripts/python`。
