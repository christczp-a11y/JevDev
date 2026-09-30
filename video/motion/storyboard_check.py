#!/usr/bin/env python
"""分镜表检查（工作流第 4 步的过关脚本）：只查分镜表上能查的静态规则；出片后的闪烁 / 静止 / 响度 render.py 已经在查，这里不重复。

用法（Git Bash，仓库根目录，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）：
  python video/motion/storyboard_check.py video/stories/tj01/storyboard.json     （也可以只写集名 tj01）
  --json 结果.json      把所有发现写成 JSON（{errors, warnings, info, stats}）
  --registry 路径       换一份素材登记表（默认 video/assets/REGISTRY.md）
  --no-plugins          不加载 video/motion/fx/ 里的特效插件，特效只按名字分类（测试用：不受特效包进度影响）
  --assets-root 目录    换一个素材根目录（默认 video/assets/；测试用，配合 --registry，让测试不受素材增减影响）
退出码：0 = 没有错误（可以有警告）；1 = 有错误（一次列完，带镜头编号）；2 = 输入 / 环境坏了（分镜表读不了、找不到配音时间线、找不到登记表），没有检查。

查什么（错误 = 退出码 1；警告只打印）——规则出处：docs/规则/节奏和特效.md 第二、七节，docs/规则/版式和画风.md，docs/施工计划-动态漫画引擎.md 第四节 C
  [格式]   顶层 / 镜头 / 人物 / 图层里拼错的字段、缺 id / from、镜头编号重复；引擎解析（video/motion/engine/scene.py）报的错（出场名、小动作名、调色名、镜头运动、特效自己的 check）
  [锚点]   每个 from / to / at 都要能在配音时间线上对上（line 越界、word 找不到、写死秒数、from 不递增、to 压到下一镜）；
           at 落在自己的镜头结束之后 = 错（永远不会出现），在镜头开始之前 0.25 秒以上 = 警告（是不是锚错了句）
  [长度]   镜头长度：< 0.8 秒 = 错；> 7 秒 = 错（讲知识点最长 5–7 秒）；长于 5 秒的一集不超过 8 个；快切（0.8–1.2 秒）连续不超过 5 个
  [频率]   每分钟 18–24 个镜头（不足一分钟按比例，各放宽 1 个）；前 3 秒至少 3 次视觉变化；平均每 3 秒以内一次视觉变化
  [静止]   任何画面静止不超过 1.5 秒：镜头运动（推 / 拉 / 摇，幅度 ≥ 1%）盖不到的地方，要有换表情 / 小动作 / 特效 / 补间 / 震屏……（默认缓推的镜头不会静止；写 amount 0 才会）
  [特效]   讲知识点的镜头不堆：新出现的东西（特效 + 中途出场的人物 / 图层）≤ 3、不快切、不闪白；别的镜头特效超过 5 个警告
           「讲知识点的镜头」= 镜头 note 里有「知识」两个字，或者用了清单 / 属性卡 / 地图 / 进度物类特效
  [闪烁]   闪白（flash 特效、名字里有 flash 的转场）一集 ≤ 4 次、任何 1 秒内 ≤ 3 次；分镜表里给闪白写了参数的话再查：亮度 ≤ 60%、时长 ≤ 0.12 秒、不用红色、不反色（alpha / strength / intensity / dur / color）
           （特效包的 flash 自己固定 55% 亮度、几帧，不带参数，所以主要查次数）
  [安全区] 脸（人物图上面 40%、中间 50% 宽）要在 y 360–1400、x 80–940（右边 140 是平台遮挡区）以内，按镜头运动算到画面里的位置；
           props/ 里的关键道具、砸字 / 大字标题 / 游戏卡片 / 清单 / 属性卡的中心点同样（人名牌和清单按估出来的方框查）；砸字估出来的宽度超出 x 80–940 只警告；贴纸进了遮挡区只警告
  [素材]   图片（背景 / 人物 / 换表情 / 前景 / 特效自带的）和音效在不在；登记表里：没登记 = 错，「停用」= 错，「试做集」范围用在新集 = 错，「宣传图」范围 = 错，「未定稿」= 警告
  [放大]   屏幕显示 ÷ 原图 ≤ 1.3，含镜头放大（远景层按视差系数折算；blur 的背景不查）
  [朝向]   按登记表的原图朝向（左 / 右 / 正面）算，flip 反过来：不是正面的人物要面向说话的人（有人在这一镜说话）；旁白的镜头面向同镜头里的别人；一个人站着背对全场警告
  [人名牌] 每个人物（不含司马光；按 who，没写按 id）第一次出场的那个镜头里，要有一个人名牌特效（name_plate；参数里带人名就按人名对，没带就按数量对）；
           人名牌看得清的时间 < 1.5 秒报错（按分镜表的时间算：落下的 0.42 秒不算，写了 dur 的话 dur 以后的淡出也不算）
  [翻转]   交领人物不许翻转（PITFALLS M1，翻过来衣襟就成了左衽）：chars/ 下的图 flip: true 报错；例外：司马光（sgm_，圆领）、皮影（文件名含 shadow）、登记表备注里写了「可翻转」的图、道具 / 物件
  [压脸]   贴纸 / 砸字 / 水花 / 闪粉 / 纸屑的框和任何人物的脸框重叠（脸框面积的 5% 以上）报错（M4）；写了 follow 的贴纸（挂在人物身上）不算；
           闪粉 / 纸屑没写 avoid = 特效包自动避开脸，不查；写了 avoid: [] 关掉、或者写的框没盖住脸，而粒子的范围（闪粉 area，纸屑整个画面）碰到脸就报错
  [集中线] lines_focus 必须写 clear（不画线的留白圈：[x, y, r]，或者一个半径数、圆心取 center / pos / [540, 900]），而且这个圈要盖住这一镜主体（面积最大的人物）的脸框（M2）

特效名字怎么分类：storyboard_check.py 里的 FX_KINDS（按名字里的子串；特效包 fx/ 里的 name_plate = 人名牌、smash = 砸字、big_title / card_* = 大字标题和游戏卡片、
checklist / stat_card / map* / progress = 讲知识点的、flash = 闪白、lines_* / sparkle / rain 等 = 氛围）；特效包加了新名字，不对的话改这张表（一处）。
名字既不在 fx/ 里登记、也不在 STUB_FX 里的特效 = 错（拼错）；在 STUB_FX 里但 fx/ 里还没登记的 = 警告（渲染会报错，等特效包）。
安全区里的特效位置按特效包的约定算：sticker 的 pos 是图中心、depth 默认 1（跟着镜头），别的特效钉在屏幕上（depth 0）；name_plate 的 pos 是牌子的挂点（顶部中点），
牌子高 ≈ (144 + 120 × 字数 + 44 × 有身份) × size（默认 1.15）；checklist 的 pos 是第一条的中心，每条往下 128 像素、宽 w（默认 780）；smash 宽 ≈ min(字号 × 0.95 × 字数, 920)。
"""
import argparse
import json
import math
import re
import sys
import traceback
from functools import lru_cache
from pathlib import Path

MOTION = Path(__file__).resolve().parent
VIDEO = MOTION.parent
sys.path.insert(0, str(MOTION))
sys.path.insert(0, str(VIDEO))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from PIL import Image  # noqa: E402

import fx as fxreg  # noqa: E402
import registry_check as RC  # noqa: E402
from engine import consts as C  # noqa: E402
from engine.anim import CONTINUOUS, Camera, Tracks  # noqa: E402
from engine.canvas import CX, CY  # noqa: E402
from engine.plan import TOP_KEYS  # noqa: E402
from engine.scene import ACTOR_KEYS, ACTS, LAYER_KEYS, SHOT_KEYS, Scene, SceneError  # noqa: E402
from engine.sprites import AssetError, AssetStore  # noqa: E402
from engine.timeline import AnchorError, Timeline  # noqa: E402

FPS = C.FPS
REGISTRY = C.ASSETS / "REGISTRY.md"

# ------------------------------------------------------------------ 规则常量（出处见文件头）
SHOT_MIN, SHOT_MAX = 0.8, 7.0
FAST_MAX = 1.2                      # 快切：0.8–1.2 秒
FAST_RUN_MAX = 5
LONG_OVER, LONG_MAX_COUNT = 5.0, 8
RATE_RANGE = (18.0, 24.0)
OPEN_WINDOW, OPEN_MIN_CHANGES = 3.0, 3
CHANGE_MEAN_MAX = 3.0
STATIC_MAX = C.STATIC_MAX_SEC       # 1.5
MOVE_MIN_AMOUNT, MOVE_MIN_PX = 0.01, 10.0
FLASH_MAX_EPISODE, FLASH_MAX_SEC = 4, C.FLASH_MAX_PER_SEC
FLASH_MAX_STRENGTH, FLASH_MAX_DUR = 0.6, 0.12
KNOW_MAX_NEW, GENERAL_FX_WARN = 3, 5
SAFE = (80.0, 360.0, 1000.0, 1400.0)      # 主体安全区：x0, y0, x1, y1
OCC_X, OCC_Y = C.W - 140.0, C.H - 300.0   # 平台遮挡区：右边 140、最下面 300
FACE = (0.25, 0.75, 0.0, 0.40)            # 脸在人物图里的位置：x0, x1, y0, y1（占图宽 / 图高的比例）
UPSCALE_MAX, UPSCALE_TOL = C.MAX_UPSCALE, 0.005
SERIES_HOST = {"司马光", "sgm"}           # 系列讲解人：不要求人名牌
AT_EARLY_WARN, AT_LATE_TOL = 0.25, 0.05
SWAP_BOUNCE = C.BOUNCE_DUR
DEFAULT_FX_LEN = 0.5                      # 特效没写 dur 时，当作「变化」持续多久（静止检查用）

