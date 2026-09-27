# PROGRESS — 当前进度

> 最后更新：2026-09-27 00:30（检查点）

## 当前阶段
端到端流水线已跑通，**等 Chris 同意后用「仅自己可见」试发第一篇**。
赛道：温哥华美食推荐。账号：rednote 海外新号「小红薯6AB9FF32」（0 笔记）。
长期目标：Claude + Jev 的自媒体爆文辅助网页工具（小红书 → IG / TikTok）。

## 怎么跑（新会话先看这里）
1. 启动小红书 MCP：`C:\Users\Chris\xhs\bin\start-mcp-rednote.cmd`（端口 18060；这是改装版，支持 rednote）
2. 生成一篇（约 4–7 分钟）：
   `.venv/Scripts/python scripts/make_post.py --query "<英文店名 城市>" --name "<写进笔记的店名>" --xhs-keyword "<中文店名>" [--my-notes "..."] [--no-reddit]`
   → 草稿包在 `data/posts/<时间>_<店>/`（package.json + card_*.png）
3. 预览 / 发布：`.venv/Scripts/python scripts/publish.py <草稿包> [--yes] [--public]`（默认仅自己可见；不加 --yes 只预览）
4. 数据：`scripts/collect_xhs.py`（采集赛道笔记）、`scripts/track.py`（第 1/3/7 天追踪）、`scripts/phase1_eval.py`（Jev 标题预测验证）
- 需要：环境变量 `TYPESAFE_API_KEY`（Jev）；`claude` CLI 已登录（写稿，Opus 5.5）；Codex CLI 已登录（Reddit）；Google 专用 Chrome 配置已登录小号（`scripts/open_google_profile.cmd`）
- Git Bash 里 export key：`export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`

## 已完成
- [x] 记忆系统、产品方向、执行计划；切换到本地会话
- [x] 决策：赛道、发布闸门、MCP 自动发布（Chris 接受风险）、互动由 Chris 手动完成、Google 抓取、Reddit 走 Codex（见 DECISIONS）
- [x] 小红书 MCP 改装支持 rednote（v2.5.5 + PR #798，本地编译）；Codex CLI、claude CLI（2.1.283）已登录
- [x] 外部调研 `docs/research/爆文逻辑-外部资料.md`；养号流程 `docs/新号养号流程.md`
- [x] 阶段 1 初步结果 `docs/research/阶段1-初步结果.md`：「最新」子集 Jev 标题 Spearman ≈ +0.28（n=75，不足以下结论）
- [x] 数据：179 篇赛道笔记（60 篇有详情和发布时间），SQLite `data/jevdev.db`
- [x] 流水线 `scripts/make_post.py`：Google（50 条）+ 小红书（笔记 + 评论）+ Reddit（Codex）→ Jev 逐条判断 → 画像（`jevdev/restaurant.py`）→ Claude 写 4 篇（`prompts/xhs_writer.md`）→ 逐句核查（`rubrics/claim_check_v1.json`）+ 禁用词 → Claude 只改问题句 → Jev 闸门和质量（`rubrics/draft_v1.json`）+ 标题预测 → 80/20 选稿 → 渲染卡片（自动适配）
- [x] 第一篇：明家烧腊《明家烧腊4.3分，名气和味道对得上吗》→ `data/posts/20260927-0028_HK-BBQ-Master-Richmond-BC`（4/4 过审）

## 下一步
- [ ] 【等 Chris】仅自己可见试发 → 检查图片、话题、AI 标注（MCP 可能勾不了「AI 生成」声明，靠正文末行标注）
- [ ] 发布后拿到自己笔记的 note_id，写入 notes（is_ours=1），接上 track.py
- [ ] 选店候选池（每天 1–2 家；来源：赛道笔记里出现的店 + Chris 推荐）
- [ ] 定时任务（Windows 任务计划程序）：MCP 常驻 + 每日 make_post / track / collect（改系统配置前先问 Chris）
- [ ] 阶段 1 扩样本：同龄追踪积累「第 7 天互动」→ 重新验证标题预测
- [ ] 封面看图：用 Claude / Codex 把封面转成文字描述 → Jev 封面题（8.2 节）

## 阻塞 / 待 Chris 处理
- [ ] 同意试发（仅自己可见）
- [ ] 改掉已出现在聊天里的凭据：TypeSafe key（控制台作废重建）、Google 小号密码
- [ ] 可选：在手机上手动互动，每天在 `data/养号日志.csv` 记一行

## 已知问题
- MCP 的 search_feeds 偶尔超时（context deadline exceeded）→ make_post 会重试一次，再失败就改用缓存
- 小红书采集的「最新」排序偶尔超时；collect_xhs 失败的组合下次自动补
- 选稿用的标题预测模型只基于 177 篇（信号弱），目前权重只占 0.1
