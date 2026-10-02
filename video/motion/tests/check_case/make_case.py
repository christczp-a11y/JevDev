"""storyboard_check.py 的测试数据（合成的，不依赖真实素材、不依赖特效包的进度）。

  python video/motion/tests/check_case/make_case.py write            重写提交进 git 的固定数据：
        video/motion/tests/check_case/voice/timeline.json   合成的配音时间线（22 句，约 68 秒；没有音频，检查工具用不到）
        video/motion/tests/good_storyboard.json             一个正确的分镜表（必须 0 个错误、0 个警告）
        video/motion/tests/bad_*.json                       每种错一个：在 good 的基础上只改一处（改了什么见下面的 CASES）
        video/motion/tests/check_expect.json                每个 bad_*.json 应该报出来的那句话（测试用）
  python video/motion/tests/check_case/make_case.py assets 目录     测试时生成（不进 git）：目录/assets/*.png（纯色小图，尺寸和登记表一致）+ 目录/REGISTRY.md
        测试用 --assets-root 目录/assets --registry 目录/REGISTRY.md --no-plugins 跑，这样素材和特效包怎么变，这些测试都不受影响。
"""
import copy
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
sys.stdout.reconfigure(encoding="utf-8")

# ------------------------------------------------------------------ 合成素材和登记表
# 路径: (宽, 高, 朝向, 状态, 范围)；属于（登记表第二列）在 OWNERS 里按前缀找
OWNERS = {"zb": "智伯 `zb_`", "dg": "段规 `dg_`", "hkz": "韩康子 `hkz_`", "zxz": "赵襄子 `zxz_`", "sgm": "司马光 `sgm_`", "sy2": "商鞅 `sy2_`"}
IMGS = {
    "chars/zb_point": (464, 409, "右", "定稿", "tj01"), "chars/zb_grab": (405, 422, "右", "定稿", "tj01"),
    "chars/zb_angry": (387, 470, "右", "定稿", "tj01"), "chars/zb_stand": (291, 470, "右", "定稿", "tj01"),
    "chars/dg_kneel": (352, 443, "右", "定稿", "tj01"), "chars/dg_whisper": (331, 428, "左", "定稿", "tj01"),
    "chars/hkz_low": (376, 427, "右", "定稿", "tj01"), "chars/hkz_give": (475, 444, "右", "定稿", "tj01"),
    "chars/hkz_old": (300, 499, "右", "停用", "tj01"),
    "chars/zxz_kneel": (389, 428, "右", "定稿", "tj01"), "chars/zxz_no": (387, 431, "右", "定稿", "tj01"),
    "chars/sgm_finger": (426, 474, "右", "定稿", "系列"), "chars/sgm_thumb": (443, 484, "正面", "定稿", "系列"),
    "chars/sy2_stand": (235, 467, "右", "定稿", "试做集"),
    # 画在右边、脸朝左的人用原图朝左的图（交领人物不许 flip，PITFALLS M1）：和朝右的那张同尺寸
    "chars/zb_point_l": (464, 409, "左", "定稿", "tj01"), "chars/zb_angry_l": (387, 470, "左", "定稿", "tj01"),
    "chars/dg_kneel_l": (352, 443, "左", "定稿", "tj01"), "chars/hkz_low_l": (376, 427, "左", "定稿", "tj01"),
    "chars/zxz_kneel_l": (389, 428, "左", "定稿", "tj01"), "chars/zxz_no_l": (387, 431, "左", "定稿", "tj01"),
    "sets/jin_land/sky": (1024, 1536, "正面", "定稿", "tj01"), "sets/jin_land/ridge_far": (1016, 462, "正面", "定稿", "tj01"),
    "sets/jin_land/ground": (1528, 218, "正面", "定稿", "tj01"),
    "props/cup_lacquer": (513, 257, "正面", "定稿", "tj01"), "props/map_silk": (1132, 806, "正面", "定稿", "tj01"),
}


NOTES = {"chars/zb_stand": "测试图（侧面立像，可翻转）"}          # 登记表备注写了「可翻转」的图可以 flip


