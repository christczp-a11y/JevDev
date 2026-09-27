# PROGRESS — 当前进度

> 最后更新：2026-09-27（本地会话）

## 当前阶段
阶段 0 基建（`PLAN.md`）。赛道：温哥华美食推荐。账号：rednote 海外新号「小红薯6AB9FF32」（0 笔记）。目标：全自动、能自我优化、能自我验证。

## 已完成
- [x] 建立 `memory/` 记忆目录；产品方向和风险分析（`PRODUCT.md`）；执行计划（`PLAN.md`）
- [x] 切换到本地会话（Claude Desktop + Claude in Chrome；本地已装 TypeSafe 插件）
- [x] 定赛道、定发布闸门、接受 Google 抓取风险、Reddit 走 Codex（见 DECISIONS）
- [x] 小红书 MCP 改装为支持 rednote，新号已登录，搜索可用（见 CONTEXT）
- [x] Codex CLI 已装并登录，实测能搜到 Reddit
- [x] TypeSafe key 到手，存为用户环境变量 `TYPESAFE_API_KEY`；Jev 中文评价测试通过（软广识别、口味分档都对）
- [x] 新号养号流程 → `docs/新号养号流程.md`；日志模板 `data/养号日志.csv`
- [x] 定发布方式：MCP 自动发布（Chris 接受风险），互动由 Chris 手动完成（见 DECISIONS）
- [x] 项目骨架：`jevdev/`（xhs、db、jev）、`scripts/collect_xhs.py`、`scripts/phase1_eval.py`、`rubrics/`、`.venv`
- [x] 外部调研 → `docs/research/爆文逻辑-外部资料.md`（32 道 Jev 候选题）
- [x] 阶段 1 初步结果 → `docs/research/阶段1-初步结果.md`：「最新」子集上 Jev 标题 Spearman ≈ +0.28，有信号但样本不足

## 下一步
- [ ] 同龄追踪脚本（「最新」笔记在第 3、7 天再抓一次）+ 扩大样本
- [x] Google 评价抓取（专用 Chrome 配置 + 小号登录）+ 餐厅画像（`jevdev/restaurant.py`、`rubrics/review_v1.json`）
- [x] 端到端流水线 `scripts/make_post.py`：Google + 小红书 → Jev 画像 → Claude（`claude -p`，Opus 5.5）写 4 篇 → 逐句核查 + 禁用词 → Claude 修改 → Jev 审稿闸门和质量 → 选稿 → 渲染卡片（自动适配）；第一篇：明家烧腊，草稿包在 `data/posts/20260926-2354_HK-BBQ-Master-Richmond-BC`
- [ ] 用「仅自己可见」测试发布 `scripts/publish.py <包> --yes`（等 Chris 同意）
- [ ] 定时任务（Windows 任务计划程序）：MCP 常驻 + 每日采集 / 追踪（改系统配置前先问 Chris）

## 阻塞 / 待 Chris 处理
- [ ] Chris 在手机上手动做互动（可选：逛、回评论），每天在 `data/养号日志.csv` 记一行
- [ ] TypeSafe key 已经出现在聊天记录里 → 流程跑稳后在控制台作废，重新生成
- [ ] `.claude/settings.json` 与 `CLAUDE.md` 需 Chris 手动创建，内容见 `log/2026-09-27.md`（可选）
