"""生成 tj03 分镜表 video/stories/tj03/storyboard.json（配音 video/out/tj03_voice，174.22 秒）。
依据：A_在德.json、镜头大纲.md、素材清单.md（新图的文件名照清单；builder 画完登记）。照 tj02 的 gen_storyboard.py 写。
站位：船头朝右往右漂；魏武侯在左朝右、吴起在右（船头）朝左、划桨的人在船尾（左）朝右（素材清单第二节）。
司马光（10-01 Chris、版式和画风最后一节）：一律在书房、站在书桌后面，人在画面中部，脸框底边 ≤ y 1300（字幕卡 + 说话人标签从约 1327 起），
手和遥控器在 y 1300 以上；不从画面底边探头、不用 page_edge。
船和人的比例：船图 1969 宽、放大不能超过 1.3 倍，人按中景的大小放，船按能放的最大倍数放（tj02 预告同样的做法）；人站在 boat_back 和 boat_front 之间，
腰（大约图高 0.6 处）落在近侧船舷上沿上，船舷以下被 boat_front 和前景的水挡住。
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "storyboard.json"
ASSETS = Path(__file__).resolve().parents[2] / "assets"


def A(line=None, word=None, dt=None, nth=None):
    a = {}
    if line is not None:
        a["line"] = line
    if word is not None:
        a["word"] = word
    if nth is not None:
        a["nth"] = nth
    if dt is not None:
        a["dt"] = round(dt, 2)
    return a


def D(dt):
    return {"dt": round(dt, 2)}


# ---------------------------------------------------------------- 图层
def L(img, pos, depth=1.0, anchor=None, **kw):
    d = {"img": img, "depth": depth, "pos": [round(pos[0]), round(pos[1])]}
    if anchor is not None:
        d["anchor"] = list(anchor)
    d.update(kw)
    return d


def blurred(layers, blur):
    if blur:
        for x in layers:
            x["blur"] = blur
    return layers


def sky(blur=0, **kw):
    d = L("sets/jin_land/sky.png", [0, 0], 0.1, w=1080, **kw)
    if blur:
        d["blur"] = blur
    return d


def ridges(y_far=470, y_mid=640, near=None, blur=0):
    out = [L("sets/jin_land/ridge_far.png", [540, y_far], 0.2, [0.5, 0], w=1100),
           L("sets/jin_land/ridge_mid.png", [540, y_mid], 0.3, [0.5, 0], w=1100)]
    if near is not None:
        out.append(L("sets/jin_land/ridge_near.png", [540, near], 0.4, [0.5, 0], w=1100))
    return blurred(out, blur)


def ground(y0=1290, blur=0):
    """地面条一条比一条宽地往下铺满（照 tj02 strips()，间距收紧、多一条）。"""
    out, y = [], float(y0)
    for k, w in enumerate((1300, 1450, 1600, 1750, 1900)):
        g = L("sets/jin_land/ground.png", [540, y], 0.9, [0.5, 0], w=w, repeat="x")
        if k % 2:
            g["flip"] = True
        out.append(g)
        y += 218 * w / 1528 * 0.65      # 0.65（tj02 是 0.8）：上沿草丛的缺口落在上一条不透明的地方，条和条之间不露底（[铺满]）
    return blurred(out, blur)


def water(y0=1180, n=4, depth=0.7, dy=140, amp=26, blur=0):
    out = []
    for k in range(n):
        d = L("sets/jin_land/water.png", [540, y0 + dy * k], min(depth + 0.05 * k, 1.0), [0.5, 0], w=1528, repeat="x",
              sway={"x": amp, "y": 6, "period": 3.4, "phase": round(0.4 * k, 2)})
        if blur:
            d["blur"] = blur
        out.append(d)
    return out


def river_ridges(blur=0):
    """大河的三层山（照 tj02 s68–s72，量过不露缝：远山 y 300、中山 640、近山 830，宽 1250，底边藏在水面后面）。"""
    out = [L("sets/jin_land/ridge_far.png", [540, 300], 0.2, [0.5, 0], w=1250),
           L("sets/jin_land/ridge_mid.png", [490, 640], 0.3, [0.5, 0], w=1250),
           L("sets/jin_land/ridge_near.png", [470, 830], 0.4, [0.5, 0], w=1250)]
    return blurred(out, blur)


def river(blur=0):
    return [sky(blur)] + river_ridges(blur) + water(1180, 6, 0.7, 140, blur=blur)


def palace_bg(blur=0):
    return blurred([sky()] + ridges(470, 640, near=820) + [L("sets/palace/hall.png", [540, 1330], 0.6, [0.5, 1], w=1300)] + ground(1250), blur)


def study_bg(blur=0, full=False):
    """书房后墙（1024×1536）。有书桌前景的镜头宽 1080 就够（铺出来 1620 高，下面被书桌盖住）；
    没有书桌的镜头写 full=True：宽 1300、往左挪 110，铺出来 1950 高（震屏也不露底），画面最下面也有画（M7 第三次再犯）。"""
    if full:
        out = [L("sets/study/wall.png", [-110, 0], 0.3, w=1300)]
    else:
        # 书桌镜头：后墙宽 1080 只铺到 y 1620，桌腿中间会露底 → 下面先垫一张同样的墙往下挪 320（只露出它的木地板，铺到 y 1940），
        # 正常那张盖在上面（书架、鸡蛋落点的位置不变）
        out = [L("sets/study/wall.png", [0, 320], 0.3, w=1080), L("sets/study/wall.png", [0, 0], 0.3, w=1080)]
    if blur:
        for d in out:
            d["blur"] = blur
    return out


def desk():
    """书桌：底边 1930、宽 1150 → 桌面上沿约 y 1430；司马光的半身图下沿藏在桌子后面。"""
    return L("sets/study/desk.png", [540, 1930], 1.0, [0.5, 1], w=1150)


def fore(y=1930):
    return L("sets/jin_land/fore.png", [540, y], 1.0, [0.5, 1], w=1850, repeat="x")


# ---------------------------------------------------------------- 大木船（量过的近侧船舷上沿：图 x → 图 y，图 1969×410）
# 近侧船身下沿（船底）：图 x → 图 y（不透明的最下面一行）
BOT = [(300, 229), (400, 267), (500, 287), (600, 300), (700, 309), (800, 317), (900, 325), (1000, 330), (1100, 333), (1200, 334),
       (1300, 333), (1400, 331), (1500, 327), (1600, 319), (1700, 306), (1800, 278), (1900, 204)]
WATER_CREST = 50       # water.png 最上面 50 行是浪尖（有缝），第 50 行起整行不透明
GUN = [(300, 114), (400, 137), (500, 152), (600, 166), (700, 178), (800, 186), (900, 193), (1000, 198), (1100, 201), (1200, 203),
       (1300, 203), (1400, 199), (1500, 191), (1600, 180), (1700, 162), (1800, 135), (1900, 86)]
BOAT_W, BOAT_H, HULL_BOTTOM = 1969, 410, 330


def _interp(tab, xi):
    xi = min(max(xi, tab[0][0]), tab[-1][0])
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x0 <= xi <= x1:
            return y0 + (y1 - y0) * (xi - x0) / (x1 - x0)
    return tab[-1][1]


def gun_y(cx, by, k, x):
    """屏幕 x 处近侧船舷上沿的屏幕 y（船底边中点 (cx, by)、放大 k 倍）。"""
    xi = (x - (cx - BOAT_W * k / 2)) / k
    xi = min(max(xi, GUN[0][0]), GUN[-1][0])
    for (x0, y0), (x1, y1) in zip(GUN, GUN[1:]):
        if x0 <= xi <= x1:
            yi = y0 + (y1 - y0) * (xi - x0) / (x1 - x0)
            return by - (BOAT_H - yi) * k
    return by - (BOAT_H - GUN[-1][1]) * k


class Boat:
    def __init__(self, cx, by, k, blur=0, drift=None):
        self.cx, self.by, self.k, self.blur, self.drift = cx, by, k, blur, drift

    def layer(self, img):
        e = {"anim": [dict(self.drift)]} if self.drift else {}
        d = L(img, [self.cx, self.by], 1.0, [0.5, 1], w=round(BOAT_W * self.k), note="布景前层", **e)
        if self.blur:
            d["blur"] = self.blur
        return d

    def back(self):
        return self.layer("props/boat_back.png")

    def water_top(self):
        """前景第一条水的上沿：浪尖从这里开始，往下 WATER_CREST 像素起整行不透明（= 船底中间往上 10 像素，船吃水）。"""
        return round(self.by - (BOAT_H - HULL_BOTTOM) * self.k - 10 - WATER_CREST)

    def front(self):
        """近侧船身 + 前景的水：水满不透明的那一行在船底上面，站在船里的人船舷以下的腿脚全被船身和水盖住；
        水一条接一条铺到画面底下以外（≥ 1990，镜头推了也看不到最后一条的平直下沿）。"""
        y0 = self.water_top()
        n = max(3, -(-(1990 - 203 - y0) // 120) + 1)
        return [self.layer("props/boat_front.png")] + water(y0, n, 1.0, 120, blur=self.blur)

    def gun(self, x):
        return gun_y(self.cx, self.by, self.k, x)

    def stand(self, id_, who, img, x, h, note, hip=0.6, **kw):
        """站在船里：图高 hip 处落在近侧船舷上沿。船头 / 船尾的船底往上翘，比前景水满不透明的那一行高的地方，
        脚底（图的下沿）不低于这一段船底，免得下摆和鞋尖从船底和水之间露出来。"""
        y = self.gun(x) - hip * h + h
        iw, ih = Image.open(ASSETS / img).size
        half = 0.25 * iw * h / ih
        k = self.k
        x0i, x1i = [(xx - (self.cx - BOAT_W * k / 2)) / k for xx in (x - half, x + half)]
        bot = min(_interp(BOT, xi) for xi in (x0i, (x0i + x1i) / 2, x1i))
        hull = self.by - (BOAT_H - bot) * k
        full = self.water_top() + WATER_CREST
        if hull < full:
            y = min(y, hull - 4)
        return P(id_, who, img, [x, y], h, note, **kw)


MED = Boat(281, 1625, 1.2)           # 中景：船舷平的那段（图 x 900–1500）在画面中间，船舷上沿约 y 1377；船图中心 y 1379（关键道具中心 ≤ 1400，镜头推 4% 以后也在里面），放大 1.2（留镜头推的余量）
HOOK = Boat(124, 1537, 1.0)          # 开场：船头在画面右边（图 x 1900 → 屏幕约 1040）


def rowers(boat, x, h, img="chars/rower_row.png", oars=True, note="五个划桨的人（交领粗布短衣、橙黄头巾）坐着划桨", **kw):
    """划桨的人：图高 0.7 处（膝盖）落在船舷上沿；脸框是五个人合起来的一个大框（图宽 0.10–0.96），所以 h ≤ 380、中心 x 约 474 才进得了 x 80–940；桨叶前景层 rower_oars_fg 同位置同大小叠在 boat_front 前面（换成 rower_stop 时淡掉）。"""
    y = boat.gun(x) - 0.7 * h + h
    a = P("rw", RW, img, [x, y], h, note, **kw)
    fgl = [L("chars/rower_oars_fg.png", [x, y], 1.0, [0.5, 1], h=h, note="布景前层（桨叶伸出船舷，和 rower_row 同画布）")] if oars else []
    return a, fgl


# ---------------------------------------------------------------- 人物、特效
def P(id_, who, img, pos, h, note, **kw):
    d = {"id": id_, "who": who, "img": img, "pos": [round(pos[0]), round(pos[1])], "h": round(h)}
    d.update(kw)
    d["note"] = note
    return d


def act(at, do=None, swap=None, **kw):
    d = {"at": at}
    if do:
        d["do"] = do
    if swap:
        d["swap"] = swap
    d.update(kw)
    return d


def fx(type_, at=None, **kw):
    d = {"type": type_}
    if at is not None:
        d["at"] = at
    d.update(kw)
    return d


def st_text(text, pos, at, size=110, **kw):
    return fx("sticker", at, text=text, pos=list(pos), size=size, **kw)


def st(name, pos, at, size=110, **kw):
    return fx("sticker", at, name=name, pos=list(pos), size=size, **kw)


def plate(name, role, pos, at, size=0.55, house=None, color=None, **kw):
    d = fx("name_plate", at, name=name, role=role, pos=list(pos), size=size, **kw)
    if house:
        d["house"] = house
    if color:
        d["color"] = color
    return d


def cam(*moves):
    return list(moves)


def push(a=0.04):
    return {"move": "push", "amount": a}


def pull(a=0.04):
    return {"move": "pull", "amount": a}


def pan(dx=0, dy=0):
    return {"move": "pan", "dx": dx, "dy": dy}


def punch(at, a=0.1):
    return {"move": "punch", "at": at, "amount": a}


def shake(at, dur=0.3, amp=10):
    return {"move": "shake", "at": at, "dur": dur, "amp": amp}


def sfx(name, at, gain=None):
    d = {"name": name, "at": at}
    if gain is not None:
        d["gain"] = gain
    return d


SH = []


def shot(id_, frm, size, note, **kw):
    s = {"id": id_, "from": frm, "size": size}
    s.update(kw)
    s["note"] = note
    SH.append(s)
    return s


WUH, WQ, SGM, RW, WWH = "魏武侯", "吴起", "司马光", "划桨的人", "魏文侯"
GB, WH, ZS = "苟变", "卫侯", "子思"
WQ_COLOR = "#5b4636"          # 吴起的说话人颜色（深皮甲棕；魏武侯用魏家橙黄）
RW_COLOR = "#a8742e"
WH_COLOR = "#7d8440"          # 卫侯（橄榄苔绿，登记表）
ZS_COLOR = "#6b6158"
GB_COLOR = "#8a7a62"

# 司马光的高清半身 / 全身：脸框下沿占图高的比例（faces.json），用来把脸框底边放在 y 1300
SGM_FB = {"chars/sgm_hi_remote.png": 0.606, "chars/sgm_hi_point.png": 0.65, "chars/sgm_hi_read.png": 0.662,
          "chars/sgm_hi_shock.png": 0.674, "chars/sgm_thumb.png": 0.523, "chars/sgm_book.png": 0.527}
REMOTE = (0.88, 0.50)     # sgm_hi_remote 里遥控器在图里的位置（比例）
SGM_RATIO = {"chars/sgm_hi_remote.png": 1016 / 1310}


def sgm(img, x, h, note, face_bottom=1300, **kw):
    """书桌后面的司马光：脸框底边放在 face_bottom（默认 1300，字幕卡 + 标签上沿约 1327 之上），图的下沿藏在书桌（桌面 1430）后面。"""
    y = face_bottom - SGM_FB[img] * h + h
    return P("sgm", SGM, img, [x, y], h, note, **kw)


def remote_pos(x, h, face_bottom=1300):
    w = h * SGM_RATIO["chars/sgm_hi_remote.png"]
    top = face_bottom - SGM_FB["chars/sgm_hi_remote.png"] * h
    return [round(x - w / 2 + REMOTE[0] * w), round(top + REMOTE[1] * h)]


# 高清半身特写：下沿出画（≥ 1920），脸框底边 ≤ 1310
def hi_wuh(img, x, note, **kw):          # wuh_hi_*：795×1188，脸框 y 0.22–0.53
    return P("wuh", WUH, img, [x, 1925], 1300, note, **kw)


def hi_wq(img, x, note, **kw):           # wq_hi_*：1020×1358，脸框 y 0.18–0.52
    return P("wq", WQ, img, [x, 1925], 1300, note, **kw)


# ======================================================== 开场：反差钩子（第 0 句，动作）
shot("s01", A(0, dt=-0.3), "medium",
     "开场反差：大河中间（原文「中流」，不画峡谷），第二集的大木船顺流往右漂；船里，魏武侯（左，魏家橙黄衣服、黑小冠，是侯）扶着船舷仰头哈哈大笑，"
     "一朵浪花「噗」地溅上来，他照样笑（笑点）；船头的吴起（右，炭黑褐色皮甲，不拿兵器）本来抱着胳膊望着前方，眉头一皱、转过身来（不碰剑）",
     bg=river() + [HOOK.back()],
     actors=[HOOK.stand("wuh", WUH, "chars/wuh_laugh.png", 420, 440, "魏武侯扶着船舷，仰头张大嘴哈哈大笑，得意极了（不凶）", hip=0.57,
                        acts=[act(D(0.2), "bounce"), act(D(1.0), "bounce")]),
             HOOK.stand("wq", WQ, "chars/wq_stand.png", 820, 470, "吴起站在船头双臂抱胸望着前方，没有笑；眉头一皱、转过身来对着魏武侯（不碰剑）",
                        acts=[act(D(1.4), swap="chars/wq_frown_l.png", h=470)])],
     fg=HOOK.front(),
     fx=[plate("魏武侯", "魏文侯的儿子", [150, 400], D(0.1), house="魏家"),
         plate("吴起", "常胜将军", [600, 400], D(0.5), color=WQ_COLOR),
         fx("splash", D(0.4), pos=[120, 1500], size=0.6, layer="back"),
         st_text("噗", [640, 980], D(0.45), 90, color="blue"),
         st_text("咚", [880, 880], D(2.1), 110)],
     sfx=[sfx("whoosh", D(1.4)), sfx("slam_1", D(2.1))],
     camera=cam(push(0.04), punch(D(2.1), 0.1)))

# ======================================================== 司马光的反问（第 1 句）
x, h = 540, 1000
shot("s02", A(1), "medium",
     "书房里，司马光站在书桌后面（人在画面中部），举起遥控器「咔」地按一下，笑呵呵地开口：「如果你坐着全天下最坚固的无敌战舰……」",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举着遥控器按下去，哈哈笑着问观众", acts=[act(D(0.35), "bounce")])],
     fg=[desk()],
     fx=[fx("remote_click", D(0.3), pos=remote_pos(x, h))],
     camera=cam(push(0.03)))

WIDE = Boat(540, 1450, 0.6)


def wide_people(boat, rw_img="chars/rower_row.png", drift=None, wq_img="chars/wq_frown_l.png"):
    """远景里的船上的人（当布景图层画，人很小）：划桨的人在船尾、魏武侯在中间、吴起在船头。"""
    e = {"anim": [dict(drift)]} if drift else {}
    gx = lambda x: boat.gun(x)  # noqa: E731
    return [L(rw_img, [330, gx(330) - 0.66 * 170 + 170], 1.0, [0.5, 1], h=170, **e),
            L("chars/wuh_stand.png", [640, gx(640) - 0.6 * 210 + 210], 1.0, [0.5, 1], h=210, **e),
            L(wq_img, [800, gx(800) - 0.6 * 220 + 220], 1.0, [0.5, 1], h=220, **e)]


shot("s03", A(1, word="最坚固"), "wide",
     "知识（比喻）：「全天下最坚固的无敌战舰，身边全是你自己的保镖」：大河上整条大木船（远景），船上的人都在；旁边弹出一张属性卡「无敌战舰」："
     "坚固 ★★★★★、保镖 ★★★★★（游戏面板，是比喻；画面上仍是第二集的大木船）",
     bg=river() + [WIDE.back()] + wide_people(WIDE),
     fg=WIDE.front(),
     fx=[fx("stat_card", D(0.05), name="无敌战舰",
            rows=[{"label": "坚固", "stars": 5, "icon": "props/icon_boat.png"}, {"label": "保镖", "stars": 5, "icon": "props/icon_guard.png"}],
            pos=[540, 760], w=600, gap=0.8)],
     camera=cam(push(0.03)))

x, h = 540, 780
shot("s04", A(1, word="你信不信"), "close",
     "司马光转向镜头，伸出食指指着观众，眉毛一挑：「你信不信——下一秒……」",
     bg=study_bg(blur=5),
     actors=[sgm("chars/sgm_hi_point.png", x, h, "司马光笑眯眯，伸出食指指着观众，眉毛一挑", acts=[act(A(1, word="下一秒"), "bounce")])],
     fg=[desk()],
     camera=cam(push(0.03)))

rw, rw_fg = rowers(MED, 474, 380)
rw["acts"] = [act(D(0.4), "bounce"), act(D(1.4), "bounce")]
HEADS = [(0.13, 0.10), (0.32, 0.08), (0.51, 0.09), (0.70, 0.17), (0.88, 0.13)]     # rower 图里五个人头顶的位置（比例）


def head_xy(a, k):
    """a = rowers() 返回的 actor：第 k 个人头顶上方一点的屏幕位置。"""
    x, y, h = a["pos"][0], a["pos"][1], a["h"]
    w = h * 1526 / 621
    fx_, fy_ = HEADS[k]
    return [round(x - w / 2 + fx_ * w), round(y - h + fy_ * h - 55)]


shot("s05", A(1, word="这船上的人"), "medium",
     "「这船上的人，都可能变成你的对手？」：船上五个划桨的人笑眯眯地划着桨；说到「对手」，五个人头顶「啪啪啪」一个接一个冒出问号（不画兵器、不画刀对着人）",
     transition={"type": "whip", "dur": 0.28},
     bg=river(blur=3) + [MED.back()],
     actors=[rw],
     fg=MED.front() + rw_fg,
     fx=[plate("划桨的人", "船上的人", [150, 400], D(0.1), color=RW_COLOR)] +
        [st("question", head_xy(rw, k), A(1, word="对手", dt=0.1 * k), 90) for k in range(5)],
     camera=cam(push(0.04)))

# ======================================================== 时代：魏宫前（第 2–3 句）
shot("s06", A(2), "wide",
     "承接上一集：魏宫前，小字条「公元前387年 · 战国」；魏文侯冲镜头温和地点点头，慢慢退到后面淡出（「去世」只这样带过，不画灵堂、不画哭）；"
     "儿子魏武侯从后面一步站出来，神气地扬扬下巴",
     transition={"type": "page_turn", "dur": 0.6},
     bg=palace_bg(),
     actors=[P("wwh", WWH, "chars/wwh_stand.png", [260, 1530], 420, "魏文侯温和地点点头，慢慢退到后面淡出",
               acts=[act(D(0.15), "nod")], anim=[{"at": A(2, word="去世", dt=0.1), "dur": 0.8, "dpos": [-40, -30], "alpha": 0.0}]),
             P("wuh", WUH, "chars/wuh_stand.png", [600, 1540], 470, "魏武侯从后面一步站出来，下巴微抬、神气地笑",
               enter={"type": "slide_right", "at": A(2, word="儿子"), "dur": 0.4}, acts=[act(A(2, word="接班"), "bounce")])],
     fg=[fore()],
     fx=[plate("魏文侯", "上一集的主角", [150, 620], D(0.05), house="魏家"),
         fx("card_title", D(0.1), text="公元前387年", sub="战国", pos=[600, 560])],
     camera=cam(push(0.03)))

shot("s07", A(3), "wide",
     "知识：「当时的魏国兵强马壮」：魏宫前，魏家的大旗「噌」地立得高高的，一辆两轮战车套着马停在旁边（马只拉车，不画骑马）；「兵强马壮」四个字砸下来",
     bg=palace_bg() + [L("props/chariot_back.png", [640, 1500], 1.0, [0.5, 1], w=820, note="布景前层")],
     fg=[L("props/chariot_front.png", [640, 1500], 1.0, [0.5, 1], w=820, note="布景前层"),
         L("props/horse.png", [864, 1500], 1.0, [0.5, 1], w=268, note="布景前层"),
         L("props/flag_wei.png", [190, 1560], 1.0, [0.5, 1], h=420,
           anim=[{"at": D(0.2), "dur": 0.35, "ease": "back", "scale": 1.35}]), fore()],
     fx=[fx("smash", D(0.1), text="兵强马壮", pos=[540, 680], size=190, color="orange")],
     sfx=[sfx("whoosh", D(0.2))],
     camera=cam(push(0.04)),
     notes={"jev_allow": ["subject"], "why": "旁白讲「当时的魏国兵强马壮」：说到的是魏国，画面就是魏家的大旗和套好马的战车（魏国的兵马），这句的后半「常胜将军吴起」下一镜 s08 由吴起出场接上"})

shot("s08", A(3, word="常胜将军"), "medium",
     "「还拥有常胜将军吴起！」：吴起大步跨进画面，双臂抱胸站定，身边「叮叮叮」亮起三颗小星星；旗子底下一只小青蛙也挺起胸膛学他站好（笑点）",
     bg=palace_bg(blur=4),
     actors=[P("wq", WQ, "chars/wq_stand.png", [560, 1570], 520, "吴起大步跨进来，双臂抱胸站定，目光锐利",
               enter={"type": "slide_right", "dur": 0.4})],
     fg=[L("props/frog_proud.png", [830, 1500], 1.0, [0.5, 1], w=110, enter={"type": "pop", "at": D(1.0)}), fore()],
     fx=[st("star", [800, 1000], D(0.5), 80), st("star", [860, 1120], D(0.65), 70), st("star", [790, 1240], D(0.8), 60)],
     sfx=[sfx("frog_croak", D(1.2))],
     camera=cam(push(0.04)))

# ======================================================== 大船（第 4–5 句）
drift = {"at": D(0.0), "dur": 2.4, "ease": "linear", "dpos": [60, 0]}
WIDE2 = Boat(500, 1450, 0.6, drift=drift)
shot("s09", A(4, word="这艘"), "wide",
     "「就在这艘顺流而下的大船上」：大河上，一整条大木船顺流往右漂（浪花平稳，不画翻船），船上小小的魏武侯、吴起和划桨的人",
     transition={"type": "iris", "dur": 0.6, "pos": [540, 1250]},
     bg=river() + [WIDE2.back()] + wide_people(WIDE2, drift=drift),
     fg=WIDE2.front(),
     camera=cam(push(0.03)))

shot("s10", A(4, word="吴起却把"), "medium",
     "「吴起却把魏武侯……」：船上，魏武侯（左）还扶着船舷得意地笑，吴起（右）皱着眉看着他",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_laugh.png", 330, 460, "魏武侯扶着船舷仰头大笑", hip=0.57, acts=[act(D(0.3), "bounce")]),
             MED.stand("wq", WQ, "chars/wq_frown_l.png", 760, 500, "吴起皱着眉，严肃地看着魏武侯")],
     fg=MED.front(),
     camera=cam(push(0.04)))

shot("s11", A(4, word="吓出了"), "close",
     "「吓出了一身冷汗！」：魏武侯特写，笑脸「唰」地变成冷汗脸、身子一抖（滑稽的汗珠，不画吓得发抖）",
     bg=river(blur=6),
     actors=[hi_wuh("chars/wuh_hi_laugh.png", 380, "魏武侯哈哈大笑，一下子愣住，额头冒出冷汗珠",
                    acts=[act(A(4, word="冷汗", dt=-0.2), swap="chars/wuh_hi_sweat.png", h=1300), act(A(4, word="冷汗"), "shake")])],
     fx=[st("sweat", [760, 760], A(4, word="冷汗"), 110)],
     camera=cam(push(0.03), punch(A(4, word="冷汗"), 0.08)))

shot("s12", A(5), "medium",
     "大问题「点个赞，看战神如何给国君上课！」：船上，魏武侯（左）笑嘻嘻、吴起（右）皱着眉；点赞的小心心「啵」地弹出来，顶荷叶的小青蛙从船舷上蹦上去按了一下（笑点）",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_stand.png", 330, 480, "魏武侯站着，下巴微抬，得意地笑"),
             MED.stand("wq", WQ, "chars/wq_frown_l.png", 760, 500, "吴起皱着眉，严肃地看着魏武侯", acts=[act(A(5, word="战神"), "nod")])],
     fg=MED.front() + [L("props/frog_leaf.png", [560, 1420], 1.0, [0.5, 1], w=150,
                         anim=[{"at": A(5, word="点个赞", dt=0.35), "dur": 0.4, "ease": "out", "dpos": [0, -360]},
                               {"at": A(5, word="点个赞", dt=0.75), "dur": 0.3, "ease": "in", "dpos": [0, 40]}])],
     fx=[st("heart", [560, 820], A(5, word="点个赞"), 170)],
     sfx=[sfx("whoosh", A(5, word="点个赞", dt=0.35)), sfx("frog_croak", A(5, word="点个赞", dt=0.8))],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject", "meme"], "why": "大问题（剧本原话，Chris 10-02 同意）：「战神」说的就是常胜将军吴起，「国君」是魏武侯，两个人都在船上（吴起在右、魏武侯在左）；「点个赞」是系列的行动呼吁，配青蛙按赞的笑点"})

# ======================================================== 第一关：夸山河（第 6–9 句）
shot("s13", A(6), "medium",
     "第一关（大字）：大木船行到河中间，两岸是高高的山；魏武侯扶着船舷仰头大笑：「哈哈哈哈！吴将军快看！」",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=river() + [HOOK.back()],
     actors=[HOOK.stand("wuh", WUH, "chars/wuh_laugh.png", 420, 440, "魏武侯扶着船舷仰头哈哈大笑，冲吴将军喊快看", hip=0.57,
                        acts=[act(A(6, word="哈哈"), "bounce"), act(A(6, word="快看"), "bounce")])],
     fg=HOOK.front(),
     fx=[fx("rays", A(6, dt=0.05), pos=[540, 540]), fx("big_title", A(6, dt=0.05), text="第一关：\n险峻山川与自满膨胀", pos=[540, 540], size=95, deco="none"),
         st_text("哈哈哈", [760, 940], A(6, word="哈哈"), 90)],
     camera=cam(push(0.03)))

shot("s14", A(6, word="万丈绝壁"), "wide",
     "「两边是万丈绝壁，脚下是滚滚黄河！」：魏武侯在船上指着两岸的高山，镜头慢慢推近；说到「滚滚」，船边浪花翻起来（这是他夸口，画面不画峡谷）",
     bg=river() + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_point.png", 330, 520, "魏武侯一手指着远处的高山、一手叉腰，仰头得意地笑", hip=0.66,
                       acts=[act(A(6, word="滚滚"), "bounce")])],
     fg=MED.front(),
     fx=[fx("splash", A(6, word="滚滚"), pos=[760, 1520], size=1.0, layer="back")],
     camera=cam(push(0.04)))

shot("s15", A(7), "medium",
     "知识：「只要守住这险要地形，谁能攻得进来？」：魏武侯叉腰指着两岸，身边弹出「得意值」刻度板往上涨；两岸山头「咚、咚」各冒出一面魏家小旗",
     bg=river() + [MED.back(),
                   L("props/flag_wei.png", [560, 930], 1.0, [0.5, 1], h=150, enter={"type": "pop", "at": A(7, word="谁能")}),
                   L("props/flag_wei.png", [880, 900], 1.0, [0.5, 1], h=150, enter={"type": "pop", "at": A(7, word="攻得")})],
     actors=[MED.stand("wuh", WUH, "chars/wuh_point.png", 300, 600, "魏武侯一手叉腰、一手指着两岸的山，得意地笑")],
     fg=MED.front(),
     fx=[fx("progress", D(0.05), pos=[780, 760], title="得意值", kind="fill", color="orange", size=0.7, **{"from": 0.3, "to": 0.7})],
     camera=cam(push(0.03)))

shot("s16", A(7, word="这真是"), "close",
     "「这真是我们魏国天下无敌的传家宝啊！」：魏武侯特写哈哈大笑，「传家宝」金字一闪；得意值涨到头，「嘭」地冒一小股烟（笑点）",
     bg=river(blur=6),
     actors=[hi_wuh("chars/wuh_hi_laugh.png", 340, "魏武侯张大嘴哈哈大笑，眼睛笑成两条缝",
                    acts=[act(A(7, word="传家宝"), "bounce")])],
     fx=[fx("progress", D(0.0), pos=[800, 760], title="得意值", kind="fill", color="orange", size=0.7, pop_in=False, **{"from": 0.7, "to": 1.0}),
         st_text("传家宝", [810, 1150], A(7, word="传家宝"), 90, color="gold"),
         fx("dust", A(7, word="传家宝", dt=0.6), mode="puff", pos=[800, 470], size=110)],
     camera=cam(push(0.03)))

rw, rw_fg = rowers(MED, 472, 380)
rw["acts"] = [act(D(0.3), "bounce"), act(D(1.2), "bounce"), act(D(2.0), "bounce")]
shot("s17", A(8), "medium",
     "「船上所有人都在跟着魏武侯欢呼」：船上划桨的人跟着笑、桨划得更起劲，头顶冒出「好！」「哦——」（画面右边外面就是魏武侯）",
     bg=river(blur=3) + [MED.back()],
     actors=[rw],
     fg=MED.front() + rw_fg,
     fx=[st_text("好！", head_xy(rw, 0), D(0.3), 80, color="red"), st_text("哦——", head_xy(rw, 2), D(0.7), 80, color="orange"),
         st_text("好！", head_xy(rw, 4), D(1.1), 80, color="red")],
     camera=cam(push(0.04)),
     notes={"jev_allow": ["subject"], "why": "旁白「船上所有人都在跟着魏武侯欢呼」：主体就是说到的「船上所有人」（划桨的人）；同一句后半的吴起转身、冷水浇下来由下两镜 s18（吴起）、s19（魏武侯）接上"})

shot("s18", A(8, word="只有"), "medium",
     "「只有常胜将军吴起，冷冷地转过身」：船头的吴起没有笑，眉头一皱，慢慢转过身来（不碰剑）",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wq", WQ, "chars/wq_stand.png", 640, 500, "吴起双臂抱胸望着前方，没有笑；眉头一皱，转过身来",
                       acts=[act(A(8, word="转过身"), swap="chars/wq_frown_l.png", h=500)])],
     fg=MED.front(),
     fx=[fx("dust", A(8, word="转过身"), mode="puff", pos=[640, 1480], size=110)],
     camera=cam(push(0.03)))

shot("s19", A(8, word="一盆冷水"), "medium",
     "知识：「一盆冷水直接浇了下来！」：魏武侯头顶飘来一朵小乌云，「哗」地下了一小阵雨，浇在得意值刻度板上，刻度一下子掉下去一大截（笑点；只是浇了一下，不吓人）",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_stand.png", 360, 480, "魏武侯还在得意地笑，头顶飘来一朵小乌云",
                       acts=[act(A(8, word="浇了", dt=0.2), "shake")])],
     fg=MED.front() + [L("props/cloud_rain_small.png", [930, 470], 1.0, [0.5, 0.5], w=230, alpha=0.0,
                         anim=[{"at": D(0.05), "dur": 0.2, "alpha": 1.0}, {"at": D(0.05), "dur": 0.6, "ease": "out", "pos": [790, 520]}])],
     fx=[fx("progress", D(0.0), pos=[780, 900], title="得意值", kind="fill", color="orange", size=0.7, pop_in=False, **{"from": 1.0, "to": 0.4}),
         st_text("哗——", [640, 640], A(8, word="浇了"), 90, color="blue")],
     camera=cam(push(0.03)))

shot("s20", A(9), "medium",
     "「主公，你错了！」：吴起（右）上前一步（不碰剑），正对魏武侯；魏武侯（左）的笑一下子僵在脸上",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_stand.png", 300, 480, "魏武侯的笑僵在脸上"),
             MED.stand("wq", WQ, "chars/wq_speak_l.png", 800, 500, "吴起上前一步，正对魏武侯，一手摊开严肃地说：主公，你错了",
                       anim=[{"at": D(0.05), "dur": 0.35, "ease": "out", "dpos": [-60, 0]}])],
     fg=MED.front(),
     fx=[st("exclaim", [0, 0], A(9, word="错了"), 90, follow="wuh", attach="head")],
     camera=cam(push(0.04)),
     notes={"jev_allow": ["kid"], "why": "吴起这句「在德不在险」是通鉴原话（剧本原话），这一镜配了一行白话小字「靠德行，不靠山河险」，接下来 s23–s26 司马光用「山再高、水再深，只是地形」和高墙下打呼噜的泡泡再讲一遍"})

shot("s21", A(9, word="一个国家"), "close",
     "「一个国家的安危」：吴起特写，眉头紧皱，严肃（不凶）",
     bg=river(blur=6),
     actors=[hi_wq("chars/wq_hi_frown.png", 640, "吴起眉头紧皱、严肃地直视魏武侯")],
     camera=cam(push(0.03), punch(D(0.1), 0.08)))

shot("s22", A(9, word="在德"), "close",
     "知识（点题）：「在德，不在险！」吴起摊开手讲道理，「在德不在险」五个大字砸下来，左边两行小字「靠德行，不靠山河险」（不压吴起的冠）（知识镜头只出三样：定格挪到下一镜 s23 开头）",
     bg=river(blur=6),
     actors=[hi_wq("chars/wq_hi_speak.png", 640, "吴起一手摊开，认真地讲道理：在德，不在险")],
     fx=[fx("smash", A(9, word="在德", dt=-0.1), text="在德不在险", pos=[540, 560], size=160, color="gold"),
         st_text("靠德行，", [215, 720], A(9, word="不在险"), 52, color="red"),
         st_text("不靠山河险", [215, 800], A(9, word="不在险", dt=0.1), 52, color="red")],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["kid"], "why": "吴起这句「在德不在险」是通鉴原话（剧本原话），这一镜配了一行白话小字「靠德行，不靠山河险」，接下来 s23–s26 司马光用「山再高、水再深，只是地形」和高墙下打呼噜的泡泡再讲一遍"})

# ======================================================== 司马光提醒（第 10–11 句）
MED_W = Boat(540, 1450, 0.6)
FROZEN_PEOPLE = wide_people(MED_W)
shot("s23", A(10, word="山再高"), "wide",
     "知识：「山再高、水再深」：定格的大河画面（远景）：说到「山」，岸边的大山旁弹出一个「地形」小标签；说到「水」，河水旁也弹一个",
     bg=river() + [MED_W.back()] + FROZEN_PEOPLE,
     fg=MED_W.front(),
     fx=[fx("freeze", D(0.0), dur=1.7),
         st_text("地形", [300, 760], A(10, word="山再高", dt=0.1), 90, color="brown"),
         st_text("地形", [820, 1240], A(10, word="水再深", dt=0.1), 90, color="blue")],
     notes={"jev_allow": ["subject"], "why": "司马光的解说（第 10 句），这一镜是他说的「山再高、水再深」那幅定格的河景；他本人在前后两镜（书房）出镜"})

x, h = 540, 820
shot("s24", A(10, word="只是"), "medium",
     "「只是自然界的地形」：书房里，司马光仰头看一座「噌」地冒出来的剪纸高山，脖子越仰越后，赶紧一把扶住帽子（笑点）",
     transition={"type": "paper_wipe", "dur": 0.5},
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_shock.png", x, h, "司马光仰头看高山，眼睛圆睁，一手赶紧扶住帽子", acts=[act(D(0.5), "jump")])],
     fg=[desk(), L("props/mini_mountains.png", [860, 640], 1.0, [0.5, 0.5], w=260, enter={"type": "pop", "at": D(0.15)})],
     fx=[st_text("好高！", [840, 870], D(0.55), 80, color="red")],
     sfx=[sfx("pop", D(0.15))],
     camera=cam(push(0.03)))

x, h = 310, 820
shot("s25", A(11), "medium",
     "「要是以为有了天险就能为所欲为」：司马光头顶冒出想象泡泡：高高的夯土墙下，一个纸片小人跷着二郎腿打呼噜（以为有墙就万事大吉）",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举着遥控器，笑眯眯地讲", acts=[act(A(11, word="为所欲为"), "nod")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_wall_nap.png", pos=[420, 880], w=820),
         st_text("Zzz", [880, 520], A(11, word="就能"), 70)],
     camera=cam(push(0.03)))

shot("s26", A(11, dt=2.45), "medium",
     "「大祸马上就要上门！」：泡泡推近墙脚，「啪嗒」掉下一块土，一个红色感叹号「叮」地弹出来；司马光再按一下遥控器，定格解除",
     bg=study_bg(blur=6, full=True),
     fx=[fx("bubble", D(0.0), img="props/bubble_wall_nap.png", pos=[120, 1300], w=820, crop=[0, 0, 1532, 1015], crop_to=[700, 380, 1440, 884],
            crop_t=0.0, crop_dur=0.8),
         fx("dust", A(11, word="上门", dt=-0.2), mode="puff", pos=[700, 1180], size=110),
         st("exclaim", [880, 620], A(11, word="上门"), 130, color="red")],
     sfx=[sfx("click", A(11, word="上门", dt=0.6))],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "司马光的解说（第 11 句），这一镜只放他头顶那个泡泡的特写（上一镜 s25 他在泡泡下面出镜）"})

# ======================================================== 第二关：三个例子（第 12–13 句）
CARDS = [("props/card_sanmiao.png", "props/flag_plain_a.png", "三苗"), ("props/card_xiajie.png", "props/flag_plain_b.png", "夏桀"),
         ("props/card_shangzhou.png", "props/flag_plain_c.png", "商纣")]


def cards(xs, yc, w, pop=None, fall=None):
    """三张快闪卡（1215×约 994 的横版立体卡）+ 每张卡前景正中那块米色平地（图高约 0.87）上立一面现成的无字小旗；pop = 念到谁谁翻出来；fall = 旗子依次倒下的锚点。"""
    hgt = w * 994 / 1215
    out = []
    for k, ((card, flag, name), x) in enumerate(zip(CARDS, xs)):
        e = {"enter": {"type": "flip", "at": A(12, word=name if name != "商纣" else "商纣王")}} if pop else {}
        out.append(L(card, [x, yc], 1.0, [0.5, 0.5], w=w, **e))
        fl = L(flag, [x, yc - hgt / 2 + 0.87 * hgt], 1.0, [0.5, 1], h=round(0.32 * w), **e)
        if fall:
            fl["anim"] = [{"at": {**fall, "dt": round(fall.get("dt", 0) + 0.2 * k, 2)}, "dur": 0.3, "ease": "in", "rot": -85}]
        out.append(fl)
    return out


shot("s27", A(12), "medium",
     "第二关（大字）：吴起（右）伸手一挥，船上空「啪、啪、啪」依次翻出三张纸艺立体快闪卡（念到谁谁翻出来）：三苗（两片大湖）、夏桀（大河、高山、像大门一样的山口）、"
     "商纣（险要的山口、太行山、大河），每张卡前面立着一面小旗（只画山水，不画人、不画打仗，不标方位）；魏武侯（左）抬头看",
     transition={"type": "whip", "dur": 0.28},
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_stand.png", 300, 480, "魏武侯抬头看着空中的三张卡"),
             MED.stand("wq", WQ, "chars/wq_speak_l.png", 780, 500, "吴起伸手一挥，严肃地讲：当年的三苗、夏桀、商纣王",
                       acts=[act(A(12, word="三苗", dt=-0.2), "bounce")])],
     fg=MED.front() + cards([200, 540, 860], 860, 290, pop=True),
     fx=[fx("big_title", A(12, dt=0.05), text="第二关：\n历史来打脸", pos=[540, 500], size=110, deco="none")],
     camera=cam(push(0.03)))

shot("s28", A(12, word="他们的"), "medium",
     "「他们的地盘比我们险要十倍！」：三张卡占满画面，「十倍！」红字「咚」地盖上来；魏武侯在左下角伸长脖子看，嘴张成大 O（笑点）",
     bg=river(blur=6) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_shock.png", 170, 520, "魏武侯站在船里，伸长脖子看着三张卡，眼睛瞪圆、嘴张成小 o",
               acts=[act(A(12, word="十倍"), "jump")])],
     fg=MED.front() + cards([190, 540, 880], 860, 320),
     fx=[st_text("十倍！", [540, 520], A(12, word="十倍", dt=-0.1), 150, color="red"),
         st("exclaim", [0, 0], A(12, word="十倍", dt=0.2), 80, follow="wuh", attach="head")],
     camera=cam(push(0.03), shake(A(12, word="十倍"), 0.3, 8)),
     notes={"jev_allow": ["subject"], "why": "吴起在说三苗、夏桀、商纣（「他们」），这一镜的主体是说到的那三张快闪卡，魏武侯在角落做反应"})

clouds = [L("props/cloud_rain_small.png", [x, 420], 1.0, [0.5, 0.5], w=150, alpha=0.0,
            anim=[{"at": A(13, word="不修", dt=0.25 * k), "dur": 0.1, "alpha": 1.0},
                  {"at": A(13, word="不修", dt=0.25 * k), "dur": 0.6, "ease": "out", "pos": [x + 30, 590]}])
          for k, x in enumerate((190, 540, 880))]
shot("s29", A(13), "medium",
     "「可他们不修德行、欺负老百姓」：三张卡的小旗上方，各飘来一朵小乌云（不画坏人、不画欺负人的场面）",
     bg=river(blur=6),
     fg=cards([190, 540, 880], 860, 320) + clouds,
     fx=[st_text("不修德行", [540, 1250], A(13, word="不修", dt=0.3), 80, color="brown")],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "吴起在说三苗、夏桀、商纣（「他们」），主体是三张快闪卡"})

shot("s30", A(13, word="结果呢"), "medium",
     "「结果呢？一个个都没守住自己的国家！」：三面小旗一面接一面「啪嗒」倒下（只画旗子倒下，不画人、不画打仗；纸卡「咚」一声，不用雷声）",
     bg=river(blur=6),
     fg=cards([190, 540, 880], 860, 320, fall=A(13, word="一个个", dt=-0.3)),
     fx=[st("question", [540, 520], A(13, word="结果呢"), 150)],
     sfx=[sfx("plate_drop", A(13, word="一个个", dt=0.0 + 0.2 * k)) for k in range(3)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "吴起在说三苗、夏桀、商纣没守住国家，主体是三张快闪卡上倒下的旗子（战争只用倒下的旗子表示，source.md 第六节）"})

shot("s31", A(13, word="都没守住"), "close",
     "魏武侯看着倒下的旗子，额头冒汗，悄悄咽了一下口水「咕咚」（笑点）",
     bg=river(blur=6),
     actors=[hi_wuh("chars/wuh_hi_sweat.png", 380, "魏武侯吓呆了，眼睛瞪圆、额头冒汗，悄悄咽口水",
                    acts=[act(A(13, word="国家"), "nod")])],
     fx=[st_text("咕咚", [800, 700], A(13, word="自己"), 90)],
     camera=cam(push(0.03)))

# ======================================================== 考你（第 14–15 句）
x, h = 540, 780
shot("s32", A(14), "close",
     "「考考屏幕前的小朋友」：书房里，司马光站在书桌后面，笑眯眯地伸出食指指着观众",
     transition={"type": "paper_wipe", "dur": 0.5},
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_point.png", x, h, "司马光笑眯眯，伸出食指指着观众出题", acts=[act(A(14, word="小朋友"), "bounce")])],
     fg=[desk()],
     sfx=[sfx("click", D(0.1))],
     camera=cam(push(0.03)))

x, h = 310, 820
shot("s33", A(14, word="就像玩游戏", dt=-0.25), "medium",
     "「就像玩游戏，如果是你」：司马光按一下遥控器，头顶冒出想象泡泡（游戏画面只在泡泡里）：金光闪闪的满级铠甲小勇士，旁边四个小伙伴手拉手",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举着遥控器按一下，笑呵呵地出题")],
     fg=[desk()],
     fx=[fx("remote_click", D(0.1), pos=remote_pos(x, h)),
         fx("bubble", D(0.0), img="props/bubble_knight_a.png", pos=[420, 880], w=820)],
     camera=cam(push(0.03)))

shot("s34", A(14, word="你觉得"), "medium",
     "「你觉得是身上的『满级防御甲』重要」：选项【满级防御甲】弹出来；泡泡推到小勇士：大铠甲太重，走一步晃三晃（笑点）",
     bg=study_bg(blur=6, full=True),
     fx=[fx("card_quest", D(0.05), text="满级防御甲", sub="选 A", pos=[540, 540]),
         fx("bubble", D(0.0), img="props/bubble_knight_a.png", pos=[120, 1300], w=820, crop=[0, 100, 1100, 848]),
         st_text("晃～", [780, 900], A(14, word="满级", dt=0.5), 80)],
     camera=cam(push(0.03), shake(A(14, word="重要"), 0.3, 6)),
     notes={"jev_allow": ["subject"], "why": "司马光对观众出题（弹幕选择），这一镜只放选项卡和泡泡里的小勇士，司马光在前后几镜出镜"})

papers = [L("props/paperman_wave.png", [x, 1310], 1.0, [0.5, 1], w=130, flip=(k % 2 == 1), enter={"type": "pop", "at": A(14, word="队友", dt=0.12 * k)})
          for k, x in enumerate((330, 470, 610, 750))]
shot("s35", A(14, word="还是"), "medium",
     "「还是『队友齐心不背叛』重要？」：上一镜的选项【满级防御甲】接着挂在上面不动，选项【队友齐心不背叛】也弹出来，两个按钮一上一下；下面四个纸片小伙伴手拉手站成一排",
     bg=study_bg(blur=6, full=True),
     fg=papers,
     fx=[fx("card_quest", A(14, word="你觉得", dt=0.05), text="满级防御甲", sub="选 A", pos=[540, 540], sfx=None),
         fx("card_quest", A(14, word="队友", dt=-0.2), text="队友齐心不背叛", sub="选 B", pos=[540, 900])],
     sfx=[sfx("pop", A(14, word="队友", dt=0.12 * k)) for k in range(4)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "司马光对观众出题（弹幕选择），这一镜只放两个选项卡和比喻的纸片小人，司马光在前后几镜出镜"})

x, h = 540, 1000
shot("s36", A(15), "close",
     "「把你的选择打在弹幕上！」：司马光冲镜头眨眨眼，弹幕小纸条「嗖嗖」越飘越多；他再按一下遥控器，剧情接着往下演（不等答案）",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举着遥控器，笑眯眯地冲镜头眨眨眼", acts=[act(A(15, word="弹幕"), "bounce")])],
     fg=[desk()],
     fx=[fx("danmaku", A(15, dt=0.1), texts=["队友齐心！", "满级防御甲", "队友！", "我选队友", "大家一起", "队友齐心！", "铠甲太重啦"],
            dur=1.4, density=1.0, area=[0, 380, 1080, 860]),
         fx("remote_click", A(15, dt=1.8), pos=remote_pos(x, h))],
     camera=cam(push(0.03)))

# ======================================================== 第三关：船上的人（第 16–21 句）
shot("s37", A(16), "medium",
     "第三关（大字）：回到大木船，吴起上前一步，伸手指指两岸远远的大山（不指人），摇摇头：「由此看来……」",
     transition={"type": "iris", "dur": 0.6, "pos": [700, 1150]},
     bg=river() + [MED.back()],
     actors=[MED.stand("wq", WQ, "chars/wq_point_l.png", 760, 500, "吴起上前一步，一手指向左边两岸远远的大山，眉头微皱",
                       acts=[act(A(16, word="决定"), "shake")])],
     fg=MED.front(),
     fx=[fx("rays", A(16, dt=0.05), pos=[540, 520]), fx("big_title", A(16, dt=0.05), text="第三关：船上的人，\n会变成对手吗？", pos=[540, 520], size=90, deco="none")],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["kid"], "why": "吴起总结「人心与德行比山河要紧」（通鉴「由此观之，在德不在险」，剧本原话）；这一镜是第三关开头，下一镜 s38 马上用天平（两座小山对一颗心，心那边沉下去）把这句讲成孩子看得懂的比喻"})

shot("s38", A(16, word="人心"), "medium",
     "知识：「决定胜负的永远是人心与德行，而不是险要的山河」：纸天平弹出来，一边两座小山、一边一颗红心——说到「人心」，心那边「咚」地沉下去；魏武侯在左下角跟着上下点头（笑点）",
     bg=river(blur=6) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_shock.png", 170, 520, "魏武侯站在船里，盯着天平，跟着一上一下地看",
               acts=[act(A(16, word="人心", dt=0.1), "nod"), act(A(16, word="山河"), "nod")])],
     fg=MED.front() + [L("props/scale_heart_a.png", [640, 1330], 1.0, [0.5, 1], w=600, enter={"type": "pop", "at": D(0.05)},
           anim=[{"at": A(16, word="人心", dt=0.1), "dur": 0.05, "alpha": 0.0}]),
         L("props/scale_heart_b.png", [640, 1330], 1.0, [0.5, 1], w=600, alpha=0.0,
           anim=[{"at": A(16, word="人心", dt=0.1), "dur": 0.05, "alpha": 1.0}])],
     sfx=[sfx("slam_1", A(16, word="人心", dt=0.1))],
     camera=cam(push(0.03), shake(A(16, word="人心", dt=0.1), 0.3, 8)),
     notes={"jev_allow": ["subject", "kid"], "why": "吴起讲「人心比山河重」（通鉴「由此观之，在德不在险」，剧本原话）：这一镜就是给孩子的比喻——天平一边两座小山、一边一颗红心，心那边沉下去；主体是天平，听的魏武侯在角落，说话的吴起在前一镜和后一镜出镜"})

shot("s39", A(17), "close",
     "知识：「今天主公要是不好好体恤百姓、做好德行」：吴起特写，语重心长（背景音乐收住）",
     bg=river(blur=6),
     actors=[hi_wq("chars/wq_hi_speak.png", 640, "吴起一手摊开，语重心长地劝",
                   acts=[act(A(17, word="德行"), "nod")])],
     camera=cam(push(0.03)))

rw, rw_fg = rowers(MED, 455, 380)
rw["acts"] = [act(A(17, word="所有人", dt=-0.1), swap="chars/rower_stop.png", h=380)]
for f in rw_fg:
    f["anim"] = [{"at": A(17, word="所有人", dt=-0.1), "dur": 0.05, "alpha": 0.0}]
shot("s40", A(17, word="我告诉你"), "medium",
     "「我告诉你——这艘船上的所有人」：镜头慢慢横摇过船上划桨的人；说到「所有人」，他们停下桨，你看看我、我看看他（困惑，不瞪人）；只剩河水声，不配心跳",
     bg=[L("sets/jin_land/sky.png", [-20, 0], 0.1, w=1120, blur=3)] + river(blur=3)[1:] + [MED.back()],      # 这一镜横摇：天空宽一点，左右不露边
     actors=[rw],
     fg=MED.front() + rw_fg,
     camera=cam(pan(dx=-50)),
     notes={"jev_allow": ["subject"], "why": "吴起说「这艘船上的所有人」，这一镜的主体就是他说到的船上划桨的人"})

rw, rw_fg = rowers(MED, 388, 300, img="chars/rower_stop.png", oars=False, note="五个划桨的人停下桨，一起看向魏武侯（困惑、为难，不瞪人）")
shot("s41", A(17, word="转眼"), "medium",
     "「转眼全都会变成你的敌人！」：停下桨的人一起看向右边的魏武侯（困惑、为难，不瞪人），头顶各冒一个问号；魏武侯转过头看着他们，愣住了（不画兵器）",
     bg=river(blur=3) + [MED.back()],
     actors=[rw, MED.stand("wuh", WUH, "chars/wuh_shock_l.png", 850, 500, "魏武侯转头看着停下桨的人，愣住，额头冒汗")],
     fg=MED.front(),
     fx=[st("question", head_xy(rw, k), A(17, word="敌人", dt=-0.3 + 0.1 * k), 70) for k in range(5)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "吴起说「这艘船上的所有人，转眼全都会变成你的敌人」：主体就是他说到的船上的人（划桨的人）和被说的魏武侯，说话的吴起在 s39 特写过；画成一船人停桨、困惑地看向魏武侯，不瞪人（红线第 10 条）"})

shot("s42", A(17, word="敌人", dt=0.35), "close",
     "（动作）魏武侯的笑一下子收住，脑门冒出汗珠；得意值刻度板「噗——」地瘪到底（笑点；不画吓得发抖）",
     bg=river(blur=6),
     actors=[hi_wuh("chars/wuh_hi_sweat.png", 380, "魏武侯愣住，额头冒汗，认真地看着吴起", acts=[act(D(0.2), "shake")])],
     fx=[fx("progress", D(0.0), pos=[800, 760], title="得意值", kind="fill", color="orange", size=0.7, pop_in=False, **{"from": 0.4, "to": 0.0}),
         st_text("噗——", [800, 1180], D(0.8), 80)],
     camera=cam(push(0.03)))

shot("s43", A(19), "medium",
     "「吴将军，说得好！」（原文「善」）：魏武侯（左）冲吴起拱手、认真点头；吴起（右）松开眉头，也拱手回礼（不画递水、不画从此改好）",
     bg=river(blur=3) + [MED.back()],
     actors=[MED.stand("wuh", WUH, "chars/wuh_bow.png", 330, 480, "魏武侯冲吴起恭敬地拱手，认真地说：说得好", hip=0.62,
                       acts=[act(A(19, word="说得好"), "nod")]),
             MED.stand("wq", WQ, "chars/wq_bow_l.png", 780, 500, "吴起松开眉头，拱手回礼", acts=[act(A(19, word="好"), "nod")])],
     fg=MED.front(),
     camera=cam(push(0.03)))

rw, rw_fg = rowers(MED, 388, 300, img="chars/rower_stop.png", note="划桨的人重新拿起桨，接着划")
rw["acts"] = [act(A(20, word="人心齐", dt=-0.1), swap="chars/rower_row.png", h=300)]
for f in rw_fg:
    f["alpha"] = 0.0
    f["anim"] = [{"at": A(20, word="人心齐", dt=-0.1), "dur": 0.05, "alpha": 1.0}]
shot("s44", A(20), "medium",
     "「山川再险峻，抵不过人心齐」：魏武侯（右）转过头看着停下桨的人，若有所思地点点头；说到「人心齐」，大家又拿起桨接着划",
     bg=river(blur=3) + [MED.back()],
     actors=[rw, MED.stand("wuh", WUH, "chars/wuh_ponder_l.png", 850, 480, "魏武侯看着划船的人，一手握拳抵着下巴，若有所思地点头",
                           acts=[act(A(20, word="险峻"), "nod")])],
     fg=MED.front() + rw_fg,
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "旁白说的道理（剧本原话），画面是魏武侯听完吴起的话，若有所思地看着划船的人（红线第 4 条：只画他若有所思）"})


def paper_bg(mid=None):
    """纸片小人的比喻场景；mid = 夹在远山和地面条之间的图层（地面条盖住它的平底边）。"""
    return [sky(4)] + ridges(470, 640, near=820, blur=4) + (mid or []) + ground(1140, blur=4)


MEN = [("props/paperman_wave.png", 520), ("props/paperman_thumb.png", 600), ("props/paperman_wave.png", 680),
       ("props/paperman_thumb.png", 760), ("props/paperman_wave.png", 840), ("props/paperman_thumb.png", 920)]


def people_wall(gather=None, glow=False):
    out = []
    for k, (img, x) in enumerate(MEN):
        sx = [580, 800, 680, 900, 620, 860][k]
        sy = [1180, 1200, 1300, 1290, 1390, 1380][k]
        d = L(img, [sx, sy], 1.0, [0.5, 1], w=110, flip=(k % 2 == 1))
        if gather:
            d["anim"] = [{"at": {**gather, "dt": round(gather.get("dt", 0) + 0.08 * k, 2)}, "dur": 0.35, "ease": "back", "pos": [x - 20, 1360]}]
        if glow:
            d["pos"] = [x - 20, 1360]
        out.append(d)
    return out


shot("s45", A(20, word="城墙"), "medium",
     "知识（比喻）：「城墙再厚重，抵不过得民心」：画面一分为二：左边一座剪纸青山（整座山，平底边藏在地面后面）前，孤零零站着一个纸片小人；右边一群纸片小人手拉手，「咚」地肩并肩站成一道人墙（夯土城墙的样子，不画砖）",
     bg=paper_bg(mid=[L("props/mini_mountains.png", [230, 1260], 0.9, [0.5, 1], w=700)]),
     fg=[L("props/paperman_shrug.png", [260, 1390], 1.0, [0.5, 1], w=110)] + people_wall(gather=A(20, word="得民心", dt=-0.3)),
     fx=[st_text("咚", [760, 1080], A(20, word="民心"), 90)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "旁白讲道理（剧本原话），画面是比喻：孤零零的一个人对一群手拉手的人，没有故事人物"})

shot("s46", A(21), "medium",
     "「只要心怀仁德与尊重，哪怕没有险要地形」：人站成的城墙亮起金光，一张张笑脸；小青蛙蹦过来，也挤进人墙里站好（笑点）",
     bg=paper_bg(),
     fg=people_wall(glow=True) + [L("props/frog_proud.png", [470, 1360], 1.0, [0.5, 1], w=80, enter={"type": "pop", "at": A(21, word="哪怕")})],
     fx=[fx("rays", D(0.05), pos=[740, 1200], layer="back"), fx("sparkle", D(0.3), area=[480, 1050, 980, 1380], count=14)],
     sfx=[sfx("frog_croak", A(21, word="哪怕", dt=0.2))],
     camera=cam(push(0.04)),
     notes={"jev_allow": ["subject"], "why": "旁白讲道理（剧本原话），画面是人墙的比喻，没有故事人物"})

drift = {"at": D(0.0), "dur": 2.8, "ease": "linear", "dpos": [50, 0]}
WIDE3 = Boat(500, 1450, 0.6, drift=drift)
shot("s47", A(21, word="人心也会", dt=-0.45), "wide",
     "「人心也会筑成最坚固的城墙！」：暖光里，大木船载着一船人接着往下走，划桨的人一起划；标题条下面「啪」地盖上红印章「在德不在险」（大问题揭晓）",
     bg=river() + [WIDE3.back()] + wide_people(WIDE3, drift=drift),
     fg=WIDE3.front(),
     fx=[fx("tone", D(0.05), tone="warm", ramp=0.8),
         fx("smash", D(0.1), text="在德不在险", pos=[540, 600], size=150, color="red", shake=8)],
     camera=cam(pull(0.03)),
     notes={"jev_allow": ["subject"], "why": "旁白讲道理（剧本原话），台词里没有故事人物；画面是一船人一起划桨的远景，加上大问题揭晓的红印章「在德不在险」"})

# ======================================================== 点题、比喻（第 22–25 句）
x, h = 540, 800
shot("s48", A(22), "medium",
     "「《资治通鉴》里这句名言」：书页一翻回到书房，司马光站在书桌后面（人在画面中部），低头翻开一本书",
     transition={"type": "page_turn", "dur": 0.7},
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_read.png", x, h, "司马光低头看书，一根手指点在书页上", acts=[act(A(22, word="名言"), "nod")])],
     fg=[desk()],
     sfx=[sfx("page_flip", D(0.2))],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["kid"], "why": "系列固定的点题：司马光说《资治通鉴》里的原话「在德不在险」（第 9 句吴起已经说过，s22 配过白话），下一镜 s50 起马上用白话和小勇士的比喻再讲一遍"})

shot("s49", A(22, word="两千多年"), "close",
     "知识（点题）：「传了两千多年：『在德不在险！』」：书页特写，「在德不在险」五个大字一个接一个亮起来，落定时书页一震",
     bg=[L("sets/study/book_page_hi.png", [-110, 0], 0.5, w=1300)],
     fx=[fx("big_title", A(22, word="在德不在险", dt=-0.1), text="在德不在险", pos=[540, 820], size=190, deco="none"),
         fx("sparkle", A(22, word="在德不在险", dt=0.4), area=[160, 640, 920, 1000], count=12)],
     camera=cam(push(0.03), shake(A(22, word="在德不在险", dt=0.5), 0.3, 6)),
     notes={"jev_allow": ["kid", "subject"], "why": "系列固定的点题：通鉴原话「在德不在险」（吴起说的，第 9 句已经出现过），下一镜 s50 马上用白话再说一遍；这一镜只放书页上的字"})

x, h = 318, 820
shot("s50", A(23, word="优越"), "medium",
     "「优越的条件和厉害的装备」：司马光头顶冒出想象泡泡：小勇士穿上金光闪闪的「999 级」大铠甲，摆了个神气的姿势",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举着遥控器，笑呵呵地讲", acts=[act(A(23, word="装备"), "nod")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_knight_a.png", pos=[420, 880], w=820, crop=[0, 100, 1100, 848]),
         st_text("999 级", [860, 520], A(23, word="装备"), 70, color="gold")],
     camera=cam(push(0.03)))

shot("s51", A(23, word="从来"), "medium",
     "「从来不是无敌的护身符！」：泡泡推近小勇士，铠甲上的「护身符」小纸条「呼」地被风撕跑了；草丛里亮起一对圆溜溜的眼睛（笑点）",
     bg=study_bg(blur=6, full=True),
     fx=[fx("bubble", D(0.0), img="props/bubble_knight_a.png", pos=[120, 1300], w=820, crop=[0, 100, 1100, 848], crop_to=[0, 150, 900, 762],
            crop_t=0.0, crop_dur=1.2),
         st_text("护身符", [520, 960], D(0.2), 70, color="red", dur=1.6, exit="tear"),
         st("question", [250, 1180], A(23, word="护身符", dt=0.3), 70)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "司马光讲比喻（第 23 句），这一镜只放泡泡里的小勇士（游戏画面只在泡泡里），司马光在前一镜出镜"})

shot("s52", A(24), "medium",
     "（动作 →「装备再厉害，对人不好」）泡泡里：小勇士鼻子朝天，冲小伙伴们一甩手（不推人）；小伙伴们耸耸肩，一个接一个转身走开",
     bg=study_bg(blur=6, full=True),
     fx=[fx("bubble", D(0.0), img="props/bubble_knight_bc.png", pos=[120, 1300], w=820, crop=[0, 150, 830, 715], crop_to=[270, 330, 830, 711],
            crop_t=1.6, crop_dur=1.6),
         st_text("哼", [760, 820], D(0.5), 90),
         st_text("哒哒哒", [760, 1000], A(25, word="对人不好"), 70)],
     sfx=[sfx("hmph", D(0.5))] + [sfx("step", A(25, word="对人不好", dt=0.25 * k)) for k in range(3)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "动作行和司马光讲比喻（第 24–25 句），这一镜只放泡泡里的画（游戏画面只在泡泡里），司马光在 s50 出镜"})

shot("s53", A(25, word="队友"), "medium",
     "「队友也会一个个走开」：小勇士一个人，一只软乎乎的果冻小怪「啵」地蹦出来，他脚下一滑一屁股坐在地上（笑点；小怪一点都不吓人）",
     bg=study_bg(blur=6, full=True),
     fx=[fx("bubble", D(0.0), img="props/bubble_knight_bc.png", pos=[120, 1300], w=820, crop=[850, 180, 1678, 743]),
         st_text("啪叽", [700, 1080], A(25, word="走开"), 90)],
     sfx=[sfx("pop", A(25, word="一个个"))],
     camera=cam(push(0.03), shake(A(25, word="走开"), 0.3, 6)),
     notes={"jev_allow": ["subject"], "why": "司马光讲比喻（第 25 句），这一镜只放泡泡里的画"})

shot("s54", A(25, word="真心待人"), "medium",
     "金句：「真心待人，身边的人才是你最强的后盾！」：泡泡里，小勇士挠头说对不起，小伙伴们跑回来在他身后排成一面大盾牌；金句大字停在上面",
     bg=study_bg(blur=6, full=True),
     fx=[fx("rays", D(0.05), pos=[540, 520], layer="back"),
         fx("big_title", D(0.05), text="真心待人，身边的人\n才是你最强的后盾", pos=[540, 520], size=84, deco="none"),
         fx("bubble", D(0.1), img="props/bubble_knight_d.png", pos=[120, 1300], w=820),
         st_text("对不起", [420, 820], A(25, word="身边", dt=-0.3), 60)],
     sfx=[sfx("shine", A(25, word="后盾"))],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "司马光说金句（第 25 句），这一镜是金句大字和比喻泡泡；司马光在下一镜出镜"})

# ======================================================== 行动呼吁（第 26–27 句）
x, h = 540, 570
SHELF_EGGS = [(95, 1168), (165, 1172)]     # 左边书架最下一格那堆卷轴的顶上（墙图 1024 宽铺 1080，卷轴顶约 y 1213、x 0–188）；depth 同墙，跟书架一起动
eggs = [L("props/egg.png", [560, 1280], 0.3, [0.5, 0.5], w=70, alpha=0.0,
          anim=[{"at": A(26, word="大格局", dt=0.15 * k), "dur": 0.05, "alpha": 1.0},
                {"at": A(26, word="大格局", dt=0.15 * k), "dur": 0.45, "ease": "out", "pos": [330 - 40 * k, 1040], "rot": 360},
                {"at": A(26, word="大格局", dt=0.45 + 0.15 * k), "dur": 0.45, "ease": "in", "pos": list(SHELF_EGGS[k]), "rot": 720}])
        for k in range(2)]
shot("s55", A(26), "medium",
     "「给孩子讲历史，学做大格局的人」：司马光捧着书冲镜头笑；两张小纸条「讲历史」「学做大格局的人」弹出来；书缝里「噗」地蹦出两个鸡蛋，翻着跟头落到左边书架的卷轴堆上（下集的伏笔，笑点；书桌桌面在字幕卡后面，不放那里）",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=study_bg(),
     actors=[sgm("chars/sgm_book.png", x, h, "司马光双手捧着书，笑着看观众", acts=[act(A(26, word="讲历史"), "bounce"), act(A(26, word="大格局", dt=0.3), "jump")])],
     fg=[desk()] + eggs,
     fx=[st_text("讲历史", [800, 560], A(26, word="讲历史"), 90), st_text("学做大格局的人", [600, 780], A(26, word="学做"), 70, color="red")],
     sfx=[sfx("pop", A(26, word="大格局")), sfx("whoosh", A(26, word="大格局", dt=0.2))],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["subject"], "why": "旁白对家长的行动呼吁（PITFALLS S25，剧本原话），台词里没有故事人物；由系列讲解人司马光在书房里出镜串场"})

x, h = 540, 1000
shot("s56", A(27), "medium",
     "「点赞并收藏这集视频」：司马光举起遥控器冲镜头比「收藏」；红心和金星弹出来，小青蛙跳上书架卷轴堆上的鸡蛋，抱着鸡蛋转了一圈（笑点）",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_remote.png", x, h, "司马光举起遥控器，冲镜头哈哈笑", acts=[act(A(27, word="收藏"), "bounce")])],
     fg=[desk(), L("props/egg.png", list(SHELF_EGGS[1]), 0.3, [0.5, 0.5], w=70),
         L("props/egg.png", list(SHELF_EGGS[0]), 0.3, [0.5, 0.5], w=70, anim=[{"at": A(27, word="收藏", dt=0.65), "dur": 0.6, "rot": 360}]),
         L("props/frog_jump.png", [250, 1000], 0.3, [0.5, 0.5], w=120, alpha=0.0,
           anim=[{"at": A(27, word="收藏", dt=0.15), "dur": 0.05, "alpha": 1.0}, {"at": A(27, word="收藏", dt=0.2), "dur": 0.45, "ease": "out", "pos": [100, 1105]}])],
     fx=[st("heart", [200, 640], A(27, word="点赞"), 170), st("star", [880, 640], A(27, word="收藏"), 160)],
     sfx=[sfx("whoosh", A(27, word="收藏", dt=0.2)), sfx("frog_croak", A(27, word="收藏", dt=0.7))],
     camera=cam(push(0.03)))

x, h = 540, 800
shot("s57", A(27, word="看懂"), "medium",
     "「带孩子看懂什么叫『真正的强大』！」：「真正的强大」大字盖下来，下面一行小字「不靠山多高，靠人心齐」；司马光指着观众笑",
     bg=study_bg(),
     actors=[sgm("chars/sgm_hi_point.png", x, h, "司马光伸出食指指着观众，笑眯眯")],
     fg=[desk()],
     fx=[fx("big_title", A(27, word="看懂", dt=-0.2), text="真正的强大", pos=[540, 500], size=150, deco="none"),
         st_text("不靠山多高，靠人心齐", [540, 700], A(27, word="真正", dt=-0.3), 56, color="red")],
     camera=cam(push(0.03)))

# ======================================================== 下集预告（第 28–29 句）
shot("s58", A(28), "wide",
     "「关注我们，下一集带你看」：画面压暗，卫国宫殿前站着背着手的卫侯（下一集的人），他头顶一个大问号纸牌「啪」地翻起来",
     transition={"type": "iris", "dur": 0.6},
     bg=palace_bg(),
     actors=[P("wh", WH, "chars/wh_stand_l.png", [600, 1520], 460, "卫侯（卫国国君，是侯：小冠）背着手站在宫殿前，挑剔地斜眼看着")],
     fg=[fore()],
     fx=[plate("卫侯", "卫国的国君", [150, 420], D(0.1), color=WH_COLOR), st("question", [540, 820], A(28, word="下一集"), 260)],
     grade="tense",
     camera=cam(push(0.04)),
     notes={"jev_allow": ["subject"], "why": "旁白的下集预告（剧本原话），台词里没有故事人物；下一镜起是苟变、卫侯、子思"})

shot("s59", A(29), "medium",
     "「有个人能带五百辆战车」：一个普通官员模样的卫国青年（不画成大英雄）站在一辆两轮马车旁，「五百辆」字条弹出来",
     bg=[sky()] + ridges(470, 640, near=820) + ground(1140) + [L("props/chariot.png", [360, 1450], 1.0, [0.5, 1], w=620, note="布景前层")],
     actors=[P("gb", GB, "chars/gb_stand_l.png", [800, 1460], 470, "苟变站在马车旁，局促而诚恳地笑")],
     fg=[fore()],
     fx=[plate("苟变", "卫国人", [150, 400], D(0.1), color=GB_COLOR), st_text("五百辆", [360, 1040], A(29, word="五百"), 100, color="red")],
     camera=cam(push(0.03)))

eggs2 = [L("props/egg.png", [100, 1335], 1.0, [0.5, 0.5], w=80, alpha=0.0,
           anim=[{"at": A(29, word="收税", dt=0.15 * k), "dur": 0.1, "alpha": 1.0},
                 {"at": A(29, word="收税", dt=0.15 * k), "dur": 1.2, "ease": "out", "pos": [600 - 60 * k, 1335], "rot": 720}])
         for k in range(2)]
shot("s60", A(29, word="可他"), "medium",
     "「可他以前收税时吃了老百姓两个鸡蛋」：画面变成旧纸黄（从前的事）；两个鸡蛋骨碌碌滚到他脚边，他不好意思地挠挠头（笑点；不画钱）",
     bg=[sky(4)] + ridges(470, 640, near=820, blur=4) + ground(1140, blur=4),
     actors=[P("gb", GB, "chars/gb_stand_l.png", [640, 1380], 600, "苟变站着，有点局促",
               acts=[act(A(29, word="鸡蛋", dt=0.2), swap="chars/gb_scratch_l.png", h=590)])],
     fg=eggs2,
     fx=[fx("tone", D(0.0), tone="memory", ramp=0.5)],
     camera=cam(push(0.03)))

shot("s61", A(29, word="卫国国君"), "medium",
     "「卫国国君就不肯用他」：卫国宫殿前，卫侯（左，是侯：小冠、没有王冠）背着手转开脸；苟变（右）在他身后挠头",
     bg=palace_bg(),
     actors=[P("wh", WH, "chars/wh_stand_l.png", [330, 1540], 480, "卫侯背着手，转开脸不肯用身后的苟变",
               acts=[act(A(29, word="不肯"), "shake")]),
             P("gb", GB, "chars/gb_scratch_l.png", [780, 1540], 460, "苟变在卫侯身后挠头，不好意思")],
     fg=[fore()],
     fx=[plate("卫侯", "卫国的国君", [150, 420], D(0.05), color=WH_COLOR), st_text("不用", [560, 960], A(29, word="不肯"), 90, color="red")],
     camera=cam(push(0.03)))

shot("s62", A(29, word="孔子"), "wide",
     "「孔子的孙子子思会怎么说？」：白胡子的子思（左，交领儒者装束）笑眯眯地快步走进来，对着卫侯；一个大问号「啪」地弹出来（下集揭晓）",
     bg=palace_bg(),
     actors=[P("zs", ZS, "chars/zs_stand.png", [300, 1500], 540, "子思（孔子的孙子）快步走进来，慈祥地笑着看卫侯",
               enter={"type": "slide_left", "dur": 0.5}),
             P("wh", WH, "chars/wh_stand_l.png", [640, 1500], 440, "卫侯转头看着走进来的子思"),
             P("gb", GB, "chars/gb_stand_l.png", [860, 1500], 420, "苟变站在后面，诚恳地看着")],
     fg=[fore()],
     fx=[plate("子思", "孔子的孙子", [150, 420], D(0.5), color=ZS_COLOR), st("question", [560, 760], A(29, word="怎么说"), 200)],
     camera=cam(push(0.03)))

sb = {
    "episode": "tj03", "no": 3, "name": "在德不在险",
    "title": ["吴起要给魏武侯", "上一堂什么课？"],
    "voice": "video/out/tj03_voice",
    "bgm": "video/assets/audio/bgm/tj03_cand12.mp3",   # ACE-Step 1.5 生成，70 Hz 高通、-20 LUFS；Chris 选别的就换文件名
    "speakers": {"魏武侯": "魏家", "吴起": WQ_COLOR},
    "note": "tj03 分镜表（剧本 A_在德.json，配音 video/out/tj03_voice，全长 174.22 秒）。素材见 video/stories/tj03/素材清单.md，镜头见 镜头大纲.md；"
            "交领人物不翻转；船上魏武侯在左朝右、吴起在船头朝左、划桨的人在船尾；司马光一律在书房书桌后、人在画面中部（不从底边探头、不用 page_edge）；"
            "弹幕选择用两张 card_quest + danmaku（不用 kaoni，不倒计时）；背景音乐见顶层 bgm（ACE-Step 候选 12，Chris 选定后换文件名）",
    "shots": SH,
}
OUT.write_text(json.dumps(sb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("shots", len(SH))