# 特效按名字分类：(类别, 名字里含有这些子串之一)，从上往下第一个对上的算。名字来自《节奏和特效》第五节；特效包定了名字再改这里。
FX_KINDS = [
    ("flash", ("flash", "闪")),
    ("namecard", ("name_plate", "nameplate", "namecard", "name_card", "nametag", "name_tag", "人名牌")),
    ("slam", ("slam", "smash", "砸")),
    ("title", ("title", "banner", "大字")),
    ("gamecard", ("card_", "gamecard", "game_card", "游戏卡", "quest", "mvp")),
    ("list", ("list", "清单")),
    ("stat", ("stat", "attr", "属性")),
    ("map", ("map", "地图")),
    ("gauge", ("gauge", "progress", "进度")),
    ("focus", ("lines_focus", "focus_lines", "集中线")),
    ("splash", ("splash", "水花")),
    ("sparkle", ("sparkle", "闪粉")),
    ("confetti", ("confetti", "纸屑")),
    ("ambient", ("dust", "rain", "rays", "glow", "fire", "flame", "particle", "lines_", "speed", "radial", "tone", "氛围", "光芒", "速度线")),
    ("sticker", ("sticker", "贴纸")),
    ("ritual", ("kaoni", "card", "考你", "人物卡")),
]
KNOWLEDGE_KINDS = {"list", "stat", "map", "gauge"}
TEXT_KINDS = {"slam", "title", "namecard", "gamecard", "list", "stat"}     # 重要的字 / 卡片：中心点要在安全区里
AMBIENT_KINDS = {"ambient", "focus", "sparkle", "confetti"}                # 一直在画面上流动、不算「一样东西」、算画面在动的特效
OVERLAY_KINDS = {"sticker", "slam", "splash", "sparkle", "confetti"}       # 不许压脸的
OVERLAP_MIN = 0.05                                                         # 和脸框重叠超过脸框面积的这么多就算压脸
PLATE_FALL, PLATE_MIN_CLEAR = 0.42, 1.5                                    # name_plate 落下来要 0.42 秒；看得清的时间至少 1.5 秒
SPARKLE_AREA = (80.0, 360.0, 1000.0, 1400.0)
SUBJECT_LATER_WINS = 0.85                                                  # 主体：面积最大的人物；后画的（在上面的）面积 ≥ 最大的 85% 时取它
STUB_FX = ("sticker", "flash", "name_plate", "smash", "big_title", "checklist", "stat_card", "map", "progress", "kaoni", "person_card",
           "card_quest", "card_fail", "card_title", "card_mvp", "splash", "sparkle", "confetti", "lines_focus", "lines_radial", "lines_speed", "dust", "rays")           # --no-plugins 时认得的名字（和特效包 fx/ 里登记的一致）；有插件时以插件为准
STUB_TRANSITIONS = ("dissolve", "flash")
NAME_HINT_SKIP = {"type", "sfx", "at", "note", "dur", "layer"}


def kind_of(name):
    n = str(name).lower()
    for kind, subs in FX_KINDS:
        if any(s in n for s in subs):
            return kind
    return "other"


class Fatal(Exception):
    """输入 / 环境坏了（退出码 2）。"""


class Report:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []
        self.times = {}
        self._seen = set()

    def _add(self, lst, level, tag, shot, msg):
        key = (level, tag, shot, msg)
        if key in self._seen:
            return
        self._seen.add(key)
        lst.append({"tag": tag, "shot": shot, "msg": msg})

    def err(self, tag, msg, shot=None):
        self._add(self.errors, "e", tag, shot, msg)

    def warn(self, tag, msg, shot=None):
        self._add(self.warnings, "w", tag, shot, msg)


def fmt(f, times=None):
    when = ""
    if f["shot"] is not None and times and f["shot"] in times:
        when = f"（{times[f['shot']][0]:.1f}–{times[f['shot']][1]:.1f} 秒）"
    return f"[{f['tag']}] " + (f"镜头 {f['shot']}{when}：" if f["shot"] is not None else "") + f["msg"]


# ------------------------------------------------------------------ 素材 / 登记表
@lru_cache(maxsize=None)
def img_size(path):
    with Image.open(path) as im:
        return im.size


def load_registry(path):
    p = Path(path)
    if not p.exists():
        raise Fatal(f"找不到素材登记表 {p}")
    assets, persons, _ = RC.parse(p.read_text(encoding="utf-8"))
    rows = {}
    for key, (_, c) in assets.items():
        rows[key] = {"owner": c[1], "facing": c[2], "status": RC.status_of(c[5]), "note": c[6], "scope": c[7]}
    return rows


def owner_name(owner):
    """「智伯 `zb_`」→（智伯，zb）。"""
    m = re.match(r"^([^`（(]+)", owner or "")
    name = m.group(1).strip() if m else ""
    p = re.search(r"`([a-z0-9]+)_?`", owner or "")
    return name, (p.group(1) if p else "")


class Ctx:
    def __init__(self):
        self.asset_msgs = {}

    def note_asset(self, level, key, msg, sid):
        self.asset_msgs.setdefault((level, key, msg), [])
        if sid not in self.asset_msgs[(level, key, msg)]:
            self.asset_msgs[(level, key, msg)].append(sid)


def flush_asset_msgs(ctx, rep):
    for (level, _key, msg), sids in ctx.asset_msgs.items():
        more = f"（同样的图还用在镜头 {'、'.join(map(str, sids[1:8]))}{'……' if len(sids) > 8 else ''}）" if len(sids) > 1 else ""
        (rep.err if level == "e" else rep.warn)("素材", msg + more, sids[0])


def load_storyboard(sb_arg):
    """分镜表路径或集名 → (分镜表 dict, 绝对路径)；读不了就 Fatal（退出码 2）。storyboard_jev.py 也用这个。"""
    p = Path(sb_arg)
    if not (p.suffix == ".json" and p.exists()):
        q = C.VIDEO / "stories" / sb_arg / "storyboard.json"
        if not q.exists():
            raise Fatal(f"找不到分镜表：{sb_arg}（也没有 {q}）")
        p = q
    p = p.resolve()
    try:
        sb = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Fatal(f"分镜表读不了或不是 JSON：{p}（{e}）")
    if not isinstance(sb, dict):
        raise Fatal("分镜表顶层要是对象")
    return sb, p


def find_voice(sb, base):
    v = sb.get("voice")
    if not isinstance(v, str):
        raise Fatal("分镜表缺 voice（配音目录）")
    for cand in (C.ROOT / v, base / v):
        if (cand / "timeline.json").exists():
            return cand
    raise Fatal(f"找不到配音时间线：{v}/timeline.json（先跑第 3 步 voice.py）")


def rel_of(tl, t0):
    return lambda a: tl.resolve(a, shot_t0=t0) - t0


# ------------------------------------------------------------------ 第 1 步：格式
def check_format(sb, rep):
    bad = set(sb) - TOP_KEYS
    if bad:
        rep.err("格式", f"分镜表顶层有不认识的字段 {sorted(bad)}（可用：{sorted(TOP_KEYS)}）")
    for k in ("episode", "voice", "shots"):
        if k not in sb:
            rep.err("格式", f"分镜表缺 {k}")
    shots = sb.get("shots")
    if not isinstance(shots, list) or not shots:
        raise Fatal("shots 要是非空列表")
    seen = set()
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            raise Fatal(f"shots[{i}] 不是对象")
        sid = s.get("id", f"#{i}")
        if "id" not in s:
            rep.err("格式", f"shots[{i}] 缺 id")
        if sid in seen:
            rep.err("格式", f"镜头编号重复：{sid}")
        seen.add(sid)
        bad = set(s) - SHOT_KEYS
        if bad:
            rep.err("格式", f"不认识的字段 {sorted(bad)}（拼错了？可用：{sorted(SHOT_KEYS)}）", sid)
        if "from" not in s:
            rep.err("格式", "缺 from", sid)
        for grp, allowed in (("bg", LAYER_KEYS), ("fg", LAYER_KEYS), ("actors", ACTOR_KEYS)):
            for j, e in enumerate(s.get(grp, []) or []):
                if not isinstance(e, dict):
                    raise Fatal(f"镜头 {sid} {grp}[{j}] 不是对象")
                bad = set(e) - allowed
                if bad:
                    rep.err("格式", f"{grp}[{j}] 不认识的字段 {sorted(bad)}（拼错了？可用：{sorted(allowed)}）", sid)
        for j, e in enumerate(s.get("fx", []) or []):
            if not isinstance(e, dict) or "type" not in e:
                rep.err("格式", f"fx[{j}] 要写成 {{\"type\": 特效名, \"at\": 锚点, ...}}", sid)
    for j, r in enumerate(sb.get("rituals", []) or []):
        if not isinstance(r, dict) or "type" not in r:
            rep.err("格式", f"rituals[{j}] 要写成 {{\"type\": 特效名, \"at\": 锚点, ...}}")