def owner_of(path):
    name = path.split("/")[-1].split("_")[0]
    if path.startswith("chars/"):
        return OWNERS[name]
    return "布景 jin_land（共用：天空、山、地面、水）" if path.startswith("sets/") else "道具"


def make_assets(out):
    out = Path(out)
    rows = ["# 测试用登记表（make_case.py 生成）", "", "## 二、素材表", "",
            "| 路径 | 属于 | 朝向 | 尺寸 | 内含别的角色 | 状态 | 备注 | 范围 |", "|---|---|---|---|---|---|---|---|"]
    for path, (w, h, facing, status, scope) in IMGS.items():
        f = out / "assets" / f"{path}.png"
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (w, h), (200, 180, 160, 255)).save(f)
        rows.append(f"| `{path}.png` | {owner_of(path)} | {facing} | {w}×{h} | 无 | {status} | {NOTES.get(path, '测试图')} | {scope} |")
    (out / "REGISTRY.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{len(IMGS)} 张测试图 + 登记表写到 {out}")


# ------------------------------------------------------------------ 配音时间线
LINES = [   # (说话人, 台词, 有声时长)
    ("旁白", "要地，给不给？", 2.6), ("智伯", "韩康子，给我一座城！", 3.0), ("韩康子", "给……给你吧。", 2.6), ("段规", "给了他，他更骄傲。", 3.0),
    ("旁白", "智伯有五样本事，样样比别人强！", 3.4), ("旁白", "只缺一样：好心。", 2.6), ("司马光", "考考你，赵襄子给不给？", 3.0), ("赵襄子", "不给。", 2.4),
    ("智伯", "什么？你不给？", 2.6), ("旁白", "智伯很生气！", 2.2), ("段规", "变，就要来了。", 2.6), ("韩康子", "我们再看看。", 2.4),
    ("旁白", "智伯去看水势，得意大笑。", 3.4), ("智伯", "水，也能灭国！", 2.6), ("韩康子", "他，他说什么？", 2.6), ("旁白", "韩康子的心里，都发凉。", 3.6),
    ("司马光", "记住这句话。", 2.4), ("旁白", "本事是本钱，好心是队长。", 3.6), ("赵襄子", "晋阳，我们守得住！", 3.2), ("段规", "夜里，挖开堤。", 2.6),
    ("旁白", "水，掉头了！", 2.4), ("司马光", "才胜德，就会输。", 2.8),
]
GAP = 0.3


def make_timeline():
    t, lines = 0.3, []
    for i, (who, text, d) in enumerate(LINES):
        lines.append({"t0": round(t, 3), "t1": round(t + d, 3), "who": who, "text": text, "audio": None, "voiced_end": round(d - 0.5, 3), "i": i})
        t += d + GAP
    return {"duration": round(t, 3), "lines": lines, "note": "合成的时间线（storyboard_check 的测试用，没有音频）"}


TL = make_timeline()
T0 = [ln["t0"] for ln in TL["lines"]]


# ------------------------------------------------------------------ 分镜表
PEOPLE = {"zb": "智伯", "dg": "段规", "hkz": "韩康子", "zxz": "赵襄子", "sgm": "司马光"}
LEFT_X, RIGHT_X, ALONE_X, FEET = 330, 760, 540, 1560


def actor(pid, pose, x, left=False, y=FEET, **extra):
    """left=True：脸朝左的人（画在右边）：用原图朝左的图（`_l`），不 flip。"""
    key = f"chars/{pid}_{pose}" + ("_l" if left else "")
    w, h, *_ = IMGS[key]
    a = {"id": pid, "who": PEOPLE[pid], "img": key + ".png", "pos": [x, y], "h": round(h * 0.95)}
    a.update(extra)
    return a


