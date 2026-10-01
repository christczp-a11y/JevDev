# tj01 三家分晋：进度

> **2026-09-29 换成动态漫画**（three.js 停用，旧工作流作废，见 `docs/自动化工作流-每集生成.md`）。
> - 已完成、继续有效：史料 `source.md`、定稿剧本 `B_段规.json`、配音 `video/out/tj01_voice/`、已画好的人物和场景素材；
> - 下一步：先施工（`docs/施工计划-动态漫画引擎.md` A → B + C），再从新流程的**第 4 步分镜表**做起，先出第一场样片给 Chris；
> - 下面表格里的「第 0 步」「第 5–6 步」是旧流程的，只作记录。

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
| 4 | 配音和时间线 | **作废**（旧 Edge 配音，09-29 起由下一行 Qwen3-TTS 整集重配取代） | 1/3 | `video/out/tj01_voice/timeline.json`（200.9 秒） | script_check 0 警告；最长平淡段 8.6 ≤ 9.0 |
| 3（新流程） | 配音（Qwen3-TTS 整集重配） | **完成**（09-29） | 1/3 | `video/out/tj01_voice_qwen/timeline.json`（**230.9 秒**，90 句，67 句合成 + 2 句仪式录音） | script_check 退出码 0、0 警告；最长平淡段 6.5 秒（≤ 9.0）；大问题 4.69–7.16 秒念完（≤ 7.3）；新参考音 4 个角色 + 9 个语气变体；段规、赵襄子、韩康子（含 4 个语气变体）09-29 又重设计一轮（基频改到约 118–133 Hz、起伏 4–6 个半音）（见下面「重跑用的命令」）；等 reviewer 听 |
| 3（新流程，G_尊重） | 配音（新剧本 `G_尊重.json`，Qwen3-TTS 整集） | **完成**（09-30） | 1/3 | `video/out/tj01_voice_g/timeline.json`（**208.0 秒**，52 句（38 句有配音，无仪式句；09-30 第 37、38 行由动作行改成旁白、第 50、51 行下集预告改字后重配：第 37–38 行 2.15 / 2.12 秒，第 50–51 行 4.54 / 5.53 秒）） | script_check 退出码 0（0 处错误，24 条「单句超 15 字」警告）；`story.py --only G_尊重` 最长平淡段真实 19.3 秒、估算 20.8 秒（结尾行动呼吁那段，Chris 原话，不改）；大问题「地盘最大、兵马最多，为什么一夜之间全部输光？」22.08–27.13 秒；新声音 3 个（韩康子、魏桓子、张孟谈的「坚定、干脆」）；齐声 1 句、心声 2 句；Whisper 转全部台词，没有念错的，只有 2 句超速用 `voice_text` 加逗号；等 reviewer 听 |
| 0-10/11/14/21 | 3D 按集、布景数据化、GPU、3D bug、背景音乐、系列格式 | 做中 | 1/3 | | |
| 5–10 | | 没开始 | | | |

## 定稿和基线
- 定稿剧本：`video/stories/tj01/B_段规.json`（待 Chris 在检查点 1 确认；备选 `D_智伯.json`）
- 大问题：「最强的智伯，为什么输了？」（检查点 1 请 Chris 确认）
- 基线（第 0 步第 1 项，reviewer 09-29 复核通过；空缓存重问 Jev 不变。注意估算值离阈值近：lines[25] 的 b_new 0.57–0.60，掉到 0.5 以下就变 15.4 秒；候选和基线相差 0.3 秒以内不算明显差别）：N6 按 story_v2 的最长平淡段 = 8.9 秒（估算秒数，96.9 秒起）；按真实时间线 = **9.0 秒**（09-29 起时间线去掉句尾静音；N6 全长 142.04 秒；报告 `video/out/voice_test/N6_trim_tl.json`）。旧的「9.4 秒 / 161.35 秒」是没裁静音的，不再用；比较时两边都用裁过的时间线

