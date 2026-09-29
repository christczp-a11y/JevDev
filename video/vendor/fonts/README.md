# 字体（工作流第 0 步第 19 项）

`engine.html`（2D 引擎）和 `stage3d/stage.html`（3D 舞台）都用 `<link rel="stylesheet" href="…/vendor/fonts/fonts.css">` 加载这里的字体，**不再连 Google Fonts**。
以前连在线字体时，中文字形按分片首次用到才下载，第一次画字用的是备用字体：截图、成片每一段的第一帧字体不对，参考帧也是这样截歪的（PITFALLS E1，09-29 再犯）。

| 文件 | 是什么 | 大小 | 来源、许可证 |
|---|---|---|---|
| `NotoSansSC-subset.woff2` | Noto Sans SC，weight 轴只留 500–900（全项目只用 500 / 700 / 900），子集化 | 1.9 MB | Windows 自带的 `C:\Windows\Fonts\NotoSansSC-VF.ttf`（Version 2.04，原文件 17.7 MB）；SIL OFL 1.1，见 `NotoSansSC-OFL.txt` |
| `ZCOOLKuaiLe-subset.woff2` | ZCOOL KuaiLe（站酷快乐体），子集化 | 0.8 MB | https://github.com/google/fonts/tree/main/ofl/zcoolkuaile 的 `ZCOOLKuaiLe-Regular.ttf`（Version 2.001，1.5 MB）；SIL OFL 1.1，见 `ZCOOLKuaiLe-OFL.txt` |
| `fonts.css` | 两条 `@font-face`（weight 400 的 ZCOOL、500–900 的 Noto），外加一条：ZCOOL 里没有的字（例如絺）由 Noto Sans SC 补上 | | 由 `subset_fonts.py` 生成，不要手改 |
| `charset.txt` | 字符集 | | 由 `subset_fonts.py` 生成 |
| `coverage.json` | 两个 woff2 里实际有哪些字（cmap） | 43 KB | 由 `subset_fonts.py` 生成；`video/glyph_check.py` 用它查场景里的字有没有缺 |
| `subset_fonts.py` | 重新子集化的脚本 | | |

**字符集** = ASCII + GB2312 全部（6763 个常用简体字和常用符号）+ 仓库里所有会上画面的文字里出现过的字（`video/stories/`、`video/scenes/`、`video/episodes/`、`video/sets/`、`video/engine.html`、`video/stage3d/stage.html`，其中包括 tj01 简报里的生僻字）+ 几个常用标点。
不要表情符号。字库本身没有的字不会报错，所以 `checkFonts` 加载时会验证字体真的生效（见下面）。

## 缺字检查（`video/glyph_check.py`）

`checkFonts` 只验证字体整体生效，验证不了每个字都在。第 5 步生成场景 JSON 以后、渲染之前，`glyph_check.py` 把每场要上画面的字（字幕、说话人、人名牌、卷号、计分牌标签、横幅、选择题、告示牌、气泡……）逐个对着 `coverage.json` 查，
缺字就报「第几场、哪个位置、缺哪个字」并退出 1。`build_stage3d.py` 的 `qa` 和 `render`、分场脚本模板（生成场景 JSON 以后）都会自动跑它，也可以单独跑：`python video/glyph_check.py video/scenes/<集>/shot*.json`。
判断按 fonts.css 的实际分工：ZCOOL 缺、由 Noto 补的字（例如絺）不算缺。缺字以后重新子集化的一条命令：`python video/vendor/fonts/subset_fonts.py`（见下）。

## 什么时候要重新子集化

第一集出现了字库里没有的字（画在屏幕上的名字、台词里的生僻字：简报里的絺、瑤之类）时：

```
pip install fonttools brotli          # 只有重新子集化才要，不在 requirements.txt 的必装项里
python video/vendor/fonts/subset_fonts.py
```
它读仓库里的文字重新算字符集，生成 `NotoSansSC-subset.woff2`、`ZCOOLKuaiLe-subset.woff2`、`fonts.css`、`charset.txt`、`coverage.json`。只想按现有 woff2 重写 `coverage.json`：加 `--coverage-only`。原字体的位置见脚本开头的参数：
Noto 用 Windows 自带的（或者任何 Noto Sans SC 可变字体，`--noto 路径`）；ZCOOL 要先把 `ZCOOLKuaiLe-Regular.ttf` 放到 `video/out/fonts_src/`（不进 git）或者 `--zcool 路径`。
**ZCOOL KuaiLe 里没有的字**（现在 598 个，包括 tj01 的「絺」）在 `fonts.css` 里用 Noto Sans SC 补，画面上不会跳出系统备用字体，但那个字的风格和别的字不一样；人名牌上出现这种字，第 3 步出人名试听（检查点 2）时一起给 Chris 看。

## 加载时怎么检查（`engine.html` 的 `checkFonts`，`stage.html` 也调它）

1. `await document.fonts.load('400 100px "ZCOOL KuaiLe"', 这一场要画的所有字)`，Noto 的 500 / 700 / 900 各来一次：**带上要画的字**（旧版不带字，只加载了空格那一份）；返回的列表是空的、或者报错，就退出。
2. 加载完再用 `measureText` 对着备用字体验证：一串拉丁字母数字的宽度、一串汉字的墨迹范围（宽度、上下沿、左右沿）都和 `sans-serif` 不一样，才算字体真的生效（只有空格或一部分字形加载成功的字体，两项里总有一项和备用字体一样）。不用 `document.fonts.check()`：字体根本不存在时它也返回 true。
3. FontFace 的状态必须是 loaded。
4. 不合格就抛「字体没加载成功：…」，`render.py`（2D）和 `build_stage3d.py`（3D）收到就打印原因、**退出码 2**，不往下渲。
5. 初始化完先空渲一帧（t = 0）再截第一帧。3D 每段并行渲染都新开浏览器，每一段的第一帧也是这样（`video/tests/fonts/check_fonts.py` 验证）。

测试：`bash video/tests/fonts/run_all.sh`。
