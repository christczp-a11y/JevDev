# 字体（动态漫画合成器用）

| 文件 | 用在哪 | 来源、许可证 |
|---|---|---|
| `NotoSansSC-Bold.ttf` | 字幕、说话人标签、正文字 | Google Fonts `ofl/notosanssc/NotoSansSC[wght].ttf`，用 fontTools 固定成 wght=700 的静态字体（10.6 MB）；SIL OFL 1.1，见 `NotoSansSC-OFL.txt` |
| `ZCOOLKuaiLe-Regular.ttf` | 标题条、砸字、贴纸上的字 | Google Fonts `ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf`（1.5 MB）；SIL OFL 1.1，见 `ZCOOLKuaiLe-OFL.txt` |

- 合成器找不到这两个文件就报错，不许退回系统字体（PITFALLS E1）。
- ZCOOL KuaiLe 没有的字（比如「絺」）逐字用 Noto Sans SC Bold 补，合成器按字体的 cmap 判断。
- 重新生成 Bold：`.venv/Scripts/python -m fontTools.varLib.instancer NotoSansSC[wght].ttf wght=700 --update-name-table -o NotoSansSC-Bold.ttf`
