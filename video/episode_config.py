"""每集一份配置（工作流第 0 步第 7、8、9 项）：video/episodes/<集>.py 里的 CFG。

分场脚本模板（episode_build.py）和质检（layout_qa.py、logic_qa.py）都从这里读同一份配置。
集名 = 场景 JSON 所在的目录名（video/scenes/<集>/shotN.json），试做集是 ep01v2，第一集是 tj01。

CFG 的项：
  EP_LABEL  场景 JSON 的 about 里的集号，例如 "第 1 集"
  TITLE     片头 {"kicker": 角标（按卷：tj01 =「资治通鉴 · 卷一」）, "lines": [标题第一行, 第二行]}，[[…]] 括起来的字标红
  FOOTER    2D 画面底部的出处行
  LABEL     字幕上说话人的显示名：{台词里的说话人: 显示名}（例如 {"农夫": "爹"}）
  B         按台词行号分场：[(i, j), ...]，每一对是一个场次边界 = 第 i 句结束和第 j 句开始的中点；
            n 对分出 n+1 场（开头 0 秒和结尾整集时长不用写）
  PX        按姿势图前缀设人物比例 {前缀: px}，写这一集要改的；没写的前缀先取 video/assets/REGISTRY.md 人物表的 PX 列
            （司马光 sgm_ 0.62 这类不用每集重填），登记表里也没有才用默认 0.42（episode_build.DEFAULT_PX）
  VOICE     配音目录（里面有 timeline.json 和每句的 mp3）
  OUT       渲染输出目录（每场的 mp4、meta.json、混音、成片）
  SCENES    场景 JSON 输出目录（video/scenes/<集>）
  FINAL     渲完拼好的成片文件名（放在 OUT 里），不写就叫 full.mp4；试做集是 ep01_full.mp4（3D 版借它的声音）
  NAMETAGS  人名牌名单：{角色 id: {"name": 名字, "house": 家名}}。家族颜色不写在这里（每集必须一样，工作流第七节）：
            家名必须是系列表 video/series_style.json 的 houses 里的键（家名不在表里就报错；颜色还是占位 null 时允许，人名牌用墨色）。
            人物第一次入画时名字和家名一起出现约 2 秒；空 {} = 这一集不画人名牌，画面和没有这个功能时完全一样
  QA        质检的按集配置（可以省略）：
              baked        {姿势图名前缀: (被画在里面的角色的姿势名前缀, ...)}，layout_qa 查重影（R11）
              action_text  {动作名: 这一刻人物在做什么}，logic_qa 给观察员和 Jev 看；只写这一集里跟具体道具有关的动作
              format       logic_qa 提示词「这是一部{format}里的一刻」里的画面形式：试做集（2D 横版）写「纸艺风格横版动画」；
                           tj01 是 3D 集，但 logic_qa 截的是 2D 引擎画的人物，写「纸艺动画（这里看的是 2D 引擎画的人物）」，别让观察员去找 3D 效果

还没定的项写 PLACEHOLDER（或 B 写 None）：`python video/episode_build.py <集> --check-config` 会列出来；
有没填的项，分场脚本不许开跑。
"""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # video/
PLACEHOLDER = "【第 5 步再填】"

REQUIRED = {"EP_LABEL": str, "TITLE": dict, "FOOTER": str, "B": list, "VOICE": (str, Path), "OUT": (str, Path), "SCENES": (str, Path)}
OPTIONAL = {"LABEL": dict, "PX": dict, "NAMETAGS": dict, "QA": dict, "FINAL": str}
QA_KEYS = {"baked", "action_text", "format"}


class ConfigError(Exception):
    pass


STYLE_PATH = ROOT / "series_style.json"
REGISTRY_PATH = ROOT / "assets" / "REGISTRY.md"