def bg():
    return [{"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080},
            {"img": "sets/jin_land/ridge_far.png", "depth": 0.15, "pos": [0, 430], "w": 1080},
            {"img": "sets/jin_land/ground.png", "depth": 0.9, "pos": [540, 1330], "anchor": [0.5, 0], "w": 1200, "repeat": "x"}]


def L(line, dt=0.0):
    a = {"line": line}
    if dt:
        a["dt"] = dt
    return a


def sticker(line, text, dt=0.6, x=840, y=700):
    return {"type": "sticker", "text": text, "pos": [x, y], "at": L(line, dt), "size": 180}


ROLE = {"智伯": ("智家", "智家老大"), "段规": ("韩家", "韩家谋士"), "韩康子": ("韩家", "韩家主人"), "赵襄子": ("赵家", "赵家主人")}


def namecard(line, name, x, dt=0.2):
    """特效包的人名牌：name_plate，pos 是牌子挂点（顶部中点）。"""
    house, role = ROLE[name]
    return {"type": "name_plate", "name": name, "role": role, "house": house, "pos": [x, 380], "at": L(line, dt)}


CAMERAS = [None, [{"move": "pull", "amount": 0.05}], [{"move": "pan", "dx": -50}], None, [{"move": "push", "amount": 0.06}]]

# 每句一镜：(左边的人, 右边的人, 只有一个人时的姿势)。左边的人用朝右的图，右边的人用朝左的图（`_l`），互相面对面
SCENES = {
    1: (("zb", "grab"), ("dg", "kneel")), 2: (("hkz", "low"), ("zb", "point")), 3: (("dg", "kneel"), ("hkz", "low")),
    7: (("zxz", "no"), ("zb", "angry")), 8: (("zxz", "kneel"), ("zb", "angry")), 10: (("dg", "kneel"), ("hkz", "low")),
    11: (("hkz", "give"), ("dg", "kneel")), 14: (("hkz", "low"), ("zb", "point")), 15: (("hkz", "give"), ("zxz", "kneel")),
    18: (("zxz", "no"), ("dg", "kneel")), 19: (("dg", "kneel"), ("zxz", "no")),
}
ALONE = {4: ("zb", "stand"), 5: ("zb", "angry"), 9: ("zb", "angry"), 12: ("zb", "grab"), 13: ("zb", "point"), 20: ("zb", "stand")}
SGM = {0: "finger", 6: "finger", 16: "finger", 17: "finger", 21: "thumb"}
NAMECARDS = {1: [("zb", "智伯", LEFT_X), ("dg", "段规", RIGHT_X)], 2: [("hkz", "韩康子", LEFT_X)], 7: [("zxz", "赵襄子", LEFT_X)]}


def base_shot(i):
    s = {"id": f"s{i + 1:02d}", "from": L(i), "bg": bg(), "fx": []}
    if i == 0:
        s["from"] = L(0, -0.3)
    cam = CAMERAS[i % len(CAMERAS)]
    if cam:
        s["camera"] = cam
    if i in SCENES:
        (lp, lpose), (rp, rpose) = SCENES[i]
        s["actors"] = [actor(lp, lpose, LEFT_X), actor(rp, rpose, RIGHT_X, left=True)]
        s["size"] = "medium"
    elif i in ALONE:
        s["actors"] = [actor(*ALONE[i], ALONE_X)]
        s["size"] = "close"
    else:
        s["actors"] = [actor("sgm", SGM[i], 300)]
        s["size"] = "medium"
    for pid, name, x in NAMECARDS.get(i, []):
        s["fx"].append(namecard(i, name, x, dt=0.2 if x == LEFT_X else 0.5))
    return s


def make_good():
    shots = [base_shot(i) for i in range(len(LINES))]
    s0 = shots[0]
    s0["actors"][0]["enter"] = "pop"
    s0["actors"][0]["acts"] = [{"at": L(0, 1.6), "swap": "chars/sgm_thumb.png"}]
    s0["fx"].append(sticker(0, "？", dt=0.9, x=760))
    shots[1]["actors"][0]["enter"] = "slide_left"
    shots[2]["actors"][0]["acts"] = [{"at": {"line": 2, "word": "给"}, "do": "bounce"}]
    shots[3]["fx"].append(sticker(3, "咚"))
    shots[4].update(note="知识点：智伯的五样本事")
    shots[4]["fx"] += [{"type": "checklist", "items": ["高大", "力气", "才艺"], "pos": [540, 480], "at": L(4, 0.2)}, sticker(4, "！", dt=1.4)]
    shots[5]["fx"].append(sticker(5, "汗", dt=0.9))
    shots[8]["camera"] = [{"move": "punch", "at": {"line": 8, "word": "不给"}, "amount": 0.1}, {"move": "push", "amount": 0.05}]
    shots[13]["fx"].append({"type": "flash", "at": {"line": 13, "word": "灭国"}, "alpha": 0.5, "dur": 0.1})
    shots[20]["fx"].append(sticker(20, "呼", dt=0.5))
    # 交领人物不许 flip（M1），例外：司马光（圆领）、登记表备注写了「可翻转」的图
    shots[16]["actors"][0].update(pos=[780, FEET], flip=True)                     # 司马光翻身
    shots[20]["actors"][0]["flip"] = True                                          # zb_stand：备注「可翻转」
    # 贴纸挂在人物身上（follow）压脸不算；闪粉没写 avoid = 特效包自动避开脸
    shots[11]["fx"].append({"type": "sticker", "text": "汗", "follow": "hkz", "attach": "head", "at": L(11, 0.6), "size": 180})
    shots[19]["fx"].append({"type": "sparkle", "at": L(19, 0.3)})
    # 道具图标不许盖住主角（M8）：放在旁边的、只盖住一点（< 20%、碰不到脸）的都行
    shots[13]["fg"] = [{"img": "props/cup_lacquer.png", "depth": 1.0, "pos": [860, 1300], "anchor": [0.5, 0.5], "w": 200}]
    shots[18]["fg"] = [{"img": "props/cup_lacquer.png", "depth": 1.0, "pos": [470, 1340], "anchor": [0.5, 0.5], "w": 150}]
    # 集中线：写 clear，圈盖住主体（智伯）的脸
    shots[20]["fx"].append({"type": "lines_focus", "pos": [540, 1200], "clear": 320, "at": L(20, 0.4)})
    sb = {"episode": "tj01", "no": 1, "title": ["最强的智伯，", "为什么输了？"], "voice": "video/motion/tests/check_case/voice",
          "note": "storyboard_check 的测试数据：正确的分镜表（0 错误 0 警告）。用 make_case.py 生成，别手改。",
          "speakers": {"智伯": "智家", "段规": "韩家", "韩康子": "韩家", "赵襄子": "赵家"},
          "shots": shots,
          "rituals": [{"type": "kaoni", "at": L(6), "options": ["给", "不给"]}]}
    return sb


def shot_ids(sb):
    return [s["id"] for s in sb["shots"]]


def sh(sb, sid):
    return next(s for s in sb["shots"] if s["id"] == sid)


def renumber(sb):
    for k, s in enumerate(sb["shots"], 1):
        s["id"] = f"s{k:02d}"


def split_shot(sb, sid, at_line, dt):
    """在 sid 这一镜里 line 的 dt 秒处再切一刀（后半段是新镜头，画面照抄）。"""
    i = next(k for k, s in enumerate(sb["shots"]) if s["id"] == sid)
    a = sb["shots"][i]
    b = copy.deepcopy(a)
    b["id"] = sid + "b"
    b["from"] = L(at_line, dt)
    b["fx"] = []
    b.pop("note", None)
    if "actors" in b:
        for x in b["actors"]:
            x.pop("enter", None)
            x.pop("acts", None)
    sb["shots"].insert(i + 1, b)
    return b


# ------------------------------------------------------------------ 每种错一个
CASES = {}


def case(name, needle):
    def deco(fn):
        CASES[name] = (fn, needle)
        return fn
    return deco


# ---- 锚点
@case("bad_anchor_line", "只有 22 句")
def _(sb):
    sh(sb, "s04")["fx"][0]["at"] = {"line": 99}


@case("bad_anchor_word", "找不到")
def _(sb):
    sh(sb, "s03")["actors"][0]["acts"][0]["at"] = {"line": 2, "word": "根本没有"}


@case("bad_anchor_seconds", "不能写死秒数")
def _(sb):
    sh(sb, "s04")["fx"][0]["at"] = 3.5


@case("bad_anchor_order", "之后")
def _(sb):
    sh(sb, "s06")["from"] = {"line": 2}


@case("bad_anchor_after_end", "在镜头结束之后")
def _(sb):
    sh(sb, "s04")["fx"][0]["at"] = {"line": 12}


@case("bad_anchor_to_overlap", "两镜重叠")
def _(sb):
    sh(sb, "s04")["to"] = {"line": 6}


# ---- 镜头长度
@case("bad_shot_too_short", "短于 0.8 秒")
def _(sb):
    split_shot(sb, "s11", 10, 0.5)                    # 第 10 句「变，就要来了」的镜头，前 0.5 秒单独一镜
    renumber(sb)


@case("bad_shot_too_long", "长于 7 秒")
def _(sb):
    del sb["shots"][10:12]                            # 第 9、10、11 句并成一个镜头，约 8 秒
    renumber(sb)


@case("bad_long_shots_many", "长于 5 秒的镜头有")
def _(sb):
    shots, i, out, n = sb["shots"], 0, [], 0
    while i < len(shots):
        if n < 9 and i + 1 < len(shots):
            out.append(shots[i])
            i += 2
            n += 1
        else:
            out.append(shots[i])
            i += 1
    sb["shots"] = out
    renumber(sb)


@case("bad_fast_cuts", "个快切镜头")
def _(sb):
    for sid, line, cuts in (("s06", 5, (0.95, 1.9)), ("s07", 6, (1.1, 2.2)), ("s08", 7, (1.0,))):     # 第 5、6、7 句各切成 1 秒左右的小镜头：连续 8 个
        i = next(k for k, s in enumerate(sb["shots"]) if s["id"] == sid)
        for n, dt in enumerate(cuts):
            b = split_shot(sb, sid, line, dt)
            sb["shots"].remove(b)
            b["id"] = f"{sid}_{n}"
            sb["shots"].insert(i + 1 + n, b)
    renumber(sb)


# ---- 频率、静止
@case("bad_rate_low", "每分钟")
def _(sb):
    sb["shots"] = [s for k, s in enumerate(sb["shots"]) if k % 2 == 0]
    renumber(sb)


@case("bad_rate_high", "太快")
def _(sb):
    for s in list(sb["shots"]):
        if s["id"] == "s01":
            continue
        split_shot(sb, s["id"], int(s["from"]["line"]), 1.5)
    renumber(sb)


@case("bad_static", "画面静止")
def _(sb):
    s = sh(sb, "s10")
    s["camera"] = [{"move": "push", "amount": 0}]
    s["fx"] = []
    s["actors"][0].pop("acts", None)


@case("bad_opening", "前 3 秒只有")
def _(sb):
    s = sh(sb, "s01")
    s["fx"] = []
    s["actors"][0].pop("enter", None)
    s["actors"][0].pop("acts", None)


# ---- 特效数量、闪烁
@case("bad_knowledge_pileup", "最多 3 样")
def _(sb):
    s = sh(sb, "s05")
    s["fx"] += [sticker(4, "？", dt=0.8, x=200), sticker(4, "！", dt=1.0, x=300), sticker(4, "啪", dt=1.2, x=400)]


@case("bad_knowledge_flash", "知识点不闪白")
def _(sb):
    sh(sb, "s05")["fx"].append({"type": "flash", "at": L(4, 1.0), "alpha": 0.4, "dur": 0.1})


@case("bad_knowledge_fast", "知识点不快切")
def _(sb):
    b = split_shot(sb, "s05", 4, 2.6)
    b["note"] = "知识点：还有一样"
    b["fx"] = [{"type": "checklist", "items": ["好心"], "pos": [540, 620], "at": L(4, 2.7)}]
    renumber(sb)


@case("bad_flash_total", "闪白一集 5 次")
def _(sb):
    for sid, line in (("s02", 1), ("s06", 5), ("s10", 9), ("s16", 15)):
        sh(sb, sid)["fx"].append({"type": "flash", "at": L(line, 1.0), "alpha": 0.4, "dur": 0.1})


@case("bad_flash_burst", "1 秒内有 4 次闪白")
def _(sb):
    for k in range(3):
        sh(sb, "s14")["fx"].append({"type": "flash", "at": L(13, 0.9 + 0.3 * k), "alpha": 0.3, "dur": 0.08})


@case("bad_flash_strength", "最多 0.6")
def _(sb):
    sh(sb, "s14")["fx"][0]["alpha"] = 0.9


# ---- 安全区
@case("bad_safe_face_top", "上边")
def _(sb):
    sh(sb, "s10")["actors"][0]["pos"] = [ALONE_X, 700]        # 脚在 y 700：脸在标题条下面、y 360 以上


@case("bad_safe_face_left", "左边")
def _(sb):
    sh(sb, "s10")["actors"][0]["pos"] = [110, FEET]


@case("bad_safe_face_right", "右侧平台遮挡区")
def _(sb):
    sh(sb, "s09")["actors"][1]["pos"] = [930, FEET]


@case("bad_safe_slam", "smash（slam）")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "smash", "text": "不给", "size": 200, "pos": [540, 1700], "at": L(9, 0.1)})


