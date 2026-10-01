# tj02 魏文侯之约：进度

> 主会话维护。流程见 `docs/自动化工作流-每集生成.md`；照 `video/stories/tj01/复盘.md`「下一集照着做」执行。只做动画，不做文案。
> 最后更新：2026-10-01

## 当前：第 6 步合成整集（builder）

## 每一步的状态
| 步 | 内容 | 状态 | 产出 | 备注 |
|---|---|---|---|---|
| 自检 | 装机检查 | 通过（10-01） | — | `bash scripts/cloud_setup.sh` 全过 |
| 1 | 史料 | **通过**（10-01） | `video/stories/tj02/source.md`（researcher 第 1 版；`source_check.py` 108 条引文 0 错） | 纠正 Gemini 出处（通鉴在威烈王二十三年，「魏于是乎始强」只在《战国策》）；按简报主会话再收 3 处措辞：「夹在正中间」→「身边的邻居可不少」、「都来到了魏国」→「都在魏国帮魏文侯做事」（只有吴起明写「往归」）、预告「渡黄河」→「顺着大河往下走」（河名不说） |
| 2 | 剧本 | **通过**（10-01） | `A_守约.json`（43 行，33 句台词，估算 217.5 秒）+ `episode.json` | 闸门 史实 0.28 / 不宜 0.03 / 对立 0.03；最长平淡段 16.5 秒（tj01 G 版 20.8）；script_check 退出码 0、28 条警告（单句 >8 秒 7 条、>15 字 21 条，照「不硬拆」）。主会话按规则再改 4 处：「前几天…今天中午」→「早就…约好，今天」（日子查不实）；「连看林人都不骗的国君」→「魏文侯说的话」（不分身份高低）；预告语病；第一关横幅「致命舒适圈」→「又暖又舒服的宴会」。魏文侯「备车去打猎」只做动作不配音（他是去取消打猎） |
| 5（提前） | 新角色 | **完成**（10-01，fa5f496） | 魏文侯 `wwh_` 15 张 + 竹片 `props/wwh_slip`、虞人 `yr_` 5、大臣 `wdc_a/b/c` 15、吴起 `wq_` / 乐羊 `ly_` / 李克 `lk_` / 西门豹 `xmb_` 各站姿 + 背包袱走路（吴起另 2 张高清）；REGISTRY 54 行，registry_check 0 | Codex 14 次，0 重画；阵容 `video/out/tj02/lineup.png` 已发 Chris（不等回复）。PX：魏文侯 0.453、虞人 0.331、大臣 0.381/0.352/0.350、吴起 0.290、乐羊 0.302、李克 0.282、西门豹 0.301。场景（茅草棚、雨、磁铁、大木船）等分镜表 |
| 3 | 配音（Qwen3-TTS 整集） | **完成**（10-01；等 reviewer 听，我只能靠指标和 Whisper，没有人耳听过） | `video/out/tj02_voice/timeline.json`（**194.5 秒**，43 行 = 33 句台词 + 10 个动作行，33 句全是新合成，没有仪式句；cache 在同目录） | script_check 退出码 0（0 处错误，26 条警告：21 条单句 >15 字、5 条单句 >8 秒，都是导演「不硬拆」的长句）；`story.py --only A_守约` 最长平淡段真实时间线 **13.0 秒**（从 61.56 秒起，≤ 16.5；估算秒数下 16.5 秒）；大问题 25.04–28.62 秒念完（bigq_by 32）；语速报警 0 处。新声音 3 个角色 7 段参考音（存 `video/assets/audio/voices/`，每个声音换种子设计 8 个候选，按基频、起伏、Whisper 转写、说话人向量挑；json 的 `pick` 记着）：**魏文侯** 133.4 Hz（@坚定干脆 129.8）、**虞人** 132.3（只做基准，本集没有句子用；@小声自言自语有点失望 98.4、@又惊又喜激动 148.4）、**大臣** 123.3（@语气疑惑不解有点着急 128.1）；整集念出来的实际基频：魏文侯 111–127 Hz、虞人 96.5（小声）/ 124（惊喜）、大臣 141–144。`voice_text` 9 条，都在剧本顶层：1 条换同音字（「乐羊」→「岳羊」，Whisper 强制解码打分「岳羊」比「乐羊」高 3 分、比「勒羊」高 17 分，读 yuè），8 条只改标点（原句超每秒 5 个字，加逗号：lines[1]、[5]、[11]、[12]、[14]、[27]、[40]；lines[20]「老人家快起来！」第一次加逗号念出来只有 98 Hz、太低，改成「老人家！快起来！」后 111 Hz）。多音字：「虽乐」（lines[29]）没写 voice_text，Whisper 强制解码「乐 / 勒」比「月 / 越 / 悦」高 9–16 分，读 lè；「一会期」期读 qī（比「基 / 机」高 8 分）；「大将军」读 jiàng、「弹幕」读 dàn、「冒雨」「还重」都对。拿不准的两处：lines[29] 句尾「哉」Whisper 听成「待 / 在」（和「再 / 灾」得分一样，应该是 zāi / zài，听一遍确认）；lines[17] 虞人小声一句基频 96.5 Hz 偏低（小声失望本来就低；备选是 `虞人@小声自言自语有点失望` 的候选 #1，json 里记着） |
| 4 | 分镜表 | **通过**（10-01） | `storyboard.json` + `gen_storyboard.py`（72 镜，22.2 镜/分钟，没有超过 5 秒的）；`素材清单.md`、`镜头大纲.md` | storyboard_check 0 错（`[停留]` 0 错），3 条朝向警告是有意的（s14 大臣朝画外的魏文侯、s69/s70 船上两人都朝前进方向）；storyboard_jev 退出码 0（9 镜按 notes 放行：地图 / 出题 / 行动呼吁 / 预告的主体，「鸽子王」原话，文言点题）。主会话定：魏文侯自己驾车、弹幕选择用两张 card_quest + danmaku、人名牌提前到 s01、第 25 句打对勾 |
| 5 | 画面素材 | **通过**（10-01，9bd4e10） | 素材清单 T1–T3、C1–C13（含新角色魏武侯 `wuh_`）、P1–P17、F1–F3、B1–B5 + 两张拼图；REGISTRY +44 行，25 张 tj01 复用素材范围改成「系列」；registry_check 0 | 主会话看过总览 `video/out/tj02/assets_new.png`。待补：青蛙荷叶是手工改绿的，Codex 额度 12:22 PDT 恢复后可重画 `frogs.txt`；魏文侯腰间小竹片上的弓在小图里有点像伞（特写用的 `props/wwh_slip` 没问题） |
| 6、7 | 合成、成片检查 | 没开始 | | |

