# 动态漫画合成器（video/motion/）

读 `video/stories/<集>/storyboard.json`，出竖屏 1080×1920、每秒 30 帧、带配音 / 音效 / 背景音乐的成片。
画面 = Codex 画的插画；「动」= 这个合成器（镜头运动、人物小动作、特效叠层）。不用浏览器、不用显卡。
设计依据：`docs/施工计划-动态漫画引擎.md`、`docs/规则/节奏和特效.md`、`docs/规则/版式和画风.md`、`docs/workflow/7-成片检查.md`。
17 秒小样（`_prototype_mc.py`，写死了镜头）已经用分镜表重做：`tests/proto17/storyboard.json`。

## 用法

Git Bash，仓库根目录，Python 用 `.venv/Scripts/python`，设 `PYTHONIOENCODING=utf-8`。

```
python video/motion/render.py tj01                  整集（1080×1920，crf 20）
python video/motion/render.py tj01 --preview        半分辨率 540×960，快
python video/motion/render.py tj01 --final          发布版：高码率（crf 14）、慢编码（preset slow）、音频 256k
python video/motion/render.py tj01 --shots 1-1,1-2  只渲、拼、混这几镜；时间线按镜头裁，台词比画面长也不会崩（PITFALLS A6）
python video/motion/render.py path/to/storyboard.json ...      直接给分镜表路径
```
其它参数：`--jobs N`（并行进程数，默认 CPU 数 − 1）、`--out 目录`（默认 `video/out/motion/<集>/`）、`--cache-dir 目录`（默认 `video/out/motion/_cache`）、
`--no-cache`（选中的镜头不用缓存重渲）、`--frame-hashes`（报告里写每一帧的哈希，测试可复现用）。

输出：`<out>/<集>[_preview|_final][_shots_1-1+1-2].mp4`、同名 `.wav`（混好的音轨）、同名 `.report.json`（自动检查报告）。

**退出码**：0 = 出片成功、自动检查全过；1 = 出了片但自动检查没过（闪烁、静止、响度、人声，报告里写明）；2 = 输入有错，没有出片。
输入有错包括：找不到字体（`video/vendor/fonts/`，不许退回系统字体）、找不到背景音乐 `video/assets/audio/bgm_main.mp3`、找不到图片 / 音效 / 配音文件、
锚点对不上、拼错的字段、不存在的特效 / 转场、字体里没有的字。**所有能查的错一次列完**再退出。

**速度**（本机 12 核，无显卡，2026-09-29 实测）：17 秒小样预览 13 秒（每 30 秒成片约 22 秒）；172 秒（60 个镜头）预览 64 秒（每 30 秒成片 11 秒）、
整集高清 251 秒、`--final` 318 秒。验收线：预览每 30 秒成片 ≤ 60 秒，整集高清（约 3 分钟）≤ 15 分钟。二次渲染没变的镜头直接用缓存，只剩混音和拼接编码。

## 一个镜头怎么排

- 每个镜头从自己的 `from` 开始，到**下一个镜头的 `from`** 结束（中间没有空隙）；第一镜从第 0 帧开始；最后一镜到它的 `to`（省略 = 到时间线结束）。
  `to` 写了但比下一镜的 `from` 早，中间就是「停住」（镜头继续走），晚于下一镜的 `from` 是错（两镜重叠）。
- 每个镜头渲一次，缓存起来（`video/out/motion/_cache/<哈希>/`）：镜头内容、用到的图（内容哈希）、锚点解析出来的时间、引擎和特效插件的源码、字体、渲染比例，任何一样变了才重渲。
  改台词、重新配音：只有时间变了的镜头重渲；字幕、标题条、水印、转场不进缓存，永远是最新的。
- 每个镜头一个进程并行渲；随机数固定种子，同样输入每一帧都一样（`tests/test_render.py` 每次测：两次从空缓存渲，每一帧的哈希、成片的 framemd5 都一致）。

## 时间锚点

时间一律锚在配音时间线（`voice.py` 写的 `timeline.json`）上，不写死秒数：

```json
{"line": 1, "word": "给", "nth": 1, "dt": -0.3}
```
| 写法 | 意思 |
|---|---|
| `{"line": 3}` | 第 3 句的开头（`t0`；句子从 0 数） |
| `{"line": 3, "word": "输"}` | 这个词第一个字开口的时刻；`nth` 是第几次出现（默认 1） |
| `{"line": 3, "dt": 0.5}` | 再偏移 0.5 秒（可以是负数） |
| `{"dt": 0.5}` | 没有 `line` = 相对**本镜头开头** |
| `to` 里的 `{"line": 3}` / `{"line": 3, "word": "输"}` | 表示结束的地方：这一句的结尾 `t1` / 这个词最后一个字说完的时刻 |

字级时间：Qwen3-TTS 不给字级时间，合成器把这一句的有声部分（`t0 + 0.08` 到 `t0 + voiced_end`）按字数（去掉标点）平均分。锚到某个字的误差约 0.1–0.2 秒。
锚点只认 `line / word / nth / dt`，多写一个字段、`line` 越界、`word` 找不到都直接报错。

## 分镜表字段

