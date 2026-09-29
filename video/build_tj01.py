"""第一集「三家分晋」（tj01）的分场脚本：现在是空样板，第 5 步再写每场的 shotN()。

配置在 video/episodes/tj01.py（有没填完：python video/build_tj01.py --check-config）。
写 shotN() 的方法照试做集 video/build_ep01_v2.py：每场 `def shotN(ep)`，开头 `B, T0, T1, at, base = ep.tools()`，
用台词行号和台词里的词定位时间，不写死秒数（工作流第 5 步）；写好以后加进 SHOTS。
配音先跑第 4 步的 voice.py，得到 video/out/tj01_voice/timeline.json。
跑法：python video/build_tj01.py [--only 场号,...] [--no-render]（写场景 JSON 到 video/scenes/tj01/，再渲染 2D）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import episode_build as eb  # noqa: E402
from episode_build import actor, choice, sprite  # noqa: E402,F401

CFG = eb.load_config("tj01")

SHOTS = []   # 第 5 步再写：[shot1, shot2, ...]


if __name__ == "__main__":
    eb.main(CFG, SHOTS)
