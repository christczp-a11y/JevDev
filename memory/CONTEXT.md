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
- 本机 git 没配身份：提交用 `git -c user.name=Chris -c user.email=christczp@gmail.com commit ...`（和之前的提交一致），不改全局配置。别的会话也会往同一个分支推，push 被拒就先 `git pull --rebase`，不强推。
- 几个子代理同时改工作区时，`git pull --rebase` 会因为别人没提交的改动失败：先 `git push`（远端没新提交就直接成功），被拒再 `git pull --rebase --autostash`。只 `git add` 自己这一步的文件，别 `git add -A`。
- 子代理的报告只在它交回的那条消息里，`tasks/<id>.output` 读出来是空的：长报告（例如 researcher 的 source.md 全文）要主会话自己用 Write 落盘。
- 改 `video/motion/engine/` 或 `fx/` 的源码会让合成器的镜头缓存全部失效（整集重渲约 6 分钟）；检查尽量写在 storyboard_check / blank_scan 里，要改引擎就挑渲染空闲的时候。

## 背景音乐：ACE-Step 1.5（2026-10-02 装，tj03 起用；PITFALLS A8，Chris 同意下载）
- **来源（确认过是官方）**：代码 `https://github.com/ACE-Step/ACE-Step-1.5`（GitHub 组织 `ace-step`，commit `ca1e85f`，2026-08-29）；权重 Hugging Face `ACE-Step/Ace-Step1.5`（官方主模型库，卡片和仓库的许可证都是 **MIT**，可商用；派活单写的 Apache 2.0 不对，但同样可商用）。
- **装了什么**：DiT `acestep-v15-turbo`（2B，8 步，4.79 GB）+ `vae`（0.34 GB）+ `Qwen3-Embedding-0.6B`（文本编码器，1.19 GB）= 权重 **6.3 GB**。**没装** 5Hz LM（`acestep-5Hz-lm-1.7B` 3.7 GB：6 GB 显存放不下，官方对 ≤ 6 GB 的卡也是「只用 DiT、不用 LM」）。
- **位置（都在 `video/out/` 或 `.venv-music/` 下，不进 git）**：代码 `video/out/acestep/ACE-Step-1.5/`；权重 `video/out/acestep/ACE-Step-1.5/checkpoints/`；环境 `.venv-music/`（Python 3.12.14，4.5 GB，`.gitignore` 已忽略）。`video/out/` 被清掉就要照下面重装。
- **怎么装（Windows，Git Bash，仓库根目录）**：
  1. 临时环境里装 uv（只用来装依赖）：`<python3.12> -m venv $TMP/uvtool && $TMP/uvtool/Scripts/python -m pip install uv`
  2. `git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git video/out/acestep/ACE-Step-1.5`
  3. `cd` 进去：`UV_PROJECT_ENVIRONMENT=<仓库根>/.venv-music UV_PYTHON=<3.12 的 python.exe> UV_PYTHON_DOWNLOADS=never $TMP/uvtool/Scripts/uv.exe sync --frozen --no-install-package torch --no-install-package torchaudio --no-install-package torchvision`（官方锁定的 torch 是 2.7.1+cu128，3 GB；本机 10-02 网速只有约 1 MB/s，所以不下，改成第 4 步）
  4. torch 从 `.venv-tts` **复制**（只读它，不改它）：把 `.venv-tts/Lib/site-packages/` 里的 `torch`、`torchaudio`、`functorch`、`torchgen` 和 `torch-2.9.1+cu126.dist-info`、`torchaudio-2.9.1+cu126.dist-info` 用 robocopy 拷进 `.venv-music/Lib/site-packages/`。torch 2.9.1+cu126 跑 ACE-Step 没问题（官方 macOS 的要求就是 torch ≥ 2.9.1）；torchao 会提示「cpp extensions 版本不匹配」，不影响（我们不量化）。
  5. 权重：`.venv-tts` 里的 huggingface_hub：`snapshot_download("ACE-Step/Ace-Step1.5", local_dir="video/out/acestep/ACE-Step-1.5/checkpoints", allow_patterns=["acestep-v15-turbo/*","vae/*","Qwen3-Embedding-0.6B/*","config.json"])`（可断点续传；10-02 下了约 1.7 小时，网慢）。