```json
{
  "episode": "tj01", "no": 1,
  "title": ["最强的智伯，", "为什么输了？"],
  "voice": "video/out/tj01_voice",
  "speakers": {"智伯": "智家", "段规": "韩家"},
  "shots": [ ... ],
  "rituals": [{"type": "kaoni", "at": {"line": 1}, "options": ["给", "不给"]}]
}
```
- `title`：1–2 行，做顶部标题条。`no`：第几集；`name`：本集名（标题条上面的小字「第 N 集 · <本集名>」，不写就只有「第 N 集」；系列名只在右上角水印里出现一次）。
- `bgm_start`（可选）：背景音乐从第几秒开始放（默认 0；样片合集避开音乐里的空拍用）。
- `voice`：配音目录（里面有 `timeline.json`），先按仓库根目录找，再按分镜表所在目录找。
- `speakers`：说话人 → 家名（`video/series_style.json` 的 `houses`）或 `#rrggbb`，用来给字幕上的说话人标签上色。司马光固定红色、旁白固定灰褐色；不在表里的用旁白色。
- `rituals`：系列仪式（考你、人物卡……），每一项就是一个特效（`type` 是特效名，`at` 是锚点），交给它开始那一刻所在的镜头去画。特效本身是阶段 B 的事。
- 可以加 `note` / `notes` 写备注（引擎不看）。顶层和镜头里出现别的字段都会报错，防拼错。

### 镜头

| 字段 | 说明 |
|---|---|
| `id` | 镜头编号，唯一（`--shots` 按它选） |
| `from` / `to` | 见上面「一个镜头怎么排」 |
| `size` | 景别（wide / medium / close）：只是标记，给检查工具用 |
| `bg` | 背景图层列表，先写的在下面（远的在前） |
| `actors` | 人物列表，画在 `bg` 之上、`fg` 之下 |
| `fg` | 前景图层列表，画在人物之上（案几、书页边、界面卡片……）。字段和 `bg` 一样 |
| `camera` | 镜头运动列表（见下）。没有推 / 拉 / 摇的镜头自动加一个缓推 |
| `fx` | 特效列表，每项 `{"type": 特效名, "at": 锚点, ...参数}` |
| `sfx` | 音效列表，`{"name": 音效名, "at": 锚点, "gain": 增减 dB}`，名字对应 `video/motion/sfx/<名字>.wav` |
| `grade` | 调色：`normal`（默认）/ `warm` / `gold` / `cool` / `memory`（旧纸黄 + 颗粒 + 暗角）/ `tense`（稍暗 + 暗角，不用血红） |
| `transition` | 本镜怎么「进来」：`"cut"`（默认）/ 转场名 / `{"type": 转场名, "dur": 秒, ...}`（第一镜不用写） |
| `note` | 备注 |

### 图层（`bg` / `fg`）

`{"img": "sets/jin_land/sky.png", "depth": 0.1, "pos": [0, 0], "w": 1080}`

| 字段 | 说明 |
|---|---|
| `img` | 相对 `video/assets/` 的路径（找不到再找分镜表所在目录）；找不到直接报错 |
| `pos` | 锚点在设计坐标（1080×1920，原点左上）里的位置 |
| `anchor` | 图上的锚点比例，默认 `[0, 0]`（左上角）；`[0.5, 1]` = 底边中点 |
| `w` / `h` / `scale` | 屏幕上多宽 / 多高 / 相对原图的倍数，三选一；不写 = 原图大小。显示 ÷ 原图 > 1.3 会警告 |
| `depth` | 视差系数：0 = 钉在屏幕上（界面、卡片），0.1–0.3 远景，0.5–0.8 中景，1 = 主体，1.2–1.4 前景。默认 1 |
| `flip` / `blur` / `alpha` | 水平翻转 / 高斯模糊半径（设计像素，特写背景用）/ 不透明度 |
| `repeat` | `"x"` = 左右无缝重复（地面、水、城墙长条；摇镜不会露边） |
| `sway` | `{"x": 28, "y": 8, "period": 3.7, "phase": 0}`：水面这类慢慢晃 |
| `enter` | 出场，见下 |
| `anim` | 补间，见下 |

### 人物（`actors`）

`{"id": "sgm", "who": "司马光", "img": "chars/sgm_finger.png", "pos": [235, 1585], "h": 520, "flip": false, "enter": "pop", "acts": [...]}`

- `pos` 是**脚底中点**，`h` 是屏幕上多高（像素）；`flip: true` 水平镜像（朝向按 REGISTRY 登记的原图朝向算，只在要反过来的时候写）；`depth` 默认 1。
- `who`：时间线里这个人的说话人名（默认 = `id`）。**说话的人**随句子轻轻上下起伏 3 像素；没说话的人呼吸（高度 ±0.8%）。旁白不属于任何人物。
- `enter`（字符串或 `{"type", "at", "dur", "sfx"}`；`at` 省略 = 镜头开头；出场之前看不见）：
  `pop`（从脚底弹出，带过冲）、`slide_left` / `slide_right`（从画外滑进来，带过冲）、`drop`（从上面掉下来，落地弹跳）、`flip`（翻纸片）、`fade`。人物出场自动配 `pop` 音效（`"sfx": null` 关掉）。
- `acts`：`[{"at": 锚点, "do": 名字}, {"at": 锚点, "swap": "chars/xx.png"}]`
  - `swap`：换表情 / 换姿势（新图按同样的 `h`，也可以写 `"h"`），自动配一个小弹跳和 `pop` 音效（`"bounce": false` / `"sfx": null` 关掉）。
  - `do`：`bounce`（小弹跳，可写 `amp`）、`jump`（大跳）、`nod`（点头）、`shake`（摇头）、`wobble`（晃）、`pop`（放大一下）、`exit`（走出画面，`"dir": "left" | "right" | "down"`）。都可以写 `dur`。

### 补间（`anim`）

任何图层 / 人物都能写：`"anim": [{"at": 锚点, "dur": 0.5, "ease": "smooth", "pos": [760, 690]}]`。每一段从「这一刻的当前值」补到目标值，按 `at` 排序依次生效。
目标可以是 `pos`（绝对位置）/ `dpos`（相对位移）/ `scale` / `sx` / `sy` / `alpha` / `rot`（度，顺时针）。缓动 `ease`：`smooth`（默认）/ `linear` / `out` / `in` / `back`（过冲）/ `bounce`。

