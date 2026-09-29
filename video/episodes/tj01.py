"""第一集「三家分晋」（tj01）的配置样板：现在只有确定的项，其余是占位。写法见 video/episode_config.py。

每一项什么时候填（有没填完，`python video/episode_build.py tj01 --check-config` 会列出来；PLACEHOLDER 没清掉之前分场脚本不许开跑）：
  TITLE.lines  第 2 步定了大问题以后（片头标题两行）
  FOOTER       第 5 步（2D 画面底部出处行；3D 成片不画）
  LABEL        第 5 步：字幕上说话人的显示名（台词里的说话人 → 屏幕上写的名字）
  B            第 4 步配音、拿到 timeline.json 以后，第 5 步按台词行号写：[(第 i 句, 第 j 句), ...]
  PX           第 3 步登记人物前缀以后，第 5 步写；不登记的前缀用默认 0.42
  NAMETAGS     第 5 步按 shotN() 里的角色 id 写，每人只写 name 和 house；家名必须是系列表 video/series_style.json 的 houses 里的键
               （智家、赵家、韩家、魏家、周王室）。家族颜色不写在这里：第 3 步定色时填进 series_style.json（现在是占位 null，人名牌用墨色）
  QA           第 5 步：baked（姿势图里自带别的角色的，R11）、action_text（跟本集道具有关的动作说明）；
               format 已定：「纸艺动画（这里看的是 2D 引擎画的人物）」（tj01 是 3D 集，但 logic_qa 截的是 2D 引擎画的人物）
"""
from pathlib import Path

from episode_config import PLACEHOLDER

ROOT = Path(__file__).resolve().parents[1]   # video/

CFG = {
    "EP_LABEL": "第一集",
    "TITLE": {"kicker": "资治通鉴 · 卷一",   # 片头角标按故事所在的卷写，不沿用试做集的「卷二」
              "lines": [PLACEHOLDER]},       # 第 2 步定了大问题再填，例如 ["最强的智伯，", "为什么[[输]]了？"]
    "FOOTER": PLACEHOLDER,                    # 第 5 步再填，例如 "三家分晋 · 出自《资治通鉴》卷一"
    "LABEL": {},                              # 第 5 步再填
    "B": [],                                  # 第 5 步再填（要先有第 4 步的配音时间线）
    "PX": {},                                 # 第 5 步再填
    "VOICE": ROOT / "out/tj01_voice",         # 第 4 步：python video/voice.py <定稿剧本> video/out/tj01_voice ...
    "OUT": ROOT / "out/tj01",
    "SCENES": ROOT / "scenes/tj01",
    "FINAL": "tj01_full.mp4",
    # 人名牌名单：{角色 id: {"name": 名字, "house": 家名}}。第 5 步按 shotN() 里的角色 id 填，例如：
    #   "zb": {"name": "智伯", "house": "智家"},
    # 不要写 color：家族颜色每集必须一样（工作流第七节），写在系列表 video/series_style.json 的 houses 里（第 3 步定色）；
    # house 不在系列表里就报错
    "NAMETAGS": PLACEHOLDER,
    "QA": {
        "baked": {},          # 第 5 步再填
        "action_text": {},    # 第 5 步再填
        "format": "纸艺动画（这里看的是 2D 引擎画的人物）",   # logic_qa 提示词里的画面形式：tj01 是 3D 集，但 logic_qa 截的图是 2D 引擎画的人物，别让观察员去找 3D 效果
    },
}
