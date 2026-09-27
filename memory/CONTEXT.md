# CONTEXT — 环境与约束

## 仓库
- GitHub：`christczp-a11y/JevDev`
- 开发分支：`claude/loving-cerf-f4z5v5`
- 运行环境：本地 Windows（Claude Desktop），路径 `C:\Users\Chris\Claude x Jev\JevDev`；云容器会话已弃用

## 本地环境（2026-09-27 切换后实测）
- 网络：`docs.typesafe.ai`、`www.xiaohongshu.com` 均可访问（云端拦截问题不存在）
- Claude in Chrome 已连接（Chris 本机 Chrome，带登录态）
- TypeSafe 插件已装（user scope）

## 本地小红书环境（先前会话搭建，2026-08）
- 位置：`C:\Users\Chris\xhs\`；说明见 `~/.claude/projects/C--Users-Chris-xhs/memory/xiaohongshu-mcp-setup.md`
- 服务：HTTP MCP `localhost:18060`（已写入 `~/.claude.json`，名为 `xiaohongshu-mcp`）；**必须用 `bin\start-mcp.cmd` 启动**，未启动时 MCP 显示 ECONNREFUSED
- 命令行调用：`bin\mcp_call.py`、`bin\xhs.py`；数据与盘点报告在 `data\`
- 已登录一个现成真号（14 篇笔记，2025-12 起停更）；cookies 在 `bin\cookies.json`（敏感，不入库）
- 同一账号不能在多个网页端同时登录：MCP 登录期间别在 Chrome 登网页版，否则会被踢下线
- 发帖 / 评论 / 点赞等对外操作，动手前先跟 Chris 确认

## 能力边界（云端会话时期，仅供参考）
- 云端可用：无头 Chromium + Playwright 1.56.1（无用户登录态；受网络策略限制）
- 不能操作 Chris 本地电脑；需要本地操作时用 Claude Desktop 或本地 `claude remote-control`
- 已连接服务：Gmail、Google Calendar、Google Drive、Figma、GitHub
- 未授权服务：Canva、Cloudflare_Developer_Platform、HyperFrames_by_HeyGen
- 网络策略拦截（2026-09-27 实测）：`docs.typesafe.ai`、`www.xiaohongshu.com`；`raw.githubusercontent.com` 可访问

## TypeSafe
- 插件：`typesafe@typesafe-ai`，skill：`typesafe-ai`
- 新会话若未启用，重装：
  ```
  claude plugin marketplace add typesafe-ai/skills
  claude plugin install typesafe@typesafe-ai
  ```
- 文档以在线为准：https://docs.typesafe.ai/llms.txt
- API 密钥只放服务端环境变量，不入库

## 协作约定
- 默认中文；行业术语 / 北美市场可夹英文
- 简洁直接，给真实判断，有依据；不确定就说不确定
