# CONTEXT — 环境与约束

## 仓库
- GitHub：`christczp-a11y/JevDev`
- 开发分支：`claude/loving-cerf-f4z5v5`
- 运行环境：2026-09-27 起**切回云端会话**（本地这周额度用完，改用云端 credit），交接见 `memory/HANDOFF-CLOUD.md`；本地 Windows 路径 `C:\Users\Chris\Claude x Jev\JevDev`（Codex 画素材、小红书 MCP 只能在本地做）

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

## 云端环境（2026-09-28 实测）
- 网络：Chris 已改成 Full（改完当前会话立即生效）；环境变量（如 TYPESAFE_API_KEY）要开新会话才生效
- 走 wss:// 的 Python 客户端（aiohttp）要设置 WSS_PROXY=$HTTPS_PROXY 才能走代理（例：Edge TTS）
- 装机：`bash scripts/cloud_setup.sh`；Python 一律用 `.venv/bin/python`（3.12）
- 渲染：19 秒测试片段约 100 秒；ffmpeg 6.1（apt 装的）；Chromium 141 用预装的那个
- 网络：pypi、fonts.googleapis.com、fonts.gstatic.com 通；api.typesafe.ai、docs.typesafe.ai、playwright 下载地址被拦（在旧容器里测的，环境设置改完要开新会话才生效）
- Jev 相关（logic_qa / motion_qa / story）需要 `TYPESAFE_API_KEY` 加上 api.typesafe.ai 放行
- Codex：`npm i -g @openai/codex` 可以装（0.157.1）；登录用 `codex login --device-auth`（Chris 在自己的设备上输入验证码）；需要放行 auth.openai.com、chatgpt.com、api.openai.com（可能还有别的域名，遇到 403 再补）；登录状态存在容器的 ~/.codex，容器回收后要重新登录

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

## Codex CLI → Reddit（已接入流水线，默认开启）
- `make_post.py` 的 `reddit_data()` 直接调用 codex.exe（`AppData/Roaming/npm/node_modules/@openai/codex/.../bin/codex.exe`），不走 codex.cmd（cmd 会把引号转义坏）；提示词走 stdin，`--output-schema` 做结构化输出，`-o` 写结果文件
- 实测：HK BBQ Master 用 43 秒拿到 5 个帖子、13 条要点；结果缓存在 reviews 表（source='reddit'），7 天内复用
- 写稿规范：正文里不点名 Reddit、Yelp 等平台，来源统一说「网友评价」；评分写「谷歌评分」

## Codex CLI（2026-09-27 实测可用）
- 0.157.1，已用 ChatGPT 账号登录
- 调用方式：`codex --search exec --skip-git-repo-check -s read-only "<prompt>"`
- 实测：能找到 Kirin 相关的 5 个 Reddit 帖子（带链接和日期），每次约消耗 2.8 万 token；帖子正文打不开，只能拿到搜索摘要，是 Codex 转述后的内容（二手信息，需要注意可能失真）

## Google 评价：不登录拿不到（2026-09-27 实测）
- 未登录的 Google 地图是「limited view」：只有「概览」和「简介」，**没有评价标签页**，只显示星级（如 4.1），连评价数都没有
- 不登录时，Google 搜索页也会直接跳到验证码（/sorry/）→ 不登录这条路彻底走不通
- **现行方案（已跑通）**：专用 Chrome 配置 `C:\Users\Chris\jevdev-browser\google-profile`，由 Chris 手动登录 Google 小号（Claude 不经手密码）；`scripts/google_reviews.py` 用 Playwright 复用这个登录态抓 Google 地图评价（按最新排序，约 50 条）
- 登录态失效时：运行 `scripts/open_google_profile.cmd` 重新登录；这个配置被窗口占用时脚本会报「profile is already in use」
- 实测：HK BBQ Master 抓到 50 条（33 条有正文），没有遇到验证码；Jev 判断 33 条只用了 1.6 秒

## 写稿用的 LLM
- `claude -p`（npm 版 CLI）登录已过期：「OAuth session expired」→ 需要 Chris 在终端运行 `claude` 重新登录一次
- Codex CLI 已登录，可以作为备选

## 视频工具链（儿童历史动画，2026-09-27）
- 渲染：`video/render.py <剧本.json>` → `video/out/<名>.mp4`（Playwright 逐帧截 `video/engine.html` → ffmpeg；18 秒约 40 秒渲完）；`--still <秒>` 出单帧
- 纸偶：`video/puppet.js`（部件和关节在 `video/assets/rig/<角色视角>/rig.json`）；场景在 `video/sets/`，剧本在 `video/scenes/`
- 检查：`video/contact.py`（连续帧联系表，`--follow` 跟人物）；`video/logic_qa.py`（每集必做的合理性复查）；`video/motion_qa.py`（改前 vs 改后动作比较）；`video/story.py`（剧本质检）
- 素材：Codex CLI `codex exec -m gpt-6-astra -c 'model_reasoning_effort="low"' -s workspace-write -C <目录> -i <参考图> -`（只在本地可用）；绿幕素材用 `video/split_sheet.py` 切，透明底用 `video/split_alpha.py` 切
- 依赖：`requirements.txt` + `python -m playwright install chromium` + ffmpeg；字体从 Google Fonts 在线加载
- 手机端（Remote Control）收文件上限 30 MiB；发视频前压成手机版（做法见 docs/workflow/7-成片检查.md「发给 Chris」）。
- 上传到手机（Remote Control）还有 30 秒超时：网慢时 25 MB 也会失败，切成上下两段发（做法见第 7 步）。
