"""读分镜表 → 出片计划：解析锚点、排镜头的帧范围、转场、音效、算缓存哈希；出片前把所有能查的错一次列完。
镜头怎么排：每个镜头从自己的 from 开始，到下一个镜头的 from 结束（中间没有空隙）；最后一镜到 to（省略 = 到时间线结束）。
第一镜从第 0 帧开始。转场以切点为中心（各多渲一半），配音时间线不动。
"""
import hashlib
import json
from pathlib import Path

import fx as fxreg

from . import consts as C
from .scene import Scene, SceneError
from .sprites import AssetError, AssetStore, font_file, missing_glyphs
from .timeline import AnchorError, Timeline
from .ui import UI

TOP_KEYS = {"episode", "no", "title", "voice", "shots", "rituals", "speakers", "bgm_start", "name", "note", "notes"}
KNOWN_ERRORS = (SceneError, AssetError, AnchorError, ValueError, KeyError, TypeError)


class PlanError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(errors))


class ShotPlan:
    def __init__(self, idx, spec):
        self.idx, self.spec, self.id = idx, spec, spec.get("id", f"#{idx}")
        self.f0 = self.f1 = 0
        self.pre = self.post = 0
        self.trans = None          # 进入本镜的转场：{"type", "dur", "params", "a", "b"}（a = 切点前多渲的帧，b = 切点后）
        self.key = None
        self.scene = None

    @property
    def t0(self):
        return self.f0 / C.FPS

    @property
    def dur(self):
        return (self.f1 - self.f0) / C.FPS


class Plan:
    pass


_sha_memo = {}


def file_sha1(p):
    p = Path(p)
    st = p.stat()
    k = (str(p), st.st_mtime_ns, st.st_size)
    if k not in _sha_memo:
        _sha_memo[k] = hashlib.sha1(p.read_bytes()).hexdigest()
    return _sha_memo[k]


def engine_hash(extra_fx_dirs=()):
    """引擎和特效插件所有源码 + 字体的哈希：代码或字体一变，所有缓存作废。"""
    h = hashlib.sha1(f"v{C.ENGINE_VERSION}".encode())
    files = sorted((C.MOTION / "engine").glob("*.py")) + fxreg.plugin_sources(extra_fx_dirs)
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    for f in (C.FONT_TITLE, C.FONT_BODY):
        if f.exists():
            h.update(file_sha1(f).encode())
    return h.hexdigest()


def anchor_times(spec, tl, t0):
    """分镜表里所有 "at" 锚点解析后的绝对时间（缓存哈希用：改了台词或重新配音，时间变了，镜头就要重渲）。"""
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "at" and isinstance(v, dict):
                    out.append(round(tl.resolve(v, shot_t0=t0), 4))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(spec)
    return out


def parse_shot_ids(arg):
    return [s.strip() for s in arg.split(",") if s.strip()] if arg else None


