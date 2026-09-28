# PROGRESS — 当前进度

> 最后更新：2026-09-28（已在云端会话；装机用 `bash scripts/cloud_setup.sh`，渲染已跑通；Jev 还不能用：key 和网络要开新会话才生效）

## 当前阶段：儿童历史动画「资治通鉴」第 1 集（徙木立信）
- 剧本定稿 N5：`video/stories/ep01/N5_最终.json`（讨论和决策见 `docs/讲故事-方法与决策.md`）
- 画风：纸艺立体书 + 横版闯关 + Q 版（Chris 认可）；资源集中在人物动作上
- 人物：纸偶关节动画 `video/puppet.js`。小伙已完成侧面（`video/assets/rig/youth`）+ 45° 半正面（`youth_q`）两套、五种手形；前臂和手合成一张（改了原图要重跑 `video/merge_limbs.py`）
- 测试片段：`video/scenes/test_puppet_youth.json`（19 秒）。最后一轮合理性复查 13/17 通过，剩下 4 处都在「抱木杆」这一段
- 每集必做：`video/logic_qa.py` 合理性复查（Chris 的要求）；动作改动用 `video/motion_qa.py` 做改前 vs 改后

### 下一步（按顺序）
0. ✅ Chris 认可第四轮测试片段（旗杆、手腕、脚踝、捧金子的双臂）。Jev 质检还没跑（云端 key 未生效）：新会话里补跑 `video/motion_qa.py`（改前 vs 改后）和 `video/logic_qa.py`
0.5 ✅ Chris 确认标题「一根木头 / 怎么让秦国人开始相信？」和开场「同学之间的约定」
0.6 【等 Chris】放行 auth.openai.com、chatgpt.com、api.openai.com，然后开新会话 → 跑 `codex login --device-auth`，把网址和验证码给 Chris，他在自己的设备上确认 → 在云端用 Codex 画 8 个新角色的纸偶
0.7 【等 Chris】配乐方案（见 log 2026-09-28）：推荐 ElevenLabs（音乐和 9 种中文配音可以用同一家，需要付费和 API key）+ Claude 按剧本写每段的配乐说明 + Jev 从几个候选里挑；不花钱的备选是本地开源模型 ACE-Step（要看本地有没有 NVIDIA 显卡）
1. 【等 Chris】看 `test_puppet_youth.mp4`：接不接受「抱在腰前」代替「扛在肩上」（Q 版扛肩一定横过下巴）；45° 视角和手部动作方向对不对
2. 收尾抱杆段（复查剩下的 4 处）：远侧前臂和手画到木杆前面（上臂仍在身体后面）；木杆带一点下垂弧度；抱着时后仰更明显；放杆时杆头要真正着地
3. 其余角色做纸偶（侧面 + 45° 各一张 Codex 部件图，astra low）：商鞅、小豆子、爹、大婶、现代小孩、同桌、司马光、两位老师 ——**Codex 只能在本地跑**，云端先做别的
4. 按 N5 搭完整第 1 集：新场景（现代教室）、三关信用值 HUD、解锁徽章、商鞅抛金、群众反应、下集预告；跑合理性复查
5. 第 4 轮：声音（9 种配音 + 音乐，找可商用的开源中文语音合成）；第 5 轮：运营

## 美食赛道（2026-09-27 暂停：图片版权）
暂停时的状态：
工作流 v2 完成：「10 个 Skill」的规则已用 Jev 在赛道数据上检验，验证过的写进了写作规则和选稿复合分（总结见 `docs/小红书爆款工作流.md`）。
**等 Chris 同意后用「仅自己可见」试发第一篇**，新草稿包是 `data/posts/20260927-0239_HK-BBQ-Master-Richmond-BC`。发之前请 Chris 看一下正文里「只收现金」这句。
赛道：温哥华美食推荐。账号：rednote 海外新号「小红薯6AB9FF32」（0 笔记）。
长期目标：Claude + Jev 的自媒体爆文辅助网页工具（小红书 → IG / TikTok）。