## 重跑用的命令
（每步做完补上：带环境变量和参数的完整命令）
- 第 3 步配音（新流程，Qwen3-TTS，配音跑 `.venv-tts`，voice.py 自己调；一整集第一次约 20 分钟，之后走缓存约 1 分钟；旧的 `video/out/tj01_voice/` 是 Edge 的，作废）：
  `.venv/Scripts/python video/voice.py video/stories/tj01/B_段规.json video/out/tj01_voice_qwen 2=1 7=0.8 13=1.5 16=1.2 19=0.8 22=0.6 27=0.6 32=1 43=1.2 58=1.5 60=1.8 68=1.2 72=2 79=1.2 82=1.4 86=1.5 87=1.5`
  （动作行秒数 = 剧本估算秒数；「考你」停顿 2/16/43/60 行 = 1.0/1.2/1.2/1.8 秒。参考音已存在 `video/assets/audio/voices/`，重跑不会变。voice.py 的种子由（角色、描述、语气）算出来，同样的描述 `--redesign` 只会得到一模一样的声音；所以 智国、智果（cast 描述都加了「男声」，智果改「浑厚爽朗」）、智果@赌气干脆、魏桓子@小声紧张、智伯@生气不耐烦 是换种子各设计 6 个候选、按基频（再看说话人相似度、Whisper 转写）手挑的，段规、赵襄子、韩康子（cast 描述改成「男声、三十多岁…温和、有精神」）及 4 个语气变体（段规@小声着急、赵襄子@坚定干脆、韩康子@委屈咬着牙、韩康子@小声紧张）也是这样手挑的（各 8 或 6 个候选）；json 的 pick 字段记着。剧本顶层 `voice_text` 有 5 条，都只改标点、字幕仍是原文：「不信！我不惹事，谁敢惹我？」→ 末尾改「！」（原句中间停 1.16 秒）；「就像排队打针，下一个就轮到你！」→ 加一个逗号（原句 5.04 字/秒超速）；「给……给你！」→「给…给你！」（原句念到 250 Hz 像女声）；「不给。」→「不给！」（Whisper 转成「不可以」）；「走，去晋阳！」→「走！去晋阳！」（Whisper 转成「去敬仰」））
  过关：`.venv/Scripts/python video/script_check.py video/stories/tj01/B_段规.json --timeline video/out/tj01_voice_qwen/timeline.json`；`.venv/Scripts/python video/story.py video/stories/tj01 --only B_段规 --timeline video/out/tj01_voice_qwen/timeline.json`
- 第 3 步配音（新剧本 G_尊重，输出到新目录；旧的 `video/out/tj01_voice_qwen/`（B 版）不动）：
  `.venv/Scripts/python video/voice.py video/stories/tj01/G_尊重.json video/out/tj01_voice_g 0=2.4 2=1 8=1.8 12=1.3 20=1.5 22=1.5 27=1.3 28=1.5 30=2 33=2 35=1 40=2.8 43=1 46=1.2`
  （动作行秒数 = 剧本估算秒数。新目录第一次约 15 分钟，可以先把 `video/out/tj01_voice_qwen/cache/*.mp3` 拷进 `video/out/tj01_voice_g/cache/`，同一句同一声音直接用缓存；之后重跑走缓存约 1 分钟。参考音都在 `video/assets/audio/voices/`；本剧新设计的 3 个：`韩康子@坚定干脆`（129 Hz）、`魏桓子@坚定干脆`（105.5 Hz）、`张孟谈@坚定干脆`（114 Hz），手挑方法同上一轮（json 的 `pick` 记着）。`G_尊重.json` 的 `tone`：魏桓子、韩康子两句心里话写成「心声、小声、紧张」（声音是去掉「心声」后的「小声、紧张」，不另设计，念完由 voice.py 加混响和压低高频）；第 36 句说话人「韩康子+魏桓子+张孟谈」是齐声（三个声音各念一遍、起点对齐叠在一起）。`voice_text` 4 条：两条导演写的（「我……我不想给……」→「我…我不想给…」，「天哪…」那句加逗号、换省略号），两条配音时加的（lines[1]「如果一个全校第一……」加 3 个逗号、lines[3]「时光倒流，两千四百多年……」加 1 个逗号，都只改标点，原来超过每秒 5 个字）。）
  过关：`.venv/Scripts/python video/script_check.py video/stories/tj01/G_尊重.json --timeline video/out/tj01_voice_g/timeline.json`；`.venv/Scripts/python video/story.py video/stories/tj01 --only G_尊重 --timeline video/out/tj01_voice_g/timeline.json`
  voice.py 新增（09-30）：说话人写「甲+乙+丙」= 齐声，语气写「心声」= 心里话处理，说明在 `video/voice.py` 文件头；测试 `video/tests/voice/test_chorus.py`（`bash video/tests/voice/run_all.sh test_chorus`）