### 镜头运动（`camera`）

参数照《节奏和特效》第三节，常量在 `engine/consts.py`。所有运动默认用 smootherstep，起步收尾都柔和；每一项都可以写 `at`（锚点）和 `dur`（秒），`push / pull / pan` 不写就是整个镜头。

| `move` | 参数 | 说明 |
|---|---|---|
| `push` / `pull` | `amount`（默认 0.05，范围 3–8%） | 缓推 / 缓拉。**没有 push / pull / pan 的镜头自动加 `push 0.05`**（不想要就写 `{"move": "push", "amount": 0}`，但那样画面会静止，检查会报） |
| `pan`（别名 `move` / `track`） | `dx`、`dy`（设计像素；`dx > 0` = 镜头往右，画面往左走） | 摇 / 移；最快每秒超过画面宽度的 15% 会警告 |
| `punch` | `at`、`amount`（默认 0.10，范围 8–15%）、`keep`（默认 0.5） | 冲击推：0.15 秒放大，再用 0.3 秒回弹一半 |
| `shake` | `at`、`dur`（0.25–0.4）、`amp`（像素，≤ 画面宽度的 1.5%） | 震屏，二次衰减 |
| `whip` | `at`、`dir`（left / right / up / down = 画面滑动的方向）、`mode`（`in` 从旁边甩进来 / `out` 甩出去）、`dur`（0.2）、`dist` | 甩镜：位移加运动模糊 |
| `frame` | `zoom`、`dx`、`dy` | 固定取景（不动）：特写把画面放大到 1.3 倍再推，就是 `frame` + `push` |

再加**呼吸漂移**：所有镜头永远有（振幅 4 像素、周期 4 秒，按整集绝对时间算，切镜头不断），防止画面「死」。

## 自动加上去的东西（分镜表里不写）

- **顶部标题条**（y 90–330）：`title` 两行大字（ZCOOL KuaiLe）+ 上方小字「第 N 集 · <本集名>」，整集都在；**水印**「光爷爷的资治通鉴大冒险」右上角。
- **字幕**（中心 y≈1480）：米色纸卡、墨色粗体（Noto Sans SC Bold）；上方**说话人标签**（司马光红色、旁白灰褐色、其他人家族色）。每行最多 15 字、每页最多 2 行；台词更长就按标点分页，页与页的分界按字数比例落在有声部分里。
  出现的帧 = 这一句 `t0` × 30 取最近的整数帧（差 ≤ 0.5 帧），淡入 3 帧、淡出 3 帧。
- 字体只有两种：ZCOOL KuaiLe（标题、砸字、贴纸字）和 Noto Sans SC Bold（其余）。ZCOOL 没有的字逐字用 Noto 补，两种都没有的字报错。
- 界面画在转场之后，转场不会把标题条和字幕一起带走。

## 声音

配音（最响）→ 音效 → 背景音乐（`video/assets/audio/bgm_main.mp3`，不够长就交叉淡入淡出循环）。全部在绝对时间轴上用 numpy 摆，再按输出的镜头范围切出来。

- 每句配音先调到同一个有声部分 RMS（−21 dBFS，最多调 ±8 dB），不同角色的音量拉齐。
- 背景音乐调到和配音同样的 RMS 再降 13 dB；**有人说话时再压 10 dB**（提前 0.06 秒压、攻击 0.08 秒、释放 0.6 秒、字与字之间小于 0.35 秒的停顿不放开）。片头淡入 0.6 秒、片尾淡出 1.5 秒。
- 音效来源：分镜表 `sfx`、特效登记的默认音效（例如 `sticker` → `pop`）、人物出场 / 换表情自动的 `pop`。
- 最后整体调到 **−16 LUFS**（ffmpeg ebur128 量，容差 ±1 LU），带前瞻限幅，真峰值 ≤ **−1.5 dB**；报告里的数字是从成片的音轨上重新量的。

## 特效和转场接口（阶段 B 照这个加，不用改 `render.py`）

`video/motion/fx/` 里每个不以下划线开头的 `.py` 都会被自动加载；一个特效 / 转场一个函数，用装饰器登记。**照 `fx/sticker.py`（特效）和 `fx/dissolve.py`（转场）抄。**

### 特效

```python
from engine import anim
from fx import fx

@fx("flash", layer="front", sfx="whoosh", assets=lambda p: [], check=lambda p: [])
def flash(canvas, t, params, at):
    """canvas：画布；t：镜头内时间（秒）；params：分镜表里这个特效的整个字典；at：锚点解析后的时刻（镜头内秒）。"""
    u = t - at
    if u < 0 or u > 0.2:
        return
    canvas.tint((255, 255, 255), 0.5 * (1 - u / 0.2))
```
- 分镜表：`{"type": "flash", "at": {"line": 3, "word": "输"}, ...你自己的参数}`。**引擎每一帧都调用，只要 `t >= at`**（`at` 省略 = 镜头开头）；结束、消失、`dur` 都由函数自己判断，什么都不画就直接 `return`。
- **画布 `canvas`**（`engine/canvas.py`）：
  - `canvas.img`：当前这一帧（BGR uint8，形状 `(canvas.h, canvas.w, 3)`），可以直接读写（做全屏后处理）；`canvas.S`：渲染比例（预览 0.5），直接往 `img` 上画的时候坐标要 × `S`。
  - 坐标一律用**设计坐标**（1080×1920）：`canvas.blit(sprite, x, y, scale=1, sx=1, sy=1, rot=0, alpha=1, anchor=(0.5, 0.5), depth=0)`。`depth` 是视差系数：0 钉在屏幕上，1 跟着画面走（贴在人物旁边的贴纸用 1）。
  - `canvas.xform(x, y, depth)` → `(屏幕 x, 屏幕 y, 放大倍数)`；`canvas.zoom / px / py` 是当前镜头。`canvas.tint(rgb, alpha)` 整幅盖色。
  - `canvas.assets`：`.image(路径, w=/h=/scale=, flip, blur)`（读图，带缓存，路径相对 `video/assets/`）、`.text(文字, "title" | "body", 字号, 颜色, stroke, edge=白纸边宽度)`、`.sticker(路径, 高度, edge)`、`.from_pil(PIL 图)`，返回 `Sprite`，传给 `blit`。
  - `canvas.rng`：numpy 随机数生成器，**每一帧重新播种**（同一帧永远拿到同样的随机数）；**特效里不许用 `random` / `time`**；要「整个特效期间不变」的随机数，用 `anim.seed_of(镜头 id, 特效序号)` 自己造种子。`canvas.fps`、`canvas.dur`（镜头长度）。