- **怎么调用**：`export PYTHONIOENCODING=utf-8; .venv-music/Scripts/python video/music_gen.py --ids 1 2 3`（提示词表在脚本里；`--duration 210` 秒是默认；`--caption "..." --bpm 100 --key "D Major" --seed 7 --name x` 出临时的一首；`--controls` 出 3 首故意电子的对照组）→ `video/out/bgm_cands/raw/cand_N.flac` + `.json`（提示词、种子、用时、显存）。筛选 + 响度归一 + 截试听版：`.venv-music/Scripts/python video/music_screen.py <文件...> [--whisper]`、`--normalize 输出.mp3 --trial 试听.mp3`。生成完脚本退出，显卡就放开了，没有常驻进程。
- **显存和速度（GTX 1660 Ti 6 GB，turbo 8 步，fp16 + eager 注意力 + 全 CPU offload）**：载入模型 20–40 秒（第一次冷盘 54 秒把 DiT 搬上显卡）；**30 秒的曲子约 45 秒**；**210 秒的曲子 310–405 秒（约 5–7 分钟）**：DiT 扩散 ≈ 8 步 × 40 秒、VAE 分块解码约 1 分钟；显存峰值（torch 分配）**5.5–5.8 GB**，已经贴着 6 GB 上限，生成时不要开别的吃显存的东西（Qwen3-TTS 配音峰值约 4.9 GB，**不能和它同时用显卡**，两边抢会一起 OOM）。内存：offload 会把 DiT 放在内存里，要 ≥ 5 GB 空闲。
- **本机踩的坑（脚本里都绕开了）**：① 官方的「主模型齐全」检查把 5Hz LM 也算进去，缺了就自动整库下载（3.7 GB，网慢会挂几十分钟没输出）→ `music_gen.py` 把这个检查换成只看 DiT / VAE / 文本编码器；② 这张卡（Turing，没有 bf16）上 VAE 用 fp16 解码出 NaN（整首无声 / 存盘报错）→ VAE 改 fp32（0.34 GB，没压力）；③ torchcodec 加载不了（缺 FFmpeg 的 dll），官方存盘走 torchaudio → torchcodec 失败 → 脚本不让它存盘，自己用 soundfile 存 flac；transformers 的 ASR pipeline 也会去碰 torchcodec，所以 `music_screen.py` 的 Whisper 直接用 `WhisperForConditionalGeneration`；④ Whisper fp16 在这张卡上全是 NaN（转写成一串 "!"），用 fp32；⑤ 生成 210 秒的曲子，输出管道要用 `python -u` + 日志文件，不然几分钟看不到任何输出。
- **提示词经验（10-02 出了 14 首，3 首故意写成电子的对照组）**：写了 `hand drum` / `hand percussion` 的曲子，频谱上都出现每拍一下、固定在 55–60 Hz 的低频冲击（像底鼓）或宽带噪声，自动筛挡掉了；只写拨弦（古筝、琵琶、pizzicato）+ 木鱼 / 梆子轻敲 + 笛 / 箫、不写任何鼓的最干净。`ACE-Step` 的曲子低频普遍很重（30–100 Hz 占 32–52% 的能量），结尾有 3–9 秒数字静音（`music_screen.py --normalize` 会切掉）。每集的曲子怎么挑、候选在哪、筛选数据：`video/out/bgm_cands/README.md`（不进 git）。
- **筛选脚本 `video/music_screen.py` 的边界**：看频谱特征（持续音比例、高频泛音梳、35–65 Hz 底鼓基频能量、开头噪声感、平直包络）+ Whisper 查人声（`<|nocaptions|>` 概率，纯音乐时转写出来的是乱码，只看概率）；阈值是拿 3 首对照组标定的，**样本很少**。它不是音色分类器（要 AudioSet 标签得再下约 350 MB 的分类模型，没经同意不下）——这是 PITFALLS 待补 21 还没做完的部分。
- **合成器怎么换背景音乐**：分镜表顶层 `"bgm": "video/assets/audio/bgm/<文件>.mp3"`（仓库根或分镜表所在目录相对路径，或绝对路径）；不写 = 老的 `video/assets/audio/bgm_main.mp3`（tj01、tj02 不写，输出不变）。出片报告 `audio.bgm` 记着实际用了哪首。选定的曲子由主会话复制进 `video/assets/audio/bgm/`（进 git）。