- 第 6 步合成（整集，G 版分镜表 80 镜 / 206.1 秒；配音 `video/out/tj01_voice_g/`）。Git Bash、仓库根目录、`export PYTHONIOENCODING=utf-8`，不用显卡：
  分镜检查：`.venv/Scripts/python video/motion/storyboard_check.py video/stories/tj01/storyboard.json`（必须 0 错）
  预览（540×960，约 3 分钟）：`.venv/Scripts/python video/motion/render.py tj01 --preview --out video/out/tj01/full/preview`
  整集正式版（1080×1920、30 帧，配音 + 音效 + 背景音乐；冷启动约 10 分钟，缓存命中时只重渲改过的镜头，最后的拼接编码约 5 分钟）：放后台跑 `nohup bash -c '.venv/Scripts/python video/motion/render.py tj01 --out video/out/tj01/full/build > video/out/tj01/full/build_log.txt 2>&1; echo EXIT=$? >> video/out/tj01/full/build_log.txt' &`，出 `build/tj01.mp4 / .wav / .report.json`，再复制成 `video/out/tj01/full/tj01_full.mp4 / .wav / .report.json`
  抽帧（每秒 1 帧联系表 26 张 + 每镜头前 2 秒每秒 10 帧动作条 80 张）：`.venv/Scripts/python video/motion/review_frames.py video/out/tj01/full/tj01_full.mp4 tj01 --out video/out/tj01/full`
  整集自动检查（2026-09-30 第三轮，81 镜 / 208.0 秒，补空白 + 截段）：响度 −16.0 LUFS、真峰值 −2.0 dB、闪烁 0 处、静止 > 1.5 秒 0 处、台词没有人声 0 句、空白 0 处（出片时检测 + `blank_scan.py` 对成片再扫一遍），退出码 0；storyboard_check 0 错；storyboard_jev 退出码 0。冷启动 5.3 分钟（126 块），改 1–3 个镜头再出整集约 40 秒；整集命令不变（见上），出片后跑 `.venv/Scripts/python video/motion/blank_scan.py video/out/tj01/full/tj01_full.mp4 tj01`
  整集自动检查（2026-09-30 第二轮，按 reviewer 意见改完重出）：响度 −16.0 LUFS、真峰值 −1.9 dB、闪烁 0 处、静止 > 1.5 秒 0 处、台词没有人声 0 句、合成器警告 0 条，退出码 0；motion 测试 153 项（test_units / plan_errors / fx / storyboard_check）全过
  整集自动检查（2026-09-30 第一轮）：响度 −16.0 LUFS、真峰值 −2.0 dB、闪烁 0 处、静止 > 1.5 秒 0 处、台词没有人声 0 句、合成器警告 0 条，退出码 0；storyboard_check 0 错（2 条朝向警告：s48、s50 智伯坐战车车头面朝前进方向，是有意的）
  重画的素材（同名）进来以后只重渲用到它的镜头：直接再跑上面的整集命令，缓存按图的内容哈希自动判断
