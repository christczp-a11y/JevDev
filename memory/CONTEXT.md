# CONTEXT — 环境与约束

## 仓库
- GitHub：`christczp-a11y/JevDev`
- 开发分支：`claude/loving-cerf-f4z5v5`
- 运行环境：本地 Windows（Claude Desktop），路径 `C:\Users\Chris\Claude x Jev\JevDev`；云容器会话已弃用

## 本地环境（2026-09-27 切换后实测）
- 网络：`docs.typesafe.ai`、`www.xiaohongshu.com` 均可访问（云端拦截问题不存在）
- Claude in Chrome 已连接（Chris 本机 Chrome，带登录态）
- TypeSafe 插件已装（user scope）

## 外部数据渠道实测（2026-09-27）
- Reddit：本机脚本访问 `search.json` 返回 403；Claude 的 WebSearch 也被 reddit.com 屏蔽；官方 API 现在需要审批（2–4 周）
- Gemini CLI 0.56.0 已安装，但个人账号登录被停用（IneligibleTierError，提示改用 Antigravity）；Antigravity 是桌面 IDE，没找到命令行入口
- Codex CLI 未安装（有 `~/.codex` 目录，可能来自桌面版）
- Chris 只有 ChatGPT / Gemini 会员，没有付费 API key

## 小红书 MCP：改装版支持 rednote 海外号（2026-09-27 跑通）
- 新号是 rednote 海外账号；rednote.com 和 xiaohongshu.com 在网页端是两套独立的登录。官方 MCP（最高 v2.5.5）只支持国内站（相关：issue #838、PR #798）
- 改装版源码：`C:\Users\Chris\xhs\xiaohongshu-mcp-rednote\`，分支 `rednote` = v2.5.5 + PR #798（cherry-pick，解决 3 处冲突），另外把创作者中心和通知页的 URL 改成随站点切换
- 编译：`go build -o ../bin/xiaohongshu-mcp-rednote.exe .`（Go 1.27 在 `C:\Program Files\Go`）
- **启动新号：`xhs\bin\start-mcp-rednote.cmd`**（带 `-site rednote`，端口同样是 18060）；登录工具：`start-login-rednote.cmd`
- cookies：新号 → `bin\cookies-rednote.json`；旧号（国内）→ `bin\cookies.json`（已恢复）
- 实测：`check_login_status` ✅ 已登录（小红薯6AB9FF32）；`search_feeds`「温哥华 餐厅」返回 20 条，带点赞、收藏、评论数
- 还没测：发布功能

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

## TypeSafe key（2026-09-27）
- 已充值 $5，绑卡正常，但 Create key 一直报「Failed to create API key」（填了名字也不行）；控制台 `/keys` 页面有请求返回 503
- 第三方消息：TypeSafe 自 2026-09-22 起暂停新用户注册；备选渠道：OpenRouter、Vercel AI Gateway

## Codex CLI（2026-09-27 实测可用）
- 0.157.1，已用 ChatGPT 账号登录
- 调用方式：`codex --search exec --skip-git-repo-check -s read-only "<prompt>"`
- 实测：能找到 Kirin 相关的 5 个 Reddit 帖子（带链接和日期），每次约消耗 2.8 万 token；帖子正文打不开，只能拿到搜索摘要，是 Codex 转述后的内容（二手信息，需要注意可能失真）