def load_series_style(path=None):
    """系列表 video/series_style.json：家名 → 家族颜色和旗的纹样。读不了、写法不对都报清楚的中文错误。"""
    path = Path(path or STYLE_PATH)
    try:
        style = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"找不到系列表 {path}（家名 → 家族颜色，工作流第七节）") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"系列表 {path} 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列，{e.msg}") from e
    houses = style.get("houses")
    if not isinstance(houses, dict):
        raise ConfigError(f"系列表 {path} 里要有 houses（{{家名: {{\"color\": \"#rrggbb\" 或 null, \"flag\": ...}}}}）")
    for name, h in houses.items():
        col = h.get("color") if isinstance(h, dict) else 0
        if col is not None and not (isinstance(col, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", col)):
            raise ConfigError(f"系列表 {path}：家「{name}」的 color = {col!r}，要写成 \"#rrggbb\"，还没定就写 null")
    return style


def registry_px():
    """video/assets/REGISTRY.md 历史人物表里的 PX 列 → {姿势图前缀: px}。
    「PX」列写法：开头的数字是这个前缀的比例，括号里可以再写「`前缀` 数字」的特例；没有数字（—）、状态是停用的行不取。读不到登记表就返回空字典。"""
    try:
        md = REGISTRY_PATH.read_text(encoding="utf-8")
    except OSError:
        return {}
    out, in_table = {}, False
    for line in md.splitlines():
        if line.startswith("## 一、"):
            in_table = True
        elif line.startswith("## ") and in_table:
            break
        if not in_table or not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 6 or "停用" in c[5]:
            continue
        m = re.fullmatch(r"`([a-z0-9]+_)`", c[1])
        px = re.match(r"\d+(?:\.\d+)?", c[4])
        if m and px:
            out[m.group(1)] = float(px.group(0))
            for pre, v in re.findall(r"`([a-z0-9]+_[a-z0-9]*)`\s*(\d+(?:\.\d+)?)", c[4]):
                out[pre] = float(v)
    return out


def config_path(name):
    return ROOT / "episodes" / f"{name}.py"


def load_config(name):
    """读 video/episodes/<name>.py 里的 CFG。找不到、读不出来都报清楚的中文错误。"""
    path = config_path(name)
    if not path.exists():
        raise ConfigError(f"找不到这一集的配置：{path}。配置的写法见 video/episode_config.py 开头；tj01 的样板是 video/episodes/tj01.py")
    spec = importlib.util.spec_from_file_location(f"episode_cfg_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:   # noqa: BLE001 —— 配置文件写错了，原样把原因报出来
        raise ConfigError(f"读不了配置 {path}：{type(e).__name__}: {e}") from e
    if not hasattr(mod, "CFG") or not isinstance(mod.CFG, dict):
        raise ConfigError(f"配置 {path} 里没有 CFG 字典")
    return mod.CFG


def episode_of_scene(scene_path):
    """video/scenes/<集>/shotN.json → <集>；不在这种目录里就返回 None（要用 --ep 指定）。"""
    p = Path(scene_path).resolve()
    return p.parent.name if p.parent.parent.name == "scenes" else None


def qa_config(name):
    """质检要的按集配置，缺的项给空值。name 是 None 或找不到配置时，返回 (空配置, 原因)。"""
    empty = {"baked": {}, "action_text": {}, "format": "纸艺风格动画"}
    if not name:
        return empty, "没有指定集名（场景 JSON 不在 video/scenes/<集>/ 下，也没有 --ep）"
    try:
        cfg = load_config(name)
    except ConfigError as e:
        return empty, str(e)
    qa = cfg.get("QA") or {}
    return {"baked": qa.get("baked", {}), "action_text": qa.get("action_text", {}), "format": qa.get("format", "纸艺风格动画")}, None


def _unfilled(v, path, none_ok=False):
    """配置里没填的地方：None、PLACEHOLDER，或者嵌在列表、字典里的 PLACEHOLDER。返回它们的位置（例如 TITLE.lines[0]）。"""
    if v == PLACEHOLDER or (v is None and not none_ok):
        return [path]
    if isinstance(v, dict):
        return [p for k, x in v.items() for p in _unfilled(x, f"{path}.{k}", none_ok)]
    if isinstance(v, (list, tuple)):
        return [p for i, x in enumerate(v) for p in _unfilled(x, f"{path}[{i}]", none_ok)]
    return []


def check(cfg, style="default"):
    """返回 (errors, todos, notes)：errors = 写法不对（缺项、类型不对、多了不认识的项），todos = 还没填的项，
    notes = 可以先这样的提示（家族颜色在系列表里还是占位 = 第 3 步定色之前人名牌用默认墨色）。
    style：系列表（load_series_style() 的结果），"default" = 读 video/series_style.json，None = 不查家名。"""
    errors, todos, notes = [], [], []
    if style == "default":
        try:
            style = load_series_style()
        except ConfigError as e:
            style = None
            errors.append(str(e))
    for k, typ in REQUIRED.items():
        if k not in cfg:
            errors.append(f"缺少 {k}")
        elif not isinstance(cfg[k], typ) and cfg[k] is not None:
            errors.append(f"{k} 的类型不对：要 {typ}，实际 {type(cfg[k]).__name__}")
    for k, typ in OPTIONAL.items():
        if k in cfg and not isinstance(cfg[k], typ) and cfg[k] != PLACEHOLDER:
            errors.append(f"{k} 的类型不对：要 {typ}，实际 {type(cfg[k]).__name__}")
    for k in cfg:
        if k not in REQUIRED and k not in OPTIONAL:
            errors.append(f"不认识的项 {k}（写错了？可用的项：{'、'.join([*REQUIRED, *OPTIONAL])}）")
    t = cfg.get("TITLE")
    if isinstance(t, dict):
        if not isinstance(t.get("kicker"), str) or not isinstance(t.get("lines"), list):
            errors.append("TITLE 要有 kicker（字符串）和 lines（字符串列表）")
    b = cfg.get("B")
    if isinstance(b, list):
        for i, p in enumerate(b):
            if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(x, int) for x in p) and p[0] < p[1]):
                errors.append(f"B[{i}] = {p!r}：要写成 (第 i 句, 第 j 句)，两个整数，i < j")
        if not b:
            todos.append("B（还没有场次边界）")
    for k, v in cfg.items():
        todos += _unfilled(v, k, none_ok=(k == "NAMETAGS"))   # 人名牌的家族颜色可以先写 None
    nt = cfg.get("NAMETAGS")
    if isinstance(nt, dict):
        for id_, tag in nt.items():
            if not isinstance(tag, dict) or not isinstance(tag.get("name"), str):
                errors.append(f"NAMETAGS[{id_!r}] 要写成 {{\"name\": 名字, \"house\": 家名}}")
                continue
            if "color" in tag:
                errors.append(f"NAMETAGS[{id_!r}] 写了 color：家族颜色不写在每集配置里（工作流第七节），写在系列表 video/series_style.json 的 houses 里")
            extra = set(tag) - {"name", "house", "color"}
            if extra:
                errors.append(f"NAMETAGS[{id_!r}] 里不认识的项：{sorted(extra)}")
            house = tag.get("house") or ""
            if house and style is not None:
                if house not in style["houses"]:
                    errors.append(f"NAMETAGS[{id_!r}] 的家名「{house}」不在系列表 video/series_style.json 里（现有：{'、'.join(style['houses'])}）；新家先加进系列表（第 3 步定色）")
                elif style["houses"][house].get("color") is None:
                    notes.append(f"家名「{house}」的家族颜色还是占位（null）：人名牌用默认墨色，第 3 步定了色再填 video/series_style.json")
    qa = cfg.get("QA")
    if isinstance(qa, dict):
        for k in qa:
            if k not in QA_KEYS:
                errors.append(f"QA 里不认识的项 {k}（可用：{'、'.join(sorted(QA_KEYS))}）")
    return errors, todos, notes