- 第 6 步合成（第一场，第 0–13 句 = 0–33.4 秒；配音时间线 `video/out/tj01_voice_qwen/timeline.json`）。Git Bash、仓库根目录、`export PYTHONIOENCODING=utf-8`，不用显卡：
  先过分镜检查：`.venv/Scripts/python video/motion/storyboard_check.py video/stories/tj01/storyboard.json`（必须 0 错）
  预览（540×960，约 25 秒）：`.venv/Scripts/python video/motion/render.py tj01 --preview --out video/out/tj01/scene1/preview`
  正式（1080×1920、30 帧，配音 + 音效 + 背景音乐，约 1.5 分钟；有缓存时只重渲改过的镜头）：`.venv/Scripts/python video/motion/render.py tj01 --out video/out/tj01/scene1/build`，出 `build/tj01.mp4 / .wav / .report.json`，再复制成 `video/out/tj01/scene1/tj01_scene1.mp4 / .wav / .report.json`
  抽帧（每秒 1 帧联系表 + 每镜头前 2 秒每秒 10 帧）：`.venv/Scripts/python video/motion/review_frames.py video/out/tj01/scene1/tj01_scene1.mp4 tj01 --out video/out/tj01/scene1`
  分镜 Jev 检查：`.venv/Scripts/python video/motion/storyboard_jev.py video/stories/tj01/storyboard.json`（要先设 TYPESAFE_API_KEY，见下面「环境」），退出码 0（s12 主体是泡泡里的画，已放行）
  第一场自动检查（导演改完分镜表、s13 换成智伯在左段规在右之后重出）：响度 −16.1 LUFS、真峰值 −2.1 dB、闪烁 0 处、静止 > 1.5 秒 0 处、台词没有人声 0 句、合成器警告 0 条，退出码 0；storyboard_check 0 错（2 条警告：s02 考你从上一句起演、s10 韩康子低头扭脸朝右，都是有意的）
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
| 09-29 | df1e867 | 施工 B：特效样片合集手机版（127.6 秒，45 个特效和转场，带声音） | reviewer 一轮后修好 5 处挡住交付 + 特效小问题；标题条小字改成「第 N 集 · 本集名」 |
| 09-29 | 975b3dd | D：第一场样片手机版（33.4 秒，第 0–13 句，带声音） | 第一次发；reviewer 一轮后修好 5 处挡住交付和小问题；s13 面对面、下半屏空带铺满。等 Chris 通过再做整集 |
- 待补（故事定了以后，换进分镜表时一起做）：s27/s29/s49/s50/s51 换朝左的新图（zxz_no_l、hkz_stand_l、zb_cheer_l、wgh_reins_l）；s50 智伯 acts 里的 zb_glance 和 s49/s50 魏桓子的 wgh_reins 也要朝向一致。
| 09-30 | 2f502a3 | G 版整集手机版（206.1 秒，720×1280，带声音）：Chris 定的新剧本 | 第一次发整集；reviewer 一轮 + 尾段补查后修好 2 处挡住交付（战车段穿模、浪吞兵）和 22 处小问题 |
| 09-30 | b21e28d | G 版整集第 2 版手机版（208.0 秒，上下两段，带声音） | Chris 7 条意见：字幕下移（底边 y 1615）、12 镜空白补满、城不挡脸、反击段补两句旁白、下集预告讲清；截段重渲 |
| 09-30 | （本次提交） | 第 9 步发布包 `publish.md` + 封面 `video/out/tj01/publish/cover_3x4.png` | Jev 挑标题（10 选 1）、封面字（7 选 1）、组合（5 选 1）；正文 544 字；建议 10/2 北京 20:00 定时发 |

## 发布后数据（2 小时 / 24 小时 / 72 小时 / 7 天）
| 时间点 | 曝光 | 点击率 | 完播率 | 平均观看时长 | 2 秒流失 | 5 秒流失 | 收藏 | 评论 | 改了什么 |
|---|---|---|---|---|---|---|---|---|---|