## 怎么跑（新会话先看这里）
1. 启动小红书 MCP：`C:\Users\Chris\xhs\bin\start-mcp-rednote.cmd`（端口 18060；这是改装版，支持 rednote）
2. 生成一篇（约 4–7 分钟）：
   `.venv/Scripts/python scripts/make_post.py --query "<英文店名 城市>" --name "<写进笔记的店名>" --xhs-keyword "<中文店名>" [--my-notes "..."] [--photos <实拍文件夹>] [--no-reddit]`
   （没给 --photos 就用 Codex 画插画当封面主图；已有草稿包补图或换图：`scripts/add_image.py <草稿包> [--photos 文件夹]`）
   → 草稿包在 `data/posts/<时间>_<店>/`（package.json + card_*.png）
3. 预览 / 发布：`.venv/Scripts/python scripts/publish.py <草稿包> [--yes] [--public]`（默认仅自己可见；不加 --yes 只预览）
4. 数据：`scripts/collect_xhs.py`（采集赛道笔记）、`scripts/track.py`（第 1/3/7 天追踪）
5. 自我优化（每 1–2 周）：`scripts/covers.py --download --describe`（封面转文字）→ `scripts/autoresearch.py --rounds 2`（Claude 提题、Jev 作答、交叉验证去留）→ `scripts/composite.py --build --eval`（重建选稿复合分）；`scripts/rule_catalog.py` 输出所有题的逐条检验总账。留出测试集只在最后看一次（`autoresearch.py --final`）
- 需要：环境变量 `TYPESAFE_API_KEY`（Jev）；`claude` CLI 已登录（写稿，Opus 5.5）；Codex CLI 已登录（Reddit）；Google 专用 Chrome 配置已登录小号（`scripts/open_google_profile.cmd`）
- Git Bash 里 export key（PEXELS_API_KEY 同理）：`export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`

## 已完成
- [x] 记忆系统、产品方向、执行计划；切换到本地会话
- [x] 决策：赛道、发布闸门、MCP 自动发布（Chris 接受风险）、互动由 Chris 手动完成、Google 抓取、Reddit 走 Codex（见 DECISIONS）
- [x] 小红书 MCP 改装支持 rednote（v2.5.5 + PR #798，本地编译）；Codex CLI、claude CLI（2.1.283）已登录
- [x] 外部调研 `docs/research/爆文逻辑-外部资料.md`；养号流程 `docs/新号养号流程.md`
- [x] 阶段 1 初步结果 `docs/research/阶段1-初步结果.md`：「最新」子集 Jev 标题 Spearman ≈ +0.28（n=75，不足以下结论）
- [x] 数据：179 篇赛道笔记（60 篇有详情和发布时间），SQLite `data/jevdev.db`
- [x] 流水线 `scripts/make_post.py`：Google（50 条）+ 小红书（笔记 + 评论）+ Reddit（Codex）→ Jev 逐条判断 → 画像（`jevdev/restaurant.py`）→ Claude 写 4 篇（`prompts/xhs_writer.md`）→ 逐句核查（`rubrics/claim_check_v1.json`）+ 禁用词 → Claude 只改问题句 → Jev 闸门和质量（`rubrics/draft_v1.json`）+ 标题预测 → 80/20 选稿 → 渲染卡片（自动适配）
- [x] 第一篇：明家烧腊《明家烧腊4.3分，名气和味道对得上吗》→ `data/posts/20260927-0028_HK-BBQ-Master-Richmond-BC`（4/4 过审）
- [x] 「10 个 Skill」调研：66 条候选规则（`docs/research/10个skill-提取.md`）
- [x] 自动研究（照 TypeSafe 的 autoresearch cookbook）：398 篇笔记和封面，3 轮；大回归在测试集上过拟合 → 改用复合分（21 条规则，测试集 +0.29 [0.10, 0.46]）
- [x] 写作规则 v2（标题要有好奇缺口、不能写成名词堆砌；正文 350–700 字；标题承诺要兑现）+ 选稿改用复合分（`jevdev/engagement.py`）
- [x] 明家烧腊按 v2 重跑：《列治文这家烧腊店，你可能排错了队🤔》→ `data/posts/20260927-0239_HK-BBQ-Master-Richmond-BC`（4/4 过审，复合分平均 −0.04 → +0.43）