- `engine/anim.py`：`smooth`（smootherstep）、`out_cubic`、`in_cubic`、`back_out`（过冲）、`bounce_out`、`clamp`。
- 登记参数：
  - `layer`：`"front"`（默认，人物和前景之上、调色之前）或 `"back"`（背景之上、人物之下，光芒之类）。
  - `sfx`：默认音效名，在特效的 `at` 时刻自动加进混音；分镜表里这个特效写 `"sfx": null` 关掉，写别的名字换掉。
  - `assets(params)` → 这个特效要读的图的路径列表（绝对路径，或相对 `video/assets/`）：出片前检查它们在不在（缺了报错）、内容算进缓存哈希。**读文件的特效必须写这个**，否则图换了缓存不更新。
  - `check(params)` → 错误说明列表（缺字段、名字不对……），出片前调用，空 = 没问题。
    `check` 可以写成 `check(params)` 或 `check(params, shot)`：后一种拿到整个镜头的字典（人物、图层、sfx……），用来查要看整个镜头才知道的错（`flame` 和人物重叠就报错）、记下这个镜头的信息（氛围粒子避开人物的脸：`_avoid`）、或者往镜头的 `sfx` 表里追加音效（`fx/_paper.py` 的 `add_sfx`：sticker 撕掉的 `tear`、stat_card 每颗星的 `star_ding`、kaoni 盖章的 `pop`；出片前 check 在主进程和渲染进程各跑一遍，`add_sfx` 不会重复加）。
    特效画的时候 `canvas.actor_state[人物 id]` 是这一帧这个人物的变换（x、y 脚底点、scale、sx、sy、rot、alpha、flip、depth、wd、hd），sticker 的 follow 就用它。
    `check` 在出片前对每个特效调用一次、音效表在那之后才收集，所以特效可以在 `check` 里往 `params` 补默认的 `sfx`（`fx/_paper.py` 的 `auto_sfx`：分镜表没写才补，写了 / 写 `null` 就不动）；砸字、清单、属性卡按「几下」选 `slam_N` / `list_N` / `stat_N` 就是这样。
- 每个特效画完要能被缓存：**只依赖 `(t, params, at, canvas)`，不许有隐藏状态**（同一个镜头在不同进程里渲，结果必须一样）。
- 字体只有两种，用 `canvas.assets.text(..., "title" | "body")`，不要自己 `ImageFont.truetype` 别的字体。

### 转场

```python
import cv2
from engine import anim
from fx import transition

@transition("dissolve", dur=0.4, sfx=None)
def dissolve(a, b, p, params, canvas):
    e = anim.smooth(p)
    return cv2.addWeighted(a, 1 - e, b, e, 0)
```
- 分镜表：写在**后一镜**里，表示「这一镜怎么进来」：`"transition": "dissolve"` 或 `{"type": "dissolve", "dur": 0.5, ...参数}`；不写 = 硬切。
- `a`：前一镜这一帧，`b`：后一镜这一帧（BGR uint8，形状 `(canvas.h, canvas.w, 3)`，**没有字幕和标题条**）；`p`：0..1 的线性进度（缓动自己在函数里加）；`params`：`transition` 字典；`canvas`：拿 `.assets` / `.w` / `.h` / `.S` / `.rng` 用。返回混好的一帧，不许改 `a`、`b`。
- **转场以切点为中心**：切点前 `dur/2` 是前一镜的收尾，切点后 `dur/2` 是后一镜的开头；两个镜头各自多渲这么长（前一镜的镜头运动继续走，后一镜停在开头的姿势）；配音时间线不动。
  每个镜头长度要装得下前后两个转场，否则报错。
- 登记参数同特效（`sfx` 在切点触发、`assets`、`check`）。

### 音效

`video/motion/sfx/<名字>.wav`，全部程序合成（`sfx/synth.py`：numpy + scipy，钟琴 / 马林巴 / 木琴 + 低通噪声，五声音阶，不刺耳；`python video/motion/sfx/synth.py` 重新生成，结果固定，`.wav` 一起提交）。
全系列同一个特效用同一个声音；每个音效的「重音」按特效的动画时间摆好（特效的音效在它的 `at` 响，转场的在切点响），时间常数在 `sfx/timing.py`（特效和合成共用）。
加新音效：在 `synth.py` 里写一个函数（单声道 44.1 kHz，峰值约 0.5）、登记进 `SOUNDS`，跑一遍脚本。`tests/test_fx.py` 会查每个文件：单声道 44.1 kHz、峰值、头尾没有咔嗒声、10 kHz 以上没有能量。
现有：`pop` `whoosh` `burst` `focus` `slam_1..6` `list_1..6` `stat_open` `stat_row_1..6` `paper_unfold` `city_pop` `draw` `shine` `twinkle` `party` `dust_puff` `rain` `splash` `whoomp` `tone_shift` `flash` `kaoni` `plate_drop` `person_card`
`card_quest` `card_fail` `card_title` `card_mvp` `title_boom` `gauge_pop` `screen_on` `click` `bubble_pop` `page_slide`；
分镜表 `sfx` 里按名字用的：`frog_croak`（蛙叫「呱呱」）、`hmph`（「哼」，短促下滑的低音管音色，不用人声）、`tear`（撕纸）、`light_up`（一样东西亮起来）、`star_ding`（属性卡亮一颗星「叮」，stat_card 自动一颗一声）；转场：`page_flip` `paper_swipe` `brush` `iris` `fade_soft` `whip` `tv_click`。

