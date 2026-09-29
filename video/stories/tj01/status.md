# tj01 三家分晋：进度

> 主会话维护：reviewer 每次给出结论、每个检查点结束后更新，然后 commit + push。流程见 `docs/自动化工作流-每集生成.md`。
> 最后更新：2026-09-29

## 当前：第 0 步（卡住第 2–5 步的第 1–9a 项）+ 第 1 步（reviewer 核对引文）

## 每一步的状态
| 步 | 内容 | 状态 | 轮次 | 产出 | reviewer 结论 |
|---|---|---|---|---|---|
| 自检 | 运行环境 | 通过 | — | — | 09-29 主会话：7 项里 1–6 全过（edge-tts 当场装上）；第 7 项显卡渲染等第 14 项 |
| 0-1、0-2 | 剧本评分 v2、Jev key 检查、定基线 | 通过（小补丁做中） | 1/3 | `video/story.py`、`rubrics/story_v2.json`、`logic_qa.py` / `motion_qa.py` 开头、N6 结尾三句秒数 | 09-29 第 1 轮通过，6 条全过。另有小问题不挡过关：report.json 不记标准（E9）、timeline 全长（E10）、禁用词硬拦截（待补 7）→ 派了小补丁 |
| 0-3、0-4 | 素材登记表、系列参考帧（+ 改代码前的 ep01v2 基线） | 做中（先做第 4 项和基线） | 1/3 | `video/assets/ref/series/`、`video/stories/tj01/step0_baseline.md` | |
| 0-5、0-6 | 配音分层、仪式声音 | 没开始 | 0/3 | | |
| 0-7、0-8、0-9、0-9a | 分场模板、质检参数化、人名牌、2D 布景 | 没开始 | 0/3 | | |
| 1 | 史料简报 `source.md` | 待查（第 2 版已存档，等 source_check.py） | 2/3 | `video/stories/tj01/source.md`；补检查 `video/source_check.py`（builder 做中） | 第 1 轮不通过（09-29）：53 处引文全部逐字找到；没过的是 1 条超 20 字、没有注音、马镫年份、「晋静公」、校勘说明、出处没逐条标、#9–#12 年代没标、缺地图方位。PITFALLS S2 再犯、S14 新坑 |
| 2 | 剧本 | 没开始 | 0/3 | | |
| 检查点 1 | 复述剧本 | 没开始 | — | | |
| 3–10 | | 没开始 | | | |

## 定稿和基线
- 定稿剧本：（第 2 步定）
- 大问题：（推荐「最强的智伯为什么输了？」，检查点 1 请 Chris 确认）
- 基线（第 0 步第 1 项，reviewer 09-29 复核通过；空缓存重问 Jev 不变。注意估算值离阈值近：lines[25] 的 b_new 0.57–0.60，掉到 0.5 以下就变 15.4 秒；候选和基线相差 0.3 秒以内不算明显差别）：N6 按 story_v2 的最长平淡段 = 8.9 秒（估算秒数，96.9 秒起）；按真实时间线 = 8.9 秒（45.47 秒起，就是 lines[13] 那段 8.6 秒无台词动作）。N6 真实全长 161.3 秒

## 重跑用的命令
（每步做完补上：带环境变量和参数的完整命令）
- 基线估算：`.venv/Scripts/python video/story.py video/stories/ep01 --only N6 --out video/out/story_test/report_N6_v2_estimate_0929.json`
- 基线真实时间线：先配音 `NARRATOR_RATE=+6% .venv/Scripts/python video/voice.py video/stories/ep01/N6_你搬不搬.json video/out/ep01v2_voice_0929 2=1.0 9=1.2 13=8.6 22=1.2 29=3.3`，再 `.venv/Scripts/python video/story.py video/stories/ep01 --only N6 --timeline video/out/ep01v2_voice_0929/timeline.json --out video/out/story_test/report_N6_v2_timeline_0929.json`
- 环境（Git Bash）：`export PYTHONIOENCODING=utf-8; export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`，Python 用 `.venv/Scripts/python`

## Chris 跳过的项
（第 0 步的项目 Chris 明确同意先跳过的，写在这里）

## 交付记录
| 日期 | 提交号 | 发了什么 | 这一版改了什么 |
|---|---|---|---|