## 下一步
- [ ] 【等 Chris】仅自己可见试发 → 检查图片、话题、AI 标注（MCP 可能勾不了「AI 生成」声明，靠正文末行标注）
- [ ] 发布后拿到自己笔记的 note_id，写入 notes（is_ours=1），接上 track.py
- [ ] 选店候选池（每天 1–2 家；来源：赛道笔记里出现的店 + Chris 推荐）
- [ ] 定时任务（Windows 任务计划程序）：MCP 常驻 + 每日 make_post / track / collect（改系统配置前先问 Chris）
- [ ] 阶段 1 扩样本：同龄追踪积累「第 7 天互动」→ 用新数据做一次干净的复合分检验（测试集已经看过两次）
- [ ] 【等 Chris 决定】要不要用 MCP 查作者粉丝数（284 个作者主页），控制大号效应
- [ ] 【等 Chris】亲自去吃，用 --my-notes 写入体验（数据显示「真人亲历感」和互动正相关，我们不能冒充）；封面实拍图 vs 文字卡做 A/B
- [x] 配图：封面优先级 = 实拍（--photos）→ 图库实物抠图（Jev 选图，亮黄底爆款模板）→ Codex 插画 → 纯文字；`scripts/add_image.py` 可以给已有草稿包补图或换图；断行和页脚孤字已修
- [ ] 【等 Chris】真实店铺照片：自己去拍，或在 Tourism Richmond Media Hub（CrowdRiff）申请授权图（申请文案见 2026-09-27 的会话）；拿到后运行 `scripts/add_image.py <草稿包> --photos <文件夹> [--photo-credit 出处]`
- （Pexels 图库和写实 AI 图都被 Chris 否决：不是这家店的实物）

## 儿童历史动画（已完成）
- [x] 第 3 版画面（Chris：好）；讲故事（Chris：差）→ 剧本讨论两轮，定稿 N5；Chris 已定：约 2 分钟、加下集预告；标题和开场待确认，系列格式调试后再定
- [x] 纸偶关节动画（小伙）：Jev「改前 vs 改后」扛木杆段全面胜出
- [x] Chris 第二轮反馈（直手扛杆、城墙接缝、只有侧面、手不够细）→ 合理性复查工具、五种手形、45° 视角、无缝城墙、抱在腰前；复查从 9/17 有问题降到 4/17
- [x] 已经在画面里的史实修正：7 米木杆、金块代替方孔钱

## 阻塞 / 待 Chris 处理
- [ ] 云端 Jev 还不能用：当前容器没有 `TYPESAFE_API_KEY`，api.typesafe.ai 也被拦 → 确认环境设置已保存，然后开一个新会话（设置只对新容器生效）
- [ ] 同意试发（仅自己可见）
- [ ] 改掉已出现在聊天里的凭据：TypeSafe key（控制台作废重建）、Google 小号密码
- [ ] 可选：在手机上手动互动，每天在 `data/养号日志.csv` 记一行

## 已知问题
- MCP 的 search_feeds 偶尔超时（context deadline exceeded）→ make_post 会重试一次，再失败就改用缓存
- 小红书采集的「最新」排序偶尔超时；collect_xhs 失败的组合下次自动补
- 51 篇笔记的详情页打不开（「无法获取初始状态数据」），可能是 xsec_token 过期了；有正文的样本只有 136 篇
- 自动研究的 39 题回归只用来发现规则，不用来选稿（它在测试集上过拟合）
