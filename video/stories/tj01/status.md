# tj01 三家分晋：进度

> 主会话维护：reviewer 每次给出结论、每个检查点结束后更新，然后 commit + push。流程见 `docs/自动化工作流-每集生成.md`。
> 最后更新：2026-09-29

## 当前：第 3、4 步 + 第 0 步（第一场样片要的最小一组）同时做；目标是尽快出第一场样片。第 0 步卡住第 2–5 步的项目（1–9a）和提前做的 19 全部通过；10–18、20–22 卡第 6–8 步，等检查点 1 定了画面手法再派

## 每一步的状态
| 步 | 内容 | 状态 | 轮次 | 产出 | reviewer 结论 |
|---|---|---|---|---|---|
| 自检 | 运行环境 | 通过 | — | — | 09-29 主会话：7 项里 1–6 全过（edge-tts 当场装上）；第 7 项显卡渲染等第 14 项 |
| 0-1、0-2 | 剧本评分 v2、Jev key 检查、定基线 | 通过（小补丁也通过） | 1/3 | `video/story.py`、`rubrics/story_v2.json`、`logic_qa.py` / `motion_qa.py` 开头、N6 结尾三句秒数 | 09-29 第 1 轮通过，6 条全过。另有小问题不挡过关：report.json 不记标准（E9）、timeline 全长（E10）、禁用词硬拦截（待补 7）→ 小补丁 09-29 reviewer 通过（6 条全过）；主会话另补两行：说话人也查禁用词、词条前后带空格报错 |
| 0-3、0-4 | 素材登记表、系列参考帧（+ 改代码前的 ep01v2 基线） | **通过**（第 3 项 09-29 第 2 轮；第 4 项参考帧随 C2 第 3 轮重截为 ZCOOL KuaiLe 后通过） | 2/3 | `video/assets/REGISTRY.md`、`video/registry_check.py`、`video/assets/ref/series/`（8 张） | 第 3 步开工前补待补 12；`props/props.png` 状态改未定稿 |
| 0-5、0-6 | 配音分层、仪式声音 | **通过**（09-29 第 2 轮，b67f928）；补充「时间线去句尾静音」也通过（B 版 189.95 秒，大问题 5.55–7.80 秒） | 2/3 | `video/voice.py`、`video/series_voice.json`、`video/assets/audio/`（两段仪式录音、`sgm_pop.wav`） | 第 1 轮不通过（09-29）：9 条过关条件都过，卡在 voice_text 不查禁用词（S13 漏洞）；另补仪式句近似警告（A5）等。等 Chris：司马光弹出音效要听；tone() 老 bug（A4）修不修 |
| 0-7、0-8、0-9、0-9a、0-19 | 分场模板、质检参数化、人名牌、2D 布景机制、字体本地化 | **通过**（09-29 第 3 轮） | 3/3 | `video/episode_build.py`、`episode_config.py`、`episodes/`、`build_tj01.py`、`series_style.json`、`set_check.py`、`glyph_check.py`、`imgdiff.py`、`vendor/fonts/`、`video/tests/` | 留给以后：人名牌时长含淡入淡出（看得清的少 0.3–0.4 秒）；重新子集化要本机的 `video/out/fonts_src/` |
| 1 | 史料简报 `source.md` | **通过**（09-29 第 2 轮；主会话按 reviewer 数据补改地图方位等，source_check 152 条 0 错） | 2/3 | `video/stories/tj01/source.md`；补检查 `video/source_check.py`（builder 做中） | 第 1 轮不通过（09-29）：53 处引文全部逐字找到；没过的是 1 条超 20 字、没有注音、马镫年份、「晋静公」、校勘说明、出处没逐条标、#9–#12 年代没标、缺地图方位。PITFALLS S2 再犯、S14 新坑 |
| 2 | 剧本 | **通过**（09-29 第 2 轮 + 最后小改，reviewer 签字） | 2/3 | 定稿 `video/stories/tj01/B_段规.json`；配音试跑 `video/out/tj01/step2/voice_B3/`；`video/script_check.py` | 闸门 0.27 / 0.09 / 0.04；flat 估算 8.6（基线 8.9）、真实 8.6（基线 9.0）；pair 0.67 / 0.74 / 0.71（平均 0.707，最后小改前那版）；全长 200.9 秒；大问题 7.18 秒念完（S20：7.0 + 0.3）。备选 D 的 pair 平均 0.577，不满足「平均最高」 |
| 检查点 1 | 复述剧本 + 待定事项 | **通过**（09-29 Chris：「你自己决定吧」→ Claude 按推荐定，见 DECISIONS 最后一条） | — | | |
| 3 | 角色、布景、道具 | 做中（阵容图、剪影、布景总览、司马光圆领） | 1/3 | | 阵容图发 Chris 看，不等回复，接着画姿势图 |
| 4 | 配音和时间线 | **完成**（09-29；A4 已修） | 1/3 | `video/out/tj01_voice/timeline.json`（200.9 秒） | script_check 0 警告；最长平淡段 8.6 ≤ 9.0 |
| 0-10/11/14/21 | 3D 按集、布景数据化、GPU、3D bug、背景音乐、系列格式 | 做中 | 1/3 | | |
| 5–10 | | 没开始 | | | |

