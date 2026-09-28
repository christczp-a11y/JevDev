# MoneyPrinterTurbo 对比实验（2026-09-28）

Chris 的要求：用 demo 的素材，按 MoneyPrinterTurbo 的 skill 把同一个故事**重做**一遍（不是在原版上优化），对比有这个 skill 和没有的区别。

- skill：https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/docs/skill/SKILL.md（v1.3.2；helper 是同目录的 `mpt_agent.py`，已通读：只做下载项目、`uv sync`、检查配置、调用 `cli.py`，不会打印密钥）
- 一键运行：`bash experiments/mpt/run.sh`
- 输入：
  - 素材：`video/scenes/mpt_source_youth.json` 渲染出来的 demo 动画，按镜头切成 8 段（走到木杆前 / 说话打气 / 伸手又回头看 / 放倒抱起 / 抱着走 / 放下抬头 / 接金块 / 过关）
  - 故事要求：`prompt.txt`（和 demo 同一个故事、同样的史实要求）
  - 其余都用 skill 的默认值：中文 9:16、Edge TTS 晓晓、字幕、随机背景音乐；只改了一处，素材按顺序拼接，因为默认的随机顺序会打乱故事
- 大模型：`claude_code`（MPT 自带的选项，调用本机已登录的 claude 命令行写文案，工具全部关闭）

## 进度
- ✅ 素材渲染并切好；MPT 装好（v1.3.7，git 克隆，因为 GitHub 的 zip 下载被拦）；写文案这一步已跑通（7 秒）
- ❌ 配音被拦：Edge TTS 要连 `speech.platform.bing.com`；几种本地配音模型要从 huggingface.co 或 modelscope.cn 下载，也都被拦
- 第一次试跑写出的文案（skill 自己写的，没改）：要求 70–90 字，实际约 150 字；画面里是抱在腰前，文案写成「扛到北门」；还自己加了「官府当场盖章认账」
- 按 skill 的方式完整跑了一次（`run.sh`，2 分钟）：文案写好了，到配音这一步 Edge TTS 连续 3 次 30 秒超时，任务停在 audio 阶段。第二次写出的文案约 140 字，比第一次更贴近画面（抱着走、放下），最后一句是「秦国说话算数，从这根木头开始」——同样的输入，每次写出来的都不一样
- Chris 把网络改成 Full，当前会话立即生效（环境变量要开新会话才生效）；Edge TTS 还是超时：edge_tts 走 wss://，aiohttp 只从 WSS_PROXY 读代理 → run.sh 里设置 WSS_PROXY=HTTPS_PROXY，MPT 源码没改
- ✅ 出片：`output/mpt_xumu_2026-09-28.mp4`（30.1 秒，全程 4 分钟，全自动）；文案 `output/script.json`，字幕 `output/subtitle.srt`

## 对比结论（有 skill = MPT，没 skill = 我们自己的纸偶流水线）
| | MPT | 我们的流水线 |
|---|---|---|
| 做一条要多久 | 4 分钟，全自动 | 渲染 100 秒，但动作和场景前后改了 5 轮 |
| 配音、字幕、背景音乐 | 有，全自动 | 还没做（第 4 轮），音乐是代码合成的，难听 |
| 画面和旁白对不对得上 | 对不上：MPT 不看画面内容，只按时长切素材；19 秒素材配 30 秒旁白，19 秒后从头重播，「五十金送到怀里」时画面是小伙又走回木杆前 | 按帧对齐：台词、动作、音效都挂在剧本的时间点上 |
| 文案 | 每次都不一样；这次把「抱」写成「扛」、结尾写成「全城都信了」（和已确认标题的「开始相信」矛盾）；引号断在两行字幕之间 | 剧本定稿后逐句做两次史料复核，Jev 比较过 12 版 |
| 字幕 | 浅色字压在米色底上，看不清 | 纸片字幕卡，带说话人名牌 |
| 合理性复查 | 没有 | logic_qa（每集必做） |
结论：MPT 擅长「给素材配音、加字幕、配乐、剪成片」，这正是我们缺的；它不擅长「讲一个画面和旁白对得上的故事」。可以借用它的配音 / 字幕 / 背景音乐环节，不能用它来编排故事。