### 本集专用 / 测试用的插件

分镜表旁边的 `fx/`、`sfx/`（和图片目录）也会被找到（先找系列的，再找这里）：`tests/proto17/` 就用它放了一个倒计时圈特效。正式的集不要用——要加特效，写进 `video/motion/fx/`。
本集插件可以覆盖另一个分镜表旁边的同名插件，但不能和系列插件同名。

## 特效清单（阶段 B）

《节奏和特效》第五节表里的全部特效和转场都在 `fx/`，一个特效一个名字，参数统一：**`at` 是开始的时刻（锚点），`dur` 是停留几秒（不写 = 到镜头结束，最后淡出），`pos` 是设计坐标（1080×1920），`sfx` 写 `null` 静音**。
所有特效的动作都是时间的函数（弹簧过冲、缓动、不抖、不闪），画法是纸的样子：白纸边、柔和纸影、纸纹。样片合集（`tests/fx_reel/`，见下）每个特效演一遍，写特效的参数照着它抄。

**写法约定**
- **写了特效不认识的参数 = 出片前报错**（和分镜表拼错字段一律报错同一个规矩）：每个特效登记时（`@fx(name, params=[...])`）声明自己认的参数，通用的 `type / at / dur / sfx / layer / note` 不用声明；转场同理（`@transition(name, params=[...])`，通用的 `type / dur / note`）。本集专用的插件不声明就不查。
- **每个特效都可以写 `"layer": "back"`**（画在背景之上、人物之下）或 `"front"`（人物和前景之上），覆盖它登记的默认；比如水花画在人物后面。
- **一条特效 = 一个时刻 = 一个声音。** 一步一步出来的东西拆成几条特效，各写各的锚点，就能一条一条卡在台词的字上：地图 = `map` + `map_city`×n + `map_arrow`×m；进度物每变一次写一条 `progress`。
  例外：砸字、清单内部有固定节奏（0.14 + 0.17k 秒 / 0.55 秒一条），音效按「几下」选 `slam_N` / `list_N`；属性卡的行间隔可以用 `gap` 改，它的音效（每行 `stat_row_N`、每颗星 `star_ding`）出片前按 gap 逐个排进镜头的音效表（出片前 `check` 自动补进 `sfx`，分镜表自己写了就不动）；考你的整个流程固定 5.8 秒。时间常数在 `sfx/timing.py`，特效和音效共用。
- 位置：主体安全区 y 360–1400、左右各留 80；最下面 300、右边 140 是平台遮挡区，别放东西。除了 `sticker`（贴在画上，`depth` 默认 1 跟着镜头），别的特效都钉在屏幕上。
- 字只用两种字体（ZCOOL KuaiLe / Noto Sans SC Bold）；参数里的字出片前查缺字。颜色可以写 `"#rrggbb"`、名字（ink red cream white gold orange green blue sky brown），也可以写 `"house": "智家"` 取 `video/series_style.json` 的家族颜色。
- 闪烁：特效包里没有会闪的东西（闪白一集最多 3–4 次，两次隔 1 秒以上）。

