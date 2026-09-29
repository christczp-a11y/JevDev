# tj01 第 0 步：改代码前的基线（ep01v2）

> 用途：工作流第四节末尾「第 0 步过关条件」第 1 条。第 0 步改代码之前，先在试做集 `ep01v2` 上跑 `layout_qa`、`build_stage3d.py qa`、`frame`，结果记在这里。改完代码，用新的按集写法重跑，**结果要和这份一致**（下面「以后怎么对比」）。
> 必须是 .md：`video/stories/tj01/` 里的 .json 会被 `story.py` 当剧本读。
> 记录日期：2026-09-29（本地）。

## 代码状态

- 命令开跑时的提交：`1f08d0049189d028b39b46b87bb6a17e1564e9cf`（`git rev-parse HEAD`）。
- 跑的过程中主会话又提交了几次（收尾时 HEAD 是 `9b1575021faa62b68c6acee48564924418637c04`）。`1f08d00` 到 HEAD 之间改的是 `memory/PITFALLS.md`、`rubrics/story_v2.json`、`video/story.py`、`logic_qa.py`、`motion_qa.py`、`source_check.py`、`video/stories/` 下的 N6 剧本和 tj01 的 `source.md`、`status.md`；渲染和质检相关的文件（`video/engine.html`、`puppet.js`、`render.py`、`layout_qa.py`、`stage3d/`、`sets/`、`scenes/`、`assets/`、`audio.py`）没有任何差别（`git diff --name-only 1f08d00 HEAD -- <这些路径>` 没有输出）。所以这份基线对应的渲染和质检代码就是 `1f08d00` 时的样子，一直没变。
- 跑的时候工作区里还有别人没提交的改动（`video/story.py`、`video/logic_qa.py`、`video/motion_qa.py`、`video/qa.py` 等）。三条命令都不读它们；命令用到的文件在工作区里和 `HEAD` 一致（`git status` 里没有它们）。
- 环境：Git Bash，`export PYTHONIOENCODING=utf-8`，`.venv/Scripts/python`（Python 3.14.3），本地 Playwright 自带的 Chromium。**渲染写死 CPU（`--use-angle=swiftshader`），`--gpu` 还没接，这次没有用显卡。**

## 三条基线命令

在仓库根目录、Git Bash 里跑（`shot*.json` 通配符只能在 Git Bash 里展开）。

### 1. `layout_qa`

```
.venv/Scripts/python video/layout_qa.py video/scenes/ep01v2/shot*.json
```

- 退出码：**0**；耗时 27 秒。
- 问题条数：**0**。六场都是「没有站位错误」：`shot1.json` 到 `shot6.json`。
- 完整日志：`video/out/tj01/logs/step0_baseline_layout_qa.log`。

### 2. `build_stage3d.py qa`

```
.venv/Scripts/python video/stage3d/build_stage3d.py qa
```

- 退出码：**0**；耗时 363 秒（约 6 分钟）。
- 问题条数：**0**。输出「穿帮质检：没有问题」。
- 说明：不带场号，查的是写死的试做集镜头表（6 场，每个故事镜头抽开头、中间、结尾 3 帧）。
- 完整日志：`video/out/tj01/logs/step0_baseline_qa.log`。

### 3. `build_stage3d.py frame`

```
.venv/Scripts/python video/stage3d/build_stage3d.py frame
```

- 退出码：**1**；耗时 1056 秒（约 17.6 分钟，超过 10 分钟，所以放后台跑）。
- 问题条数：**1**。
  1. 第 1 场 42.9–42.9s，「被前面的东西挡住」，`shangyang`（fit 镜头）。那一段镜头表是 `[42.4, 45.3, "fit", {"ids": ["youth", "shangyang"]}]`（小伙：我来！），只有一个采样点（42.9 秒）报了。
- 输出原文：
  ```
    第 1 场 42.9–42.9s [被前面的东西挡住] shangyang（fit 镜头）
  入画质检：1 处
  ```
- 完整日志：`video/out/tj01/logs/step0_baseline_frame.log`；退出码和耗时：`video/out/tj01/logs/step0_baseline_frame.rc`。
- 这是试做集原来就有的问题，不是这次改动带来的。基线要记的就是「1 处、退出码 1」。

## 复跑确认（frame 第 1 场）

为确认这 1 处不是偶然，把第 1 场单独再跑了一次：`.venv/Scripts/python video/stage3d/build_stage3d.py frame 1`，退出码 **1**，耗时 616 秒，输出和整集那次完全一样（同样只有「第 1 场 42.9–42.9s [被前面的东西挡住] shangyang（fit 镜头）」1 处）。结果可复现。日志：`video/out/tj01/logs/step0_baseline_frame_rerun_shot1.log`。

## 顺带跑的其他命令

三条命令在同一个环境下，另外跑了系列参考帧的截图（第 0 步第 4 项），都退出码 0：

| 命令 | 退出码 | 耗时 | 日志 |
|---|---|---|---|
| `build_stage3d.py stills 1 1.5 6.5 20` | 0 | 27 秒 | `video/out/tj01/logs/step0_baseline_stills1.log` |
| `build_stage3d.py stills 4 10 13.9` | 0 | 19 秒 | `video/out/tj01/logs/step0_baseline_stills4.log` |
| `build_stage3d.py stills 6 5` | 0 | 15 秒 | `video/out/tj01/logs/step0_baseline_stills6.log` |

产出在 `video/assets/ref/series/`（6 张 + README.md）。

## 以后怎么对比

第 0 步改完代码（`build_stage3d.py` 加了集名参数、`layout_qa` 参数化等）以后，用新写法在 `ep01v2` 上重跑同样三项，和上面比：

| 项 | 基线 | 改完后要一致 |
|---|---|---|
| `layout_qa`（六场） | 退出码 0，0 条 | 退出码 0，0 条 |
| `qa`（新写法，集名指向试做集 `ep01v2`） | 退出码 0，0 处穿帮 | 退出码 0，0 处穿帮 |
| `frame`（新写法，同上） | 退出码 1，1 处：第 1 场 42.9–42.9s 被前面的东西挡住 `shangyang` | 退出码 1，还是这 1 处，场号、秒数、人物、类型都一样 |

- 多了或少了任何一条，都要说明原因（改了检查规则就写出来；没改检查规则却变了，就是引入了问题）。
- 如果第 22 项的新检查（镜长、朝向、放大倍数……）在试做集上报出新的问题，那是新检查抓到的旧毛病，要和这三项的「原有问题」分开写，不算不一致。
- 时长参考：`qa` 约 6 分钟、`frame` 约 17.6 分钟（CPU 渲染）。`frame` 要后台跑。
- 参考帧的对比（第 0 步过关条件第 3 条）：用同样的秒数重截，和 `video/assets/ref/series/` 并排比界面层。

## 没有的输入

- `video/out/ep01v2/ep01_full.mp4`（试做集 2D 成片，3D 版的声音借它）本地没有；`video/out/ep01v2/` 目录都不存在。三条基线命令和 `stills` 用不到它，不影响这份基线。它只影响 `build_stage3d.py render` 和第 0 步第 15 项（独立混音）的「用新的独立混音把 ep01v2 的声音混一遍」那条过关条件：那一条要先渲 2D 才有得比，或者由主会话决定怎么处理。
