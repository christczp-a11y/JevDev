"""特效插件表。一个特效一个函数，用 @fx("名字") 登记；转场用 @transition("名字") 登记，走同一套查表。
加新特效 / 转场 = 在本目录新建一个 .py 写一个函数，不用改 render.py（本目录所有不以下划线开头的 .py 会自动加载）。
接口和例子见 video/motion/README.md 的「特效和转场接口」。

    特效：   fn(canvas, t, params, at)              画在 canvas.img 上，没有返回值
    转场：   fn(a, b, p, params, canvas) -> ndarray  a = 前一镜这一帧，b = 后一镜这一帧（BGR uint8），p = 0..1 的进度，返回混好的一帧
"""
import importlib.util
import inspect
import sys
import zlib
from pathlib import Path

FX = {}
TRANSITIONS = {}
_HERE = Path(__file__).resolve().parent
_loaded = set()


class FxSpec:
    def __init__(self, name, fn, layer="front", sfx=None, assets=None, check=None, dur=None):
        self.name, self.fn, self.layer, self.sfx, self.assets, self.check, self.dur = name, fn, layer, sfx, assets, check, dur
        self.local = _loading_local     # 是不是分镜表旁边的本集 / 测试插件


_loading_local = False


def _register(table, kind, name, spec):
    if name in table and table[name].local and spec.local:
        pass                                    # 本集插件可以被另一个分镜表旁边的同名插件顶替（测试里一个进程读好几个分镜表）
    elif name in table:
        raise ValueError(f"{kind} {name!r} 登记了两次（{table[name].fn.__module__} 和 {spec.fn.__module__}）：一个名字只能有一个函数")
    table[name] = spec


COMMON_FX = {"type", "at", "dur", "sfx", "layer", "note", "_avoid"}         # 所有特效都认的参数（_avoid 是 check 自己记下来的，不是分镜表里写的）
COMMON_TR = {"type", "dur", "note"}                                          # 所有转场都认的参数


def _takes_shot(fn):
    try:
        return len([p for p in inspect.signature(fn).parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]) >= 2
    except (TypeError, ValueError):
        return False


def _guarded(kind, name, check, params, common, allow_layer):
    """给 check 前面加一道「不认识的参数一律报错」：分镜表里写的参数不在这个特效登记的 params（加上通用的 type / at / dur / sfx / layer / note）里就报错，
    不许悄悄忽略（和分镜表拼错字段一律报错同一个规矩）。params=None（本集专用插件）不查。"""
    if params is None:
        return check
    allowed = set(common) | set(params)

    def full(p, shot=None):
        errs = []
        bad = sorted(k for k in p if k not in allowed)
        if bad:
            errs.append(f"{kind} {name!r} 不认识的参数 {bad}（拼错了？可用：{sorted(allowed - {'_avoid'})}）")
        if "layer" in p and (not allow_layer or p["layer"] not in ("front", "back")):
            errs.append("layer 只能是 \"front\" 或 \"back\"（特效画在人物后面 / 前面；转场没有 layer）")
        if check:
            errs += check(p, shot) if _takes_shot(check) else check(p)
        return errs
    return full


def fx(name, layer="front", sfx=None, assets=None, check=None, params=None):
    """登记一个特效。
    layer："front"（默认，画在人物和前景之上）或 "back"（画在背景之上、人物之下，光芒之类）。
    sfx：默认音效名（video/motion/sfx/<名字>.wav），在特效开始的时刻自动加；分镜表里这个特效写 "sfx": null 可以关掉。
    assets：assets(params) -> [路径]，特效要读的图（绝对路径，或者相对 video/assets 的路径）：引擎出片前检查它们在不在，并把内容算进缓存哈希。
    check：check(params) 或 check(params, shot) -> [错误说明]，出片前检查参数（缺字段、名字不对……）；返回空列表 = 没问题。后一种拿到整个镜头的字典。
    params：这个特效认的参数名列表（不含通用的 type / at / dur / sfx / layer / note）。分镜表里写了不在里面的参数，出片前报错（不许悄悄忽略）。
            本集专用 / 测试用的插件可以不写（不查）。
    分镜表里每个特效还可以写 "layer": "back" / "front"，改它画在人物后面还是前面（默认按这里登记的 layer）。
    """
    if layer not in ("front", "back"):
        raise ValueError(f"特效 {name!r} 的 layer 只能是 front 或 back")

    def deco(fn):
        _register(FX, "特效", name, FxSpec(name, fn, layer, sfx, assets, _guarded("特效", name, check, params, COMMON_FX, True)))
        return fn
    return deco


def transition(name, dur=0.4, sfx=None, assets=None, check=None, params=None):
    """登记一个转场。dur 是默认时长（秒），分镜表里 "transition": {"type": name, "dur": 0.3} 可以改。
    转场以「切点」为中心：前 dur/2 是前一镜的收尾、后 dur/2 是后一镜的开头，两镜各自多渲这么长；配音时间线不动。
    params：这个转场认的参数名列表（不含 type / dur / note），分镜表里写了别的就报错（不许悄悄忽略）；不写 = 不查。"""
    def deco(fn):
        _register(TRANSITIONS, "转场", name, FxSpec(name, fn, "front", sfx, assets, _guarded("转场", name, check, params, COMMON_TR, False), dur))
        return fn
    return deco


def _import_file(path, unique):
    spec = importlib.util.spec_from_file_location(unique, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique] = mod
    spec.loader.exec_module(mod)


def load_plugins(extra_dirs=()):
    """加载本目录所有插件；extra_dirs 是分镜表旁边的 fx/（测试和一次性特效用）。可以重复调用。"""
    global _loading_local
    for d in (_HERE, *[Path(x) for x in extra_dirs]):
        if not d.is_dir():
            continue
        _loading_local = d != _HERE
        for f in sorted(d.glob("*.py")):
            if f.name.startswith("_") or f.resolve() in _loaded:
                continue
            _loaded.add(f.resolve())
            _import_file(f, f"_fxplugin_{zlib.crc32(str(f.resolve()).encode()) % 10**8}_{f.stem}" if d != _HERE else f"fx.{f.stem}")
    _loading_local = False


def plugin_sources(extra_dirs=()):
    """所有插件源文件（算缓存哈希用）。"""
    out = []
    for d in (_HERE, *[Path(x) for x in extra_dirs]):
        if d.is_dir():
            out += sorted(d.glob("*.py"))
    return out
