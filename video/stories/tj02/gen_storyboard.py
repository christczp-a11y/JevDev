"""生成 tj02 分镜表 video/stories/tj02/storyboard.json（配音 video/out/tj02_voice，194.46 秒）。
依据：A_守约.json、镜头大纲.md、素材清单.md（新图的文件名照清单；builder 画完登记）。照 tj01 的 gen_storyboard_G.py 写。
站位：宫里魏文侯在左朝右、大臣在右朝左；山路车头朝右；草棚里魏文侯从左边来、虞人在右朝左；人才在左朝右、魏文侯在右朝左。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "storyboard.json"


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
    d = {"img": img, "depth": depth, "pos": list(pos)}
    if anchor is not None:
        d["anchor"] = list(anchor)
    d.update(kw)
    return d


def blurred(layers, blur):
    if blur:
        for x in layers:
            x["blur"] = blur
    return layers


def sky(rain=False, blur=0, **kw):
    d = L("sets/jin_land/sky_rain.png" if rain else "sets/jin_land/sky.png", [0, 0], 0.1, w=1080, **kw)
    if blur:
        d["blur"] = blur
    return d


def ridges(y_far=470, y_mid=640, near=None, blur=0):
    out = [L("sets/jin_land/ridge_far.png", [540, y_far], 0.2, [0.5, 0], w=1100),
           L("sets/jin_land/ridge_mid.png", [540, y_mid], 0.3, [0.5, 0], w=1100)]
    if near is not None:
        out.append(L("sets/jin_land/ridge_near.png", [540, near], 0.4, [0.5, 0], w=1100))
    return blurred(out, blur)


def strips(img, h0, y0, blur=0):
    """地面条一条比一条宽地往下铺满（照 tj01 ground()）；h0 = 原图高（1528 宽时）。"""
    out, y = [], float(y0)
    for k, w in enumerate((1300, 1500, 1700, 1900)):
        g = L(img, [540, round(y)], 0.9, [0.5, 0], w=w, repeat="x")
        if k % 2:
            g["flip"] = True
        out.append(g)
        y += h0 * w / 1528 * 0.8
    return blurred(out, blur)


def ground(y0=1290, blur=0):
    return strips("sets/jin_land/ground.png", 218, y0, blur)


def mud(y0=1330, blur=0):
    return strips("sets/mountain/mud_road.png", 327, y0, blur)


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
    """大河的三层山（宽 1250，倍数 1.23）。量过的轮廓（原图 1016 宽）：最深的山谷 远 241/462、中 166/337、近 162/350；
    顶到图边的平顶山尖 远 309–322 列、中 71–95 列、近 90–115 列。
    远山 y 300–868：平顶山尖在 x≈295–311、y 300，藏在标题条（y 90–330）后面；
    中山 y 640–1055：最深山谷 844，盖住远山底边 868；平顶山尖在画面左边外面（x < 0）；
    近山 y 830–1261：最深山谷 1029，盖住中山底边 1055；底边 1261 藏在水面（1180 起，1230 以下不透明）后面。"""
    out = [L("sets/jin_land/ridge_far.png", [540, 300], 0.2, [0.5, 0], w=1250),
           L("sets/jin_land/ridge_mid.png", [490, 640], 0.3, [0.5, 0], w=1250),
           L("sets/jin_land/ridge_near.png", [470, 830], 0.4, [0.5, 0], w=1250)]
    return blurred(out, blur)


def fore(y=1930):
    return L("sets/jin_land/fore.png", [540, y], 1.0, [0.5, 1], w=1850, repeat="x")


def study_bg(blur=0):
    d = L("sets/study/wall.png", [0, 0], 0.3, w=1080)
    if blur:
        d["blur"] = blur
    return [d]


def desk():
    return L("sets/study/desk.png", [540, 1930], 1.0, [0.5, 1], w=1150)


def bq_bg(rain=True, blur=0, brazier=None):
    """宴会：夯土高台上的亭子（四面敞开，看得见外面的天和雨）。brazier = (x, y, w) 炭火盆。"""
    out = [sky(rain)] + ridges(470, 640) + [
        L("sets/lantai/terrace.png", [540, 1330], 0.6, [0.5, 1], w=1300),
        L("sets/lantai/hu.png", [150, 1300], 0.7, [0.5, 1], w=160),
        L("sets/lantai/ding.png", [930, 1300], 0.7, [0.5, 1], w=160)] + ground(1290)
    if brazier:
        x, y, w = brazier
        out.append(L("props/brazier.png", [x, y], 0.95, [0.5, 1], w=w))
    return blurred(out, blur)


def bq_fg(w=2100, y=1460):
    return [L("sets/lantai/banquet_row.png", [540, y], 1.0, [0.5, 0.5], w=w), fore()]


def road_bg(blur=0):
    return [sky(True, blur)] + ridges(520, 700, near=860, blur=blur) + mud(1330, blur)


def palace_bg(rain=False, blur=0):
    return blurred([sky(rain)] + ridges(470, 640, near=820) + [L("sets/palace/hall.png", [540, 1330], 0.6, [0.5, 1], w=1300)] + ground(1250), blur)


def hut_bg(hx=560, hy=1450, hw=1300, blur=0, mud_y=None, sunny=None):
    """深山茅草棚：阴雨天 + 远山 + 泥路 + 草棚。sunny = 天放晴的锚点（雨天的天空淡出，露出晴天）。"""
    if sunny is not None:
        skies = [sky(False), sky(True, anim=[{"at": sunny, "dur": 0.9, "alpha": 0.0}])]
    else:
        skies = [sky(True)]
    # 草棚图 1465×956：左边是棚（左前柱挂弓和箭袋、中间一截树墩），右边是古树；棚下净高约图高的 40%，站着的人放在棚前面
    out = skies + ridges(560, 720, near=880) + mud(hy - 90 if mud_y is None else mud_y) + [L("sets/mountain/hut.png", [hx, hy], 0.9, [0.5, 1], w=hw)]
    return blurred(out, blur)


def map_bg():
    return [L("sets/study/wall.png", [-100, 0], 0.3, w=1280, blur=6), L("props/map_paper.png", [540, 930], 1.0, [0.5, 0.5], w=980)]


def chariot(cx, base_y, w, enter=None, actor_note="魏文侯戴斗笠披蓑衣，站在车上双手握着缰绳往前冲"):
    """战车两层 + 马 + 驾车的魏文侯（照 tj01：车 [600,1500] w1100 时人在 [380,1330] h480、马在 [900,1500] w360）。返回 (bg 里的后层, actor, fg 里的前层和马)。"""
    k = w / 1100
    e = {"enter": dict(enter)} if enter else {}
    back = L("props/chariot_back.png", [cx, base_y], 1.0, [0.5, 1], w=w, note="布景前层", **e)
    front = L("props/chariot_front.png", [cx, base_y], 1.0, [0.5, 1], w=w, note="布景前层", **e)
    horse = L("props/horse.png", [round(cx + 300 * k), base_y], 1.0, [0.5, 1], w=round(360 * k), note="布景前层", **e)
    actor = P("wwh", WWH, "chars/wwh_reins.png", [round(cx - 220 * k), round(base_y - 170 * k)], round(480 * k), actor_note, **e)
    return back, actor, [front, horse]


# ---------------------------------------------------------------- 人物、特效
def P(id_, who, img, pos, h, note, **kw):
    d = {"id": id_, "who": who, "img": img, "pos": list(pos), "h": h}
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


def plate(name, role, pos, at, size=0.7, house=None, color=None, **kw):
    d = fx("name_plate", at, name=name, role=role, pos=list(pos), size=size, **kw)
    if house:
        d["house"] = house
    if color:
        d["color"] = color
    return d


def rain(at=None, dim=0.14, **kw):
    return fx("rain", at if at is not None else D(0.0), dim=dim, **kw)


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


def frame(zoom=1.0, dx=0, dy=0):
    return {"move": "frame", "zoom": zoom, "dx": dx, "dy": dy}


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


WWH, SGM, DC, YR = "魏文侯", "司马光", "大臣", "虞人"
DC_COLOR = "#a8656c"          # 大臣的说话人颜色（藕粉加深，不用四家色）
YR_COLOR = "#7a5a3a"          # 虞人（土褐）
HI_RAIN = "chars/wwh_hi_rain_firm.png"
FLAG_H = 300
FLAGS = [("props/flag_zhao.png", [560, 780]), ("props/flag_han.png", [790, 1060]), ("props/flag_wei.png", [380, 1300])]
PLAIN = [("props/flag_plain_a.png", [180, 1330], False), ("props/flag_plain_b.png", [560, 1370], True),
         ("props/flag_plain_c.png", [230, 1080], False), ("props/flag_plain_a.png", [520, 1140], True)]


def map_flags(wei_anim=None, plain=False, plain_at=None):
    out = []
    for img, pos in FLAGS:
        d = L(img, pos, 1.0, [0.5, 1], h=FLAG_H, sway={"x": 0, "y": 3, "period": 2.8, "phase": pos[0] / 300})
        if img.endswith("wei.png") and wei_anim:
            d["anim"] = wei_anim
        out.append(d)
    if plain:
        for k, (img, pos, fl) in enumerate(PLAIN):
            d = L(img, pos, 1.0, [0.5, 1], h=240, flip=fl)
            if plain_at is not None:
                d["enter"] = {"type": "pop", "at": {**plain_at, "dt": round(plain_at.get("dt", 0) + 0.18 * k, 2)}}
            out.append(d)
    return out


# ======================================================== 开场：反差钩子
back, wwh_car, front = chariot(600, 1500, 1100)
wwh_car["acts"] = [act(D(0.3), "bounce"), act(D(1.0), "bounce"), act(D(1.6), "bounce")]
shot("s01", A(0, dt=-0.3), "wide",
     "开场反差钩子：瓢泼大雨里，泥泞山路上，魏文侯（魏家橙黄衣服，戴斗笠披蓑衣）自己握着缰绳驾着两轮马车往右冲，车轮碾过泥坑，泥水四溅（只画雨，不画雷电）",
     bg=road_bg() + [back], actors=[wwh_car], fg=front + [fore()],
     fx=[rain(D(0.0)), plate("魏文侯", "魏国的国君", [820, 380], D(0.15), size=0.7, house="魏家"),
         fx("splash", D(0.5), pos=[150, 1540], size=1.0), fx("splash", D(1.3), pos=[660, 1560], size=0.8),
         fx("lines_speed", D(0.0), dir="left", y0=400, y1=800)],
     sfx=[sfx("whoosh", D(0.0)), sfx("step", D(0.25)), sfx("step", D(0.55)), sfx("step", D(0.85))],
     camera=cam(pan(dx=60), shake(D(0.5), 0.3, 10)))

shot("s02", A(0, dt=1.8), "close",
     "特写：魏文侯戴着斗笠在雨里往前冲，一团泥点「啪」地糊在他鼻尖上，他眨眨眼、憋着嘴顾不上擦（笑点）；司马光一开口，画面「咔」地定格，司马光从右下角的书页后面探出来，举着遥控器（魏文侯在左边，脸朝画面里）",
     bg=road_bg(blur=6),
     actors=[P("wwh", WWH, HI_RAIN, [380, 1940], 1180, "魏文侯戴斗笠披蓑衣，目光直直望着前方，泥点糊在鼻尖上，眨眨眼顾不上擦",
               acts=[act(D(0.25), swap="chars/wwh_hi_rain_mud.png")])],
     fx=[rain(D(0.0)), st("pa", [760, 640], D(0.25), 120), fx("dust", D(0.25), mode="puff", pos=[470, 1060], size=110),
         fx("freeze", A(1, dt=0.0), dur=1.8),
         fx("page_edge", A(1, dt=0.05), y=1300, w=1900, peek="chars/sgm_hi_remote.png", peek_h=640, peek_x=870),
         fx("remote_click", A(1, dt=0.5), pos=[990, 1080])],
     camera=cam(push(0.03), punch(D(0.25), 0.08)))

shot("s03", A(1, word="在暴风雨"), "medium",
     "解说台：司马光在书房里举着遥控器笑呵呵，头顶冒出想象泡泡（现代的东西只在泡泡里）：右边，穿橙色反光背心的环卫工老爷爷在雨里扫地，扭头望着路口像在等人；左边，暖和的屋里，一个小朋友裹着毯子捧着热水杯；两人中间一颗「约」字",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [290, 1740], 720, "司马光在书房的解说台后面，举着遥控器笑呵呵地问观众",
               enter={"type": "pop", "at": D(0.02)}, acts=[act(A(1, word="环卫工"), "nod"), act(A(1, word="屋里"), "bounce")])],
     fg=[desk()],
     fx=[fx("remote_click", D(0.3), pos=[513, 1351]),
         fx("bubble", D(0.4), img="props/bubble_sweeper.png", pos=[270, 1000], w=820),
         st_text("约", [600, 820], A(1, word="环卫工", dt=0.3), 90, color="red")],
     camera=cam(push(0.03)))

shot("s04", A(1, word="你会"), "close",
     "司马光转向镜头，笑眯眯地指着观众，眉毛一挑：「你会为了不让他白等，冒大雨跑一趟吗？」",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_point.png", [540, 1650], 780, "司马光笑眯眯，伸出食指指着观众，眉毛一挑",
               acts=[act(A(1, word="白等"), "bounce")])],
     fg=[desk()],
     fx=[st("question", [840, 600], A(1, word="跑一趟", dt=0.1), 150)],
     camera=cam(push(0.03), punch(A(1, word="跑一趟"), 0.08)))

# ======================================================== 时代背景：地图
shot("s05", A(2), "wide",
     "承接上一集：司马光的书桌上展开一张纸地图，赵（北）、韩、魏（南）三面家族旗「啪啪啪」插上，把晋国分成三块",
     transition={"type": "page_turn", "dur": 0.6},
     bg=map_bg(),
     fg=[dict(f, enter={"type": "pop", "at": A(2, word="三家", dt=0.25 * k)}) for k, f in enumerate(map_flags())],
     fx=[st_text("上一集", [250, 470], D(0.3), 80)],
     sfx=[sfx("paper_unfold", D(0.0))] + [sfx("pop", A(2, word="三家", dt=0.25 * k + 0.05)) for k in range(3)],
     camera=cam(push(0.03)))

wobble = [{"at": A(2, word="邻居", dt=0.2 + 0.22 * k), "dur": 0.15, "rot": (-8 if k % 2 == 0 else 8)} for k in range(5)] + \
         [{"at": A(2, word="邻居", dt=1.3), "dur": 0.2, "rot": 0}]
shot("s06", A(2, word="魏家"), "medium",
     "镜头推近南边魏家的橙黄旗子：身边一面接一面冒出没写字的别家小旗，把魏家小旗挤得左摇右晃，冒出一颗汗珠（笑点）",
     bg=map_bg(),
     fg=map_flags(wei_anim=wobble, plain=True, plain_at=A(2, word="身边")),
     fx=[st("sweat", [470, 960], A(2, word="不少"), 80)],
     sfx=[sfx("pop", A(2, word="身边", dt=0.18 * k + 0.05)) for k in range(4)],
     camera=cam(frame(1.12, -60, 130), push(0.03)))

grow = [{"at": A(3, word="最先", dt=0.0), "dur": 0.2, "ease": "back", "scale": 1.25},
        {"at": A(3, word="强了", dt=0.0), "dur": 0.2, "ease": "back", "scale": 1.5},
        {"at": A(3, word="起来", dt=0.0), "dur": 0.2, "ease": "back", "scale": 1.75}]
shot("s07", A(3), "medium",
     "地图上，魏家的旗子「噌噌噌」往上长，长得比四周所有旗子都高；旗杆顶上冒出一个红色问号：怎么做到的？",
     bg=map_bg(),
     fg=map_flags(wei_anim=grow, plain=True),
     fx=[st_text("噌噌噌", [760, 620], A(3, word="最先"), 90, color="orange"),
         st("question", [380, 690], A(3, word="起来", dt=0.25), 120)],
     sfx=[sfx("pop", A(3, word="最先")), sfx("pop", A(3, word="强了")), sfx("light_up", A(3, word="起来"))],
     camera=cam(pan(dy=-50)))

big_wei = [{"at": D(0.0), "dur": 0.01, "scale": 1.75}]
shot("s08", A(4), "wide",
     "「他的绝招只有两个字：信用！」：「信用」两个红色大字「咚」地砸在地图正中，旗顶的问号被震得撕成两半；「点个赞」：小心心弹出来，一只头顶荷叶的小青蛙蹦上去按了一下（笑点）",
     bg=map_bg(),
     fg=map_flags(wei_anim=big_wei, plain=True) +
        [L("props/frog_leaf.png", [840, 1340], 1.0, [0.5, 1], w=170,
           anim=[{"at": A(5, word="点个赞", dt=0.35), "dur": 0.4, "ease": "out", "dpos": [0, -560]},
                 {"at": A(5, word="点个赞", dt=0.75), "dur": 0.3, "ease": "in", "dpos": [0, 40]}])],
     fx=[st("question", [380, 690], D(0.0), 120, sfx=None, dur=2.75, exit="tear"),
         fx("smash", A(4, word="信用", dt=-0.14), text="信用", pos=[640, 900], size=260, color="red"),
         st("heart", [840, 620], A(5, word="点个赞"), 170)],
     sfx=[sfx("whoosh", A(5, word="点个赞", dt=0.35)), sfx("frog_croak", A(5, word="点个赞", dt=0.8))],
     camera=cam(push(0.04)))

shot("s09", A(5, word="如何"), "close",
     "大问题：回到雨里的魏文侯，他冲镜头点点头——看他怎么靠一场大雨让魏国强起来（标题条就是这个大问题）",
     transition={"type": "iris", "dur": 0.6, "pos": [600, 1000]},
     bg=road_bg(blur=6),
     actors=[P("wwh", WWH, HI_RAIN, [600, 1940], 1160, "魏文侯戴斗笠披蓑衣，冲镜头坚定地点点头",
               acts=[act(A(5, word="一场大雨"), "nod")])],
     fx=[rain(D(0.0)), plate("魏文侯", "魏国的国君", [170, 400], D(0.05), size=0.7, house="魏家")],
     camera=cam(push(0.04)))

# ======================================================== 第 1 关：宴会
shot("s10", A(6), "wide",
     "第一关（大字）：晴天，夯土高台上四面敞开的亭子里开宴会：炭火盆烧得红通通，魏文侯（左）坐在主位，三位大臣（右）举着漆耳杯笑呵呵（不画醉倒）",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=bq_bg(rain=False, brazier=(390, 1300, 200)),
     actors=[P("wwh", WWH, "chars/wwh_kneel.png", [270, 1470], 500, "魏文侯跪坐在主位，端着漆耳杯笑逐颜开"),
             P("dca", DC, "chars/wdc_a_cup.png", [530, 1470], 410, "大臣甲（藕粉色）跪坐着举杯，笑眯眯"),
             P("dcb", DC, "chars/wdc_b_cup.png", [685, 1470], 400, "大臣乙（黛紫色，灰白山羊胡）跪坐着举杯，笑眯眯"),
             P("dcc", DC, "chars/wdc_c_cup.png", [835, 1470], 395, "大臣丙（炭灰黑，年轻圆脸）跪坐着举杯，笑眯眯")],
     fg=bq_fg(),
     fx=[fx("rays", A(6, dt=0.05), pos=[540, 540]), fx("big_title", A(6, dt=0.05), text="第一关：\n又暖又舒服的宴会", pos=[540, 540], size=120, deco="none"),
         plate("大臣", "魏国的大臣", [870, 700], D(0.1), size=0.55, color=DC_COLOR)],
     camera=cam(pan(dx=50)))

shot("s11", A(6, word="喝得"), "medium",
     "「喝得正高兴」：魏文侯（左）端着漆耳杯哈哈笑，大臣甲、乙（右）举杯回敬，「叮」地碰了一下（杯里是饮料，不画醉倒）",
     bg=bq_bg(rain=False, blur=4, brazier=(430, 1390, 230)),
     actors=[P("wwh", WWH, "chars/wwh_kneel.png", [260, 1480], 500, "魏文侯跪坐着端起漆耳杯，开心地笑",
               acts=[act(A(6, word="高兴"), "bounce")]),
             P("dca", DC, "chars/wdc_a_cup.png", [640, 1480], 520, "大臣甲举着漆耳杯笑眯眯", acts=[act(A(6, word="正"), "bounce")]),
             P("dcb", DC, "chars/wdc_b_cup.png", [815, 1480], 500, "大臣乙举着漆耳杯笑眯眯")],
     fg=bq_fg(2300, 1560),
     fx=[st_text("叮", [470, 900], A(6, word="高兴"), 100, color="gold")],
     camera=cam(push(0.04)))

shot("s12", A(6, word="突然"), "wide",
     "「外面突然下起瓢泼大雨！」：天一下子暗了，亭子外哗哗下起大雨（只画雨，不画雷电）；亭子里的人都愣了一下",
     bg=[sky(False), sky(True, alpha=0.0, anim=[{"at": A(6, word="下起"), "dur": 0.6, "alpha": 1.0}])] + ridges(470, 640) + [
         L("sets/lantai/terrace.png", [540, 1330], 0.6, [0.5, 1], w=1300),
         L("sets/lantai/hu.png", [150, 1300], 0.7, [0.5, 1], w=160),
         L("sets/lantai/ding.png", [930, 1300], 0.7, [0.5, 1], w=160)] + ground(1290) +
        [L("props/brazier.png", [390, 1300], 0.95, [0.5, 1], w=200)],
     actors=[P("wwh", WWH, "chars/wwh_kneel.png", [270, 1470], 500, "魏文侯跪坐在主位，抬头看外面的雨"),
             P("dca", DC, "chars/wdc_a_cup.png", [530, 1470], 410, "大臣甲举着杯子愣住", acts=[act(A(6, word="瓢泼"), "jump")]),
             P("dcb", DC, "chars/wdc_b_cup.png", [685, 1470], 400, "大臣乙举着杯子愣住"),
             P("dcc", DC, "chars/wdc_c_cup.png", [835, 1470], 395, "大臣丙举着杯子愣住", acts=[act(A(6, word="瓢泼", dt=0.1), "jump")])],
     fg=bq_fg(),
     fx=[fx("tone", A(6, word="下起"), tone="cool", ramp=0.6), rain(A(6, word="瓢泼", dt=-0.2))],
     camera=cam(pull(0.04)))

shot("s13", A(7), "medium",
     "魏文侯忽然「咚」地放下漆耳杯站起来；侍从的两只手「唰」地从右边伸进来，捧着一件蓑衣和一顶竹编斗笠（原文「命驾将适野」）",
     bg=bq_bg(blur=4, brazier=(560, 1400, 220)),
     actors=[P("wwh", WWH, "chars/wwh_kneel.png", [300, 1500], 495, "魏文侯放下杯子，一下子站起来，严肃坚定",
               acts=[act(D(0.3), swap="chars/wwh_rise.png", h=495)])],
     fg=[L("props/hands_suoyi.png", [860, 1180], 1.0, [0.5, 0.5], w=560, enter={"type": "slide_right", "at": D(0.85), "dur": 0.4})] + bq_fg(2300, 1560),
     fx=[rain(), st_text("咚", [560, 1060], D(0.28), 100), st("sou", [880, 860], D(0.85), 110)],
     sfx=[sfx("whoosh", D(0.85))],
     camera=cam(push(0.04), shake(D(0.3), 0.25, 8)))

shot("s14", A(8), "medium",
     "全场一静：三位大臣举着漆耳杯的手停在半空，嘴张成大大的 O、眼珠瞪得溜圆（下巴好好的），「！」一个接一个弹出来；一只杯子还在滴答滴（笑点）",
     bg=bq_bg(blur=4),
     actors=[P("dca", DC, "chars/wdc_a_shock.png", [300, 1480], 480, "大臣甲嘴张成大 O、眼珠瞪圆，杯子停在半空"),
             P("dcb", DC, "chars/wdc_b_shock.png", [560, 1480], 480, "大臣乙嘴张成大 O、眼珠瞪圆"),
             P("dcc", DC, "chars/wdc_c_shock.png", [800, 1480], 470, "大臣丙嘴张成大 O、眼珠瞪圆")],
     fg=bq_fg(2300, 1560),
     fx=[rain(), st("exclaim", [0, 0], D(0.05), 90, follow="dca", attach="head"),
         st("exclaim", [0, 0], D(0.25), 90, follow="dcb", attach="head"),
         st("exclaim", [0, 0], D(0.45), 90, follow="dcc", attach="head"),
         st_text("滴答", [160, 880], D(0.7), 70, color="blue")],
     sfx=[sfx("slam_1", D(0.0))],
     camera=cam(push(0.05)))

shot("s15", A(9), "medium",
     "大臣甲站起来，满脸问号着急地摆手：「主公，外面暴雨如注……」",
     bg=bq_bg(blur=6),
     actors=[P("dca", DC, "chars/wdc_a_urge.png", [560, 1560], 575, "大臣甲站着前倾着急地摆手，满脸问号",
               acts=[act(A(9, word="暴雨"), "bounce")])],
     fg=[fore()],
     fx=[rain(), st("question3", [0, 0], D(0.3), 130, follow="dca", attach="head")],
     camera=cam(push(0.04)))

shot("s16", A(9, word="鞋子"), "medium",
     "大臣甲头上冒出想象泡泡：一只布鞋「噗叽」陷进泥里，拔出来只剩光脚丫（笑点）",
     bg=bq_bg(blur=6),
     actors=[P("dca", DC, "chars/wdc_a_urge.png", [715, 1600], 575, "大臣甲一边摆手一边比划：鞋子都陷进泥里了",
               acts=[act(A(9, word="陷进"), "shake")])],
     fg=[fore()],
     fx=[rain(), fx("bubble", D(0.05), img="props/bubble_shoe_mud.png", pos=[690, 980], w=820, flip=True),
         st_text("噗叽", [240, 1060], A(9, word="陷进", dt=0.2), 90, color="brown")],
     camera=cam(push(0.03)))

shot("s17", A(9, word="多舒服"), "wide",
     "大臣甲指指亭子外面的大雨，又指指暖和的炭火盆：「在屋里喝酒多舒服，您去打什么猎啊？」魏文侯（左）站着不说话",
     bg=bq_bg(),
     actors=[P("wwh", WWH, "chars/wwh_stand.png", [220, 1500], 525, "魏文侯站着，看着大臣甲，不说话"),
             P("dca", DC, "chars/wdc_a_urge.png", [760, 1500], 560, "大臣甲前倾摆手，指指外面的雨又指指炭火盆",
               acts=[act(A(9, word="舒服"), "bounce"), act(A(9, word="打什么猎"), "wobble")])],
     fg=[L("props/brazier.png", [480, 1450], 1.0, [0.5, 1], w=230), fore()],
     fx=[rain(), fx("sparkle", A(9, word="舒服"), area=[380, 1240, 580, 1390], count=8),
         st("question", [0, 0], A(9, word="打什么猎"), 110, follow="dca", attach="head")],
     camera=cam(push(0.04)))

shot("s18", A(10), "medium",
     "司马光揭秘：一个大放大镜「叮」地移到魏文侯腰边，镜片里是他腰间那片小竹片，放得老大：上面画着一张弓、一个太阳（不写字）",
     bg=bq_bg(blur=6),
     actors=[P("wwh", WWH, "chars/wwh_stand.png", [270, 1520], 525, "魏文侯站着，腰间系着一片小竹片")],
     fg=[L("props/wwh_slip.png", [707, 975], 1.0, [0.5, 0.5], h=290, enter={"type": "slide_right", "at": D(0.15), "dur": 0.45}),
         L("props/magnifier.png", [720, 1140], 1.0, [0.5, 0.5], w=560, enter={"type": "slide_right", "at": D(0.15), "dur": 0.45}),
         fore()],
     fx=[rain(), fx("sparkle", A(10, word="深山"), area=[560, 800, 860, 1150], count=10)],
     sfx=[sfx("whoosh", D(0.15)), sfx("light_up", D(0.6))],
     camera=cam(push(0.04)))

shot("s19", A(10, word="约好"), "medium",
     "司马光举着大放大镜对着观众，镜片里一只眼睛变得老大，眨了眨（笑点）：「今天一起去山里打猎！」旁边弹出弓箭小图标",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_magnify.png", [480, 1760], 900, "司马光举着放大镜对着观众，镜片里一只眼睛放得老大，眨了眨",
               acts=[act(A(10, word="今天"), "wobble"), act(A(10, word="打猎"), "bounce")])],
     fg=[desk(), L("props/icon_bow.png", [850, 680], 1.0, [0.5, 0.5], w=230, enter={"type": "pop", "at": A(10, word="打猎")})],
     sfx=[sfx("pop", A(10, word="打猎"))],
     camera=cam(push(0.04)))

# ======================================================== 第 2 关：劝
shot("s20", A(11), "wide",
     "第二关（大字）：大臣们急忙围上来七嘴八舌地劝（右），魏文侯（左）站着听",
     bg=bq_bg() + [L("chars/wdc_c_urge.png", [960, 1500], 1.0, [0.5, 1], h=520, enter={"type": "slide_right", "at": D(0.3), "dur": 0.4}, note="大臣丙在后面着急地摆手劝"),
                   L("chars/wdc_b_urge.png", [820, 1500], 1.0, [0.5, 1], h=530, enter={"type": "slide_right", "at": D(0.15), "dur": 0.4}, note="大臣乙在后面着急地摆手劝")],
     actors=[P("wwh", WWH, "chars/wwh_stand.png", [200, 1500], 525, "魏文侯站着听大臣们劝"),
             P("dca", DC, "chars/wdc_a_urge.png", [680, 1500], 545, "大臣甲着急地摆手劝：主公！跟您约好的是管山林的老伯伯", enter={"type": "slide_right", "dur": 0.4})],
     fg=bq_fg(2300, 1580),
     fx=[rain(), fx("rays", A(11, dt=0.05), pos=[540, 560]), fx("big_title", A(11, dt=0.05), text="第二关：约好的事，\n鸽还是不鸽？", pos=[540, 560], size=110, deco="none"),
         st_text("叽叽喳喳", [760, 860], D(0.9), 70)],
     camera=cam(push(0.03)))

shot("s21", A(11, word="老伯伯"), "medium",
     "知识：「跟您约好的是管山林的老伯伯」：深山雨林里，虞人（慈祥的老伯伯，旧斗笠旧蓑衣）站着笑眯眯；旁边弹出他的属性卡（名字条写「虞人」）：工作 护林巡山（弓箭图标：管山林、也管打猎）",
     bg=[L("props/teaser_rain.png", [-100, 0], 0.3, w=1280, blur=4)],
     actors=[P("yr", YR, "chars/yr_stand.png", [270, 1560], 640, "虞人：慈祥的老伯伯，戴旧斗笠披旧蓑衣，两手拢在身前眯眼笑")],
     fx=[plate("虞人", "管山林的人", [150, 400], D(0.1), size=0.6, color=YR_COLOR),
         fx("stat_card", D(0.05), name="虞人", rows=[{"label": "工作", "value": "护林巡山", "icon": "props/icon_bow.png"}],
            pos=[700, 840], w=520, gap=0.5)],
     camera=cam(push(0.03)))

shot("s22", A(11, word="肯定"), "medium",
     "「他也肯定能理解，何必冒雨受这份罪呢？」：大臣乙摊手笑着劝，大臣甲在旁边点头；魏文侯低头看看腰间的小竹片，竹片「叮」地一闪",
     bg=bq_bg(blur=4) + [L("chars/wdc_a_urge.png", [800, 1520], 1.0, [0.5, 1], h=520, note="大臣甲在后面跟着劝",
                           anim=[{"at": A(11, word="受这份罪"), "dur": 0.2, "rot": -5}, {"at": A(11, word="受这份罪", dt=0.2), "dur": 0.2, "rot": 0}])],
     actors=[P("wwh", WWH, "chars/wwh_stand.png", [230, 1520], 525, "魏文侯低头看了看腰间的小竹片",
               acts=[act(A(11, word="何必"), "nod")]),
             P("dcb", DC, "chars/wdc_b_urge.png", [620, 1520], 560, "大臣乙摊着手笑眯眯地劝：他也肯定能理解", acts=[act(A(11, word="理解"), "bounce")])],
     fg=[fore()],
     fx=[rain(), fx("sparkle", A(11, word="何必"), area=[180, 1240, 320, 1360], count=6)],
     sfx=[sfx("light_up", A(11, word="何必"))],
     camera=cam(push(0.04)))

FROZEN = [P("wwh", WWH, "chars/wwh_stand.png", [190, 1520], 525, "魏文侯定格在低头看竹片的样子"),
          P("dcb", DC, "chars/wdc_b_urge.png", [450, 1520], 560, "大臣乙定格在摊手劝的样子"),
          P("dca", DC, "chars/wdc_a_urge.png", [640, 1520], 540, "大臣甲定格在劝的样子")]
shot("s23", A(12), "medium",
     "「考考屏幕前的小朋友」：司马光按遥控器，画面「咔」地定格在大臣们围着魏文侯劝的那一幕；司马光从右下角的书页边探出来",
     bg=bq_bg(blur=4),
     actors=FROZEN,
     fg=[fore()],
     fx=[fx("freeze", D(0.0), dur=1.9),
         fx("page_edge", D(0.05), y=1250, w=1900, peek="chars/sgm_hi_remote.png", peek_h=660, peek_x=820),
         fx("remote_click", D(0.5), pos=[1000, 1030])],
     camera=cam(push(0.03)))

shot("s24", A(12, word="如果"), "medium",
     "解说台：司马光头顶冒出想象泡泡（现代）：两个小朋友约好在小区门口见面，外面下起大雨，一个在窗边拎着雨靴犹豫，一个在门口雨棚下张望",
     transition={"type": "paper_wipe", "dur": 0.5},
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [250, 1740], 720, "司马光举着遥控器，笑呵呵地出题",
               acts=[act(A(12, word="暴风雨"), "nod")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_rain_meet.png", pos=[230, 1000], w=820)],
     camera=cam(push(0.03)))

shot("s25", A(12, word="你是当个"), "medium",
     "弹幕选择：两张大纸卡「咚咚」落下来：【鸽他一回】【绝不爽约】；说到「鸽子王」，一只戴小皇冠的纸鸽子「咕咕」扑腾着飞过（笑点）",
     bg=bq_bg(blur=8),
     fg=[L("props/pigeon_king.png", [900, 430], 1.0, [0.5, 0.5], w=240, enter={"type": "pop", "at": A(12, word="鸽子王", dt=-0.15)},
           anim=[{"at": A(12, word="鸽子王", dt=0.05), "dur": 1.8, "ease": "smooth", "pos": [170, 470]},
                 {"at": A(12, word="鸽子王", dt=0.1), "dur": 0.2, "rot": -12}, {"at": A(12, word="鸽子王", dt=0.3), "dur": 0.2, "rot": 10},
                 {"at": A(12, word="鸽子王", dt=0.5), "dur": 0.2, "rot": -12}, {"at": A(12, word="鸽子王", dt=0.7), "dur": 0.2, "rot": 10},
                 {"at": A(12, word="鸽子王", dt=0.9), "dur": 0.2, "rot": -10}, {"at": A(12, word="鸽子王", dt=1.1), "dur": 0.2, "rot": 0}])],
     fx=[fx("card_quest", D(0.1), text="鸽他一回", sub="选 A", pos=[540, 680]),
         fx("card_quest", A(12, word="还是想办法", dt=-0.2), text="绝不爽约", sub="选 B", pos=[540, 1080]),
         st_text("咕咕", [760, 500], A(12, word="鸽子王", dt=0.2), 80)],
     sfx=[sfx("whoosh", A(12, word="鸽子王", dt=-0.1))],
     camera=cam(push(0.03)))

shot("s26", A(13), "medium",
     "司马光冲镜头眨眨眼：「把你的选择打在弹幕上！」弹幕小纸条「嗖嗖」越飘越多；他再按一下遥控器，剧情接着往下演",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [540, 1760], 860, "司马光举着遥控器，笑眯眯地冲镜头眨眨眼",
               acts=[act(A(13, word="弹幕"), "bounce")])],
     fg=[desk()],
     fx=[fx("danmaku", A(13, dt=0.1), texts=["绝不爽约！", "鸽他一回", "不鸽！", "说好就要去", "绝不爽约！", "我选不鸽", "鸽子王快飞走", "绝不爽约！"],
            dur=1.4, density=1.0, area=[0, 380, 1080, 880]),
         fx("remote_click", A(13, dt=1.75), pos=[807, 1296])],
     camera=cam(push(0.03)))

# ======================================================== 魏文侯回答
shot("s27", A(14), "close",
     "魏文侯摇摇头：「正因为老人家在深山里等着」，一把抓起斗笠往上一抛",
     transition={"type": "whip", "dur": 0.28},
     bg=bq_bg(blur=6),
     actors=[P("wwh", WWH, "chars/wwh_hi_firm.png", [560, 1940], 1100, "魏文侯严肃坚定，眉头微皱，摇摇头",
               acts=[act(D(0.15), "shake"), act(A(14, word="深山"), "nod")])],
     fg=[L("props/douli.png", [880, 1330], 1.0, [0.5, 0.5], w=260, enter={"type": "pop", "at": A(14, word="等着", dt=-0.35)},
           anim=[{"at": A(14, word="等着"), "dur": 0.5, "ease": "out", "pos": [900, 420], "rot": 360}])],
     fx=[rain(), st("sou", [760, 620], A(14, word="等着"), 100)],
     sfx=[sfx("whoosh", A(14, word="等着"))],
     camera=cam(push(0.04)))

shot("s28", A(14, word="我才"), "close",
     "斗笠在空中转了一圈，「叮」地稳稳落在他头上（笑点）；他眼睛一亮：「我才绝不能爽约！」",
     bg=bq_bg(blur=6),
     actors=[P("wwh", WWH, "chars/wwh_hi_firm.png", [560, 1940], 1100, "魏文侯戴上斗笠、披上蓑衣，眼神清亮坚定",
               acts=[act(A(14, word="绝不", dt=-0.1), swap=HI_RAIN, h=1100)])],
     fg=[L("props/douli.png", [560, 400], 1.0, [0.5, 0.5], w=300,
           anim=[{"at": D(0.0), "dur": 0.4, "ease": "out", "pos": [560, 700], "rot": 360},
                 {"at": A(14, word="绝不", dt=-0.12), "dur": 0.05, "alpha": 0.0}])],
     fx=[rain(), fx("dust", A(14, word="绝不", dt=-0.1), mode="puff", pos=[560, 820], size=140),
         st("star", [0, 0], A(14, word="爽约"), 100, follow="wwh", attach="head")],
     sfx=[sfx("light_up", A(14, word="绝不")), sfx("shine", A(14, word="爽约"))],
     camera=cam(push(0.03), shake(A(14, word="爽约"), 0.25, 8)))

shot("s29", A(15), "close",
     "魏文侯说「虽然喝酒很开心」，身后浮出一个想象泡泡：深山里，虞人在雨里的茅草棚下抱着膝盖，望着空荡荡的泥路等着",
     bg=bq_bg(blur=6),
     actors=[P("wwh", WWH, HI_RAIN, [335, 1940], 1160, "魏文侯戴斗笠披蓑衣，严肃坚定")],
     fx=[rain(), fx("bubble", D(0.05), img="props/bubble_yr_wait.png", pos=[430, 800], w=760)],
     camera=cam(push(0.03)))

shot("s30", A(15, word="约定", nth=2, dt=-0.2), "wide",
     "「约定就是约定」：「约定」两个红色大字「咚」地砸下来；「怎么能贪图舒服就让别人苦等？！」大臣们低下头冒汗",
     bg=bq_bg(brazier=(400, 1420, 220)),
     actors=[P("dca", DC, "chars/wdc_a_urge.png", [600, 1500], 420, "大臣甲听着低下头", acts=[act(A(15, word="苦等"), "nod")]),
             P("dcb", DC, "chars/wdc_b_urge.png", [780, 1500], 420, "大臣乙听着低下头", acts=[act(A(15, word="苦等", dt=0.1), "nod")]),
             P("wwh", WWH, "chars/wwh_cape.png", [240, 1500], 600, "魏文侯戴斗笠披蓑衣，握着拳站着，看着大臣们说：约定就是约定",
               acts=[act(A(15, word="约定", nth=2), "bounce")])],
     fg=bq_fg(2300, 1580),
     fx=[rain(), fx("smash", A(15, word="约定", nth=2, dt=-0.14), text="约定", pos=[540, 760], size=240, color="red", shake=10),
         st("sweat", [0, 0], A(15, word="苦等"), 80, follow="dca", attach="head"),
         st("sweat", [0, 0], A(15, word="苦等", dt=0.15), 80, follow="dcb", attach="head")],
     camera=cam(push(0.03)))

# ======================================================== 冲进深山（燃，快切）
shot("s31", A(16), "wide",
     "快切：魏文侯「哗」地推开宫门，戴斗笠披蓑衣从魏宫台阶上大步冲进雨里",
     transition={"type": "whip", "dur": 0.24},
     bg=palace_bg(rain=True),
     actors=[P("wwh", WWH, "chars/wwh_cape.png", [200, 1520], 520, "魏文侯戴斗笠披蓑衣，大步走进雨里",
               enter={"type": "slide_left", "dur": 0.3}, anim=[{"at": D(0.3), "dur": 0.7, "dpos": [180, 0]}])],
     fg=[fore()],
     fx=[rain(), fx("lines_speed", D(0.0), dir="left", y0=400, y1=930)],
     sfx=[sfx("whoosh", D(0.0))],
     camera=cam(pan(dx=60)))

shot("s32", A(16, word="大门"), "close",
     "快切：魏文侯顶着倾盆大雨，眼神坚定往前冲",
     bg=road_bg(blur=6),
     actors=[P("wwh", WWH, HI_RAIN, [560, 1940], 1180, "魏文侯戴斗笠披蓑衣，顶着大雨，眼神坚定往前冲",
               acts=[act(D(0.1), "bounce")])],
     fx=[rain(dim=0.16)],
     sfx=[sfx("whoosh", D(0.0))],
     camera=cam(push(0.04), punch(D(0.1), 0.08)))

back, wwh_car, front = chariot(640, 1520, 900)
wwh_car["acts"] = [act(D(0.2), "bounce"), act(D(0.9), "bounce"), act(D(1.6), "bounce")]
shot("s33", A(16, word="暴雨"), "wide",
     "马车冲进泥泞的山路，泥水「噗呲」四溅（音乐变有劲）；后面大臣们用袖子遮着头在雨里追，一位大臣头上还扣着一只漆耳杯（笑点，不画伞）",
     bg=road_bg() + [L("chars/wdc_run.png", [230, 1480], 0.85, [0.5, 1], h=300, anim=[{"at": D(0.0), "dur": 2.2, "dpos": [60, 0]}]), back],
     actors=[wwh_car], fg=front + [fore()],
     fx=[rain(), fx("splash", D(0.3), pos=[300, 1570], size=0.8), fx("splash", D(1.1), pos=[960, 1560], size=0.8),
         fx("lines_speed", D(0.0), dir="left", y0=400, y1=900), st_text("啪嗒啪嗒", [230, 1010], D(0.6), 60)],
     sfx=[sfx("step", D(0.2)), sfx("step", D(0.45)), sfx("step", D(0.7))],
     camera=cam(pan(dx=80), shake(D(0.3), 0.3, 9)))

# ======================================================== 第 3 关：深山
shot("s34", A(17), "wide",
     "第三关（大字）：深山雨里，古树下一个简陋的茅草棚漏着雨；棚下小小的虞人坐着，望着空荡荡的泥路（茅草棚、深山是画面创作）",
     transition={"type": "page_turn", "dur": 0.6},
     bg=hut_bg(),
     actors=[P("yr", YR, "chars/yr_sit_l.png", [620, 1450], 300, "虞人坐在茅草棚下，缩着脖子抱着膝盖，望着左边空荡荡的泥路")],
     fg=[L("props/frog_leaf.png", [770, 1415], 1.0, [0.5, 1], w=90), fore()],
     fx=[rain(), fx("rays", A(17, dt=0.05), pos=[540, 560]), fx("big_title", A(17, dt=0.05), text="第三关：\n冒雨赴约的惊天智慧", pos=[540, 560], size=120, deco="none"),
         st_text("滴答滴答", [620, 880], D(1.0), 60, color="blue")],
     camera=cam(push(0.04)))

shot("s35", A(17, word="肯定"), "close",
     "虞人缩着脖子轻轻叹气：「肯定不会来了吧……」；棚顶一滴雨「滴」地落在旁边小青蛙头上，小青蛙也跟着叹气（笑点，不拿虞人当笑柄）",
     bg=hut_bg(blur=6),
     actors=[P("yr", YR, "chars/yr_hi_sigh_l.png", [520, 1940], 1340, "虞人缩着脖子抱着胳膊，眉毛耷拉，轻轻叹气",
               acts=[act(A(17, word="吧"), "nod")])],
     fg=[L("props/frog_leaf_sigh.png", [890, 1430], 1.0, [0.5, 1], w=190)],
     fx=[rain(), st_text("唉……", [200, 660], A(17, word="不会来"), 80), st_text("滴", [880, 1150], D(0.9), 70, color="blue")],
     camera=cam(push(0.04)))

back, wwh_car, front = chariot(330, 1480, 700, enter={"type": "slide_left", "dur": 0.6})
shot("s36", A(18), "wide",
     "「嘚嘚嘚」马车从左边冲到茅草棚前刹住，泥水四溅；棚下的虞人吓了一跳，一下子跳起来",
     bg=hut_bg(hx=760, hy=1440, hw=1100) + [back],
     actors=[wwh_car, P("yr", YR, "chars/yr_sit_l.png", [760, 1440], 260, "虞人坐在棚下，一下子跳起来，又惊又喜",
                        acts=[act(D(0.9), "jump")])],
     fg=front + [fore()],
     fx=[rain(), fx("splash", D(0.55), pos=[470, 1575], size=0.7), fx("dust", D(0.6), mode="puff", pos=[380, 1540], size=150),
         st("exclaim", [0, 0], D(0.9), 90, follow="yr", attach="head")],
     sfx=[sfx("step", D(0.05)), sfx("step", D(0.25)), sfx("step", D(0.45))],
     camera=cam(push(0.03), shake(D(0.6), 0.25, 8)))

shot("s37", A(19), "medium",
     "魏文侯（左，裤脚全是黄泥）快步走进草棚；虞人（右）连忙跪下行礼：「主公！天这么大的雨……」",
     bg=hut_bg(hx=600, hy=1380, hw=1300),
     actors=[P("wwh", WWH, "chars/wwh_cape.png", [300, 1580], 580, "魏文侯戴斗笠披蓑衣，快步走到草棚前", enter={"type": "slide_left", "dur": 0.4}),
             P("yr", YR, "chars/yr_sit_l.png", [740, 1580], 470, "虞人连忙从棚里出来跪下行礼，激动",
               acts=[act(A(19, dt=0.05), swap="chars/yr_kneel_l.png", h=500)])],
     fg=[fore()],
     fx=[rain()],
     camera=cam(push(0.04)))

shot("s38", A(19, word="您怎么"), "close",
     "虞人眼里闪着泪花，双手直哆嗦，又惊又喜：「您怎么真来了啊？！」",
     bg=hut_bg(hx=600, hy=1380, hw=1300, blur=6),
     actors=[P("yr", YR, "chars/yr_hi_cry_l.png", [540, 1940], 1340, "虞人眼眶里含着泪花，嘴张成 O，双手在胸前直哆嗦",
               acts=[act(D(0.2), "shake"), act(A(19, word="真来了"), "bounce")])],
     fx=[rain(), fx("sparkle", D(0.3), area=[120, 420, 960, 1300], count=12)],
     camera=cam(push(0.03), punch(A(19, word="真来了"), 0.08)))

shot("s39", A(20), "medium",
     "魏文侯弯腰双手把虞人扶起来，温和地笑：「老人家！快起来！」",
     bg=hut_bg(hx=600, hy=1380, hw=1300),
     actors=[P("wwh", WWH, "chars/wwh_help.png", [330, 1600], 560, "魏文侯弯腰双手向前扶人，温和地笑"),
             P("yr", YR, "chars/yr_kneel_l.png", [740, 1600], 500, "虞人被扶起来，眼泪汪汪地笑",
               acts=[act(A(20, word="起来"), swap="chars/yr_helped_l.png", h=560)])],
     fg=[fore()],
     fx=[rain(), st("heart", [540, 820], A(20, word="起来", dt=0.2), 100)],
     camera=cam(push(0.04)))

shot("s40", A(21), "medium",
     "「今天暴雨，不能打猎」：魏文侯指指外面的大雨，摇摇头；打猎的弓箭小图标上「啪」地打上一个大红叉（不打猎了）",
     bg=hut_bg(hx=600, hy=1380, hw=1300),
     actors=[P("wwh", WWH, "chars/wwh_cape.png", [290, 1580], 540, "魏文侯看看外面的大雨，摇摇头",
               acts=[act(A(21, word="不能"), "shake")]),
             P("yr", YR, "chars/yr_helped_l.png", [770, 1580], 520, "虞人站着听，有点愣")],
     fg=[L("props/icon_bow.png", [540, 860], 1.0, [0.5, 0.5], w=230, enter={"type": "pop", "at": A(21, word="打猎", dt=-0.3)}), fore()],
     fx=[rain(), st_text("×", [540, 860], A(21, word="打猎", dt=0.05), 220, color="red")],
     sfx=[sfx("pop", A(21, word="打猎", dt=-0.3))],
     camera=cam(push(0.03)))

shot("s41", A(21, word="但我"), "close",
     "反转：「但我必须亲自跑一趟，当面告诉你取消打猎」：魏文侯温和地笑，掌心向上；旁边腰间那片小竹片「叮」地亮起来（约好的事，当面说清楚）",
     bg=hut_bg(hx=600, hy=1380, hw=1300, blur=6),
     actors=[P("wwh", WWH, "chars/wwh_hi_rain_smile.png", [500, 1940], 1180, "魏文侯戴斗笠披蓑衣，温和地笑，一手掌心向上往前伸",
               acts=[act(A(21, word="亲自"), "nod"), act(A(21, word="当面"), "bounce")])],
     fg=[L("props/wwh_slip.png", [880, 980], 1.0, [0.5, 0.5], h=360, enter={"type": "pop", "at": A(21, word="当面")})],
     fx=[rain(), fx("sparkle", A(21, word="当面", dt=0.2), area=[800, 780, 960, 1180], count=8)],
     sfx=[sfx("light_up", A(21, word="当面", dt=0.1))],
     camera=cam(push(0.03), punch(A(21, word="当面"), 0.08)))

shot("s42", A(21, word="免得"), "close",
     "「免得你冒雨苦等！」：虞人先是一愣，接着咧嘴笑了",
     bg=hut_bg(hx=600, hy=1380, hw=1300, blur=6),
     actors=[P("yr", YR, "chars/yr_hi_cry_l.png", [540, 1940], 1340, "虞人先是一愣，接着咧嘴大笑，眼角还挂着泪珠",
               acts=[act(A(21, word="苦等", dt=-0.2), swap="chars/yr_hi_laugh_l.png", h=1340)])],
     fx=[rain(), st("heart", [880, 560], A(21, word="苦等"), 120)],
     camera=cam(push(0.04)))

shot("s43", A(22), "medium",
     "大臣们气喘吁吁地追到草棚门口，那位大臣头上还扣着漆耳杯，一个个累得直喘、脸上两团红晕，互相看看不好意思地低下头（笑点，不画摔跤）",
     bg=hut_bg(hx=760, hy=1380, hw=1300),
     actors=[P("dcs", DC, "chars/wdc_pant.png", [400, 1600], 460, "三位大臣淋得湿透，弯腰扶着膝盖大口喘气，脸红红的，不好意思地互相看看",
               acts=[act(D(0.2), "bounce"), act(D(0.9), "bounce")])],
     fg=[fore()],
     fx=[rain(), st_text("呼哧呼哧", [420, 860], D(0.2), 80)],
     camera=cam(push(0.04)))

# ======================================================== 燃点：传开了、人才、魏国强起来
birds = [L("props/bird_news.png", [470, 980], 1.0, [0.5, 0.5], w=110, flip=(dx < 0), alpha=0.0,
           anim=[{"at": A(23, word="传开", dt=0.08 * k), "dur": 0.05, "alpha": 1.0},
                 {"at": A(23, word="传开", dt=0.08 * k), "dur": 1.4, "ease": "out", "dpos": [dx, dy]}])
         for k, (dx, dy) in enumerate(((-300, -330), (-120, -480), (190, -500), (430, -300), (-330, 60)))]
shot("s44", A(23), "wide",
     "燃点：雨停了，阳光「唰」地穿透乌云照亮山川；茅草棚里的魏文侯和虞人笑着；一只只小纸鸟从草棚飞向四面八方——这件事传开了",
     bg=hut_bg(sunny=A(23, dt=0.15)),
     actors=[P("wwh", WWH, "chars/wwh_cape.png", [380, 1490], 400, "魏文侯戴斗笠站在草棚前，温和地笑，这件事从这里传开了"),
             P("yr", YR, "chars/yr_helped_l.png", [640, 1450], 270, "虞人站在棚下，笑着看魏文侯")],
     fg=birds + [fore()],
     fx=[rain(dur=0.6), fx("tone", A(23, dt=0.15), tone="warm", ramp=0.9),
         fx("rays", A(23, dt=0.3), pos=[720, 380]), st_text("扑棱棱", [260, 700], A(23, word="传开", dt=0.2), 80)],
     sfx=[sfx("whoosh", A(23, word="传开")), sfx("whoosh", A(23, word="传开", dt=0.3))],
     camera=cam(pull(0.04)))

shot("s45", A(23, word="魏文侯说"), "medium",
     "「魏文侯说的话，比黄金还重！」：一架纸天平，一边是一块金饼，一边是写着「说话算话」的小纸条——纸条那边「咚」地沉下去；魏文侯在旁边点点头",
     bg=[sky(False)] + ridges(470, 640, near=820, blur=4) + ground(1180, blur=4),
     actors=[P("wwh", WWH, "chars/wwh_cape.png", [210, 1520], 540, "魏文侯戴斗笠站着，点点头",
               acts=[act(A(23, word="说的话"), "nod")])],
     fg=[L("props/scale_a.png", [660, 1400], 1.0, [0.5, 1], w=620, anim=[{"at": A(23, word="比黄金"), "dur": 0.05, "alpha": 0.0}]),
         L("props/scale_b.png", [660, 1400], 1.0, [0.5, 1], w=620, alpha=0.0, anim=[{"at": A(23, word="比黄金"), "dur": 0.05, "alpha": 1.0}])],
     fx=[fx("rays", D(0.0), pos=[660, 900]), st_text("说话算话", [820, 700], D(0.3), 64, color="red"),
         fx("sparkle", A(23, word="还重"), area=[680, 900, 960, 1350], count=10)],
     sfx=[sfx("slam_1", A(23, word="比黄金"))],
     camera=cam(push(0.03), shake(A(23, word="比黄金"), 0.3, 9)))

TAL = [("wq", "吴起", "chars/wq_stand.png", 170, 540, "大将军", "吴起站出来，双臂抱胸，自信"),
       ("ly", "乐羊", "chars/ly_stand.png", 340, 520, "将军", "乐羊站出来，双手在身前相握，稳重"),
       ("lk", "李克", "chars/lk_stand.png", 500, 510, "学者", "李克站出来，拢着袖子，和蔼"),
       ("xmb", "西门豹", "chars/xmb_stand.png", 660, 510, "地方官", "西门豹站出来，一手按腰带，精神")]
shot("s46", A(24), "wide",
     "「后来，吴起、乐羊、李克、西门豹这些人才」：晴天的魏宫前，四位人才念到谁谁站出来（不画骑马、不画战场），面对右边的魏文侯",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=palace_bg(),
     actors=[P("wwh", WWH, "chars/wwh_stand_l.png", [850, 1530], 500, "魏文侯站在右边，笑着看四位人才")] +
            [P(i, who, img, [x, 1530], h, note, enter={"type": "pop", "at": A(24, word=who)}) for i, who, img, x, h, _, note in TAL],
     fg=[fore()],
     fx=[plate(who, role, [x, 380], A(24, word=who), size=0.5, house="魏家", dur=8.0) for _, who, _, x, _, role, _ in TAL],
     camera=cam(push(0.03)))

shot("s47", A(24, word="魏国"), "medium",
     "「都在魏国帮魏文侯做事」：李克和魏文侯对着竹简商量事情；乐羊、西门豹在后面点头；队伍最后，一只小青蛙也挺起胸膛站好（笑点）",
     bg=palace_bg(blur=4) + [L("sets/palace/slips_table.png", [560, 1560], 1.0, [0.5, 1], w=360)],
     actors=[P("ly", "乐羊", "chars/ly_stand.png", [160, 1440], 400, "乐羊在后面点头", acts=[act(A(24, word="做事"), "nod")]),
             P("xmb", "西门豹", "chars/xmb_stand.png", [560, 1380], 380, "西门豹在后面点头", acts=[act(A(24, word="做事", dt=0.15), "nod")]),
             P("lk", "李克", "chars/lk_stand.png", [330, 1580], 600, "李克拢着袖子，和魏文侯商量事情", acts=[act(A(24, word="帮"), "nod")]),
             P("wwh", WWH, "chars/wwh_stand_l.png", [790, 1580], 525, "魏文侯朝左看着李克，商量事情", acts=[act(A(24, word="魏文侯"), "nod")])],
     fg=[L("props/frog_proud.png", [260, 1450], 1.0, [0.5, 1], w=110, enter={"type": "pop", "at": A(24, word="魏文侯")}), fore()],
     sfx=[sfx("pop", A(24, word="魏文侯")), sfx("frog_croak", A(24, word="魏文侯", dt=0.3))],
     camera=cam(push(0.04)))

grow2 = [{"at": A(25, word="最先", dt=-0.1), "dur": 0.35, "ease": "back", "scale": 2.0}]
shot("s48", A(25), "wide",
     "「魏国，成了最先强起来的国家！」：地图上魏家的旗子「噌」地升到最高，金光一闪；顶上大问题标题条下面「啪」地打上一个大对勾（揭晓）",
     transition={"type": "page_turn", "dur": 0.6},
     bg=map_bg(),
     fg=map_flags(wei_anim=grow2, plain=True),
     fx=[fx("rays", A(25, word="最先"), pos=[380, 760], color="gold"), fx("sparkle", A(25, word="强起来"), area=[200, 500, 900, 1300], count=20),
         st_text("√", [880, 430], A(25, word="国家"), 140, color="red")],
     sfx=[sfx("light_up", A(25, word="最先")), sfx("pop", A(25, word="国家"))],
     camera=cam(push(0.04)))

# ======================================================== 书房点题
shot("s49", A(26), "medium",
     "知识：书页一翻回到书房，司马光低头看书；身旁弹出魏文侯的属性卡（像游戏里的成绩单）：武力 80 分、兵力 70 分，最后一行「守信等级 100 分」金光闪闪（分数是比喻）",
     transition={"type": "page_turn", "dur": 0.7},
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_read.png", [290, 1680], 780, "司马光低头看书，一根手指点在书页上，摸着胡子笑")],
     fg=[desk()],
     fx=[fx("stat_card", D(0.05), name="魏文侯",
            rows=[{"label": "武力", "value": "80分", "icon": "props/icon_resolve.png"}, {"label": "兵力", "value": "70分", "icon": "props/icon_bow.png"},
                  {"label": "守信等级", "value": "100分", "vcolor": "gold", "icon": "props/icon_heart.png"}],
            pos=[690, 790], w=520, gap=0.45),
         st_text("满分！", [880, 1080], D(1.9), 90, color="red")],
     camera=cam(push(0.03)))

shot("s50", A(27, word="记下"), "close",
     "「我在《资治通鉴》里记下了魏文侯的原话」：司马光摸着胡子笑，书页「哗哗」翻到这一页，一行字发着光飘起来",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_read.png", [540, 1760], 810, "司马光低头看书，手指点在书页上，笑呵呵",
               acts=[act(A(27, word="原话"), "nod"), act(A(28, dt=0.1), "bounce")])],
     fg=[desk()],
     fx=[fx("sparkle", A(28, dt=0.2), area=[200, 1050, 900, 1380], count=14)],
     sfx=[sfx("page_flip", A(28)), sfx("light_up", A(28, dt=0.4))],
     camera=cam(push(0.04)))

shot("s51", A(29), "close",
     "知识（点题，通鉴原话）：书房里，司马光低头指着书念；墙上亮起一行大字「虽乐，岂可无一会期哉！」",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_read.png", [300, 1740], 780, "司马光低头看书，手指点着书页上的原话念")],
     fg=[desk()],
     fx=[fx("rays", D(0.0), pos=[600, 600]),
         fx("big_title", A(29, dt=0.05), text="虽乐，\n岂可无一会期哉！", pos=[600, 600], size=120, deco="none", shake=0),
         fx("sparkle", A(29, dt=0.3), area=[200, 420, 1000, 820], count=12)],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["kid"], "why": "系列固定的点题：司马光念通鉴原文一句（「虽乐，岂可无一会期哉」），下一镜 s52 马上用白话「喝酒再开心，约好的事，怎么能不去」再说一遍，配漆耳杯和竹片的图"})

shot("s52", A(30), "medium",
     "白话：「喝酒再开心，约好的事，怎么能不去！」：书桌上方，「喝酒再开心」的漆耳杯想往前挤，「约好的事」那片小竹片「啵」地把它弹回去（笑点）；司马光举起食指讲",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_finger.png", [235, 1640], 560, "司马光举起食指，笑着讲白话", acts=[act(A(30, word="约好"), "nod")])],
     fg=[desk(),
         L("props/cup_lacquer.png", [580, 880], 1.0, [0.5, 0.5], w=340,
           anim=[{"at": A(30, word="开心"), "dur": 0.4, "ease": "out", "dpos": [130, 0]},
                 {"at": A(30, word="怎么能"), "dur": 0.35, "ease": "back", "dpos": [-190, 0]}]),
         L("props/wwh_slip.png", [880, 900], 1.0, [0.5, 0.5], h=440,
           anim=[{"at": A(30, word="怎么能", dt=-0.1), "dur": 0.15, "ease": "out", "scale": 1.2}, {"at": A(30, word="怎么能", dt=0.05), "dur": 0.25, "scale": 1.0}])],
     fx=[st_text("喝酒再开心", [580, 1060], A(30, word="开心", dt=-0.3), 64, color="brown"), st_text("约好的事", [860, 1190], A(30, word="约好"), 60, color="red"),
         st_text("啵", [760, 740], A(30, word="怎么能"), 90)],
     camera=cam(push(0.03)))

shot("s53", A(31), "medium",
     "小竹片「叮」一闪，变成一块巨大的红色马蹄形磁铁「咚」地砸进画面，上面写着「信用」；司马光吓了一跳，扶着帽子瞪大眼睛",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_shock.png", [305, 1760], 800, "司马光看着竹片变成大磁铁，吓了一跳，眼睛圆睁、一手扶着帽子",
               acts=[act(D(0.85), "jump")])],
     fg=[desk(),
         L("props/wwh_slip.png", [700, 880], 1.0, [0.5, 0.5], h=400, anim=[{"at": D(0.45), "dur": 0.1, "alpha": 0.0}]),
         L("props/magnet.png", [720, 880], 1.0, [0.5, 0.5], w=430, enter={"type": "drop", "at": D(0.45), "dur": 0.4})],
     fx=[fx("sparkle", D(0.0), area=[560, 640, 860, 1120], count=10), fx("dust", D(0.85), mode="puff", pos=[710, 1110], size=150),
         st_text("信用", [710, 830], D(0.95), 90, color="white")],
     sfx=[sfx("light_up", D(0.05)), sfx("slam_1", D(0.85))],
     camera=cam(push(0.04), shake(D(0.85), 0.3, 10)))

shot("s54", A(32, word="就是"), "medium",
     "金句：「信用，就是世界上最强的磁铁！」大字停在磁铁上方；司马光拍拍磁铁，竖起大拇指",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_thumb.png", [260, 1640], 560, "司马光竖起大拇指，笑眯眯", acts=[act(A(32, word="磁铁"), "bounce")])],
     fg=[desk(), L("props/magnet.png", [740, 1090], 1.0, [0.5, 0.5], w=440)],
     fx=[fx("rays", D(0.05), pos=[540, 560]), fx("big_title", D(0.05), text="信用，\n就是世界上最强的磁铁", pos=[540, 560], size=100, deco="none"),
         st_text("信用", [740, 1040], D(0.0), 90, color="white", sfx=None)],
     camera=cam(push(0.03)))

papermen = [L("props/paperman_wave.png", [sx, sy], 1.0, [0.5, 0.5], w=150, flip=(k % 2 == 1), enter={"type": "pop", "at": D(0.02 * k)},
              anim=[{"at": D(0.15 + 0.2 * k), "dur": 0.3, "ease": "back", "pos": [tx, ty]}])
            for k, ((sx, sy), (tx, ty)) in enumerate((((910, 420), (900, 860)), ((910, 1340), (900, 1200)),
                                                      ((560, 420), (650, 840)), ((560, 1340), (640, 1220))))]
shot("s55", A(33), "medium",
     "磁铁「嗡」地一吸：一个个纸片小人（比喻人才）「啪啪啪啪」被吸过来，贴在磁铁边上笑着挥手；司马光手里的遥控器也「嗖」地被吸走，他吓一跳（笑点）",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_shock.png", [300, 1760], 800, "司马光吓了一跳，眼睛圆睁、一手扶着帽子，遥控器被吸走了")],
     fg=[desk(), L("props/magnet.png", [780, 1040], 1.0, [0.5, 0.5], w=400)] + papermen +
        [L("props/remote.png", [660, 1380], 1.0, [0.5, 0.5], w=110, anim=[{"at": D(0.9), "dur": 0.35, "ease": "in", "pos": [690, 1200], "rot": 200}])],
     fx=[st_text("嗡", [780, 760], D(0.05), 90), st("sou", [600, 1240], D(0.9), 80)],
     sfx=[sfx("pop", D(0.4 + 0.2 * k)) for k in range(4)] + [sfx("whoosh", D(0.9))],
     camera=cam(push(0.04)))

shot("s56", A(34), "medium",
     "「它不是看你平时说了多少漂亮话」：一张张花花绿绿的「漂亮话」纸条飘起来，又一张张撕成两半；司马光捋着胡子摇摇头",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_frown.png", [260, 1640], 560, "司马光捋着胡子，皱着眉摇摇头", acts=[act(A(34, word="漂亮话"), "shake")])],
     fg=[desk()],
     fx=[st_text("我保证！", [700, 560], A(34, word="平时", dt=-0.3), 80, color="orange", dur=1.2, exit="tear"),
         st_text("包在我身上！", [680, 780], A(34, word="平时", dt=-0.05), 72, color="blue", dur=1.2, exit="tear"),
         st_text("说到做到！", [720, 1000], A(34, word="平时", dt=0.2), 76, color="green", dur=1.2, exit="tear")],
     camera=cam(push(0.04)))

shot("s57", A(34, word="而是"), "medium",
     "「而是看你在别人觉得『无所谓』的微小约定上」：一个纸片小人耸耸肩，头上冒出「无所谓」；旁边那片小竹片还在「叮」地发光，磁铁转过来对准它",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_finger.png", [230, 1640], 520, "司马光举起食指，认真地讲")],
     fg=[desk(), L("props/paperman_shrug.png", [520, 1330], 1.0, [0.5, 0.5], w=200, enter={"type": "pop", "at": A(34, word="无所谓", dt=-0.3)}),
         L("props/wwh_slip.png", [780, 1220], 1.0, [0.5, 0.5], h=340),
         L("props/magnet.png", [820, 720], 1.0, [0.5, 0.5], w=280, anim=[{"at": A(34, word="微小"), "dur": 0.4, "ease": "back", "rot": -25}])],
     fx=[st_text("无所谓", [520, 1110], A(34, word="无所谓"), 70), fx("sparkle", A(34, word="微小"), area=[700, 1030, 860, 1390], count=8)],
     sfx=[sfx("pop", A(34, word="无所谓", dt=-0.3)), sfx("light_up", A(34, word="微小"))],
     camera=cam(push(0.04)))

shot("s58", A(34, word="能不能"), "close",
     "「能不能认真守约！」司马光伸出食指指着观众，认真地点头",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_point.png", [520, 1650], 780, "司马光伸出食指指着观众，认真地讲", acts=[act(A(34, word="守约"), "nod")])],
     fg=[desk(), L("props/wwh_slip.png", [880, 900], 1.0, [0.5, 0.5], h=260)],
     fx=[st_text("守约！", [840, 600], A(34, word="守约"), 100, color="red"), fx("sparkle", D(0.2), area=[800, 760, 960, 1040], count=6)],
     camera=cam(push(0.03), punch(A(34, word="守约"), 0.08)))

shot("s59", A(35), "medium",
     "「连微小约定都全力守护的人」：小竹片越变越大、亮闪闪的；司马光举着遥控器笑",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [280, 1760], 860, "司马光举着遥控器，笑呵呵地看着变大的竹片")],
     fg=[desk(), L("props/wwh_slip.png", [740, 1060], 1.0, [0.5, 0.5], h=280, anim=[{"at": D(0.2), "dur": 1.6, "ease": "smooth", "scale": 1.6}])],
     fx=[fx("rays", D(0.1), pos=[740, 1060]), fx("sparkle", D(0.3), area=[560, 600, 940, 1380], count=14)],
     sfx=[sfx("light_up", D(0.2))],
     camera=cam(push(0.03)))

shot("s60", A(35, word="的人"), "medium",
     "「才能赢得……」：纸片小人一个接一个从两边围过来，竖起大拇指（「啵啵」）；司马光也竖大拇指",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_thumb.png", [540, 1640], 560, "司马光竖起大拇指，笑眯眯")],
     fg=[desk()] + [L("props/paperman_thumb.png", [x, y], 1.0, [0.5, 0.5], w=170, flip=fl, enter={"type": "pop", "at": D(0.15 + 0.25 * k)})
                    for k, (x, y, fl) in enumerate(((180, 1230, False), (900, 1230, True), (200, 760, False), (880, 760, True)))],
     sfx=[sfx("pop", D(0.15 + 0.25 * k)) for k in range(4)],
     camera=cam(push(0.04)))

shot("s61", A(35, word="最宝贵"), "medium",
     "解说台的纸屏幕上又出现开场那一幕（魏文侯冒雨驾车赶路），红色「信任」两个大字像印章一样「咚」地盖上去——那天冒雨赶的，就是这个约定",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [280, 1760], 820, "司马光举着遥控器，笑着看屏幕",
               acts=[act(A(35, word="信任"), "nod")])],
     fg=[desk()],
     fx=[fx("screen", D(0.0), img="props/screen_rain_ride.png", pos=[660, 650], w=560),
         fx("smash", A(35, word="宝贵", dt=-0.14), text="信任", pos=[660, 700], size=200, color="red", shake=10),
         fx("remote_click", A(36, dt=0.05), pos=[507, 1296])],
     camera=cam(push(0.03)))

# ======================================================== 安全提醒、行动呼吁
shot("s62", A(37), "medium",
     "「放到今天，打个电话、发个消息……」：司马光按一下遥控器，旁边弹出「打个电话」「发个消息」小纸条",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [290, 1760], 860, "司马光按一下遥控器，笑眯眯地讲")],
     fg=[desk()],
     fx=[fx("remote_click", D(0.1), pos=[557, 1296]), st_text("放到今天", [740, 560], D(0.2), 80),
         st_text("打个电话", [740, 780], A(37, word="打个电话"), 80, color="blue")],
     camera=cam(push(0.04)))

shot("s63", A(37, word="发个消息"), "medium",
     "司马光头顶冒出想象泡泡（现代）：小朋友在家用电话手表发消息「下大雨啦，我们改天再玩！」；好朋友收到了，比个 OK，脚边小狗也举起一只爪子（笑点）",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [250, 1740], 720, "司马光笑呵呵地看着泡泡", acts=[act(A(37, word="对方"), "nod")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_watch_msg.png", pos=[230, 1000], w=820),
         st_text("下大雨啦，我们改天再玩！", [600, 720], D(0.5), 44, color="blue"),
         st("heart", [880, 860], A(37, word="对方"), 90)],
     camera=cam(push(0.03)))

shot("s64", A(38), "medium",
     "安全提醒：泡泡里小朋友套上雨靴要往门外冲，门边小青蛙顶着荷叶冲他摇头；司马光「咔」地按一下遥控器，摇摇手指：「打雷下大雨，可别自己往外跑哦！」",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [290, 1740], 720, "司马光按遥控器，笑眯眯地摇摇头",
               acts=[act(A(38, word="别自己"), "shake")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_door.png", pos=[270, 1000], w=820),
         fx("remote_click", A(38, word="别自己"), pos=[513, 1351])],
     camera=cam(push(0.03)))

shot("s65", A(39), "medium",
     "行动呼吁：司马光捧着书冲镜头笑，两张小纸条「讲历史」「做靠谱人」一张张弹出来",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_book.png", [270, 1680], 570, "司马光双手捧着书，笑着看观众",
               acts=[act(A(39, word="讲历史"), "bounce"), act(A(39, word="靠谱"), "nod")])],
     fg=[desk()],
     fx=[st_text("讲历史", [740, 660], A(39, word="讲历史"), 100), st_text("做靠谱人", [740, 900], A(39, word="靠谱", dt=-0.2), 100, color="red")],
     camera=cam(push(0.03)))

shot("s66", A(40), "medium",
     "「点赞，并收藏这集视频」：一颗大红心（点赞）和一颗金星星（收藏）弹出来，一只青蛙跳上去按了一下（笑点）；司马光竖起大拇指",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_thumb.png", [270, 1680], 600, "司马光竖起大拇指，笑眯眯", acts=[act(A(40, word="收藏"), "bounce")])],
     fg=[desk(), L("props/frog_jump.png", [920, 1350], 1.0, [0.5, 0.5], w=180, flip=True,
                   anim=[{"at": A(40, word="收藏", dt=0.3), "dur": 0.45, "ease": "out", "dpos": [-230, -380]}])],
     fx=[st("heart", [680, 640], A(40, word="点赞"), 220), st("star", [860, 860], A(40, word="收藏"), 200)],
     sfx=[sfx("whoosh", A(40, word="收藏", dt=0.3)), sfx("frog_croak", A(40, word="收藏", dt=0.7))],
     camera=cam(push(0.04)))

shot("s67", A(40, word="带孩子"), "medium",
     "「带孩子看懂什么叫真正的『一诺千金』」：大字「一诺千金」盖下来，下面一行小字「答应的事，说到做到」；那架纸天平又弹出来，「一诺」那边「咚」地沉下去，金子翘了起来",
     bg=study_bg(blur=4),
     fg=[desk(),
         L("props/scale_a.png", [540, 1420], 1.0, [0.5, 1], w=600, anim=[{"at": A(40, word="一诺", dt=0.1), "dur": 0.05, "alpha": 0.0}]),
         L("props/scale_b.png", [540, 1420], 1.0, [0.5, 1], w=600, alpha=0.0, anim=[{"at": A(40, word="一诺", dt=0.1), "dur": 0.05, "alpha": 1.0}])],
     fx=[fx("big_title", D(0.05), text="一诺千金", pos=[540, 500], size=170, deco="rays"),
         st_text("答应的事，说到做到", [540, 700], D(0.6), 60, color="red"),
         st_text("一诺", [740, 880], D(0.9), 64, color="red")],
     sfx=[sfx("slam_1", A(40, word="一诺", dt=0.1))],
     camera=cam(push(0.03), shake(A(40, word="一诺", dt=0.1), 0.3, 8)),
     notes={"jev_allow": ["subject"], "why": "旁白对家长的行动呼吁（PITFALLS S25，剧本原话），台词里没有故事人物；画面是「一诺千金」字卡和天平，呼应前面 s45「比黄金还重」"})

# ======================================================== 下集预告
river = [sky(False)] + river_ridges() + water(1180, 6, 0.7, 140)


def boat(cx, by, w, drift=None):
    e = {"anim": [dict(drift)]} if drift else {}
    return (L("props/boat_back.png", [cx, by], 1.0, [0.5, 1], w=w, note="布景前层", **e),
            L("props/boat_front.png", [cx, by], 1.0, [0.5, 1], w=w, note="布景前层", **e))


bb, bf = boat(560, 1480, 1000)
shot("s68", A(41), "wide",
     "下集预告：「关注我们，下一集带你看」：整屏压暗，大河上漂着一艘大木船（没有帆、不是战船），一个大问号「啪」地翻起来",
     transition={"type": "iris", "dur": 0.7},
     bg=river + [bb], fg=[bf] + water(1440, 2, 1.0, 120),
     fx=[st("question", [540, 760], A(41, word="下一集"), 260)],
     grade="tense",
     camera=cam(push(0.04)))

drift = {"at": D(0.0), "dur": 3.5, "ease": "linear", "dpos": [70, 0]}
bb, bf = boat(560, 1480, 1100, drift)
shot("s69", A(42), "wide",
     "下集预告：大河上，一艘大木船顺流往下漂（浪花平稳）；船头站着身材魁梧的大将军吴起",
     bg=river + [bb],
     actors=[P("wq", "吴起", "chars/wq_stand.png", [800, 1390], 440, "吴起站在船头，双臂抱胸，望着前方", anim=[dict(drift)])],
     fg=[bf] + water(1440, 2, 1.0, 120),
     fx=[plate("吴起", "大将军", [560, 400], D(0.1), size=0.6, house="魏家")],
     camera=cam(push(0.03)))

drift = {"at": D(0.0), "dur": 3.2, "ease": "linear", "dpos": [50, 0]}
bb, bf = boat(540, 1530, 1500, drift)
shot("s70", A(42, word="如何"), "medium",
     "「如何在顺着大河往下走的大木船上」：大木船上，吴起站在船头（右），年轻的魏武侯（左，在他后面；魏家橙黄衣服、小冠，是侯不是王）指着前方两岸的大山得意地笑",
     bg=[sky(False)] + river_ridges(blur=3) + water(1180, 6, 0.7, 140) + [bb],
     actors=[P("wq", "吴起", "chars/wq_stand.png", [760, 1400], 560, "吴起站在船头，双臂抱胸望着前方", anim=[dict(drift)]),
             P("wuh", "魏武侯", "chars/wuh_point.png", [330, 1400], 600, "魏武侯（魏文侯的儿子）一手指着远处的大山，仰头得意地笑",
               anim=[dict(drift)], acts=[act(A(42, word="大木船"), "bounce")])],
     fg=[bf] + water(1520, 3, 1.0, 120),
     fx=[plate("魏武侯", "魏文侯的儿子", [150, 380], D(0.1), size=0.55, house="魏家")],
     camera=cam(push(0.03)))

shot("s71", A(42, word="给得意"), "close",
     "「给得意忘形的魏武侯」：魏武侯指着大山仰头哈哈大笑，得意极了",
     bg=[sky(False, blur=4)] + river_ridges(blur=4) + water(1180, 6, 0.7, 140, blur=4),
     actors=[P("wuh", "魏武侯", "chars/wuh_point.png", [540, 2200], 1380, "魏武侯指着远处的大山，仰头得意地哈哈大笑",
               acts=[act(A(42, word="得意"), "bounce")])],
     fx=[st_text("哈哈哈", [860, 560], A(42, word="得意", dt=0.1), 90)],
     camera=cam(push(0.03)))

shot("s72", A(42, word="上一堂"), "close",
     "「上一堂震撼的大课？」：吴起回头皱着眉，伸手指向远方；一个大问号「啪」地弹出来（下集揭晓）",
     bg=[sky(False, blur=5)] + river_ridges(blur=5) + water(1180, 6, 0.7, 140, blur=5) + [boat(540, 1630, 2400)[0]],
     actors=[P("wq", "吴起", "chars/wq_hi_point_l.png", [560, 1480], 990, "吴起站在船上回过头，皱着眉，一手伸食指指向远方，严肃",
               acts=[act(A(42, word="震撼"), "bounce")])],
     fg=[boat(540, 1630, 2400)[1]] + water(1500, 3, 1.0, 120),
     fx=[st("question", [230, 640], A(42, word="大课"), 180)],
     camera=cam(push(0.03)))

# ---------------------------------------------------------------- 放行（Jev）
GE = "「鸽」= 放鸽子（答应了又不去），孩子日常口语；「鸽还是不鸽」「鸽子王」是定稿剧本原话（第二关名、司马光的题，Chris 10-01 同意），不是大人的网络梗"
CTA = "旁白对家长的行动呼吁 / 下集预告（PITFALLS S25、S29，剧本原话），台词里没有故事人物"
ALLOW = {
    "s08": {"jev_allow": ["subject"], "why": "地图镜头：旁白讲魏国的绝招「信用」，主体是地图上的魏家旗子；后半句「看魏文侯……」下一镜 s09 由魏文侯特写接上"},
    "s20": {"jev_allow": ["meme"], "why": GE},
    "s23": {"jev_allow": ["subject", "meme"], "why": "定格画面，司马光从书页边探出来出题（page_edge 特效，不是 actor），台词是司马光对观众说的；" + GE},
    "s24": {"jev_allow": ["meme"], "why": GE},
    "s25": {"jev_allow": ["subject", "meme"], "why": "司马光对观众出题（弹幕选择），这一镜只放两张选项纸卡和飞过的「鸽子王」，司马光在前后两镜 s24、s26 出镜；" + GE},
    "s65": {"jev_allow": ["subject"], "why": CTA + "；由系列讲解人司马光在书房里出镜串场"},
    "s66": {"jev_allow": ["subject"], "why": CTA + "；由系列讲解人司马光在书房里出镜串场"},
    "s68": {"jev_allow": ["subject"], "why": CTA + "；下一镜 s69 起是吴起和魏武侯"},
}
for s in SH:
    if s["id"] in ALLOW and "notes" not in s:
        s["notes"] = ALLOW[s["id"]]

sb = {
    "episode": "tj02", "no": 2, "name": "魏文侯之约",
    "title": ["一场大雨，", "怎么让魏国强起来？"],
    "voice": "video/out/tj02_voice",
    "speakers": {"魏文侯": "魏家", "大臣": DC_COLOR, "虞人": YR_COLOR},
    "note": "tj02 分镜表（剧本 A_守约.json，配音 video/out/tj02_voice，全长 194.46 秒）。素材见 video/stories/tj02/素材清单.md，镜头见 镜头大纲.md；"
            "交领人物不翻转；驾车用 wwh_reins（魏文侯自己握缰绳）；弹幕选择用两张 card_quest + danmaku（不用 kaoni，不倒计时）",
    "shots": SH,
}
OUT.write_text(json.dumps(sb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("shots", len(SH))
