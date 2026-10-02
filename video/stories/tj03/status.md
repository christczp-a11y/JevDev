# tj03 在德不在险：进度

> 主会话维护。流程见 `docs/自动化工作流-每集生成.md`；照 tj01、tj02 复盘「下一集照着做」执行（`memory/PROGRESS.md` 有派活顺序）。只做动画，不做文案。
> 最后更新：2026-10-02

## 当前：红线改法 Chris 同意（第 2 条「常胜将军吴起」，第 6 条可以说「黄河」）；同时做：source.md（researcher）、剧本 JSON（director）、新角色定妆（builder + Codex）、新背景音乐（builder + ACE-Step 1.5）

## 每一步的状态
| 步 | 内容 | 状态 | 产出 | 备注 |
|---|---|---|---|---|
| 自检 | 装机检查 | 通过（10-02） | — | `bash scripts/cloud_setup.sh` 全过 |
| 1 | 史料 | Gemini 已出（`geminiscripts/episodes/ep03_在德不在险/source_ep03.md`） | — | 出处写成安王十六年（应为十五年）；「同舟共济」出处写错。我们自己的 source.md 等点头后由 researcher 照通鉴写 |
| 2 | 剧本 | 红线改法清单已发 Chris | `红线改法.md`（史实 7、儿童安全 3、用词 1、素材 3） | |
| 背景音乐 | Chris 10-02：旧 BGM 老旧、第二集开头像电子音乐，要重选 | Chris 同意下载，装模型、出候选中 | — | Qwen3-TTS 只能说话不能作曲；推荐 ACE-Step 1.5（Apache 2.0、可商用、显存 < 4 GB，本机 GTX 1660 Ti 6 GB 能跑） |