# ------------------------------------------------------------------ 第 2 步：锚点 → 镜头的时间范围
class Shot:
    def __init__(self, idx, spec):
        self.idx, self.spec, self.id = idx, spec, spec.get("id", f"#{idx}")
        self.f0 = self.f1 = None

    @property
    def t0(self):
        return self.f0 / FPS

    @property
    def t1(self):
        return self.f1 / FPS

    @property
    def dur(self):
        return (self.f1 - self.f0) / FPS


def compute_ranges(shots, tl, rep):
    """同 engine/plan.py：每镜从自己的 from 到下一镜的 from，最后一镜到 to（省略 = 时间线结束）。返回是不是全部算出来了。"""
    total = round(tl.duration * FPS)
    starts, ok = [], True
    for sh in shots:
        try:
            starts.append(round(tl.resolve(sh.spec["from"], edge="start") * FPS))
        except (AnchorError, KeyError, TypeError, ValueError) as e:
            rep.err("锚点", f"from：{e}", sh.id)
            starts.append(None)
            ok = False
    if not ok:
        return False
    starts[0] = 0
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            rep.err("锚点", f"from（第 {starts[i]} 帧）不在上一镜 {shots[i - 1].id}（第 {starts[i - 1]} 帧）之后", shots[i].id)
            ok = False
    if not ok:
        return False
    for i, sh in enumerate(shots):
        sh.f0 = starts[i]
        sh.f1 = starts[i + 1] if i + 1 < len(shots) else total
        if "to" in sh.spec:
            try:
                to = round(tl.resolve(sh.spec["to"], edge="end") * FPS)
                if i + 1 < len(shots):
                    if to > sh.f1 + 1:
                        rep.err("锚点", f"to（第 {to} 帧）在下一镜 {shots[i + 1].id} 开始（第 {sh.f1} 帧）之后，两镜重叠", sh.id)
                        ok = False
                else:
                    sh.f1 = min(total, to)
            except (AnchorError, TypeError, ValueError) as e:
                rep.err("锚点", f"to：{e}", sh.id)
                ok = False
        if sh.f1 - sh.f0 < 3:
            rep.err("锚点", f"只有 {sh.f1 - sh.f0} 帧，太短", sh.id)
            ok = False
    return ok


def walk_at(o, path=""):
    """镜头里所有 "at" 键：(路径, 值)。"""
    if isinstance(o, dict):
        for k, v in o.items():
            p = f"{path}.{k}" if path else k
            if k == "at":
                yield p, v
            else:
                yield from walk_at(v, p)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_at(v, f"{path}[{i}]")


def check_anchors(sh, spec, tl, rep):
    for path, a in walk_at(spec):
        try:
            t = tl.resolve(a, shot_t0=sh.t0)
        except (AnchorError, TypeError, ValueError) as e:
            rep.err("锚点", f"{path}：{e}", sh.id)
            continue
        if t > sh.t1 + AT_LATE_TOL:
            if path.startswith("sfx"):
                rep.warn("锚点", f"{path} 在镜头结束之后 {t - sh.t1:.2f} 秒（音效会在别的镜头里响；是不是锚错了句？）", sh.id)
            else:
                rep.err("锚点", f"{path} 在镜头结束之后 {t - sh.t1:.2f} 秒（永远不会出现；是不是锚错了句？）", sh.id)
        elif t < sh.t0 - AT_EARLY_WARN:
            rep.warn("锚点", f"{path} 在镜头开始之前 {sh.t0 - t:.2f} 秒（第一帧就已经在演了；是不是锚错了句？）", sh.id)