| 类别 | 特效 | 参数（`at` / `dur` / `sfx` 省略） | 默认音效 | 用在哪 |
|---|---|---|---|---|
| 漫画线 | `lines_focus` 集中线 | `pos` / `center`（往哪里收拢）、`clear`：**`[x, y, r]` 这个圆里一根线都不画**（让开脸；写一个数 = 以 center 为圆心的半径；不写 = 半径 380）、`color`（墨）、`alpha`（0.30）、`count`；线细而淡，只在「圆心到画面边」的外半程可见 | `focus` | 惊讶、揭晓、点题 |
| | `lines_radial` 放射速度线 | `pos`、`color`（米白）、`alpha`、`count` | `burst` | 「燃」、冲刺、大喊 |
| | `lines_speed` 横向速度线 | `dir`（left / right = 线飞的方向）、`y0` `y1`（高度范围）、`color`、`count` | `whoosh` | 人在跑、快 |
| 贴纸 | `sticker` | `name`（图片贴纸）或 `text`（文字贴纸）、`pos`、`size`、`rot`、`flip`、`color`、`depth`；**`follow`: 人物 id + `offset: [dx, dy]`（离脚底中点，人物原大小时）或 `attach: "head"`：贴纸挂在人物身上，跟着出场 / 跳 / 呼吸 / 视差动，人物翻身（flip / sx 变负）位置跟着镜像；`exit: "tear"`（要写 `dur`）：到 dur 那一刻从中间撕成毛边的两半，翻着落下，音效 `tear` 自动排进镜头** | `pop` | 反应和笑点，见下面的贴纸表 |
| 砸字 | `smash` | `text` 1–6 个字、`pos`、`size`（300）、`color` / `house`、`shake`（震屏像素，默认 9，≤ 16） | `slam_1`…`slam_6` | 关键词、数字、结论；第 k 个字在 `at`+0.14+0.17k 落地 |
| 清单 | `checklist` | `items` 1–6 条、`pos`（第一条中心，每条下移 128）、`mark`（check / star / none）、`w` | `list_1`…`list_6` | 本事、理由、功绩 |
| 属性卡 | `stat_card` | `name`、`rows` 1–6 行 `{label, stars 0–5, icon}`（**有几行画几格**：卡片按行数裁短，奇数行最后一个空格抹掉）、`pos`、`w`（760）、**`gap`（行与行亮起的间隔秒数，默认 0.75，0.15–2.0；6 行写 0.3 只要 2.3 秒）**、`star_ding`（false = 星星不出声）；底板 `props/card_attr.png` | `stat_open`（+ 每行 `stat_row_N`、每颗星 `star_ding`，自动排） | 讲人物，「本事 ★★★★★ / 好心 ★」逐行亮起 |
| 地图 | `map` | `pos`、`w`（940）、`dim` 背景压暗；底板 `props/map_paper.png` | `paper_unfold` | 讲地理、行军 |
| | `map_city` | `pos`、`name`、`house` / `color`、`icon`（现成圆形城图标）、`size` | `city_pop` | 城标落在地图上 |
| | `map_arrow` | `pts` 路径点（≥ 2）、`house` / `color`、`width` | `draw` | 虚线箭头 0.8 秒画出，画完箭头弹一下 |
| 氛围 | `rays` 光芒（画在人物后面） | `pos`、`color`、`alpha`、`count`、`radius` | `shine` | 高潮、胜利 |
| | `sparkle` 闪粉 | `area`、`count`、`avoid` | `twinkle` | 宝物、变身 |
| | `confetti` 纸屑彩带 | `mode`（burst 喷起 / fall 飘落）、`count`、`avoid` | `party` | 胜利 |
| | `dust` 灰尘 | `mode`（float 飘 / puff 扬起：一团柔和的尘雾颗粒 + 碎纸屑，向两边和上面散开、胀大、1 秒左右淡掉）、`area` / `pos`、`size`、`avoid` | `dust_puff`（只有 puff 出声） | 旧屋、行军、落地 |
| | （闪粉、纸屑、飘着的灰尘**自动避开人物的脸**：出片前 `check` 按镜头里每个人物的图和 `pos` / `h` 算出脸框，粒子飘近脸框会渐隐，不会盖住脸；`avoid: []` 关掉，`avoid: [[x0,y0,x1,y1]]` 自己指定） | | | |
| | `rain` 雨 | `dim`（压暗 0.16）、`density`、`slant` | `rain` | 天气 |
| | `splash` 水花 | `pos`、`size`、`layer`（写 `"back"` 画在人物后面；默认在前面） | `splash` | 落水、水涨 |
| | `flame` 纸剪火焰 | `pos`（底边中点）、`w`、`height`、`count`；**不许和人物的框重叠（出片前报错）** | `whoomp` | 燃点（橙黄，不用血红）；放在画面两边或 big_title 的字周围 |
| 调色 | 镜头的 `grade` 字段（引擎自带）：`normal` `warm` `gold` `cool` `memory`（旧纸黄 + 颗粒 + 暗角）`tense`（稍暗 + 暗角） | | | 回忆、紧张 |
| | `tone` 镜头中间换色 | `tone`（gold warm cool night memory tense）、`from`（换色以前的色调）、`delay`（先等几秒）、`ramp`（扫过用多久，0.7）、`sweep`；写了 `from` 就不要再写镜头的 `grade`（grade 盖在特效上面，会叠出灰雾）；night 是乘法调的深蓝夜晚 | `tone_shift` | 颜色分段：得意 gold、密谋 night、从前 memory、胜利 warm |
| 闪 | `flash` 柔和闪白 | 不带参数：盖 55% 白、0.1 秒（3 帧） | `flash` | 重大揭晓，一集 ≤ 3–4 次 |
| 考你 | `kaoni` | `options` 1–3 个、`answer`（正确选项序号）、`y`、**`end_stamp`（≤ 6 个字：最后一拍 3.75 秒在计时器上盖一个小章，章和计时器一起缩走，不像被剪断；盖章一声 pop 自动排进镜头）**；「考你！」按钮 → 选项 → 3-2-1 圈 → 「看答案！」，共 5.8 秒 | `kaoni` | 系列仪式，每集 4 次（也可写进分镜表的 `rituals`） |
| 进度物 | `progress` | `pos`（默认 [740, 900]）、`title`、`labels`、`from` / `to`（0–1）、`pop_in`、`color`、`kind`（water / fill）、`size` | `gauge_pop` | 本集的概念物（水位刻度），变化时整体弹一下 |
| 人物卡 | `person_card` | `img`、`name`、`line`（一句话）、`no`、`stats`、`w`（700）；底板 `props/card_char.png` | `person_card` | 每集结尾的收藏卡 |
| 人名牌 | `name_plate` | `name`、`role`（身份）、`house` / `color`、`pos`（挂点 = 牌子顶部中点）、`size`（1.15）、`dur`（**默认 2.4 = 落下 0.42 + 能看清 2.0 秒；能看清的时间 < 1.5 秒（dur < 1.92）出片前报错**） | `plate_drop` | 人物第一次出场（竖排大字 + 小字身份，家族颜色） |
| 游戏卡片 | `card_quest` `card_fail` `card_title` `card_mvp` | `text`（主文字）、`sub`（小字，默认：任务 / 任务失败 / 获得称号 / 本集 MVP）、`pos` | `card_quest` `card_fail` `card_title` `card_mvp` | 关卡开始 / 结束、揭晓 |
| 大字标题 | `big_title` | `text`（1–2 行，长了自动分行）、`pos`、`deco`（rays / flame / none）、`color`、`size`（220）、`shake` | `title_boom` | 「第 1 关：忍」「水，倒过来了！」 |
| 解说台 | `screen` 纸屏幕 | `img`（屏幕里的画）、`pos`、`w`；框 `props/screen_frame.png`；再写一条同位置的 = 换画 | `screen_on` | 司马光的书房 = 后墙 `sets/study/wall.png` + 书桌 `sets/study/desk.png`（`fg`）+ 高清半身 `chars/sgm_hi_remote.png` + 屏幕 |
| | `remote_click` | `pos`（按钮位置）、`color` | `click` | 「按一下」，再接转场 `tv_switch` |
| | `bubble` 想象泡泡 | `img` 或 `text`、`pos`（**尾巴尖，点在说话人的头顶旁边**）、`w`（宽度上限 820，放不下自动缩小，夹进安全区 y 360–1400、x 80–1000，尾巴尖不动；宽 < 460 放不下就报错）、`flip`、`inner_sway`（默认 1：泡泡轻轻呼吸，里面的画上下浮动 + 轻轻鼓动，0 = 不动，不许冻住）；底板 `props/bubble_cloud.png` | `bubble_pop` | 古今对照的想象画 |
| | `page_edge` 书页边 | `y`（书页上沿，1240）、`w`、`peek`（探出来的人物半身图）、`peek_h`、`peek_x`；`props/page_edge.png` | `page_slide` | 「考你」时司马光从书页后面探出来：写 `peek`，书页升起来以后人才升起来、落下去以前人先缩回去，半身像的平切下沿一直藏在书页后面 |

