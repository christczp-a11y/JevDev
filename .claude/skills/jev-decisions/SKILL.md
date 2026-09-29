---
name: jev-decisions
description: JevDev 仓库里怎么用 Jev（TypeSafe System One）帮忙做决定：剧本打分、候选挑选（古今对照、「考你」题、金句、标题、封面文字）、分镜表逐镜语义检查、评论分类。凡是工作流里写着「Jev」的步骤，先读这个。
---

# 在 JevDev 里用 Jev 做决定

Jev 是 TypeSafe 的 System One 模型：给它一段文字和几个问题，它直接回答数值（打分、是 / 否的概率、选项的概率），不写长文。它便宜、快，适合**批量比较和把关**。创作还是 Claude 来做。
TypeSafe 的官方用法和 API 细节看插件 skill `typesafe:typesafe-ai`（`.claude/settings.json` 已启用）；本文件只写这个仓库的约定。

## 怎么调用
- 统一用 `jevdev/jev.py`：`jev.ask(state, questions)` 返回 `(answers, usage)`；`jev.flatten(answers)` 把答案展开成数值。模型固定为 `jev-1.13.0`。
- key 从环境变量 `TYPESAFE_API_KEY` 读取。Git Bash 里这样设：`export TYPESAFE_API_KEY=$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User')" | tr -d '\r')`。**不许把 key 写进文件或打印出来。**
- Python 用 `.venv/Scripts/python`，设 `PYTHONIOENCODING=utf-8`。
- 同一段文字的问题一次问完：它们并行回答、互相看不到答案，更省钱。

## 出题的规矩（踩过的坑）
- score 题的 `criteria` 必须是**列表**，从低到高排；写成字典会报 422（PITFALLS E6）。
- 两两比较**正反顺序各问一次**，取平均，消掉「先出现的占便宜」。
- 新题目先放一两个**故意很差的对照项**进去：对照项排不到最后，就说明题目有问题，先改题再用。
- 问题要写完整：题目的 id 不会发给 Jev，意思全靠题干和选项。
- 阈值（比如闸门 < 0.5）先在我们自己的例子上试过再定，不照搬。
- 评分标准存成数据：`rubrics/*.json`（剧本用 `story_v2`）。改题不用改代码；新旧版本的分数不混在一起比。

## 仓库里用到 Jev 的地方（工作流对应的步骤）
| 步 | 做什么 | 工具 |
|---|---|---|
| 2 剧本 | 候选剧本打分、两两比较、三道闸门（史实、儿童不宜、两代人对立） | `video/story.py` |
| 2 剧本 | 从候选里挑古今对照、「考你」题、金句 | `video/jev_pick.py`（施工 C 做） |
| 4 分镜表 | 逐镜检查：画面主体是不是台词说到的人；孩子看不看得懂；有没有吓人的东西；梗是不是孩子的梗 | `video/motion/storyboard_jev.py`（施工 C 做） |
| 9 发布 | 标题和封面文字：孩子更想点、家长更想转，两两比较挑出第一 | `video/jev_pick.py` |
| 9 复盘 | 评论分类：看懂了、没看懂、想看下一集、有意见 | `video/jev_pick.py classify` |

没有 key，或者连不上 api.typesafe.ai，脚本要立刻报错退出，不许静默跳过（PITFALLS P8）。