@case("bad_safe_prop", "关键道具")
def _(sb):
    sh(sb, "s10")["fg"] = [{"img": "props/cup_lacquer.png", "pos": [990, 1000], "anchor": [0.5, 0.5], "w": 300}]


# ---- 素材、放大
@case("bad_missing_image", "找不到素材")
def _(sb):
    sh(sb, "s04")["bg"][0]["img"] = "sets/nope/none.png"


@case("bad_missing_swap", "找不到素材")
def _(sb):
    sh(sb, "s01")["actors"][0]["acts"][0]["swap"] = "chars/none.png"


@case("bad_missing_sfx", "找不到音效")
def _(sb):
    sh(sb, "s04")["sfx"] = [{"name": "boom", "at": L(3)}]


@case("bad_upscale", "屏幕显示 ÷ 原图")
def _(sb):
    a = sh(sb, "s13")["actors"][0]
    a["h"] = 640
    a["pos"] = [ALONE_X, 1700]


@case("bad_upscale_camera", "含镜头放大")
def _(sb):
    s = sh(sb, "s13")
    s["actors"][0]["h"] = 520
    s["camera"] = [{"move": "push", "amount": 0.08}]


@case("bad_registry_disabled", "停用")
def _(sb):
    sh(sb, "s13")["actors"][0]["img"] = "chars/hkz_old.png"