**贴纸**（`video/motion/stickers/`，`sticker` 的 `name`）：`question` 问号　`question3` 三个问号　`exclaim` 感叹号　`bulb` 灯泡　`sweat` 汗滴　`anger` 怒气　`star` 闪光星星　`star_eyes` 星星眼　`heart` 小心心　`dong`「咚」　`pa`「啪」　`sou`「嗖」。
来源 `video/assets/codex_series/stickers_v1.png`（9 个）和 `stickers_v2.png`（3 个），`python video/motion/stickers/build.py` 拆图（去绿底、去绿边、修白纸边）；文字贴纸（`text`）用来临时写别的拟声字。

**转场**（写在后一镜的 `transition`，字符串或 `{"type": ..., "dur": 秒, ...}`；声音在切点响，所以每个转场的音效都是「重音在开头、尾巴慢慢散」）

| 转场 | 默认时长 | 样子 | 参数 | 音效 |
|---|---|---|---|---|
| `page_turn` 翻书页 | 0.7 | 一页纸从右往左卷起来，露出带圆柱明暗的纸背（浅浅透出旧画面）和新画面 | `side`（right / left） | `page_flip` |
| `paper_wipe` 纸片擦过 | 0.8 | 三条彩色纸片（朱红、金、米白，带白纸边和软阴影）斜着扫过 | `colors`、`dir` | `paper_swipe` |
| `ink_wipe` 墨笔刷 | 0.7 | 一两道粗墨笔从左往右一笔扫过：笔头圆、边缘平滑起伏，笔肚一整块浓墨，笔尾是一缕一缕的飞白（毛刷纹路里露着新画面），带纸纹；上下两笔叠着盖满 | `strokes`（2）、`dir` | `brush` |
| `iris` 圆圈收拢 | 0.7 | 纸圈收成一点，再从一点放开（圈外是纸色，带白纸边）；缓动按圈里画面的**面积**走，画面亮度逐帧平滑变化 | `pos` 圆心、`color` 纸色 | `iris` |
| `fade_paper` 淡到纸色 | 0.7 | 淡到一整张纸，再淡入下一镜 | | `fade_soft` |
| `whip` 甩镜 | 0.28 | 整幅画面横着甩出去，带运动模糊 | `dir`（left right up down） | `whip` |
| `tv_switch` 解说台切进故事 | 0.8 | **前一镜要先放好纸屏幕（`screen`）**：屏幕里的画先叠化成故事的画，再从纸面大小放大到盖满整个画面 | `pos` 纸面中心、`w` 纸面宽（默认 408 = 木框宽 540 时的纸面；pos = 框中心 + (−0.0057, −0.0688)×框宽；纸面比例读 layout.json） | `tv_click` |
| `dissolve` 交叉淡化 | 0.4 | 接口示例 | | |

**特效样片合集**：`video/motion/tests/fx_reel/`——`build_reel.py` 生成分镜表 `storyboard.json` 和配音时间线 `voice/timeline.json`（43 个镜头，每个特效 2–3 秒，画面下方一个小标签写名字；带音效和背景音乐，用三句现成的配音试字幕）；
出片 `python video/motion/render.py video/motion/tests/fx_reel/storyboard.json --final --out video/out/motion/fx_reel`；`make_review.py <mp4>` 出联系表（每秒 1 帧）和每个镜头动作段的每秒 10 帧抽帧条；`fx/label.py` 是样片专用的名字标签。
**晋地外景怎么铺**（样片合集 `build_reel.py` 的 `TERRAIN` / `WATER`，正式的集照抄）：远山三层 → 灌木丛 `fore.png`（画在地平线上）→ 四条一条比一条大的草土带 `ground.png`（w 1300 / 1500 / 1700 / 1900，`repeat: "x"`，隔一条 `flip`），每一条的上沿（草）盖住上一条的平切下沿——**相邻两条的间距 = 上一条高度 × 0.8**，最后一条的下沿在画面外面；这样从地平线到画面底没有空带、看不到平切边。河边：草土带后面接三条一条比一条大的 `water.png`，同样的叠法。

开发时看单个特效：`python video/motion/tests/fx_peek.py '{"type":"smash","text":"本事","pos":[540,800]}' --t 0,0.1,0.2,0.4 --out x.png`（转场用 `--transition`）。

