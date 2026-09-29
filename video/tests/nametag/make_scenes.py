"""人名牌测试的场景：给试做集（ep01v2）的角色配上名字和家名，用通用分场模板（时间线用 video/tests/fixtures/ep01v2_voice/）生成带 nametags 的场景 JSON。
家族颜色来自测试用的系列表 series_style_test.json（不是真的家族色）。输出到 video/out/tests/nametag/scenes/，不动 video/scenes/ep01v2/。
用法（仓库根目录）：python video/tests/nametag/make_scenes.py [输出目录]"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                     # video/
sys.path.insert(0, str(ROOT))
import build_ep01_v2 as b  # noqa: E402
import episode_build as eb  # noqa: E402
import episode_config as ec  # noqa: E402

TAGS = {
    "host": {"name": "司马光", "house": "书房"},
    "shangyang": {"name": "商鞅", "house": "秦国"},
    "shangyang2": {"name": "商鞅", "house": "秦国"},   # 同一个人的第二个角色 id：只算第一次出场
    "dad": {"name": "爹", "house": ""},                  # 没有家名：只写名字，用默认墨色
    "douzi": {"name": "小豆子", "house": "秦国"},
    "youth": {"name": "小伙", "house": "秦国乙"},        # 家族颜色是占位（null）：用默认墨色
    "auntie0": {"name": "大婶", "house": "秦国"},        # 和小豆子同时出场、站得近：测两张牌撞在一起时的摆位（T23）
}


LONG = "商鞅在南门立了一根三丈长的木头，谁能把它搬到北门，就赏十金；可是没有一个人敢信，于是赏钱涨到了五十金。"   # 3D 里排成四行


def build(out):
    cfg = copy.deepcopy(b.CFG)
    cfg["NAMETAGS"] = TAGS
    style = ec.load_series_style(HERE / "series_style_test.json")
    errs, _, _ = ec.check(cfg, style)
    assert not errs, errs
    ep = eb.Episode(cfg, ROOT / "tests/fixtures/ep01v2_voice", out, out.parent / "out")
    ep.scenes.mkdir(parents=True, exist_ok=True)
    scenes = eb.build_scenes(ep, b.SHOTS, style)
    # 测试用的四行字幕（说话人标签顶得比三行的更高，牌子下沿要跟着上移）：盖住第 1 场 49.0–52.0 秒里原来的字幕（小伙、爹的牌子在 49.4–51.5 秒出现）
    sc1 = scenes[0]
    sc1["subtitles"] = [x for x in sc1["subtitles"] if x[1] < 49.0 or x[0] > 52.0] + [[49.0, 52.0, "旁白", LONG]]
    sc1["subtitles"].sort()
    for k, sc in enumerate(scenes, 1):
        (out / f"shot{k}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    return scenes


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out/tests/nametag/scenes"
    for k, sc in enumerate(build(out), 1):
        print(k, [(t["name"], t["color"], t["t0"], t["t1"]) for t in sc.get("nametags", [])])
