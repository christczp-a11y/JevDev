# tj01 三家分晋：进度

> 主会话维护：reviewer 每次给出结论、每个检查点结束后更新，然后 commit + push。流程见 `docs/自动化工作流-每集生成.md`。
> 最后更新：2026-09-29

## 当前：检查点 1，等 Chris；第 0 步 7–9a + 19 第 2 轮做中（不卡检查点 1）

## 每一步的状态
| 步 | 内容 | 状态 | 轮次 | 产出 | reviewer 结论 |
|---|---|---|---|---|---|
| 自检 | 运行环境 | 通过 | — | — | 09-29 主会话：7 项里 1–6 全过（edge-tts 当场装上）；第 7 项显卡渲染等第 14 项 |
| 0-1、0-2 | 剧本评分 v2、Jev key 检查、定基线 | 通过（小补丁也通过） | 1/3 | `video/story.py`、`rubrics/story_v2.json`、`logic_qa.py` / `motion_qa.py` 开头、N6 结尾三句秒数 | 09-29 第 1 轮通过，6 条全过。另有小问题不挡过关：report.json 不记标准（E9）、timeline 全长（E10）、禁用词硬拦截（待补 7）→ 小补丁 09-29 reviewer 通过（6 条全过）；主会话另补两行：说话人也查禁用词、词条前后带空格报错 |
| 0-3、0-4 | 素材登记表、系列参考帧（+ 改代码前的 ep01v2 基线） | 第 3 项**通过**（09-29 第 2 轮；等 C2 一起提交，registry_check 依赖 episode_config）；第 4 项参考帧不通过（E1：5 张备用字体）→ 并进 C2 第 2 轮重截；基线通过 | 2/3 | `video/assets/REGISTRY.md`、`video/registry_check.py`、`video/tests/registry/` | 第 3 步开工前补待补 12（隐式素材、布景 dir、子目录）；`props/props.png` 状态改未定稿 |
| 0-5、0-6 | 配音分层、仪式声音 | **通过**（09-29 第 2 轮，b67f928）；补充「时间线去句尾静音」也通过（B 版 189.95 秒，大问题 5.55–7.80 秒） | 2/3 | `video/voice.py`、`video/series_voice.json`、`video/assets/audio/`（两段仪式录音、`sgm_pop.wav`） | 第 1 轮不通过（09-29）：9 条过关条件都过，卡在 voice_text 不查禁用词（S13 漏洞）；另补仪式句近似警告（A5）等。等 Chris：司马光弹出音效要听；tone() 老 bug（A4）修不修 |
| 0-7、0-8、0-9、0-9a（+ 提前做 0-19 字体） | 分场模板、质检参数化、人名牌、2D 布景 | 做中（第 3 轮，最后一轮） | 3/3 | `video/episode_build.py`、`episode_config.py`、`episodes/`、`build_tj01.py`、`set_check.py`、`sets/README.md`；人名牌在 stage.html / engine.html | 第 1 轮不通过（09-29）：第 8、9a 项过；卡在人名牌标错人（T23）、主角牌子没出现（T24）、家族颜色进了每集配置（第七节）、测试在 video/out（P10）、单场混音崩溃（A6）。第 19 项（字体本地化）并进这一轮，做完重截参考帧。第 2 轮不通过（09-29）：只卡 selfcheck --base 对老提交崩溃；其余全过（字体本地化生效，8 张参考帧重截为 ZCOOL KuaiLe，混音新旧逐样本一致）。第 3 轮加字形覆盖检查 |
| 1 | 史料简报 `source.md` | **通过**（09-29 第 2 轮；主会话按 reviewer 数据补改地图方位等，source_check 152 条 0 错） | 2/3 | `video/stories/tj01/source.md`；补检查 `video/source_check.py`（builder 做中） | 第 1 轮不通过（09-29）：53 处引文全部逐字找到；没过的是 1 条超 20 字、没有注音、马镫年份、「晋静公」、校勘说明、出处没逐条标、#9–#12 年代没标、缺地图方位。PITFALLS S2 再犯、S14 新坑 |
| 2 | 剧本 | **通过**（09-29 第 2 轮 + 最后小改，reviewer 签字） | 2/3 | 定稿 `video/stories/tj01/B_段规.json`；配音试跑 `video/out/tj01/step2/voice_B3/`；`video/script_check.py` | 闸门 0.27 / 0.09 / 0.04；flat 估算 8.6（基线 8.9）、真实 8.6（基线 9.0）；pair 0.67 / 0.74 / 0.71（平均 0.707，最后小改前那版）；全长 200.9 秒；大问题 7.18 秒念完（S20：7.0 + 0.3）。备选 D 的 pair 平均 0.577，不满足「平均最高」 |
| 检查点 1 | 复述剧本 + 待定事项 | **等 Chris** | — | 试听视频 `video/out/tj01/checkpoint1/cp1_sounds.mp4`（司马光弹出音效；A4 现状 / 修好） | |
| 3–10 | | 没开始 | | | |

## 定稿和基线
- 定稿剧本：`video/stories/tj01/B_段规.json`（待 Chris 在检查点 1 确认；备选 `D_智伯.json`）
- 大问题：「最强的智伯，为什么输了？」（检查点 1 请 Chris 确认）
- 基线（第 0 步第 1 项，reviewer 09-29 复核通过；空缓存重问 Jev 不变。注意估算值离阈值近：lines[25] 的 b_new 0.57–0.60，掉到 0.5 以下就变 15.4 秒；候选和基线相差 0.3 秒以内不算明显差别）：N6 按 story_v2 的最长平淡段 = 8.9 秒（估算秒数，96.9 秒起）；按真实时间线 = **9.0 秒**（09-29 起时间线去掉句尾静音；N6 全长 142.04 秒；报告 `video/out/voice_test/N6_trim_tl.json`）。旧的「9.4 秒 / 161.35 秒」是没裁静音的，不再用；比较时两边都用裁过的时间线

## 重跑用的命令
（每步做完补上：带环境变量和参数的完整命令）
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