def build_plan(sb_path, only=None, scale=1.0):
    sb_path = Path(sb_path).resolve()
    base = sb_path.parent
    errors, warnings = [], []
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    bad = set(sb) - TOP_KEYS
    if bad:
        errors.append(f"分镜表顶层有不认识的字段 {sorted(bad)}（可用：{sorted(TOP_KEYS)}）")
    for k in ("episode", "voice", "shots"):
        if k not in sb:
            errors.append(f"分镜表缺 {k}")
    if errors:
        raise PlanError(errors)

    # 固定的东西：字体、背景音乐
    for f in (C.FONT_TITLE, C.FONT_BODY):
        try:
            font_file("title" if f == C.FONT_TITLE else "body")
        except AssetError as e:
            errors.append(str(e))
    if not C.BGM.exists():
        errors.append(f"找不到背景音乐 {C.BGM}")

    # 配音时间线
    voice = None
    for cand in (C.ROOT / sb["voice"], base / sb["voice"]):
        if (cand / "timeline.json").exists():
            voice = cand
            break
    if voice is None:
        raise PlanError(errors + [f"找不到配音时间线：{sb['voice']}/timeline.json（先跑第 3 步 voice.py）"])
    tl = Timeline.load(voice)

    fx_dirs = [d for d in (base / "fx",) if d.is_dir()]
    fxreg.load_plugins(fx_dirs)
    roots = [base]
    store = AssetStore(scale, roots)
    total = round(tl.duration * C.FPS)

    plan = Plan()
    plan.sb, plan.path, plan.base, plan.tl, plan.voice = sb, sb_path, base, tl, voice
    plan.fx_dirs, plan.roots, plan.scale, plan.total_frames = fx_dirs, roots, scale, total
    plan.sfx_dirs = [C.SFX_DIR] + [d for d in (base / "sfx",) if d.is_dir()]

    # ---------- 镜头的帧范围 ----------
    specs = sb["shots"]
    shots = [ShotPlan(i, s) for i, s in enumerate(specs)]
    seen = set()
    for sp in shots:
        if sp.id in seen:
            errors.append(f"镜头编号重复：{sp.id}")
        seen.add(sp.id)
    starts = []
    for sp in shots:
        try:
            if "from" not in sp.spec:
                raise AnchorError("缺 from")
            starts.append(round(tl.resolve(sp.spec["from"], edge="start") * C.FPS))
        except KNOWN_ERRORS as e:
            errors.append(f"镜头 {sp.id} from：{e}")
            starts.append(None)
    if any(s is None for s in starts):
        raise PlanError(errors)
    if starts and starts[0] > 1:
        warnings.append(f"第一镜 {shots[0].id} 的 from 在第 {starts[0]} 帧，前面的画面由第一镜补上")
    if starts:
        starts[0] = 0
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            errors.append(f"镜头 {shots[i].id} 的 from（第 {starts[i]} 帧）不在 {shots[i - 1].id}（第 {starts[i - 1]} 帧）之后")
    if errors:
        raise PlanError(errors)
    for i, sp in enumerate(shots):
        sp.f0 = starts[i]
        if i + 1 < len(shots):
            sp.f1 = starts[i + 1]
            if "to" in sp.spec:
                try:
                    to = round(tl.resolve(sp.spec["to"], edge="end") * C.FPS)
                    if to > sp.f1 + 1:
                        errors.append(f"镜头 {sp.id} 的 to（第 {to} 帧）在下一镜 {shots[i + 1].id} 开始（第 {sp.f1} 帧）之后，两镜重叠")
                except KNOWN_ERRORS as e:
                    errors.append(f"镜头 {sp.id} to：{e}")
        else:
            sp.f1 = total
            if "to" in sp.spec:
                try:
                    sp.f1 = min(total, round(tl.resolve(sp.spec["to"], edge="end") * C.FPS))
                except KNOWN_ERRORS as e:
                    errors.append(f"镜头 {sp.id} to：{e}")
        if sp.f1 - sp.f0 < 3:
            errors.append(f"镜头 {sp.id} 只有 {sp.f1 - sp.f0} 帧，太短")

    # ---------- 转场 ----------
    for i, sp in enumerate(shots):
        t = sp.spec.get("transition", "cut")
        if i == 0 or t in (None, "cut"):
            continue
        p = {"type": t} if isinstance(t, str) else dict(t)
        typ = p.get("type")
        if typ == "cut":
            continue
        if typ not in fxreg.TRANSITIONS:
            errors.append(f"镜头 {sp.id}：没有叫 {typ!r} 的转场（已登记：{sorted(fxreg.TRANSITIONS)}）")
            continue
        plug = fxreg.TRANSITIONS[typ]
        errs = plug.check(p) if plug.check else []
        if errs:
            errors.append(f"镜头 {sp.id} 转场：{'；'.join(errs)}")
        d = max(2, round(float(p.get("dur", plug.dur)) * C.FPS))
        a = d // 2
        sp.trans = {"type": typ, "params": p, "a": a, "b": d - a, "plug": plug}
        sp.pre = a
        shots[i - 1].post = d - a
    for i, sp in enumerate(shots):
        need = (sp.trans["b"] if sp.trans else 0) + (shots[i + 1].trans["a"] if i + 1 < len(shots) and shots[i + 1].trans else 0)
        if need and sp.f1 - sp.f0 < need:
            errors.append(f"镜头 {sp.id} 只有 {sp.f1 - sp.f0} 帧，装不下前后两个转场（要 {need} 帧）")
    if errors:
        raise PlanError(errors)

    # ---------- 逐镜头解析（所有错一次报完） ----------
    rit = list(sb.get("rituals", []))
    for r in rit:
        try:
            t = tl.resolve(r["at"])
        except KNOWN_ERRORS as e:
            errors.append(f"rituals {r.get('type')}：{e}")
            continue
        f = round(t * C.FPS)
        home = next((sp for sp in shots if sp.f0 <= f < sp.f1), shots[-1])
        e = dict(r)
        home.spec = dict(home.spec)
        home.spec["fx"] = list(home.spec.get("fx", [])) + [e]
    sfx_events = []
    for sp in shots:
        try:
            sc = Scene(sp.spec, tl, sp.t0, sp.dur, store, fxreg.FX)
        except KNOWN_ERRORS as e:
            errors.append(f"{type(e).__name__}：{e}")
            continue
        sp.scene = sc
        warnings += sc.warnings
        for p in sc.asset_paths():
            if not Path(p).exists():
                errors.append(f"镜头 {sp.id}：找不到素材 {p}")
        for t, name, g in sc.sfx_events():
            sfx_events.append((t, name, g, sp.id))
        if sp.trans and sp.trans["plug"].sfx:
            sfx_events.append((sp.t0, sp.trans["plug"].sfx, 0.0, sp.id))
    if errors:
        raise PlanError(errors)
    plan.sfx_events = sfx_events
    for t, name, g, sid in sfx_events:
        if plan_sfx_path(plan, name) is None:
            errors.append(f"镜头 {sid}：找不到音效 {name!r}（要 {name}.wav，放在 video/motion/sfx/）")

    # ---------- 字：标题、字幕 ----------
    lines = sb.get("title") or []
    if not isinstance(lines, list) or len(lines) > 2 or not all(isinstance(x, str) for x in lines):
        errors.append("title 要写成 1–2 行文字的列表，比如 [\"最强的智伯，\", \"为什么输了？\"]")
    text = "".join(lines if isinstance(lines, list) else []) + "".join(l["text"] for l in tl.lines) + str(sb.get("name", ""))
    for sp in shots:
        for e in sp.spec.get("fx", []):
            if isinstance(e.get("text"), str):
                text += e["text"]
    try:
        miss = missing_glyphs(text)
    except AssetError as e:
        miss = []
        errors.append(str(e))
    if miss:
        errors.append(f"这些字两种字体里都没有：{''.join(miss)}（换字，或补字体子集）")

    # ---------- 选镜头 + 输出范围 ----------
    ids = [sp.id for sp in shots]
    if only:
        unknown = [x for x in only if x not in ids]
        if unknown:
            errors.append(f"--shots 里没有这些镜头：{unknown}（分镜表里有：{ids}）")
        sel = [sp for sp in shots if sp.id in only]
    else:
        sel = shots
    plan.shots, plan.selected = shots, sel
    if errors:
        raise PlanError(errors)
    plan.ranges = [(sp.f0, sp.f1) for sp in sel]
    plan.out_frames = sum(b - a for a, b in plan.ranges)
    plan.t_end = max(b for a, b in plan.ranges) / C.FPS

    # 每句台词的配音文件（只查输出范围内的）
    for i, ln in enumerate(tl.lines):
        if tl.is_speech(i) and any(round(ln["t1"] * C.FPS) > a and round(ln["t0"] * C.FPS) < b for a, b in plan.ranges):
            if tl.audio_path(i) is False:
                errors.append(f"第 {i} 句「{ln['text']}」找不到配音文件（{ln.get('audio')} / {ln.get('series_audio')}）")
    if errors:
        raise PlanError(errors)

    # ---------- 缓存哈希 ----------
    eh = engine_hash(fx_dirs)
    for sp in shots:
        sc = sp.scene
        payload = {"engine": eh, "S": scale, "f0": sp.f0, "f1": sp.f1, "pre": sp.pre, "post": sp.post, "spec": sp.spec,
                   "anchors": anchor_times(sp.spec, tl, sp.t0),
                   "speech": {a.who: [[round(x, 4) for x in s] for s in sc.speech_spans(a.who)] for a in sc.actors if a.who},
                   "assets": sorted({file_sha1(p) for p in sc.asset_paths()})}
        sp.key = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:20]
    plan.warnings = warnings
    plan.engine_hash = eh
    plan.ui = UI(store, tl, sb)
    return plan


def plan_sfx_path(plan, name):
    for d in plan.sfx_dirs:
        p = Path(d) / f"{name}.wav"
        if p.exists():
            return p
    return None
