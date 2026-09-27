# CONTEXT — 环境与约束

## 仓库
- GitHub：`christczp-a11y/JevDev`
- 开发分支：`claude/loving-cerf-f4z5v5`
- 运行环境：Claude Code 云容器（临时，回收即丢失未推送内容）

## 能力边界
- 云端可用：无头 Chromium + Playwright 1.56.1（无用户登录态；受网络策略限制）
- 不能操作 Chris 本地电脑；需要本地操作时用 Claude Desktop 或本地 `claude remote-control`
- 已连接服务：Gmail、Google Calendar、Google Drive、Figma、GitHub
- 未授权服务：Canva、Cloudflare_Developer_Platform、HyperFrames_by_HeyGen

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