@case("bad_registry_scope", "试做集")
def _(sb):
    sh(sb, "s13")["actors"][0]["img"] = "chars/sy2_stand.png"


# ---- 朝向、人名牌
@case("bad_facing", "要面向说话的人")
def _(sb):
    sh(sb, "s09")["actors"][0]["img"] = "chars/zxz_kneel_l.png"      # 第 8 句智伯（右边）说话，赵襄子（左边）用了朝左的图：脸朝左，背对智伯


@case("bad_namecard", "第一次出场")
def _(sb):
    sh(sb, "s02")["fx"] = [f for f in sh(sb, "s02")["fx"] if f.get("name") != "智伯"]


# ---- 翻转、压脸、集中线、人名牌停留（PITFALLS M1、M2、M4 那一轮补的）
@case("bad_flip_cross_collar", "左衽")
def _(sb):
    sh(sb, "s13")["actors"][0]["flip"] = True


@case("bad_sticker_on_face", "贴纸「！」")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "sticker", "text": "！", "pos": [540, 1200], "at": L(9, 0.5), "size": 180})


@case("bad_smash_on_face", "砸字「不给」")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "smash", "text": "不给", "size": 200, "pos": [540, 1200], "at": L(9, 0.1)})


@case("bad_splash_on_face", "水花")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "splash", "pos": [540, 1300], "at": L(9, 0.5)})