# ------------------------------------------------------------------ 第 3 步：镜头长度、频率
def check_lengths_and_rate(shots, tl, rep, stats):
    minutes = max(sh.f1 for sh in shots) / FPS / 60
    stats["shots"], stats["duration_s"] = len(shots), round(minutes * 60, 2)
    for sh in shots:
        if sh.dur < SHOT_MIN - 1.5 / FPS:
            rep.err("长度", f"只有 {sh.dur:.2f} 秒，短于 {SHOT_MIN} 秒（最短的快切也要 0.8 秒；并到相邻的镜头里，或者在同一个镜头里换表情）", sh.id)
        if sh.dur > SHOT_MAX + 1.5 / FPS:
            rep.err("长度", f"{sh.dur:.2f} 秒，长于 {SHOT_MAX:g} 秒（讲知识点最长 5–7 秒；拆成两个镜头，或者换表情 / 换景别）", sh.id)
    longs = [sh for sh in shots if sh.dur > LONG_OVER + 1.5 / FPS]
    stats["long_shots"] = len(longs)
    if len(longs) > LONG_MAX_COUNT:
        rep.err("长度", f"长于 {LONG_OVER:g} 秒的镜头有 {len(longs)} 个，一集最多 {LONG_MAX_COUNT} 个：" + "、".join(f"{s.id}（{s.dur:.1f}s）" for s in longs))
    run, best, start, run_start = 0, 0, None, None
    for sh in shots:
        if SHOT_MIN - 1.5 / FPS <= sh.dur <= FAST_MAX + 1.5 / FPS:
            run += 1
            if run == 1:
                run_start = sh
            if run > FAST_RUN_MAX and run > best:
                best, start = run, run_start
        else:
            run = 0
    if best:
        rep.err("长度", f"从镜头 {start.id} 起连续 {best} 个快切镜头（0.8–1.2 秒），快切连续不超过 {FAST_RUN_MAX} 个，中间要回到正常节奏（1.5–4 秒）")
    # 频率
    n = len(shots)
    rate = n / minutes if minutes > 0 else 0
    stats["rate_per_min"] = round(rate, 1)
    if minutes >= 1.0:
        lo, hi = RATE_RANGE[0] - 0.5, RATE_RANGE[1] + 0.5
        ok = lo <= rate <= hi
    else:
        ok = RATE_RANGE[0] * minutes - 1 <= n <= RATE_RANGE[1] * minutes + 1
    if not ok:
        rep.err("频率", f"{n} 个镜头 / {minutes * 60:.0f} 秒 = 每分钟 {rate:.1f} 个，要在 {RATE_RANGE[0]:g}–{RATE_RANGE[1]:g} 个之间"
                        + ("（太慢：拆镜头，一句一镜）" if rate < RATE_RANGE[0] else "（太快：并镜头）"))
    per_min = {}
    for sh in shots:
        per_min[int(sh.t0 // 60) + 1] = per_min.get(int(sh.t0 // 60) + 1, 0) + 1
    rep.info.append("每分钟镜头数：" + "，".join(f"第 {m} 分钟 {c}" for m, c in sorted(per_min.items())))


# ------------------------------------------------------------------ 第 4 步：逐镜分析
def presence_window(spec, rel, dur):
    """人物「完全在画面里」的时间段：出场结束 → 开始走出画面（镜头内秒）。"""
    w0 = 0.0
    e = spec.get("enter")
    if e is not None:
        e = {"type": e} if isinstance(e, str) else e
        typ = e.get("type")
        w0 = (rel(e["at"]) if "at" in e else 0.0) + float(e.get("dur", C.ENTER_DUR.get(typ, 0.4)))
    w1 = dur
    for a in spec.get("acts", []) or []:
        if a.get("do") == "exit":
            w1 = min(w1, rel(a["at"]))
    return min(w0, max(dur - 0.05, 0.0)), max(w1, min(w0, dur))


def samples(w0, w1, n=3):
    if w1 - w0 < 0.05:
        return [max(w0, 0.0)]
    return [w0 + (w1 - w0) * k / (n - 1) for k in range(n)]


def screen_xf(cam, t, t_abs, x, y, depth):
    zoom, px, py, _ = cam.state(t, t_abs)
    Z = 1.0 + (zoom - 1.0) * depth
    return CX + Z * (x - CX) - depth * px, CY + Z * (y - CY) - depth * py, Z


def actor_frame(a, cam, t, t0):
    """人物在镜头内 t 秒时：(脸框, 整个人面积)（屏幕坐标，含镜头运动和补间）；这时人物不在画面里（出场以前 / 走出去以后）或者图找不到 = None。"""
    if a.get("window") and not (a["window"][0] - 1e-6 <= t <= a["window"][1] + 1e-6):
        return None
    r, h = a["ref"], float(a["spec"]["h"])
    for at, r2, h2 in a["swaps"]:
        if t >= at and r2.file:
            r, h = r2, h2
    if not r.file:
        return None
    v = a["tracks"].value(t)
    sw, shh = r.size
    wd = sw * h / shh * v["scale"] * v["sx"]
    hd = h * v["scale"] * v["sy"]
    X, Y, Z = screen_xf(cam, t, t0 + t, v["x"], v["y"], float(a["spec"].get("depth", 1.0)))
    w, hh = wd * Z, hd * Z
    left, top = X - 0.5 * w, Y - hh
    return (left + FACE[0] * w, top + FACE[2] * hh, left + FACE[1] * w, top + FACE[3] * hh), w * hh


def pick_subject(frames):
    """frames = [(人物, 脸框, 面积)] → 这一镜的主体：面积最大的；后画的（在上面的）面积 ≥ 最大的 85% 时取它。"""
    if not frames:
        return None
    best = max(range(len(frames)), key=lambda k: frames[k][2])
    for k in range(len(frames) - 1, best, -1):
        if frames[k][2] >= SUBJECT_LATER_WINS * frames[best][2]:
            return frames[k]
    return frames[best]


def overlap_frac(a, b):
    """a、b 两个框 (l, t, r, b)：相交面积 ÷ b 的面积。"""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    area = (b[2] - b[0]) * (b[3] - b[1])
    return w * h / area if w > 0 and h > 0 and area > 0 else 0.0


def overlay_box(kind, e, X, Y):
    """贴纸 / 砸字 / 水花在屏幕上大致占的方框，估不出来 = None。X, Y 是 pos 变换到屏幕上的位置。"""
    if kind == "sticker":
        size = float(e.get("size", 200))
        if e.get("name"):
            f = C.MOTION / "stickers" / f"{e['name']}.png"
            aspect = img_size(f)[0] / img_size(f)[1] if f.exists() else 1.0
            w, h = size * aspect, size
        else:
            w, h = size * len(str(e.get("text", ""))) * 0.95 + size * 0.15, size * 1.15
        return X - w / 2, Y - h / 2, X + w / 2, Y + h / 2
    if kind == "slam":
        return fx_box("slam", e, X, Y)
    if kind == "splash":                               # 水冠往上蹿、水滴往两边溅：按特效包的速度估的范围
        k = float(e.get("size", 1.0))
        return X - 300 * k, Y - 380 * k, X + 300 * k, Y + 40
    return None


def check_overlays(sh, out, cam, rep):
    """M4：贴纸 / 砸字 / 水花 / 闪粉 / 纸屑不许压脸。"""
    t0, dur = sh.t0, sh.dur
    for kind, at, e in out["fx"]:
        if kind not in OVERLAY_KINDS or (kind == "sticker" and "follow" in e):
            continue
        typ = e.get("type")
        rel_at = max(at - t0, 0.0)
        end = min(dur, rel_at + float(e["dur"])) if isinstance(e.get("dur"), (int, float)) else dur
        if kind == "splash":
            end = min(end, rel_at + 1.9)
        if end < rel_at:
            continue
        region, avoid = None, None
        if kind in ("sparkle", "confetti"):
            avoid = e.get("avoid")
            if avoid is None:
                continue                               # 没写 avoid = 特效包自动避开脸
            if not (isinstance(avoid, list) and all(isinstance(b, (list, tuple)) and len(b) == 4 for b in avoid)):
                continue
            region = tuple(e.get("area", SPARKLE_AREA)) if kind == "sparkle" else (0.0, 0.0, float(C.W), float(C.H))
        pos = e.get("pos")
        for t in samples(min(rel_at + 0.35, end), end):
            if region is None:
                if not (isinstance(pos, list) and len(pos) == 2):
                    break
                X, Y, _ = screen_xf(cam, t, t0 + t, float(pos[0]), float(pos[1]), float(e.get("depth", 1.0 if kind == "sticker" else 0.0)))
                box = overlay_box(kind, e, X, Y)
                if box is None:
                    break
            else:
                box = region
            hit = None
            for a in out["actors"]:
                fr = actor_frame(a, cam, t, t0)
                if fr is None:
                    continue
                if avoid and any(b[0] <= fr[0][0] and b[1] <= fr[0][1] and b[2] >= fr[0][2] and b[3] >= fr[0][3] for b in avoid):
                    continue                            # 写的 avoid 框把脸整个盖住了
                f = overlap_frac(box, fr[0])
                if f > OVERLAP_MIN and (hit is None or f > hit[1]):
                    hit = (a, f)
            if hit:
                a, f = hit
                what = {"sticker": f"贴纸「{e.get('name') or e.get('text')}」", "slam": f"砸字「{e.get('text')}」", "splash": "水花"}.get(kind, f"{typ}（{kind}）的范围")
                fix = "写 follow 挂在人物身上、或挪到主体旁边（右上方）" if kind == "sticker" else ("挪开" if region is None else "别写 avoid: []（让特效包自动避开脸），或者 avoid 的框把脸盖住")
                rep.err("压脸", f"{what}（{t:.1f} 秒时）盖住了 {a['who']} 的脸，重叠脸框的 {f:.0%}（M4）：{fix}", sh.id)
                break


def check_focus_lines(sh, out, cam, rep):
    """M2：lines_focus 要写 clear，clear 圈要盖住这一镜主体的脸框。"""
    t0, dur = sh.t0, sh.dur
    for kind, at, e in out["fx"]:
        if kind != "focus" or "focus" not in str(e.get("type")):
            continue
        clear = e.get("clear")
        if clear is None:
            rep.err("集中线", f"{e.get('type')} 没写 clear（不画线的留白圈）：集中线压在脸上像画面被划花（M2）；写 clear，圈要盖住主体的脸", sh.id)
            continue
        try:
            if isinstance(clear, (list, tuple)):                       # [x, y, r]：留白圈自己的圆心和半径
                cx, cy, kr = (float(v) for v in clear)
            else:                                                       # 一个数：以 center（没写 = pos，再没写 = [540, 900]）为圆心的半径
                c = e.get("center", e.get("pos", [C.W / 2, 900]))
                cx, cy, kr = float(c[0]), float(c[1]), float(clear)
        except (TypeError, ValueError, IndexError):
            continue                                                    # 写坏了：特效自己的 check 去报
        if kr <= 0:
            rep.err("集中线", f"{e.get('type')} 的 clear 半径是 {kr:g}：留白圈没有大小，等于没留（M2）", sh.id)
            continue
        rel_at = max(at - t0, 0.0)
        end = min(dur, rel_at + float(e["dur"])) if isinstance(e.get("dur"), (int, float)) else dur
        for t in samples(min(rel_at + 0.25, end), end):
            frames = [(a, fr[0], fr[1]) for a in out["actors"] for fr in [actor_frame(a, cam, t, t0)] if fr]
            subj = pick_subject(frames)
            if not subj:
                continue
            a, face, _ = subj
            far = max(math.hypot(x - cx, y - cy) for x in (face[0], face[2]) for y in (face[1], face[3]))
            if far > kr:
                rep.err("集中线", f"{e.get('type')} 的 clear 圈（圆心 ({cx:.0f}, {cy:.0f})，半径 {kr:.0f}）没盖住主体 {a['who']} 的脸框"
                                  f"（{t:.1f} 秒时脸框最远的角离圆心 {far:.0f}）：圆心对准脸，clear 至少 {far:.0f}（M2）", sh.id)
                break


def check_plate_time(sh, out, rep):
    """人名牌看得清的时间（不算落下的 0.42 秒；写了 dur 的话，dur 以后的淡出也不算）≥ 1.5 秒。"""
    for kind, at, e in out["fx"]:
        if kind != "namecard":
            continue
        span = sh.t1 - at
        if isinstance(e.get("dur"), (int, float)) and not isinstance(e.get("dur"), bool):
            span = min(span, float(e["dur"]))
        clear = span - PLATE_FALL
        if clear < PLATE_MIN_CLEAR - 1e-6:
            rep.err("人名牌", f"{e.get('type')}「{e.get('name')}」从 {at - sh.t0:.1f} 秒起在这个镜头里只看得清 {max(clear, 0):.1f} 秒（不算落下的 {PLATE_FALL} 秒"
                              f"{'、dur 以后的淡出' if 'dur' in e else ''}），要至少 {PLATE_MIN_CLEAR:g} 秒：at 往前挪、去掉 dur，或者把镜头留长一点", sh.id)


def check_flip(rep, sid, where, ref, who):
    """M1：交领人物不许翻转。"""
    if not ref or not ref.rel or not ref.rel.startswith("chars/") or not ref.file:
        return
    name = Path(ref.rel).name
    row = ref.row or {}
    if name.startswith("sgm_") or "shadow" in Path(ref.rel).stem or "可翻转" in row.get("note", "") or re.search(r"道具|物件|课桌", row.get("owner", "")):
        return
    rep.err("翻转", f"{where} {who or ''} 的 {ref.rel} 用了 flip: true：穿交领的古人翻过来衣襟就成了左衽（M1）。要朝另一边就换一张原图朝那边的图（没有就让 Codex 画）；"
                    "只有司马光（sgm_，圆领）、皮影、登记表备注写了「可翻转」的图可以翻", sid)


def fx_box(kind, e, X, Y):
    """特效在屏幕上大致占的方框 (l, t, r, b)，按特效包的约定估（见文件头）；估不出来就 None（只查中心点）。"""
    if kind == "namecard":
        n = len(str(e.get("name", "")))
        if not n:
            return None
        k = float(e.get("size", 1.15))
        return X - 95 * k, Y, X + 95 * k, Y + (144 + 120 * n + (44 if e.get("role") else 0)) * k
    if kind == "list":
        items = e.get("items")
        if not isinstance(items, list) or not items:
            return None
        w = float(e.get("w", 780))
        return X - w / 2, Y - 54, X + w / 2, Y + 128 * (len(items) - 1) + 54
    if kind == "slam" and isinstance(e.get("text"), str) and e["text"]:
        size = float(e.get("size", 300))
        w = min(size * 0.95 * len(e["text"]), 920.0)
        return X - w / 2, Y - size / 2, X + w / 2, Y + size / 2
    return None


def box_problems(l, t, r, b):
    out = []
    if l < SAFE[0]:
        out.append(f"左边 {l:.0f} < {SAFE[0]:.0f}")
    if r > OCC_X:
        out.append(f"右边 {r:.0f} > {OCC_X:.0f}（右侧平台遮挡区 140）")
    if t < SAFE[1]:
        out.append(f"上边 {t:.0f} < {SAFE[1]:.0f}（顶部标题条 / 安全区以外）")
    if b > SAFE[3]:
        out.append(f"下边 {b:.0f} > {SAFE[3]:.0f}（字幕和底部平台遮挡区）")
    return out


class ImgRef:
    """一张要用的图：分镜表里写的路径、找到的文件、登记行。同一张图的问题只报一次，后面列出用到它的镜头（ctx.asset_msgs → flush_asset_msgs）。"""

    def __init__(self, ctx, rep, sid, path, where):
        self.path, self.file, self.row, self.rel = path, None, None, None
        try:
            self.file = ctx.store.resolve(path)
        except AssetError:
            ctx.note_asset("e", path, f"找不到素材 {path}", sid)
            return
        try:
            self.rel = Path(self.file).resolve().relative_to(ctx.assets_root.resolve()).as_posix()
        except ValueError:
            return                                   # 不在 video/assets/ 下（本集自带的图）：不查登记
        self.row = ctx.registry.get(self.rel)
        top = self.rel.split("/")[0]
        if self.row is None:
            if top in RC.DIRS:
                ctx.note_asset("e", self.rel, f"{self.rel} 没有登记进 REGISTRY.md（先登记，朝向和状态才有据可查）", sid)
            return
        st, scope = self.row["status"], self.row["scope"]
        if st == "停用":
            ctx.note_asset("e", self.rel, f"{self.rel} 是「停用」的素材：" + self.row["note"][:60], sid)
        elif st == "未定稿":
            ctx.note_asset("w", self.rel, f"{self.rel} 是「未定稿」的素材，用之前先问主会话", sid)
        ep = ctx.episode
        if scope == "试做集" and ep not in RC.PILOT_EPS:
            ctx.note_asset("e", self.rel, f"{self.rel} 的范围是「试做集」，新集不许用（T19、S7）", sid)
        elif scope == "宣传图":
            ctx.note_asset("e", self.rel, f"{self.rel} 的范围是「宣传图」，不进视频", sid)
        elif re.fullmatch(r"tj\d+", scope) and scope != ep:
            ctx.note_asset("w", self.rel, f"{self.rel} 属于 {scope}，本集是 {ep}：先把登记表里的范围改成「系列」再用", sid)

    @property
    def facing(self):
        if not self.row:
            return 0
        return {"左": -1, "右": 1}.get(self.row["facing"], 0)

    @property
    def size(self):
        return img_size(self.file) if self.file else None


def effective_upscale(spec, kind, ref, cam, dur, t_abs0):
    """(屏幕显示 ÷ 原图, 含镜头放大)；没读到图 = None。"""
    if ref.size is None:
        return None
    sw, sh = ref.size
    if kind == "actor":
        wd = sw * float(spec["h"]) / sh
    elif "w" in spec:
        wd = float(spec["w"])
    elif "h" in spec:
        wd = sw * float(spec["h"]) / sh
    else:
        wd = sw * float(spec.get("scale", 1.0))
    base = wd / sw
    depth = float(spec.get("depth", 1.0))
    zmax = 1.0
    if cam is not None:
        for k in range(13):
            t = dur * k / 12
            zmax = max(zmax, 1.0 + (cam.state(t, t_abs0 + t)[0] - 1.0) * depth)
    return base, base * zmax, (wd, wd * sh / sw)


def analyse_shot(sh, ctx, rep, spec, out):
    """一个镜头的静态分析。out 里放跨镜头要用的东西：flash 时间、变化事件、人物首次出场……"""
    tl, sid, t0, dur = ctx.tl, sh.id, sh.t0, sh.dur
    rel0 = rel_of(tl, t0)

    def rel(a):
        try:
            return rel0(a)
        except (AnchorError, TypeError, ValueError, KeyError):
            return 0.0                                # 锚点错了 [锚点] 那一步已经报了；这里当作镜头开头，别的检查照常做
    try:
        cam = Camera(spec.get("camera"), dur, rel, sid)
    except (ValueError, AnchorError, TypeError, KeyError):
        cam = None                                   # 镜头运动写错：引擎解析那一步会报
    events = []          # (开始, 结束, 类别)：绝对秒
    cover = []           # 有东西在动的时间段（静止检查用）
    fxs = []             # (类别, 开始（绝对秒）, 参数)
    new_things = 0

    # ---- 镜头运动
    moving = False
    if cam is not None:
        for m in cam.moves:
            k, at = m["kind"], t0 + m["at"]
            if k in CONTINUOUS:
                big = (abs(m.get("amount", 0)) >= MOVE_MIN_AMOUNT) if k != "pan" else (math.hypot(m["dx"], m["dy"]) >= MOVE_MIN_PX)
                if big:
                    cover.append((at, at + m["dur"]))
                    moving = True
            elif k == "punch":
                events.append((at, at + 0.45, "镜头冲击推"))
            elif k in ("shake", "whip"):
                events.append((at, at + m["dur"], f"镜头{k}"))
    # ---- 转场
    tr = spec.get("transition")
    tr_name = tr if isinstance(tr, str) else (tr or {}).get("type")
    if tr_name and tr_name != "cut" and sh.idx > 0:
        tr_dur = float(tr.get("dur", 0.4)) if isinstance(tr, dict) else 0.4
        events.append((t0, t0 + tr_dur, "转场"))
        if kind_of(tr_name) == "flash":
            fxs.append(("flash", t0, {"type": tr_name}))
        if tr_name not in ctx.transitions:
            rep.err("格式", f"没有叫 {tr_name!r} 的转场（已登记 / 已知：{sorted(ctx.transitions)}）", sid)
        elif tr_name in ctx.stub_only_transitions:
            rep.warn("格式", f"转场 {tr_name} 还没有登记（渲染会报错，等特效包）", sid)
    if sh.idx > 0:
        events.append((t0, t0, "切镜头"))

    # ---- 图层 / 人物：图、放大倍数、补间、出场
    actors, props = [], []
    for grp in ("bg", "actors", "fg"):
        for j, e in enumerate(spec.get(grp, []) or []):
            kind = "actor" if grp == "actors" else grp
            where = f"{grp}[{j}]"
            try:
                ref = ImgRef(ctx, rep, sid, e["img"], where)
                swaps = []
                for a in (e.get("acts", []) or []) if kind == "actor" else []:
                    if "swap" in a:
                        swaps.append((rel(a["at"]), ImgRef(ctx, rep, sid, a["swap"], f"{where}.acts 换表情"), float(a.get("h", e["h"]))))
                swaps.sort(key=lambda x: x[0])
            except (KeyError, TypeError, ValueError, AnchorError) as ex:
                rep.err("格式", f"{where}：{type(ex).__name__} {ex}", sid)
                continue
            # 放大倍数
            for r, h_override in [(ref, None)] + [(s[1], s[2]) for s in swaps]:
                spec2 = dict(e, h=h_override) if h_override is not None else e
                if e.get("blur", 0) and float(e["blur"]) > 0:
                    continue
                try:
                    up = effective_upscale(spec2, kind, r, cam, dur, t0)
                except (KeyError, TypeError, ValueError):
                    up = None
                if up:
                    base, eff, (wd, hd) = up
                    if eff > UPSCALE_MAX + UPSCALE_TOL:
                        cam_note = f"，含镜头放大 {eff / base:.2f}" if eff > base * 1.001 else ""
                        rep.err("放大", f"{where} {r.path} 屏幕显示 ÷ 原图 = {eff:.2f}（图本身 {base:.2f}{cam_note}），超过 {UPSCALE_MAX:g}（会发糊：换高清图、缩小 w/h，或者少推一点）", sid)
            # 补间、出场、小动作 → 变化事件
            try:
                for a in e.get("anim", []) or []:
                    at = t0 + (rel(a["at"]) if "at" in a else 0.0)
                    events.append((at, at + float(a.get("dur", 0.4)), f"{where} 补间"))
                en = e.get("enter")
                if en is not None:
                    en = {"type": en} if isinstance(en, str) else en
                    at = t0 + (rel(en["at"]) if "at" in en else 0.0)
                    events.append((at, at + float(en.get("dur", C.ENTER_DUR.get(en.get("type"), 0.4))), f"{where} 出场"))
                    if at - t0 > 0.1:
                        new_things += 1                       # 镜头开头就出场的不算「新出现」，中途出场的算
                for a in (e.get("acts", []) or []) if kind == "actor" else []:
                    at = t0 + rel(a["at"])
                    if "swap" in a:
                        events.append((at, at + SWAP_BOUNCE, f"{where} 换表情"))
                    else:
                        d = float(a.get("dur", ACTS[a["do"]][0] if a.get("do") in ACTS else 0.4))
                        events.append((at, at + d, f"{where} {a.get('do')}"))
            except (KeyError, TypeError, ValueError, AnchorError) as ex:
                rep.err("格式", f"{where}：{type(ex).__name__} {ex}", sid)
                continue
            # 位置：人物 / props 的安全区、朝向用
            try:
                tracks = Tracks(dict(x=float(e["pos"][0]), y=float(e["pos"][1]), scale=1.0, sx=1.0, sy=1.0, alpha=1.0, rot=0.0), e.get("anim"), rel, f"{sid} {where}")
            except (KeyError, TypeError, ValueError, AnchorError) as ex:
                rep.err("格式", f"{where}：{type(ex).__name__} {ex}", sid)
                continue
            if e.get("flip"):
                for r in [ref] + [x[1] for x in swaps]:
                    check_flip(rep, sid, where, r, e.get("who", e.get("id")))
            if kind == "actor" and ref.file:
                try:
                    window = presence_window(e, rel, dur)
                except (KeyError, TypeError, ValueError, AnchorError):
                    window = None
                actors.append(dict(spec=e, ref=ref, swaps=swaps, tracks=tracks, who=e.get("who", e.get("id")), id=e.get("id"), where=where, window=window))
            elif kind != "actor" and ref.rel and ref.rel.startswith("props/") and ref.file:
                props.append(dict(spec=e, ref=ref, tracks=tracks, where=where))
    out["new_things"] = new_things

    # ---- 特效（含 rituals 分到这个镜头的）
    for j, e in enumerate(spec.get("fx", []) or []):
        typ = e.get("type")
        kind = kind_of(typ)
        if typ not in ctx.fx_table:
            rep.err("特效", f"fx[{j}]：没有叫 {typ!r} 的特效（已登记 / 已知：{sorted(ctx.fx_table)}）", sid)
            continue
        plug = ctx.fx_table[typ]
        if typ in ctx.stub_only_fx:
            rep.warn("特效", f"fx[{j}]：{typ} 还没有在 fx/ 里登记（渲染会报错，等特效包）", sid)
        for p in (plug.assets(e) if plug.assets else []):
            try:
                ctx.store.resolve(p)
            except AssetError:
                rep.err("素材", f"fx[{j}] {typ} 要的图找不到：{p}", sid)
        try:
            at = t0 + (rel(e["at"]) if "at" in e else 0.0)
        except (AnchorError, TypeError, ValueError):
            continue
        fxs.append((kind, at, e))
        dur_fx = e.get("dur")
        if kind in AMBIENT_KINDS:
            cover.append((at, sh.t1))
        events.append((at, at + (float(dur_fx) if isinstance(dur_fx, (int, float)) else DEFAULT_FX_LEN), f"fx {typ}"))
        if kind not in AMBIENT_KINDS:
            new_things += 1                                   # 氛围（光芒、闪粉……）不算「一样东西」
    out["new_things"] = new_things
    out["fx"] = fxs

    # ---- 安全区：脸、props、重要的字
    if cam is not None:
        for a in actors:
            try:
                w0, w1 = presence_window(a["spec"], rel, dur)
            except (KeyError, TypeError, ValueError, AnchorError):
                continue
            probs = []
            for t in samples(w0, w1):
                variant = a["ref"], float(a["spec"]["h"])
                for at, r, h in a["swaps"]:
                    if t >= at and r.file:
                        variant = r, h
                r, h = variant
                if not r.file:
                    continue
                v = a["tracks"].value(t)
                sw, shh = r.size
                wd = sw * h / shh * v["scale"] * v["sx"]
                hd = h * v["scale"] * v["sy"]
                X, Y, Z = screen_xf(cam, t, t0 + t, v["x"], v["y"], float(a["spec"].get("depth", 1.0)))
                w, hh = wd * Z, hd * Z
                left, top = X - 0.5 * w, Y - hh
                pr = box_problems(left + FACE[0] * w, top + FACE[2] * hh, left + FACE[1] * w, top + FACE[3] * hh)
                if pr:
                    probs.append((t, pr))
            if probs:
                t, pr = probs[0]
                rep.err("安全区", f"{a['where']} {a['who']} 的脸（{a['ref'].path} 上面 40%）在 {t:.1f} 秒时：{'；'.join(pr)}（脸要在 y 360–1400、x 80–{OCC_X:.0f} 以内）", sid)
        for p in props:
            for t in samples(0.0, dur):
                v = p["tracks"].value(t)
                sw, shh = p["ref"].size
                spec_p = p["spec"]
                wd = float(spec_p["w"]) if "w" in spec_p else sw * float(spec_p["h"]) / shh if "h" in spec_p else sw * float(spec_p.get("scale", 1.0))
                hd = wd * shh / sw
                ax, ay = spec_p.get("anchor", (0.0, 0.0))
                X, Y, Z = screen_xf(cam, t, t0 + t, v["x"], v["y"], float(spec_p.get("depth", 1.0)))
                cxx, cyy = X + (0.5 - ax) * wd * Z, Y + (0.5 - ay) * hd * Z
                pr = box_problems(cxx, cyy, cxx, cyy)
                if pr:
                    rep.err("安全区", f"{p['where']} 关键道具 {p['ref'].path} 的中心（{cxx:.0f}, {cyy:.0f}）：{'；'.join(pr)}", sid)
                    break
        for kind, at, e in fxs:
            pos = e.get("pos")
            if not (isinstance(pos, list) and len(pos) == 2):
                continue
            try:
                t = min(max(at - t0, 0.0), dur)
                X, Y, _ = screen_xf(cam, t, at, float(pos[0]), float(pos[1]), float(e.get("depth", 1.0 if kind == "sticker" else 0.0)))
                box = fx_box(kind, e, X, Y)
            except (TypeError, ValueError):
                continue
            if kind == "sticker":
                if X > OCC_X or Y > OCC_Y:
                    rep.warn("安全区", f"贴纸 {e.get('name') or e.get('text')} 中心 ({X:.0f}, {Y:.0f}) 进了平台遮挡区（右 140 / 下 300）", sid)
            elif kind in TEXT_KINDS:
                by_box = box is not None and kind in ("namecard", "list")            # pos 不是中心的（牌子挂点、第一条的中心）：查估出来的方框
                pr = box_problems(*box) if by_box else box_problems(X, Y, X, Y)
                where = f"方框 x {box[0]:.0f}–{box[2]:.0f}、y {box[1]:.0f}–{box[3]:.0f}" if by_box else f"中心 ({X:.0f}, {Y:.0f})"
                if pr:
                    rep.err("安全区", f"{e['type']}（{kind}）{where}：{'；'.join(pr)}", sid)
                if kind == "slam" and box and (box[0] < SAFE[0] or box[2] > OCC_X):
                    rep.warn("安全区", f"{e['type']} 砸字「{e.get('text')}」按字号估计宽 {box[2] - box[0]:.0f}，x 会到 {box[0]:.0f}–{box[2]:.0f}，超出 {SAFE[0]:.0f}–{OCC_X:.0f}", sid)
    out["actors"] = actors
    if cam is not None:
        check_overlays(sh, out, cam, rep)
        check_focus_lines(sh, out, cam, rep)
    check_plate_time(sh, out, rep)
    out["events"] = events
    out["cover"] = cover
    out["moving"] = moving


# ------------------------------------------------------------------ 逐镜检查后的镜头级规则
def check_static(sh, out, rep):
    cover = sorted([(max(a, sh.t0), min(b, sh.t1)) for a, b in out["cover"] + [(e[0], e[1]) for e in out["events"]] if b >= sh.t0 and a <= sh.t1])
    cur, worst, at = sh.t0, 0.0, sh.t0
    for a, b in cover:
        if a - cur > worst:
            worst, at = a - cur, cur
        cur = max(cur, b)
    if sh.t1 - cur > worst:
        worst, at = sh.t1 - cur, cur
    if worst > STATIC_MAX + 1.5 / FPS:
        rep.err("静止", f"从 {at:.1f} 秒起有 {worst:.1f} 秒画面静止（镜头没有推 / 拉 / 摇，也没有换表情 / 小动作 / 特效 / 补间），静止不许超过 {STATIC_MAX:g} 秒", sh.id)


def check_effects(sh, out, rep):
    spec = sh.spec
    fxs = [f for f in out["fx"] if f[0] not in AMBIENT_KINDS]
    note = json.dumps(spec.get("note", ""), ensure_ascii=False) + json.dumps(spec.get("notes", ""), ensure_ascii=False)
    know = "知识" in note or any(k in KNOWLEDGE_KINDS for k, _, _ in out["fx"])
    out["knowledge"] = know
    if know:
        if out["new_things"] > KNOW_MAX_NEW:
            rep.err("特效", f"这是讲知识点的镜头，画面上新出现的东西 {out['new_things']} 样（特效 + 中途出场的人物 / 图层），最多 {KNOW_MAX_NEW} 样，不堆", sh.id)
        if sh.dur <= FAST_MAX + 1.5 / FPS:
            rep.err("特效", f"这是讲知识点的镜头，只有 {sh.dur:.1f} 秒（快切）；知识点不快切", sh.id)
        if any(k == "flash" for k, _, _ in out["fx"]):
            rep.err("特效", "这是讲知识点的镜头，有闪白；知识点不闪白", sh.id)
    elif len(fxs) > GENERAL_FX_WARN:
        rep.warn("特效", f"这个镜头有 {len(fxs)} 个特效，是不是堆了？", sh.id)


def color_is_red(c):
    if not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        return False
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return r > 150 and g < 110 and b < 110


def check_flashes(flashes, rep):
    """flashes = [(绝对秒, 镜头 id, 参数)]。"""
    flashes = sorted(flashes, key=lambda f: f[0])
    if len(flashes) > FLASH_MAX_EPISODE:
        rep.err("闪烁", f"闪白一集 {len(flashes)} 次，最多 {FLASH_MAX_EPISODE} 次（镜头 {'、'.join(str(f[1]) for f in flashes)}）")
    for i in range(len(flashes)):
        n = sum(1 for f in flashes if flashes[i][0] <= f[0] <= flashes[i][0] + 1.0 + 1e-6)
        if n > FLASH_MAX_SEC:
            rep.err("闪烁", f"{flashes[i][0]:.1f} 秒起 1 秒内有 {n} 次闪白，任何 1 秒内最多 {FLASH_MAX_SEC} 次（WCAG 三次闪烁）", flashes[i][1])
            break
    for t, sid, e in flashes:
        if "invert" in str(e.get("type", "")).lower():
            rep.err("闪烁", "不用反色闪", sid)
        for k in ("alpha", "strength", "intensity", "opacity"):
            if isinstance(e.get(k), (int, float)) and e[k] > FLASH_MAX_STRENGTH:
                rep.err("闪烁", f"闪白的 {k} = {e[k]}，最多 {FLASH_MAX_STRENGTH:g}（60% 亮度）", sid)
        if isinstance(e.get("dur"), (int, float)) and e["dur"] > FLASH_MAX_DUR:
            rep.err("闪烁", f"闪白 dur = {e['dur']} 秒，最多 {FLASH_MAX_DUR} 秒（2–3 帧）", sid)
        if color_is_red(e.get("color")):
            rep.err("闪烁", "不用红色闪", sid)


# ------------------------------------------------------------------ 朝向
def check_facing(sh, out, tl, rep):
    acts = out["actors"]
    if not acts:
        return
    speakers = {}
    for i, ln in enumerate(tl.lines):
        if not tl.is_speech(i):
            continue
        s0, s1 = tl.speech_span(i)
        ov = min(s1, sh.t1) - max(s0, sh.t0)
        if ov >= 0.3:
            speakers[ln["who"]] = speakers.get(ln["who"], 0.0) + ov
    for a in acts:
        rel_ = rel_of(tl, sh.t0)
        try:
            w0, w1 = presence_window(a["spec"], rel_, sh.dur)
            v = a["tracks"].value(w1)
        except (KeyError, TypeError, ValueError, AnchorError):
            continue
        a["x_end"] = v["x"]
    for a in acts:
        if "x_end" not in a:
            continue
        variants = [(0.0, a["ref"])] + [(t, r) for t, r, _ in a["swaps"]]
        flip = -1 if a["spec"].get("flip") else 1
        others = [b for b in acts if b is not a and "x_end" in b and abs(b["x_end"] - a["x_end"]) > 20]
        for _, r in variants:
            d = r.facing * flip
            if d == 0 or not r.file:
                continue
            face = "右" if d > 0 else "左"
            if not others:
                lone = [b for b in acts if b is not a]
                if not lone and ((a["x_end"] < CX - 150 and d < 0) or (a["x_end"] > CX + 150 and d > 0)):
                    rep.warn("朝向", f"{a['where']} {a['who']} 一个人站在画面{'左' if d < 0 else '右'}侧、脸朝{face}（朝画面外，背对全场）：{r.path}", sh.id)
                continue
            spk = [b for b in others if b["who"] in speakers]
            targets = spk or others
            if any((b["x_end"] - a["x_end"]) * d > 0 for b in targets):
                continue
            names = "、".join(str(b["who"]) for b in targets)
            msg = (f"{a['where']} {a['who']} 的脸朝{face}（{r.path}，登记朝向 {r.row['facing'] if r.row else '?'}{'，flip' if flip < 0 else ''}），"
                   f"可是{'说话的' if spk else '同镜头的'} {names} 在他的{'左' if d > 0 else '右'}边：要面向说话的人（改 flip）")
            (rep.err if spk else rep.warn)("朝向", msg, sh.id)
            break


# ------------------------------------------------------------------ 人名牌
def person_tokens(a):
    name, prefix = owner_name(a["ref"].row["owner"]) if a["ref"].row else ("", "")
    return {x for x in (a["who"], a["id"], name, prefix) if x}


def is_person(a):
    row = a["ref"].row
    if row and re.search(r"道具|物件|课桌", row["owner"]):
        return False
    return True


def check_namecards(shots, outs, rep):
    known = set()                                      # 整集所有人物的名字 / id / 前缀：用来判断一张人名牌写的是谁
    for sh in shots:
        for a in (outs.get(sh.id) or {}).get("actors", []):
            known |= person_tokens(a)

    def matches(tokens, hay):
        return any(t == h or (len(t) >= 2 and t in h) for t in tokens for h in hay)

    seen = set()
    for sh in shots:
        o = outs.get(sh.id)
        if not o:
            continue
        new = []
        for a in o["actors"]:
            key = a["who"] or a["id"]
            if not key or key in seen:
                continue
            seen.add(key)
            toks = person_tokens(a)
            if toks & SERIES_HOST or not is_person(a):
                continue
            new.append((key, toks))
        if not new:
            continue
        left = list(new)
        anonymous = 0
        for k, _, e in o["fx"]:
            if k != "namecard":
                continue
            hay = [str(v) for kk, v in e.items() if isinstance(v, str) and kk not in NAME_HINT_SKIP]
            if not matches(known, hay):
                anonymous += 1                         # 没写是谁（或者写的字对不上任何人）：按数量对
                continue
            hit = next((p for p in left if matches(p[1], hay)), None)
            if hit:
                left.remove(hit)
        while anonymous and left:
            left.pop(0)
            anonymous -= 1
        for key, _ in left:
            rep.err("人名牌", f"人物「{key}」第一次出场，这个镜头里没有人名牌（要一个 name_plate 特效：旁边竖排书法大字写名字、下面小字写身份）", sh.id)


# ------------------------------------------------------------------ 变化频率
def check_changes(shots, outs, rep, stats):
    ev = []
    for sh in shots:
        o = outs.get(sh.id)
        if o:
            ev += [e[0] for e in o["events"]]
    ev.sort()
    end = max(sh.t1 for sh in shots)
    opening = sum(1 for t in ev if 0.0 <= t <= OPEN_WINDOW + 1e-6)
    stats["changes"] = len(ev)
    if opening < OPEN_MIN_CHANGES:
        rep.err("频率", f"开头前 {OPEN_WINDOW:g} 秒只有 {opening} 次视觉变化（切镜头 / 换表情 / 弹特效 / 出场……），要至少 {OPEN_MIN_CHANGES} 次（《钩子和吸引力》开头 3 秒）")
    if ev:
        mean = end / len(ev)
        stats["mean_change_s"] = round(mean, 2)
        if mean > CHANGE_MEAN_MAX:
            rep.err("频率", f"平均每 {mean:.1f} 秒才有一次视觉变化，要在 2–3 秒以内")


# ------------------------------------------------------------------ 引擎解析（Scene）
def engine_parse(sh, ctx, rep):
    spec = sh.spec
    try:
        sc = Scene(spec, ctx.tl, sh.t0, sh.dur, ctx.store, ctx.fx_table)
    except (AnchorError, AssetError):
        return None                                   # 锚点、素材那两步已经报了
    except (SceneError, ValueError, KeyError, TypeError) as e:
        if "没有叫" not in str(e) and not re.match(rf"镜头 {re.escape(str(sh.id))}( (actors|bg|fg)\[\d+\])?：不认识的字段", str(e)):   # 特效名、拼错的字段上面已经报了
            rep.err("格式", f"引擎解析：{type(e).__name__}：{e}", sh.id)
        return None
    for w in sc.warnings:
        if "÷ 原图" in w or "永远不会出现" in w:
            continue                                  # 放大倍数由 [放大] 查（含镜头放大）；锚在镜头以外由 [锚点] 查
        rep.warn("引擎", w.replace(f"镜头 {sh.id} ", ""), sh.id)
    for _, name, _g in sc.sfx_events():
        if not any((d / f"{name}.wav").exists() for d in ctx.sfx_dirs):
            rep.err("素材", f"找不到音效 {name!r}（要 {name}.wav，放在 video/motion/sfx/）", sh.id)
    return sc


# ------------------------------------------------------------------ 主流程
def run(sb_arg, registry=REGISTRY, no_plugins=False, assets_root=None):
    rep, stats = Report(), {}
    sb, p = load_storyboard(sb_arg)
    base = p.parent
    check_format(sb, rep)
    voice = find_voice(sb, base)
    tl = Timeline.load(voice)

    ctx = Ctx()
    ctx.tl, ctx.base, ctx.episode = tl, base, str(sb.get("episode", ""))
    ctx.registry = load_registry(registry)
    ctx.assets_root = Path(assets_root) if assets_root else C.ASSETS
    ctx.store = AssetStore(1.0, [base])
    ctx.store.roots = [ctx.assets_root, base]
    ctx.sfx_dirs = [C.SFX_DIR] + [d for d in (base / "sfx",) if d.is_dir()]
    if not no_plugins:
        fxreg.load_plugins([d for d in (base / "fx",) if d.is_dir()])
    ctx.fx_table = dict(fxreg.FX) if not no_plugins else {}
    missing_fx = {n for n in STUB_FX if n not in ctx.fx_table}
    for n in missing_fx:
        ctx.fx_table[n] = fxreg.FxSpec(n, None)
    ctx.stub_only_fx = set() if no_plugins else missing_fx
    real_tr = set(fxreg.TRANSITIONS) if not no_plugins else set()
    ctx.stub_only_transitions = set() if no_plugins else {n for n in STUB_TRANSITIONS if n not in real_tr}
    ctx.transitions = real_tr | set(STUB_TRANSITIONS)

    shots = [Shot(i, s) for i, s in enumerate(sb["shots"])]
    ranges_ok = compute_ranges(shots, tl, rep)
    rep.times = {sh.id: (sh.t0, sh.t1) for sh in shots if sh.f0 is not None and sh.f1 is not None} if ranges_ok else {}
    stats["timeline_lines"], stats["timeline_s"] = len(tl.lines), round(tl.duration, 2)

    # rituals 分到自己开始的那个镜头（同 plan.py）
    specs = {sh.id: dict(sh.spec) for sh in shots}
    if ranges_ok:
        for j, r in enumerate(sb.get("rituals", []) or []):
            try:
                f = round(tl.resolve(r["at"]) * FPS)
            except (AnchorError, KeyError, TypeError, ValueError) as e:
                rep.err("锚点", f"rituals[{j}] {r.get('type')}：{e}")
                continue
            home = next((sh for sh in shots if sh.f0 <= f < sh.f1), shots[-1])
            specs[home.id]["fx"] = list(specs[home.id].get("fx", []) or []) + [dict(r)]

    outs, flashes = {}, []
    if ranges_ok:
        for sh in shots:
            spec = specs[sh.id]
            check_anchors(sh, spec, tl, rep)
            o = {}
            try:
                analyse_shot(sh, ctx, rep, spec, o)
            except (KeyError, TypeError, ValueError, AttributeError, AnchorError) as ex:
                rep.err("格式", f"分析失败：{type(ex).__name__} {ex}（字段类型不对？）", sh.id)
                continue
            outs[sh.id] = o
            sh.spec = spec
            engine_parse(sh, ctx, rep)
            check_static(sh, o, rep)
            check_effects(sh, o, rep)
            check_facing(sh, o, tl, rep)
            flashes += [(t, sh.id, e) for k, t, e in o["fx"] if k == "flash"]
        check_lengths_and_rate(shots, tl, rep, stats)
        check_changes(shots, outs, rep, stats)
        check_flashes(flashes, rep)
        stats["flashes"] = len(flashes)
        check_namecards(shots, outs, rep)
        flush_asset_msgs(ctx, rep)
        # 时间线里说话的人 vs 人物的 who
        speakers = {ln["who"] for i, ln in enumerate(tl.lines) if tl.is_speech(i)}
        known_names = {owner_name(r["owner"])[0] for r in ctx.registry.values()}
        warned = set()
        for sh in shots:
            for a in (outs.get(sh.id) or {}).get("actors", []):
                if a["who"] and a["who"] not in speakers and a["who"] not in known_names and a["who"] not in warned:
                    warned.add(a["who"])
                    rep.warn("朝向", f"人物 who={a['who']!r} 既不是配音时间线里的说话人、也不是登记表里的人名（写错了？说话时不会起伏，朝向也没法对着他；时间线里有：{sorted(speakers)}）", sh.id)
    else:
        rep.info.append("锚点有错，镜头长度 / 频率 / 静止 / 特效 / 安全区 / 朝向等检查先跳过（先改锚点再跑）")
    return sb, p, rep, stats


def main():
    ap = argparse.ArgumentParser(description="分镜表检查（第 4 步过关脚本）：锚点、镜头长度、变化频率、特效数量、闪烁、安全区、素材、放大倍数、朝向、人名牌")
    ap.add_argument("storyboard", help="分镜表 JSON，或集名（video/stories/<集>/storyboard.json）")
    ap.add_argument("--json", help="把所有发现写到这个 JSON")
    ap.add_argument("--registry", default=str(REGISTRY), help="素材登记表（默认 video/assets/REGISTRY.md）")
    ap.add_argument("--no-plugins", action="store_true", help="不加载 fx/ 插件，特效只按名字分类（测试用）")
    ap.add_argument("--assets-root", help="换一个素材根目录（默认 video/assets/；测试用，配合 --registry）")
    a = ap.parse_args()
    try:
        sb, path, rep, stats = run(a.storyboard, a.registry, a.no_plugins, a.assets_root)
    except Fatal as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001  检查器自己坏了也不许当作「通过」
        traceback.print_exc()
        print("错误：检查器自己出错了（上面是原因），没有得出结论", file=sys.stderr)
        return 2
    print(f"storyboard_check {sb.get('episode')}（{path}）")
    print(f"  {stats.get('shots', len(sb['shots']))} 个镜头，" + (f"每分钟 {stats['rate_per_min']} 个，" if "rate_per_min" in stats else "")
          + f"配音时间线 {stats.get('timeline_lines')} 句 / {stats.get('timeline_s')} 秒"
          + (f"，闪白 {stats['flashes']} 次，长镜头（> 5 秒）{stats['long_shots']} 个" if "flashes" in stats else ""))
    for i in rep.info:
        print("  " + i)
    if rep.warnings:
        print(f"警告 {len(rep.warnings)}：")
        for w in rep.warnings:
            print("  " + fmt(w, rep.times))
    if rep.errors:
        print(f"错误 {len(rep.errors)}：")
        for e in rep.errors:
            print("  " + fmt(e, rep.times))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({"errors": rep.errors, "warnings": rep.warnings, "info": rep.info, "stats": stats}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("结果：" + (f"不通过（{len(rep.errors)} 个错误）" if rep.errors else "通过"))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
