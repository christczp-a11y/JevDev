# 切换到云端会话（2026-09-27）

## 为什么切换
本地这周的额度快用完了，Chris 要改用云端环境（用之前送的 $250 credit）。

## 步骤
1. 云端打开仓库 `christczp-a11y/JevDev`，分支 `claude/loving-cerf-f4z5v5`（所有进度都已推送）
2. 环境设置：
   - **密钥**：在环境变量里设 `TYPESAFE_API_KEY`（Jev）；不要写进仓库或聊天
   - **网络**：放行 `api.typesafe.ai`（Jev）、`fonts.googleapis.com` 和 `fonts.gstatic.com`（画面字体：Noto Sans SC、站酷快乐体）、`pypi.org`、`playwright.azureedge.net`（下载 Chromium）
3. 装依赖（让会话里的 Claude 跑，可以重复运行）：`bash scripts/cloud_setup.sh`
   - 会建一个 Python 3.12 的 `.venv`（云端默认是 3.11，numpy 2.5 不支持）→ 之后一律用 `.venv/bin/python`
   - Chromium 用容器里预装的 `/opt/pw-browsers/chromium`（Playwright 自己下载的地址被拦截；代码里的 `CHROMIUM` 会自动识别）
   - 会把代理 CA 导入浏览器证书库：不导入的话 Chromium 加载不了 Google 字体，中文会退回成系统字体（数字变成衬线体）
   - 最后的自检会提示 key 或网络还没配好
4. 会话的第一句话：「先读 memory/README.md、memory/PROGRESS.md 和 memory/HANDOFF-CLOUD.md，继续做儿童历史动画」

## 云端能做 / 不能做
| 能做 | 不能做（留到本地） |
|---|---|
| 渲染视频 `video/render.py`、截联系表 `video/contact.py` | **Codex 画素材**（新角色的纸偶部件图都要 Codex，astra low）——云端没有登录 Codex |
| 纸偶动作开发（`video/puppet.js`、`video/engine.html`） | 小红书 MCP（抓数据、发布）——美食赛道已暂停，暂时用不到 |
| Jev 质检：`video/logic_qa.py`、`video/motion_qa.py`、`video/story.py`（需要 `claude` 命令行已登录，云端会话自带） | Google 抓取（专用 Chrome 配置在本地） |
| 剧本、史料核对、配音方案调研 | |

## 注意
- 环境设置（环境变量、网络放行）只对**新开的容器**生效：改完设置后要开一个新会话
- 本地路径已改成兼容两边：`jevdev/writer.py` 的 `CLAUDE_EXE`、`video/render.py` 的 `FFMPEG` 在 Linux 上会自动用 PATH 里的 `claude` / `ffmpeg`
- 云端 shell 是 bash，环境变量直接可用；本地笔记里那些 PowerShell 读 key 的写法不用照搬
- `video/out/`（渲染结果）、`data/`（原始数据）不在仓库里；需要的话在云端重新渲染
- 容器是临时的：**改完就 commit + push**，不然会丢