## 定稿和基线
- 定稿剧本：`video/stories/tj01/B_段规.json`（待 Chris 在检查点 1 确认；备选 `D_智伯.json`）
- 大问题：「最强的智伯，为什么输了？」（检查点 1 请 Chris 确认）
- 基线（第 0 步第 1 项，reviewer 09-29 复核通过；空缓存重问 Jev 不变。注意估算值离阈值近：lines[25] 的 b_new 0.57–0.60，掉到 0.5 以下就变 15.4 秒；候选和基线相差 0.3 秒以内不算明显差别）：N6 按 story_v2 的最长平淡段 = 8.9 秒（估算秒数，96.9 秒起）；按真实时间线 = **9.0 秒**（09-29 起时间线去掉句尾静音；N6 全长 142.04 秒；报告 `video/out/voice_test/N6_trim_tl.json`）。旧的「9.4 秒 / 161.35 秒」是没裁静音的，不再用；比较时两边都用裁过的时间线

## 重跑用的命令
（每步做完补上：带环境变量和参数的完整命令）
- 第 4 步配音：`.venv/Scripts/python video/voice.py video/stories/tj01/B_段规.json video/out/tj01_voice 2=1.0 9=1.5 11=1.2 20=1.0 25=1.2 34=1.5 36=1.8 42=2.0 46=1.2 49=1.4 52=1.5`
- 基线估算：`.venv/Scripts/python video/story.py video/stories/ep01 --only N6 --out video/out/story_test/report_N6_v2_estimate_0929.json`
- 基线真实时间线：先配音 `NARRATOR_RATE=+6% .venv/Scripts/python video/voice.py video/stories/ep01/N6_你搬不搬.json video/out/ep01v2_voice_0929 2=1.0 9=1.2 13=8.6 22=1.2 29=3.3`，再 `.venv/Scripts/python video/story.py video/stories/ep01 --only N6 --timeline video/out/ep01v2_voice_0929/timeline.json --out video/out/story_test/report_N6_v2_timeline_0929.json`
- 环境（Git Bash）：`export PYTHONIOENCODING=utf-8; export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`，Python 用 `.venv/Scripts/python`

## 已知缺口
- 试做集 `video/stories/ep01/episode.json` 没有 cast：新 voice.py 不能重配试做集；试做集停做，不补（回归只用 `video/out/ep01v2_voice_0929/`）
- 普通话男声只有 4 个（Yunxi 留给司马光）：tj01 的 cast 在第 2 步想办法，检查点 1 和配音授权一起问 Chris
- 试做集 2D 成片 `video/out/ep01v2/ep01_full.mp4` 本地没有：影响第 0 步第 15 项（独立混音）的回归对比，到那一项再处理（要先在本地渲一遍 2D）

## Chris 跳过的项
（第 0 步的项目 Chris 明确同意先跳过的，写在这里）

## 交付记录
| 日期 | 提交号 | 发了什么 | 这一版改了什么 |
|---|---|---|---|
| 09-29 | 1ce6886 | 检查点 1：剧本复述 + 试听视频 cp1_sounds.mp4 | 第一次发 |