## 自动检查和报告

出片时自动跑，结果写进 `<out>/<名>.report.json`，任何一项不过退出码 1：

| 项 | 怎么查 | 通过条件 |
|---|---|---|
| 闪烁 | 逐帧（1/8 分辨率）平均亮度，相邻两帧差 ≥ 10% 算一次突变 | 任何 1 秒内 ≤ 3 次 |
| 静止 | 相邻两帧（1/8 分辨率灰度）平均差 < 0.03 算「没动」 | 没有超过 1.5 秒的连续静止 |
| 响度 | 成片音轨的整体响度和真峰值（ebur128） | −16 ± 1 LUFS，真峰值 ≤ −1.5 dB（不足 3 秒或没有台词的片段不查） |
| 人声 | 每句台词的时段里，配音轨道有声的比例 | ≥ 20%（配音文件是空的 / 时间对不上就会不过） |

报告里还有：帧数、时长、各阶段用时（`timing`）、缓存命中数、警告（放大倍数、摇镜太快、镜头运动超范围……）。`--frame-hashes` 再多写每一帧的哈希。
**闪烁和静止的阈值（`engine/consts.py`）按这套画风标定过**：正常推拉的画面相邻帧差 0.2–0.4，纯天空只有呼吸漂移的画面 0.001。

## 目录

```
video/motion/
  render.py            命令行入口：计划 → 多进程渲镜头 → 混音 → 拼接（转场、界面）→ 编码 → 自动检查 → 报告
  engine/              consts.py（系列常量）、timeline.py（锚点）、plan.py（读分镜表、排帧、查错、缓存哈希）、scene.py（一个镜头：图层 / 人物 / 特效 / 调色）、
                       anim.py（缓动、镜头、补间）、canvas.py（画布、贴图）、sprites.py（素材、字体、文字图）、ui.py（标题条 / 字幕 / 水印）、
                       audiomix.py、checks.py、worker.py（渲一个镜头写缓存）
  fx/                  特效和转场插件（清单见上）：_paper.py（共用：纸纹、白纸边、缓动、Sprite 缓存，下划线开头不当插件加载）、lines.py、sticker.py、smash.py、lists.py（清单、属性卡）、maps.py、
                       ambient.py、weather.py、tone.py（调色、闪白）、kaoni.py、gauge.py（进度物）、cards.py（人名牌、人物卡、游戏卡片、大字标题）、desk.py（解说台、泡泡、书页边）、transitions.py、dissolve.py
  sfx/                 系列固定音效：synth.py（合成脚本）、timing.py（时间常数）、<名字>.wav
  stickers/            系列贴纸（12 张）+ build.py（拆图）
  tests/               bash video/motion/tests/run_all.sh
  _prototype_mc.py     17 秒小样（写死了镜头，只作参考）
```

## 测试

`bash video/motion/tests/run_all.sh`（已挂进 `bash video/tests/run_all.sh`）：不要显卡、不要网络、不要 Jev key，约 2 分钟（67 项）；`SLOW=1` 再加约 5 分钟的整集高清速度测试。输出写到 `video/out/tests/motion/`。

| 文件 | 测什么 |
|---|---|
| `test_units.py` | 锚点（字级时间、`dt`、`nth`、坏锚点）、字幕分页、闪烁 / 静止检测的正反例、混音（越界不崩、限幅、压低音乐、响度归一）、特效登记 |
| `test_plan_errors.py` | 20 多种故意写坏的分镜表（缺素材 / 字体 / 背景音乐、拼错字段、坏锚点、不存在的特效……）都要报错；镜头帧范围、转场帧数、缓存哈希 |
| `test_render.py` | 端到端：① 两次从空缓存渲，每一帧哈希一致；② 字幕出现时间和时间线差 ≤ 1 帧（对着成片量，不看代码）；`--shots` 裁剪（含台词比画面长、不相邻）；缓存；预览速度；退出码；缓存镜头的颜色往返 |
| `test_fx.py` | 特效包：每个特效和转场登记了、音效文件干净（单声道 44.1 kHz、无咔嗒、不刺耳）、**每个特效一个渲染冒烟测试**（没到 at 不画、画了东西、结束收干净、同样输入两次一样、乱序画结果一样）、转场两端对得上且没有瞬移、样片合集和生成脚本一致并端到端渲一遍（自动检查全过） |
| `test_long.py`（SLOW=1） | 小样重复 10 遍拼成约 3 分钟整集，整集高清 ≤ 15 分钟 |
| `proto17/` | 17 秒小样的分镜表（验收 ③）+ 生成界面卡片和音效的脚本 + 一个本地特效（倒计时圈）+ 配音夹具 |
| `feature_case/` | 把出场、小动作、镜头运动、调色、转场、贴纸都过一遍的分镜表 |

## 已知限制（阶段 B / C 接着做）

- 特效包（阶段 B）已全：清单见「特效清单」。`props/screen_frame.png` 是 4:3 的框（1047×960，纸面 791×604）；框尺寸和纸面位置都读 `props/screen_frame.layout.json`（`size`、`screen`），换框图只改那个 json。放进屏幕的画一律铺满裁边（cover），不留空边、不露到框外。
- 多步的特效（砸字、清单、属性卡、考你）的音效是按「几下」固定的整段（`slam_N` 等，`check` 里补 `sfx`）；如果引擎让 `sfx` 可以是函数（`params → [(偏移秒, 名字)]`）就不用这个办法了。
- 图层不做遮罩、不做 3D；`repeat: "x"` 只重复左右；摇镜幅度超出图层范围会露出底下的纸色。
- 语气 / 换音乐（「燃」段换节奏更强的曲子）、片头片尾特殊处理还没有。