@case("bad_particles_no_avoid", "别写 avoid: []")
def _(sb):
    sh(sb, "s20")["fx"][0]["avoid"] = []


@case("bad_focus_no_clear", "没写 clear")
def _(sb):
    sh(sb, "s21")["fx"][-1].pop("clear")


@case("bad_focus_clear_short", "没盖住主体")
def _(sb):
    sh(sb, "s21")["fx"][-1]["clear"] = 60


@case("bad_focus_off_center", "没盖住主体")
def _(sb):
    sh(sb, "s21")["fx"][-1].update(pos=[540, 300], clear=200)


@case("bad_speed_lines_on_face", "盖住了 智伯 的脸")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "lines_speed", "dir": "left", "at": L(9, 0.2)})          # 默认 y 380–1330 整个宽度、画在人物前面：横穿智伯的脸和身体（M2 再犯）


@case("bad_plate_too_short", "只看得清")
def _(sb):
    next(f for f in sh(sb, "s02")["fx"] if f["type"] == "name_plate")["dur"] = 1.2


# ---- 字幕卡挡脸（M6、待补 20）、特效盖住主角（M8）
@case("bad_subtitle_covers_face", "字幕卡")
def _(sb):
    sh(sb, "s10")["actors"][0]["pos"] = [ALONE_X, 1800]            # 脸框 y 1354–1533：说话的时候字幕卡（一行，y 约 1478–1615）盖在嘴上