## 重跑用的命令
（每步做完补上：带环境变量和参数的完整命令。Git Bash、仓库根目录；环境：`export PYTHONIOENCODING=utf-8; export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`，Python 用 `.venv/Scripts/python`）
- 第 3 步配音（Qwen3-TTS，voice.py 自己调 `.venv-tts`；配音时别的程序不占显卡，整集第一次约 15 分钟，之后走缓存约 1 分钟；一定放后台跑）：
  `.venv/Scripts/python video/voice.py video/stories/tj02/A_守约.json video/out/tj02_voice 0=2 7=1.5 8=1.2 18=1.8 22=1.5 26=2.5 28=1 31=1 33=1.5 36=1`
  （动作行秒数 = 剧本估算秒数；这一集没有「考你」停顿。参考音都已存在 `video/assets/audio/voices/`，重跑不会变；缓存按（文字、声音、参考音 sha256、模型、种子）算，换了机器没有 `video/out/tj02_voice/cache/` 就要重新合成，种子相同，但显卡浮点不同时声音可能有细小差别。）
  过关：`.venv/Scripts/python video/script_check.py video/stories/tj02/A_守约.json --timeline video/out/tj02_voice/timeline.json`（退出码 0）；`.venv/Scripts/python video/story.py video/stories/tj02 --only A_守约 --timeline video/out/tj02_voice/timeline.json`（最长平淡段 ≤ 16.5 秒，要 TYPESAFE_API_KEY）。
  新声音怎么挑的（tj01 的做法，没有进 voice.py，脚本留在 `video/out/tj02_voice_pick/scripts/`，输出在 `video/out/tj02_voice_pick/`，都不进 git）：
  1. `make_spec.py` 按 `episode.json` 的 cast 描述和剧本里的语气，列出 3 个默认声音 + 4 个语气变体（魏文侯@坚定干脆、虞人@小声自言自语有点失望、虞人@又惊又喜激动、大臣@语气疑惑不解有点着急），写 `spec.json`；
  2. `gen_cands.py spec.json cands 8`（`.venv-tts`，约 35 分钟，放后台）：每个声音用 VoiceDesign 换种子（起点见 spec，每次加 97）出 8 个候选，不合格自动重抽；
  3. `analyze_cands.py`：每个候选量基频中位数和起伏（`experiments/tts_compare/analyze.py` 的 `f0_track`）、响度、频谱重心、Whisper-small 转写字错率、说话人向量；`f0spread.py` 量基频 5%–95% 范围（防止极端值）；`show.py`、`pairs.py`、`vsim.py` 打印对比表（说话人向量先减去全体均值再算余弦）；
  4. 挑法：男青年 110–140 Hz、男老人 100–150 Hz、男中年约 120–135 Hz；起伏 ≥ 4 个半音；Whisper 转写要全对；默认声音要和司马光（116 Hz）及另两个新角色的说话人余弦接近 0（不像）；语气变体要和默认参考音基频相近、余弦高、转写对，「小声」要比默认参考音轻 5 dB 以上，「惊喜」不能飘到 200 Hz 以上（像女声）；`install_picks.py` 把挑好的候选装进 `video/assets/audio/voices/`（wav + json，格式同 voice.py 的 write_metas，`pick` 写原因）；
  5. 第 1 轮挑了虞人@又惊又喜激动 #5（参考音 126.8 Hz），念出整句后基频在 74–280 Hz 之间来回跳，换成 #7（148.4 Hz，范围 101–220 Hz）；其余 6 个一次过。
  6. 整集念完后：`asr_timeline.py video/out/tj02_voice <输出.json> small`（`.venv-tts`）用 Whisper 转写每一句；`line_f0.py` 量每句的基频；`forced.py` 用 Whisper 强制解码给「读音相近的几个字」打分（查多音字：同一段音频，比「虽乐」「虽勒」和「虽月 / 越 / 悦」谁的对数似然更高）。