@case("bad_cover_icons_on_lead", "压在主角")
def _(sb):
    sh(sb, "s10")["fg"] = [{"img": "props/cup_lacquer.png", "depth": 1.0, "pos": [x, y], "anchor": [0.5, 0.5], "w": 230} for x in (420, 540, 660) for y in (1190, 1370)]


@case("bad_cover_bubble_on_lead", "压在主角")
def _(sb):
    sh(sb, "s10")["fx"].append({"type": "bubble", "text": "哼", "pos": [540, 1350], "w": 600, "at": L(9, 0.2)})


@case("bad_cover_speaker", "正在说话")
def _(sb):
    sh(sb, "s03")["fg"] = [{"img": "props/cup_lacquer.png", "depth": 1.0, "pos": [x, y], "anchor": [0.5, 0.5], "w": 180} for x in (250, 400) for y in (1200, 1290, 1380)]    # 第 2 句韩康子（左，比较小）说话，被图标盖住


# ---- 停留（M9、M10）
@case("bad_dwell_bubble", "只看得见")
def _(sb):
    sh(sb, "s13")["fx"].append({"type": "bubble", "text": "哼", "pos": [700, 1000], "w": 600, "at": L(12, 2.35)})      # s13 共 3.7 秒：泡泡 2.35 秒才弹出，0.15 秒弹完，只剩 1.2 秒就切走


# ---- 格式
@case("bad_typo_key", "不认识的字段")
def _(sb):
    sh(sb, "s04")["camara"] = []


@case("bad_unknown_fx", "没有叫 'sparkel' 的特效")
def _(sb):
    sh(sb, "s04")["fx"][0]["type"] = "sparkel"


def dump(sb, path):
    """紧凑一点：每个镜头一行，方便看 diff。"""
    lines = ["{"]
    for k, v in sb.items():
        if k == "shots":
            lines.append(' "shots": [')
            lines += ["  " + json.dumps(s, ensure_ascii=False) + ("," if i + 1 < len(v) else "") for i, s in enumerate(v)]
            lines.append(" ]" + ("," if list(sb)[-1] != "shots" else ""))
        else:
            lines.append(f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" + ("," if k != list(sb)[-1] else ""))
    lines.append("}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_all():
    (HERE / "voice").mkdir(exist_ok=True)
    (HERE / "voice" / "timeline.json").write_text(json.dumps(TL, ensure_ascii=False, indent=1), encoding="utf-8")
    good = make_good()
    dump(good, TESTS / "good_storyboard.json")
    expect = {}
    for name, (fn, needle) in CASES.items():
        sb = copy.deepcopy(good)
        fn(sb)
        sb["note"] = f"故意写坏的分镜表（{name}）：在 good_storyboard.json 的基础上只改一处，storyboard_check 必须报「{needle}」。make_case.py 生成。"
        dump(sb, TESTS / f"{name}.json")
        expect[f"{name}.json"] = needle
    (TESTS / "check_expect.json").write_text(json.dumps(expect, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"timeline.json（{len(LINES)} 句 {TL['duration']} 秒）+ good_storyboard.json + {len(CASES)} 个 bad_*.json + check_expect.json")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "write":
        write_all()
    elif len(sys.argv) == 3 and sys.argv[1] == "assets":
        make_assets(sys.argv[2])
    else:
        sys.exit(__doc__)
