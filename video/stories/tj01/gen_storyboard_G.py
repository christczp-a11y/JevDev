"""生成 tj01 G 版分镜表 video/stories/tj01/storyboard.json（配音 video/out/tj01_voice_g）。"""
import copy
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path("C:/Users/Chris/Claude x Jev/JevDev/video/stories/tj01/storyboard.json")


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


def sky(night=False, blur=0):
    d = L("sets/jin_land/sky_night.png" if night else "sets/jin_land/sky.png", [0, 0], 0.1, w=1080)
    if blur:
        d["blur"] = blur
    return d


def ridges(y_far=470, y_mid=640, near=None, blur=0):
    out = [L("sets/jin_land/ridge_far.png", [540, y_far], 0.2, [0.5, 0], w=1100),
           L("sets/jin_land/ridge_mid.png", [540, y_mid], 0.3, [0.5, 0], w=1100)]
    if near is not None:
        out.append(L("sets/jin_land/ridge_near.png", [540, near], 0.4, [0.5, 0], w=1100))
    if blur:
        for x in out:
            x["blur"] = blur
    return out


def ground(y0=1290, blur=0):
    out, y = [], float(y0)
    for k, w in enumerate((1300, 1500, 1700, 1900)):
        g = L("sets/jin_land/ground.png", [540, round(y)], 0.9, [0.5, 0], w=w, repeat="x")
        if k % 2:
            g["flip"] = True
        if blur:
            g["blur"] = blur
        out.append(g)
        y += 218 * w / 1528 * 0.8
    return out


def water(y0=1180, n=4, depth=0.7, dy=140, amp=26, blur=0, rise=None):
    out = []
    for k in range(n):
        d = L("sets/jin_land/water.png", [540, y0 + dy * k], min(depth + 0.05 * k, 1.0), [0.5, 0], w=1528, repeat="x",
              sway={"x": amp, "y": 6, "period": 3.4, "phase": round(0.4 * k, 2)})
        if blur:
            d["blur"] = blur
        if rise:
            d["anim"] = [dict(rise)]
        out.append(d)
    return out


def fore(y=1930):
    return L("sets/jin_land/fore.png", [540, y], 1.0, [0.5, 1], w=1850, repeat="x")


def ext_bg(horizon=1290, night=False, blur=0, y_far=470, y_mid=640):
    return [sky(night, blur)] + ridges(y_far, y_mid, blur=blur) + ground(horizon, blur)


def bq_bg(blur=0):
    t = L("sets/lantai/terrace.png", [540, 1330], 0.6, [0.5, 1], w=1300)
    h = L("sets/lantai/hu.png", [150, 1300], 0.7, [0.5, 1], w=160)
    dn = L("sets/lantai/ding.png", [930, 1300], 0.7, [0.5, 1], w=160)
    out = [sky(False, blur)] + ridges(470, 640, blur=blur) + [t, h, dn] + ground(1290, blur)
    if blur:
        for x in out:
            x["blur"] = blur
    return out


def bq_fg():
    return [L("sets/lantai/banquet_row.png", [540, 1460], 1.0, [0.5, 0.5], w=2100), fore()]


def study_bg(blur=0):
    d = L("sets/study/wall.png", [0, 0], 0.3, w=1080)
    if blur:
        d["blur"] = blur
    return [d]


def desk():
    return L("sets/study/desk.png", [540, 1930], 1.0, [0.5, 1], w=1150)


def chariot_bg():
    return ([sky()] + ridges(520, 700) + water(1180, 3, 0.6) +
            [L("sets/camp/dike.png", [540, 1440], 0.9, [0.5, 0], w=1700, repeat="x"),
             fore(1925), L("props/chariot_back.png", [600, 1500], 1.0, [0.5, 1], w=1100)])


def chariot_fg():
    return [L("props/chariot_front.png", [600, 1500], 1.0, [0.5, 1], w=1100),
            L("props/horse.png", [900, 1500], 1.0, [0.5, 1], w=360)]


def night_bg(horizon=1400, wall=True):
    out = [sky(True)] + ridges(560, 700)
    if wall:
        out += [L("sets/jinyang/wall.png", [540, 1420], 0.6, [0.5, 1], w=1528, repeat="x"),
                L("sets/jinyang/gate.png", [540, 1420], 0.6, [0.5, 1], w=1300)]
    out += ground(horizon)
    return out


def camp_night():
    return ([sky(True)] + ridges(560, 700) +
            [L("sets/camp/tent_big.png", [300, 1260], 0.5, [0.5, 1], w=560),
             L("sets/camp/tent_s1.png", [720, 1250], 0.5, [0.5, 1], w=480),
             L("sets/camp/tent_s2.png", [960, 1255], 0.5, [0.5, 1], w=420)] +
            water(1230, 4, 0.7))


# ---------------------------------------------------------------- 人物
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


def plate(name, role, house, pos, at, size=0.8, dur=2.4):
    return fx("name_plate", at, name=name, role=role, house=house, pos=list(pos), size=size, dur=dur)


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


SH = []


def shot(id_, frm, size, note, **kw):
    s = {"id": id_, "from": frm, "size": size}
    s.update(kw)
    s["note"] = note
    SH.append(s)
    return s


ZB = "智伯"
SGM = "司马光"

# ======================================================== 开场：反差钩子
hook_bg = [sky()] + ridges(820, 960) + ground(1330)
shot("s01", A(0, dt=-0.3), "wide",
     "开场反差钩子（先看结局）：山顶上，全身名牌（满印金色「智」字花纹）的智伯张开双臂仰天狂笑；一道卷成 Q 版笑脸龙头的大浪从背后扑过来，把他浇成落汤鸡，嘴里「噗」地喷水，一只青蛙掉到他头顶（笑点，出糗的是智伯；只是被浇湿）",
     bg=copy.deepcopy(hook_bg),
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [540, 1430], 880, "智伯穿着满印「智」字花纹的名牌红袍，张开双臂仰天哈哈大笑，下一秒被大浪浇成落汤鸡",
               acts=[act(A(0, dt=0.25), "bounce"), act(A(0, dt=1.3), swap="chars/zb_b_soaked.png", h=900)])],
     fg=[L("props/wave_dragon.png", [480, 1520], 1.0, [0.5, 1], w=1500,
           enter={"type": "slide_left", "at": A(0, dt=0.7), "dur": 0.6},
           anim=[{"at": A(0, dt=1.45), "dur": 0.6, "ease": "out", "dpos": [400, -40]}, {"at": A(0, dt=1.6), "dur": 0.45, "alpha": 0.0}]),
         L("props/frog_wait.png", [560, 548], 1.0, [0.5, 1], w=190, enter={"type": "drop", "at": A(0, dt=2.15)}),
         fore()],
     fx=[plate("智伯", "智家老大", "智家", [850, 390], A(0, dt=0.1)),
         st_text("哈哈哈", [230, 470], A(0, dt=0.25), 110),
         fx("splash", A(0, dt=1.3), pos=[190, 1330], size=0.8),
         st_text("噗！", [850, 650], A(0, dt=1.85), 110),
         fx("freeze", A(0, dt=2.55), dur=0.6)],
     camera=cam(push(0.04), shake(A(0, dt=1.3), 0.3, 12)),
     sfx=[{"name": "whoosh", "at": A(0, dt=0.7)}, {"name": "frog_croak", "at": A(0, dt=2.3)}])

shot("s02", A(1), "medium",
     "解说台：司马光（Q 版小老头，写《资治通鉴》的人）在书房里「啪」地弹出来，举着遥控器哈哈笑——刚才那一幕就是他按遥控器定格的；他头顶冒出想象泡泡：教室里，一个大个子学霸站在奖杯塔上鼻孔朝天（现代的东西只在泡泡里）",
     transition={"type": "paper_wipe", "dur": 0.6},
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [290, 1760], 860, "司马光在书房的解说台后面弹出来，举着遥控器哈哈笑，问观众一个问题",
               enter={"type": "pop", "at": D(0.02)}, acts=[act(A(1, word="学霸"), "bounce")])],
     fg=[desk()],
     fx=[fx("remote_click", D(0.35), pos=[557, 1296]),
         fx("bubble", A(1, word="学霸"), img="props/bubble_xueba_a.png", pos=[480, 950], w=820)],
     camera=cam(push(0.03)))

shot("s03", A(1, word="最后"), "medium",
     "司马光又按一下遥控器，泡泡里换了一幅画：老实的同学们手拉着手，把学霸脚下的奖杯塔轻轻推倒了，学霸坐在奖杯堆里发愣（推倒的是奖杯塔，不是人）",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [760, 1760], 820, "司马光站在解说台右边，转向左边的泡泡，举着遥控器哈哈笑，讲同学们合伙推翻学霸的事", flip=True,
               acts=[act(A(1, word="推翻"), "nod")])],
     fg=[desk()],
     fx=[fx("remote_click", D(0.05), pos=[506, 1317]),
         fx("bubble", D(0.12), img="props/bubble_xueba_b.png", pos=[600, 960], w=820, flip=True),
         st("exclaim", [860, 600], A(1, word="推翻", dt=0.1), 100)],
     camera=cam(push(0.03)))

shot("s04", A(1, word="你信不信"), "close",
     "司马光笑眯眯地指着观众问：「你信不信？」",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_point.png", [540, 1760], 780, "司马光笑眯眯，伸出食指指着观众")],
     fg=[desk()],
     fx=[st("question3", [830, 600], A(1, word="你信不信", dt=0.15), 150)],
     camera=cam(push(0.03), punch(A(1, word="信", nth=2), 0.08)))

# ======================================================== 时代背景
shot("s05", A(2, dt=0.5), "wide",
     "转场：翻日历，停在「两千四百多年前 · 战国」；画面换成一片古代的晋地：远山、黄土地，远处一座夯土城",
     transition={"type": "calendar_flip", "stop_text": "两千四百多年前 · 战国"},
     bg=[sky()] + ridges(520, 680, near=820) +
        [L("sets/jinyang/gate.png", [620, 1250], 0.5, [0.5, 1], w=760), L("sets/jinyang/wall.png", [620, 1250], 0.5, [0.5, 1], w=1528, repeat="x")] +
        ground(1240),
     fg=[fore()],
     camera=cam(pan(dx=140)))

flags4 = [("props/flag_zhi.png", 190), ("props/flag_zhao.png", 400), ("props/flag_han.png", 610), ("props/flag_wei.png", 820)]
shot("s06", A(3, word="诸侯"), "wide",
     "诸侯争霸的战国：晋国的智、赵、韩、魏四家的旗子一面接一面从地上弹出来，迎风飘",
     bg=ext_bg(1250),
     fg=[L(img, [x, 1420], 1.0, [0.5, 1], h=620, enter={"type": "pop", "at": A(3, word="诸侯", dt=0.1 + 0.28 * k)},
           sway={"x": 0, "y": 4, "period": 2.6 + 0.3 * k, "phase": k})
         for k, (img, x) in enumerate(flags4)] + [fore()],
     fx=[st("dong", [540, 560], A(3, word="战国"), 160)],
     sfx=[{"name": "pop", "at": A(3, word="诸侯", dt=0.1 + 0.28 * k)} for k in range(4)],
     camera=cam(push(0.05)))

# ======================================================== 智伯登场
shot("s07", A(4), "close",
     "一本书翻开：书页上砸下「资治通鉴」「第一案」（《资治通鉴》开篇讲的第一个故事），这个故事的主角智伯像立体书一样从书页里「噗」地弹出来",
     transition={"type": "page_turn", "dur": 0.7},
     bg=[L("sets/study/book_page_hi.png", [0, 0], 1.0, w=1080)],
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [540, 1400], 620, "第一案的主角智伯（名牌红袍）从书页里弹出来，张开双臂大笑",
               enter={"type": "pop", "at": A(4, word="第一案", dt=0.35)})],
     fx=[fx("smash", A(4, dt=0.1), text="资治通鉴", pos=[540, 450], size=170),
         fx("smash", A(4, word="第一案"), text="第一案", pos=[540, 650], size=200, color="red")],
     camera=cam(push(0.04)))

shot("s08", A(4, word="当时"), "close",
     "智伯登场：满印金色「智」字的名牌红袍、金腰扣，双手叉腰鼻孔朝天哈哈大笑；头顶弹出游戏里的「LV.MAX」满级牌，身边闪闪发光（笑点：臭美）",
     bg=ext_bg(1290, blur=6),
     actors=[P("zb", ZB, "chars/zb_hi_brand.png", [560, 1940], 1150, "智伯穿满印「智」字花纹的名牌红袍，双手叉腰、鼻孔朝天得意大笑",
               acts=[act(A(4, word="智伯"), "bounce")])],
     fx=[fx("rays", A(4, word="最强"), pos=[560, 1000], color="gold"),
         st_text("LV.MAX", [840, 560], A(4, word="全能"), 100, color="gold"),
         fx("sparkle", A(4, word="智伯"), area=[100, 400, 980, 1300])],
     camera=cam(push(0.04), punch(A(4, word="智伯"), 0.08)))

shot("s09", A(5), "wide",
     "「地盘最大、兵马最多」：智伯站在前面张开双臂大笑，身后一排排智家的兵和智家的旗子一个接一个站出来",
     bg=ext_bg(1250) +
        [L("chars/sold_spear.png", [x, 1330], 0.8, [0.5, 1], h=400, enter={"type": "pop", "at": A(5, word="兵马", dt=0.08 * k)})
         for k, x in enumerate((130, 290, 790, 950))] +
        [L("props/flag_zhi.png", [210, 1300], 0.7, [0.5, 1], h=560, enter={"type": "pop", "at": A(5, dt=0.2)}),
         L("props/flag_zhi.png", [870, 1300], 0.7, [0.5, 1], h=560, enter={"type": "pop", "at": A(5, dt=0.45)})],
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [540, 1560], 760, "智伯张开双臂站在最前面，得意地大笑",
               acts=[act(A(5, word="兵马"), "bounce")])],
     fg=[fore()],
     sfx=[{"name": "pop", "at": A(5, word="兵马")}],
     camera=cam(pull(0.05)))

shot("s10", A(5, word="为什么"), "medium",
     "大问题：开场那张落汤鸡的智伯「翻」回画面，头顶冒出三个问号：为什么一夜之间全部输光？",
     bg=[sky()] + ridges(820, 960) + ground(1330),
     actors=[P("zb", ZB, "chars/zb_b_soaked.png", [540, 1430], 900, "智伯浑身湿透，垂头丧气站着",
               enter={"type": "flip", "dur": 0.4})],
     fg=[fore()],
     fx=[st("question3", [860, 520], A(5, word="输光"), 160),
         fx("lines_focus", A(5, word="一夜"), center=[540, 710], clear=[540, 710, 330])],
     grade="tense",
     camera=cam(push(0.05), shake(A(5, word="输光"), 0.25, 8)))

shot("s11", A(6), "wide",
     "「点个赞，看满级大王如何凭实力作死」：点赞的小心心弹出来；智伯鼻子越翘越高、得意洋洋，「作死」两个大字砸在他脚边，他还没发现（笑点，出糗的是智伯）",
     bg=ext_bg(1290),
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [540, 1420], 860, "智伯张开双臂仰头大笑，鼻孔朝天，一点也没看脚下",
               acts=[act(A(6, word="满级"), "bounce"), act(A(6, word="作死", dt=0.3), "wobble", dur=0.4)])],
     fg=[fore()],
     fx=[st("heart", [200, 480], A(6, word="点个赞"), 170),
         fx("smash", A(6, word="作死"), text="作死", pos=[540, 1225], size=230, color="red")],
     camera=cam(push(0.04)))

# ======================================================== 第 1 关：宴会
shot("s12", A(7), "wide",
     "第 1 关（大字）：蓝台宴会的远景：夯土高台上的木亭、一长排矮案、青铜壶和鼎；智伯坐在右边的主位上仰头大笑，左边三位客人正举杯捧着他",
     transition={"type": "page_turn", "dur": 0.7},
     bg=bq_bg() + [L("chars/guests_toast.png", [340, 1470], 0.95, [0.5, 1], w=760)],
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [790, 1470], 470, "智伯（名牌红袍）跪坐在右边的主位上，朝左边的客人指指点点、仰头哈哈大笑，得意洋洋",
               acts=[act(A(7, word="智伯"), "bounce")])],
     fg=bq_fg(),
     fx=[fx("big_title", A(7, dt=0.05), text="第 1 关\n狂妄是最大的毒药", pos=[540, 520], size=140, deco="rays")],
     camera=cam(pan(dx=60)))

shot("s13", A(7, word="智伯"), "medium",
     "「大家都夸智伯厉害」：宴会上的客人（左）一边拍手一边举杯敬酒，笑得有点讨好；智伯（右）眯着眼咧嘴笑，越听越得意",
     bg=bq_bg(blur=5),
     actors=[P("zb", ZB, "chars/zb_b_hi_greedy_l.png", [760, 1760], 900, "智伯（名牌红袍，朝左）眯着眼咧嘴笑，听着大家夸他，越听越得意",
               acts=[act(A(7, word="一高兴"), "bounce")])],
     fg=[L("chars/guests_toast.png", [380, 1520], 1.0, [0.5, 1], w=880,
           anim=[{"at": D(0.15), "dur": 0.18, "ease": "out", "dpos": [0, -14]}, {"at": D(0.33), "dur": 0.18, "ease": "in", "dpos": [0, 14]},
                 {"at": D(0.75), "dur": 0.18, "ease": "out", "dpos": [0, -14]}, {"at": D(0.93), "dur": 0.18, "ease": "in", "dpos": [0, 14]},
                 {"at": D(1.35), "dur": 0.18, "ease": "out", "dpos": [0, -14]}, {"at": D(1.53), "dur": 0.18, "ease": "in", "dpos": [0, 14]}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2300), fore()],
     fx=[st_text("啪啪啪", [250, 640], D(0.15), 110), st("star_eyes", [820, 640], D(0.8), 130),
         st_text("好厉害！", [540, 520], D(1.3), 100)],
     camera=cam(push(0.04)))

shot("s14", A(7, word="整个人"), "close",
     "智伯一高兴，头顶的「得意值」一格格涨到爆表，整个人像气球一样飘了起来（笑点，出糗的是智伯）",
     bg=bq_bg(blur=5),
     actors=[P("zb", ZB, "chars/zb_hi_brand.png", [580, 1940], 1080, "智伯双手叉腰、鼻孔朝天得意大笑，整个人往上飘",
               anim=[{"at": A(7, word="飘"), "dur": 1.2, "ease": "smooth", "dpos": [0, -130]}])],
     fg=[fore()],
     fx=[fx("progress", D(0.05), pos=[190, 800], title="得意值", kind="fill", **{"from": 0.3, "to": 1.0}),
         st("star", [900, 620], A(7, word="飘"), 120),
         fx("sparkle", A(7, word="飘"), area=[100, 400, 980, 1300])],
     camera=cam(push(0.04)))

shot("s15", A(8), "wide",
     "智伯跪坐着飘在半空，往下一指、哈哈大笑；在他眼里，下面的韩康子和他的谋士段规「嗖」地缩成两个小纸人——他越喝越得意，看谁都像小弟",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [720, 900], 500, "智伯跪坐着飘在半空，朝左下方指着人哈哈大笑",
               anim=[{"at": D(0.0), "dur": 1.0, "ease": "smooth", "dpos": [0, -20]}, {"at": D(1.0), "dur": 1.0, "ease": "smooth", "dpos": [0, 20]}]),
             P("hkz", "韩康子", "chars/hkz_low.png", [250, 1470], 400, "韩康子跪坐在下面，低着头缩着肩，被智伯看成小不点",
               anim=[{"at": D(0.35), "dur": 0.4, "ease": "back", "scale": 0.72}]),
             P("dg", "段规", "chars/dg_kneel.png", [450, 1470], 390, "段规跪坐在韩康子旁边，低着头一声不吭，也被看成小不点",
               anim=[{"at": D(0.45), "dur": 0.4, "ease": "back", "scale": 0.72}])],
     fg=bq_fg(),
     fx=[plate("韩康子", "韩家主人", "韩家", [165, 390], D(0.05), dur=2.0),
         plate("段规", "韩康子的谋士", "韩家", [400, 400], D(0.1), dur=2.0)],
     sfx=[{"name": "whoosh", "at": D(0.35)}],
     camera=cam(push(0.03)))

shot("s16", A(9), "medium",
     "智伯（右）跪坐着朝左指着韩康子和段规，拍着大腿大声起哄；韩康子低下头攥紧袖子，段规抿着嘴不吭声（被取笑的人不当笑点）",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [760, 1470], 520, "智伯跪坐着，朝左伸食指指着韩康子和段规，张大嘴哈哈嘲笑",
               acts=[act(A(9), "bounce"), act(A(9, word="瞧你"), "wobble", dur=0.4)]),
             P("hkz", "韩康子", "chars/hkz_low.png", [250, 1470], 480, "韩康子低着头缩着肩，眼泪汪汪，一声不敢吭",
               acts=[act(A(9, word="瞧你", dt=0.3), "shake", dur=0.4)]),
             P("dg", "段规", "chars/dg_kneel.png", [470, 1470], 460, "段规低着头、牙关咬紧，一声不吭")],
     fg=bq_fg(),
     fx=[st_text("哈哈", [890, 820], A(9, dt=0.1), 100)],
     camera=cam(pan(dx=-40)))

shot("s17", A(9, word="你们全家"), "close",
     "智伯的近景：指着人仰头大笑，嚷着「谁敢惹我」",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [620, 1800], 1100, "智伯跪坐着伸食指指着人，鼻孔朝天哈哈嘲笑",
               acts=[act(A(9, word="谁敢"), "bounce")])],
     fx=[st_text("哈哈哈", [230, 520], A(9, word="你们全家", dt=0.1), 110)],
     camera=cam(push(0.04), punch(A(9, word="谁敢"), 0.1)))

shot("s18", A(10), "medium",
     "智国急急忙忙跑过来，一把按住智伯指着人的胳膊，满头大汗地劝：「主公！快住手！」",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [790, 1470], 440, "智伯跪坐着还在指着人笑，被智国拉住胳膊",
               acts=[act(A(10, word="快住手"), "shake", dur=0.4)]),
             P("zgu", "智国", "chars/zgu_stand.png", [450, 1500], 660, "智国急急忙忙跑过来，一手伸出去拉智伯的胳膊、一手捂着胸口，满脸着急",
               enter={"type": "slide_left", "dur": 0.45}, acts=[act(A(10, word="别小看"), "bounce")])],
     fg=bq_fg(),
     fx=[plate("智国", "智伯的族人", "智家", [165, 400], A(10, dt=0.3)),
         st("sweat", [0, 0], A(10, word="快住手"), 90, follow="zgu", attach="head")],
     camera=cam(push(0.04)))

shot("s19", A(10, word="小蚂蚁"), "medium",
     "智国接着劝「小蚂蚁急了也是会咬人的」：矮案上的漆耳杯边，爬出一只小黑蚂蚁，冲着镜头晃了晃触角（笑点）",
     bg=bq_bg(blur=5),
     actors=[P("zgu", "智国", "chars/zgu_stand.png", [290, 1560], 640, "智国着急地伸出手劝智伯",
               acts=[act(A(10, word="咬人"), "nod")])],
     fg=[L("sets/lantai/banquet_row.png", [540, 1500], 1.0, [0.5, 0.5], w=2400),
         L("props/cup_lacquer.png", [760, 1300], 1.0, [0.5, 1], w=360),
         L("props/ant.png", [720, 1215], 1.0, [0.5, 1], w=260, enter={"type": "pop", "at": A(10, word="小蚂蚁", dt=0.1)},
           anim=[{"at": A(10, word="咬人", dt=-0.4), "dur": 0.2, "rot": -10}, {"at": A(10, word="咬人", dt=-0.2), "dur": 0.2, "rot": 10},
                 {"at": A(10, word="咬人"), "dur": 0.2, "rot": -8}, {"at": A(10, word="咬人", dt=0.2), "dur": 0.2, "rot": 0}])],
     fx=[st("exclaim", [860, 980], A(10, word="咬人"), 90)],
     camera=cam(push(0.05)))

shot("s20", A(11), "medium",
     "智伯一甩袖子站起来，抬脚一踢，桌上的漆耳杯「嗖」地飞上天：「我是大象！」",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_kick_l.png", [680, 1480], 820, "智伯站着一甩袖子，朝左抬脚一踢，仰头大笑")],
     fg=[L("props/cup_lacquer.png", [400, 1330], 1.0, [0.5, 0.5], w=180,
           anim=[{"at": D(0.12), "dur": 0.55, "ease": "out", "dpos": [-120, -900], "rot": -540}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[st("sou", [260, 900], D(0.12), 130)],
     sfx=[{"name": "whoosh", "at": D(0.12)}],
     camera=cam(push(0.03), shake(D(0.12), 0.25, 8)))

shot("s21", A(11, word="在乎"), "close",
     "智伯得意大笑，头顶冒出想象泡泡：一头披着「智」字红毯子的大象鼻子扬得高高的，象鼻尖上站着一只叉腰的小蚂蚁，一点也不怕（比喻：蚂蚁也会咬人）",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_hi_brand.png", [330, 1940], 1000, "智伯双手叉腰鼻孔朝天，得意洋洋地大笑",
               acts=[act(A(11, word="蚂蚁"), "bounce")])],
     fx=[fx("bubble", D(0.05), img="props/bubble_elephant.png", pos=[470, 930], w=820)],
     camera=cam(push(0.04)))

shot("s22", A(12), "medium",
     "漆耳杯在天上翻了两个跟头，「哗」地掉回来，酒全洒在智伯自己身上，杯子扣在他冠上；他低头看着湿衣服愣住（笑点，出糗的是智伯）",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_kick_l.png", [620, 1480], 820, "智伯还在踢腿大笑，杯子掉下来扣在他头上，酒洒了一身，他愣住了",
               acts=[act(D(0.3), swap="chars/zb_b_spill.png", h=860)])],
     fg=[L("props/cup_lacquer.png", [620, 600], 1.0, [0.5, 0.5], w=170, enter={"type": "drop", "at": D(0.0), "dur": 0.3},
           anim=[{"at": D(0.32), "dur": 0.05, "alpha": 0.0}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[fx("splash", D(0.3), pos=[260, 1280], size=0.7),
         st_text("哗！", [880, 700], D(0.32), 120)],
     camera=cam(push(0.03), shake(D(0.3), 0.3, 10)))

shot("s23", A(13), "medium",
     "司马光按遥控器：画面「咔」地定格在刚才智伯指着人起哄的那一幕；司马光从书页边升上来：「注意看！」",
     bg=bq_bg(),
     actors=[P("zb", ZB, "chars/zb_b_point_l.png", [760, 1470], 520, "智伯定格在指着人嘲笑的样子"),
             P("hkz", "韩康子", "chars/hkz_low.png", [250, 1470], 480, "韩康子定格在低头缩肩的样子"),
             P("dg", "段规", "chars/dg_kneel.png", [470, 1470], 460, "段规定格在咬牙不吭声的样子")],
     fg=bq_fg(),
     fx=[fx("freeze", D(0.0), dur=1.8),
         fx("page_edge", D(0.05), y=1250, w=1900, peek="chars/sgm_hi_remote.png", peek_h=740, peek_x=820),
         fx("remote_click", D(0.55), pos=[1000, 990])],
     camera=cam(push(0.03)))

shot("s24", A(13, word="这是在"), "medium",
     "书房里，司马光捋着胡子皱着眉讲：这不是厉害",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_frown.png", [540, 1700], 560, "司马光捋着胡子皱着眉，认真地讲",
               acts=[act(A(13, word="不知不觉"), "nod")])],
     fg=[desk()],
     fx=[st("exclaim", [830, 700], A(13, word="这是在", dt=0.1), 100)],
     camera=cam(push(0.05)))

shot("s25", A(13, word="把别人"), "medium",
     "司马光的画外音「把别人都逼成了自己的敌人」：画面上就是被智伯逼成敌人的「别人」——韩康子和段规面对面，头顶「帮手」两张小纸牌「嘶」地撕成两半，换成红色的「敌人」（给后面的反转埋线）",
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_low.png", [300, 1470], 480, "韩康子（台词里被智伯逼成敌人的「别人」之一）低着头，偷偷看向段规"),
             P("dg", "段规", "chars/dg_kneel_l.png", [720, 1470], 470, "段规（也是被逼成敌人的「别人」）朝左看着韩康子，嘴抿紧",
               acts=[act(A(13, word="敌人"), "nod")])],
     fg=bq_fg(),
     fx=[st_text("帮手", [0, 0], D(0.1), 90, follow="hkz", attach="head", dur=1.95, exit="tear"),
         st_text("帮手", [0, 0], D(0.2), 90, follow="dg", attach="head", dur=1.85, exit="tear"),
         st_text("敌人", [0, 0], A(13, word="敌人"), 100, color="red", follow="hkz", attach="head"),
         st_text("敌人", [0, 0], A(13, word="敌人", dt=0.15), 100, color="red", follow="dg", attach="head")],
     camera=cam(push(0.04)))

# ======================================================== 第 2 关：要地
shot("s26", A(14), "medium",
     "第 2 关（大字）：智伯变本加厉，像个霸道的收税官：一张画着城的地图「啪」地拍在矮案上，他穿名牌袖子的大手从右边伸到韩康子面前",
     transition={"type": "page_turn", "dur": 0.6},
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_hug.png", [250, 1470], 500, "韩康子跪坐着，看着伸到面前的大手，吓了一跳",
               acts=[act(A(14, word="封地", dt=0.3), "shake", dur=0.4)])],
     fg=[L("props/map_silk.png", [560, 1350], 1.0, [0.5, 0.5], w=560, enter={"type": "drop", "at": A(14, word="交出", dt=-0.2)}),
         L("props/hand_reach_b.png", [840, 1150], 1.0, [0.5, 0.5], w=760, enter={"type": "slide_right", "at": A(14, word="交出"), "dur": 0.5}),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[fx("big_title", A(14, dt=0.05), text="第 2 关\n要地，给还是不给？", pos=[540, 520], size=130, deco="rays"),
         st("pa", [720, 1080], A(14, word="交出", dt=0.05), 120)],
     camera=cam(push(0.03), shake(A(14, word="交出", dt=0.05), 0.25, 9)))

shot("s27", A(14, word="不然"), "close",
     "智伯的近景：贪心地咧嘴笑着威胁「不然我就带着大军去收拾你」，身后两面智家的大旗「呼」地竖起来",
     bg=bq_bg(blur=6) + [L("props/flag_zhi.png", [170, 1250], 0.8, [0.5, 1], h=700, enter={"type": "pop", "at": A(14, word="大军")}),
                         L("props/flag_zhi.png", [920, 1250], 0.8, [0.5, 1], h=700, enter={"type": "pop", "at": A(14, word="大军", dt=0.2)})],
     actors=[P("zb", ZB, "chars/zb_b_hi_greedy_l.png", [600, 1940], 1080, "智伯（朝左）贪心地眯眼咧嘴笑，一副要东西的样子",
               acts=[act(A(14, word="收拾"), "bounce")])],
     fx=[st("anger", [260, 640], A(14, word="收拾"), 120)],
     sfx=[{"name": "pop", "at": A(14, word="大军")}],
     camera=cam(push(0.05)))

shot("s28", A(15), "medium",
     "司马光按遥控器：画面「咔」地定格在智伯的大手伸到韩康子面前的那一刻；司马光从右下角的书页边升上来出题",
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_hug.png", [250, 1470], 500, "韩康子定格在抱着地图、看着大手的样子")],
     fg=[L("props/map_silk.png", [560, 1350], 1.0, [0.5, 0.5], w=560),
         L("props/hand_reach_b.png", [840, 1150], 1.0, [0.5, 0.5], w=760),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[fx("freeze", D(0.0), dur=2.0),
         fx("page_edge", D(0.05), y=1250, w=1900, peek="chars/sgm_hi_remote.png", peek_h=660, peek_x=800),
         fx("remote_click", D(0.5), pos=[980, 1030])],
     camera=cam(push(0.03)))

shot("s29", A(15, word="如果"), "close",
     "「如果你是韩康子，给还是不给？」：韩康子把地图紧紧抱在怀里；两边弹出两个大按钮「给」「不给」",
     bg=bq_bg(blur=6),
     actors=[P("hkz", "韩康子", "chars/hkz_hug.png", [420, 1560], 540, "韩康子把红绳系的地图紧紧抱在怀里，警惕地看着前方",
               acts=[act(A(15, word="给还是不给"), "bounce")])],
     fx=[st_text("给", [230, 620], A(15, word="给还是不给"), 170, color="green"),
         st_text("不给", [760, 620], A(15, word="给还是不给", dt=0.35), 170, color="red")],
     camera=cam(push(0.05)))

shot("s30", A(16), "medium",
     "解说台：司马光笑着按遥控器，满屏的弹幕小纸条从右往左飞过：「给！」「不给！」……两只青蛙各举一张纸条跑过去撞了个满怀（笑点）",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [290, 1760], 860, "司马光举着遥控器，笑眯眯地看着观众")],
     fg=[desk(),
         L("props/frog_jump.png", [560, 1440], 1.0, [0.5, 1], w=180, anim=[{"at": D(0.5), "dur": 0.4, "ease": "out", "dpos": [110, -30]}]),
         L("props/frog_jump.png", [900, 1440], 1.0, [0.5, 1], w=180, flip=True, anim=[{"at": D(0.5), "dur": 0.4, "ease": "out", "dpos": [-110, -30]}])],
     fx=[fx("remote_click", D(0.05), pos=[557, 1296]),
         fx("danmaku", A(16, word="弹幕"), texts=["给！", "不给！", "给吧……", "不给！", "先给他", "我不给", "给！", "不给！"], dur=1.6, density=1.0, area=[0, 380, 1080, 1000]),
         st("dong", [760, 1300], D(0.9), 110)],
     camera=cam(push(0.03)))

shot("s31", A(17), "medium",
     "韩康子眼含泪水，把地图抱得更紧：「我……我不想给……」；智伯的大手还悬在旁边",
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_hug.png", [360, 1470], 520, "韩康子眼泪汪汪，把地图抱得紧紧的，不想撒手",
               acts=[act(A(17, word="不想给"), "shake", dur=0.5)])],
     fg=[L("props/hand_reach_b.png", [900, 1130], 1.0, [0.5, 0.5], w=620,
           anim=[{"at": D(0.2), "dur": 1.0, "dpos": [0, -12]}, {"at": D(1.2), "dur": 1.0, "dpos": [0, 12]}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[st("sweat", [0, 0], A(17, dt=0.2), 90, follow="hkz", attach="head")],
     camera=cam(push(0.05)))

shot("s32", A(18), "medium",
     "段规凑到韩康子耳边，小眼睛滴溜溜转，压低声音出主意：「主公，给他！撑大他的胃口！」",
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_hug.png", [300, 1470], 500, "韩康子抱着地图，侧耳听段规说悄悄话"),
             P("dg", "段规", "chars/dg_whisper.png", [650, 1470], 500, "段规（朝左）凑到韩康子耳边，一手挡着嘴说悄悄话、一手在空中画圈",
               acts=[act(A(18, word="给他"), "bounce"), act(A(18, word="撑大"), "nod")])],
     fg=bq_fg(),
     fx=[st_text("嘘", [880, 860], A(18, dt=0.1), 100)],
     camera=cam(push(0.05)))

shot("s33", A(18, word="拿惯"), "close",
     "「他拿惯了咱们的，转头就会去要别人的」：智伯（朝左）贪心地笑着，一座座城图标「咻」地飞进他怀里越堆越多",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_b_hi_greedy_l.png", [620, 1700], 1000, "智伯两手在胸前拢成一个圈，贪心地眯眼咧嘴笑，城一座座堆进怀里",
               acts=[act(A(18, word="转头"), "bounce"), act(A(18, word="别人", dt=0.2), "bounce")])],
     fg=[L("props/city_han.png", [620, 1330], 1.0, [0.5, 0.5], w=210, enter={"type": "slide_left", "at": A(18, word="拿惯", dt=0.1), "dur": 0.45}),
         L("props/city_wei.png", [680, 1250], 1.0, [0.5, 0.5], w=210, enter={"type": "slide_left", "at": A(18, word="转头"), "dur": 0.45}),
         L("props/city_jinyang.png", [600, 1170], 1.0, [0.5, 0.5], w=210, enter={"type": "slide_left", "at": A(18, word="别人"), "dur": 0.45}),
         L("sets/lantai/banquet_row.png", [540, 1760], 1.0, [0.5, 0.5], w=2400)],
     sfx=[{"name": "city_pop", "at": A(18, word="拿惯", dt=0.5)}, {"name": "city_pop", "at": A(18, word="转头", dt=0.4)},
          {"name": "city_pop", "at": A(18, word="别人", dt=0.4)}],
     camera=cam(push(0.04)))

shot("s34", A(19), "medium",
     "知识：段规（左）指着一张纸地图接着说：智伯的虚线箭头从左边伸向别家的城——「等别人不给，他就去打别人」",
     bg=bq_bg(blur=6),
     actors=[P("dg", "段规", "chars/dg_nod.png", [170, 1520], 560, "段规双手拢袖站在地图旁边，微微点头，胸有成竹地讲",
               acts=[act(A(19, word="打起来"), "nod")])],
     fx=[fx("map", D(0.0), pos=[640, 800], w=660, dim=0.15),
         fx("map_city", D(0.2), pos=[780, 720], name="别家", icon="props/city_jinyang.png", house="赵家"),
         fx("map_arrow", A(19, word="打起来"), pts=[[420, 900], [580, 820], [730, 740]], house="智家")],
     camera=cam(push(0.03)))

shot("s35", A(19, word="咱们"), "medium",
     "段规抱着胳膊往后一靠，冲韩康子眨眨眼、竖起食指，眼角「叮」地闪出一颗小星星：「咱们就等着看好戏！」",
     bg=bq_bg(),
     actors=[P("dg", "段规", "chars/dg_wink.png", [520, 1520], 620, "段规眨一只眼、嘴角上扬、竖起食指，胸有成竹",
               acts=[act(A(19, word="看好戏"), "bounce")])],
     fg=[fore()],
     fx=[st("star", [760, 820], A(19, word="看好戏"), 110)],
     camera=cam(push(0.05)))

shot("s36", A(20), "medium",
     "韩康子忍气吞声，咬着牙把地图推出去，一座城图标「咻」地飞向右边的智伯",
     bg=bq_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_give.png", [330, 1470], 510, "韩康子咬牙含泪，一手把地图卷往右递出去、一手捂着心口")],
     fg=[L("props/city_han.png", [560, 1150], 1.0, [0.5, 0.5], w=200, enter={"type": "pop", "at": D(0.15)},
           anim=[{"at": D(0.5), "dur": 0.6, "ease": "in", "dpos": [360, -100], "rot": 30}, {"at": D(0.9), "dur": 0.2, "alpha": 0.0}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     sfx=[{"name": "whoosh", "at": D(0.5)}],
     camera=cam(push(0.04)))

shot("s37", A(21), "close",
     "智伯一把把韩家的城搂进怀里，笑得合不拢嘴，转头又要：「魏桓子，你也交一块！」",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_b_hi_greedy_l.png", [620, 1700], 1000, "智伯怀里搂着一座城，贪心地笑")],
     fg=[L("props/city_han.png", [640, 1320], 1.0, [0.5, 0.5], w=220, enter={"type": "drop", "at": D(0.0)}),
         L("sets/lantai/banquet_row.png", [540, 1760], 1.0, [0.5, 0.5], w=2400)],
     fx=[st("sou", [260, 760], A(21, dt=0.3), 120)],
     camera=cam(push(0.04)))

shot("s38", A(21, word="交"), "medium",
     "智伯名牌袖子的大手「嗖」地伸到魏桓子面前；魏桓子皱着眉叹口气，也把一座城推过去（群像接龙第 2 位）",
     bg=bq_bg(),
     actors=[P("wgh", "魏桓子", "chars/wgh_give.png", [320, 1470], 510, "魏桓子跪坐着，一手把地图卷往右递出去，笑着但眼睛心疼",
               acts=[act(A(22), "nod")])],
     fg=[L("props/hand_reach_b.png", [880, 1130], 1.0, [0.5, 0.5], w=700, enter={"type": "slide_right", "at": D(0.0), "dur": 0.45}),
         L("props/city_wei.png", [540, 1160], 1.0, [0.5, 0.5], w=200, enter={"type": "pop", "at": A(22, dt=0.1)},
           anim=[{"at": A(22, dt=0.6), "dur": 0.5, "ease": "in", "dpos": [340, -40], "rot": 20}]),
         L("sets/lantai/banquet_row.png", [540, 1560], 1.0, [0.5, 0.5], w=2100), fore()],
     fx=[plate("魏桓子", "魏家主人", "魏家", [165, 390], D(0.1)),
         st_text("唉……", [560, 860], A(22, dt=0.05), 100)],
     sfx=[{"name": "whoosh", "at": D(0.0)}, {"name": "whoosh", "at": A(22, dt=0.6)}],
     camera=cam(push(0.04)))

shot("s39", A(23), "close",
     "智伯怀里的城越堆越高，高得挡住了他的脸，城堆摇摇晃晃；他从城堆后面探出头，朝赵襄子嚷：「喂！你的地呢？快拿来！」（笑点，出糗的是智伯）",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_b_hi_greedy_l.png", [620, 1700], 1000, "智伯搂着一大摞城，从城堆后面探出头来要地",
               acts=[act(A(23, word="快拿来"), "bounce")])],
     fg=[L("props/city_han.png", [640, 1330], 1.0, [0.5, 0.5], w=220),
         L("props/city_wei.png", [610, 1180], 1.0, [0.5, 0.5], w=220,
           anim=[{"at": D(0.3), "dur": 0.5, "rot": -6}, {"at": D(0.8), "dur": 0.5, "rot": 6}, {"at": D(1.3), "dur": 0.5, "rot": -5}, {"at": D(1.8), "dur": 0.5, "rot": 4}]),
         L("sets/lantai/banquet_row.png", [540, 1760], 1.0, [0.5, 0.5], w=2400)],
     fx=[st_text("喂！", [250, 700], A(23, dt=0.05), 130), st("question", [880, 640], A(23, word="你的地"), 110)],
     camera=cam(push(0.04)))

shot("s40", A(24), "close",
     "赵襄子（原来的造型）端坐着，一手抬到胸前轻轻一挡，眼神平静又坚定：「不给！」大字「不给」砸在桌上",
     bg=bq_bg(blur=6),
     actors=[P("zxz", "赵襄子", "chars/zxz_hi_no.png", [470, 1940], 1150, "赵襄子坐得笔直，右手抬到胸前掌心朝外一挡，嘴唇紧闭，一点也不让步",
               acts=[act(A(24, word="百姓"), "nod"), act(A(24, word="一寸"), "shake", dur=0.4)])],
     fx=[fx("smash", A(24, dt=0.02), text="不给", pos=[540, 520], size=240, color="green"),
         plate("赵襄子", "赵家主人", "赵家", [850, 560], A(24, dt=0.5))],
     camera=cam(push(0.03), punch(A(24, dt=0.02), 0.1)))

shot("s41", A(25, dt=-0.3), "close",
     "全场一静：智伯惊呆了，怀里的城「哗啦」掉了一地；接着他瞬间「红温」：咬牙瞪眼、鬓发竖起、头顶冒烟（笑点，出糗的是智伯）",
     bg=bq_bg(blur=6),
     actors=[P("zb", ZB, "chars/zb_b_hi_shock_l.png", [620, 1700], 1000, "智伯先惊呆（瞪眼、嘴成 O），接着气得咬牙瞪眼、鬓发根根竖起",
               acts=[act(A(25, word="敢不听"), swap="chars/zb_b_hi_angry_l.png")])],
     fg=[L("props/city_han.png", [640, 1330], 1.0, [0.5, 0.5], w=220, anim=[{"at": D(0.05), "dur": 0.4, "ease": "in", "dpos": [-80, 40], "rot": -60}, {"at": D(0.3), "dur": 0.2, "alpha": 0.0}]),
         L("props/city_wei.png", [610, 1180], 1.0, [0.5, 0.5], w=220, anim=[{"at": D(0.12), "dur": 0.4, "ease": "in", "dpos": [90, 200], "rot": 70}, {"at": D(0.4), "dur": 0.2, "alpha": 0.0}]),
         L("sets/lantai/banquet_row.png", [540, 1760], 1.0, [0.5, 0.5], w=2400)],
     fx=[st("dong", [250, 1150], D(0.3), 120),
         st_text("红温！", [880, 620], A(25, word="敢不听", dt=0.1), 110, color="red"),
         st("anger", [220, 700], A(25, word="敢不听", dt=0.2), 110)],
     sfx=[{"name": "plate_drop", "at": D(0.3)}],
     camera=cam(push(0.03), shake(A(25, word="敢不听"), 0.35, 12)))

shot("s42", A(25, word="韩康子"), "medium",
     "智伯（右，气得鬓发竖起）转头冲韩家、魏家下令，韩、魏两面旗子在他面前一面接一面竖起来",
     bg=ext_bg(1290),
     actors=[P("zb", ZB, "chars/zb_b_hi_angry_l.png", [730, 1940], 1000, "智伯气得咬牙瞪眼，朝左边下命令")],
     fg=[L("props/flag_han.png", [200, 1420], 1.0, [0.5, 1], h=640, enter={"type": "pop", "at": A(25, word="韩康子", dt=0.05)}),
         L("props/flag_wei.png", [420, 1420], 1.0, [0.5, 1], h=640, enter={"type": "pop", "at": A(25, word="魏桓子", dt=0.05)})],
     sfx=[{"name": "pop", "at": A(25, word="韩康子", dt=0.05)}, {"name": "pop", "at": A(25, word="魏桓子", dt=0.05)}],
     camera=cam(push(0.04)))

shot("s43", A(25, word="跟我"), "medium",
     "知识：智伯（右下，气得鬓发竖起）一挥手；旁边的纸地图上，智家的虚线箭头带着大军冲向北边的晋阳（赵家的城）",
     bg=ext_bg(1290, blur=6),
     actors=[P("zb", ZB, "chars/zb_b_hi_angry_l.png", [760, 1900], 900, "智伯（名牌红袍，朝左）咬牙瞪眼，下令大军去打赵家",
               acts=[act(A(25, word="赵家"), "bounce")])],
     fx=[fx("map", D(0.0), pos=[380, 700], w=580, dim=0.15),
         fx("map_city", D(0.15), pos=[380, 480], name="晋阳", icon="props/city_jinyang.png", house="赵家"),
         fx("map_arrow", A(25, word="赵家"), pts=[[260, 940], [320, 740], [380, 560]], house="智家")],
     camera=cam(push(0.03)))

# ======================================================== 第 3 关：水淹晋阳和大逆转
shot("s44", A(26), "wide",
     "第 3 关（大字）：智伯（左岸）张开双臂大笑，一道大水被引过来，「哗——」地涌向晋阳的夯土城墙（河不标名字）",
     transition={"type": "page_turn", "dur": 0.7},
     bg=[sky()] + ridges(520, 700) + [L("sets/jinyang/wall.png", [640, 1300], 0.6, [0.5, 1], w=1528, repeat="x"),
                                      L("sets/jinyang/gate.png", [700, 1300], 0.6, [0.5, 1], w=1100)] +
        water(1250, 4, 0.7, 140, rise={"at": A(26, word="河水"), "dur": 1.6, "ease": "smooth", "dpos": [0, -90]}),
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [330, 1500], 560, "智伯站在岸边张开双臂大笑，看着大水冲向晋阳",
               acts=[act(A(26, word="直接"), "bounce")])],
     fg=[fore()],
     fx=[fx("big_title", A(26, dt=0.05), text="第 3 关\n惊天大逆转", pos=[540, 520], size=150, deco="rays"),
         fx("splash", A(26, word="河水", dt=0.5), pos=[760, 1260], size=1.0),
         fx("lines_speed", A(26, word="河水"), dir="right", y0=1200, y1=1420)],
     camera=cam(pan(dx=80)))

shot("s45", A(26, word="直接"), "close",
     "知识：大水涌到晋阳城墙下，夯土墙的夹板印一层层被水盖住，只剩最上面三层露在水面上；右边的水位刻度涨到「三版」",
     bg=[L("props/gauge_wall_hi.png", [540, 1560], 1.0, [0.5, 1], w=1080)] +
        water(1500, 4, 1.0, 180, 30, rise={"at": D(0.1), "dur": 2.0, "ease": "smooth", "dpos": [0, -430]}),
     fx=[fx("progress", D(0.05), pos=[800, 860], title="水位", labels=["", "", "", "", "一版", "二版", "三版"], **{"from": 0.1, "to": 0.57})],
     camera=cam(push(0.03)))

shot("s46", A(27), "medium",
     "城里一口泡了水的灶，一只青蛙「噗」地跳进锅里，冲着镜头「呱呱」叫（笑点）",
     bg=ext_bg(1290, blur=5) + water(1180, 4, 0.8, 150),
     fg=[L("props/stove_flooded.png", [540, 1460], 1.0, [0.5, 1], h=900),
         L("props/frog_jump.png", [300, 700], 1.0, [0.5, 0.5], w=240,
           anim=[{"at": D(0.1), "dur": 0.45, "ease": "out", "dpos": [230, 300]}, {"at": D(0.55), "dur": 0.05, "alpha": 0.0}]),
         L("props/frog_croak.png", [560, 930], 1.0, [0.5, 1], w=300, alpha=0.0, anim=[{"at": D(0.55), "dur": 0.05, "alpha": 1.0}])],
     fx=[fx("splash", D(0.55), pos=[560, 1000], size=0.7), st_text("呱呱！", [840, 700], D(0.65), 120)],
     sfx=[{"name": "frog_croak", "at": D(0.7)}],
     camera=cam(push(0.05)))

shot("s47", A(28), "wide",
     "晋阳城头：赵襄子和百姓们站成一排，抱着胳膊一起摇头——没有一个人愿意投降（不画修堤，免得和后面挖开的堤混在一起）",
     bg=[sky()] + ridges(470, 640) + [L("sets/jinyang/wall.png", [540, 1500], 0.9, [0.5, 1], w=1528, repeat="x")] +
        [L("chars/folk_man_firm.png", [x, 1300], 0.9, [0.5, 1], h=460,
           anim=[{"at": D(0.3 + 0.1 * k), "dur": 0.25, "rot": -5}, {"at": D(0.55 + 0.1 * k), "dur": 0.25, "rot": 5}, {"at": D(0.8 + 0.1 * k), "dur": 0.25, "rot": 0}])
         for k, x in enumerate((150, 340, 780))] + water(1450, 3, 0.95, 150),
     actors=[P("zxz", "赵襄子", "chars/zxz_calm.png", [560, 1300], 500, "赵襄子双手拢袖站在城头，抬头望远处，镇定",
               acts=[act(D(0.5), "shake", dur=0.5)])],
     camera=cam(pan(dx=-60)))

shot("s48", A(29), "medium",
     "智伯去看水势：三人站在一辆两轮战车上，魏桓子握着缰绳驾车、韩康子也在车上；智伯（车头）张开双臂大笑：「原来水这么好用！」",
     bg=chariot_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_lookup.png", [195, 1330], 480, "韩康子站在车后头，腰板挺直"),
             P("wgh", "魏桓子", "chars/wgh_reins.png", [380, 1330], 480, "魏桓子在中间握着缰绳驾车"),
             P("zb", ZB, "chars/zb_b_cheer.png", [640, 1330], 500, "智伯站在车头，张开双臂仰头大笑，看着一片大水",
               acts=[act(A(29), "bounce"), act(A(29, word="原来"), "jump")])],
     fg=chariot_fg(),
     fx=[st_text("哈哈！", [900, 820], A(29, dt=0.1), 110)],
     camera=cam(push(0.03)))

shot("s49", A(29, word="能轻松"), "close",
     "智伯的近景：站在战车上，得意得张开双臂仰天大笑：「能轻松收拾一个国家！」",
     bg=[sky()] + ridges(520, 700, blur=4) + water(1180, 6, 0.6, 140, blur=4),
     actors=[P("zb", ZB, "chars/zb_b_cheer.png", [540, 1720], 1150, "智伯张开双臂，仰头哈哈大笑",
               acts=[act(A(29, word="国家"), "bounce")])],
     fg=[L("props/chariot_front.png", [700, 1652], 1.0, [0.5, 1], w=1700)],
     fx=[fx("lines_focus", A(29, word="国家"), center=[540, 790], clear=[540, 790, 450])],
     camera=cam(push(0.04)))

shot("s50", A(30), "medium",
     "笑点：魏桓子悄悄用胳膊肘碰韩康子，韩康子悄悄踩魏桓子的脚背（「！」连弹两下）；智伯一回头，两人立刻站得笔直，一起抬头看天",
     bg=chariot_bg(),
     actors=[P("hkz", "韩康子", "chars/hkz_lookup.png", [195, 1330], 480, "韩康子悄悄抬脚踩魏桓子的脚背，又马上装作看天",
               acts=[act(D(0.45), swap="chars/hkz_step.png"), act(D(1.2), swap="chars/hkz_lookup.png")]),
             P("wgh", "魏桓子", "chars/wgh_reins.png", [380, 1330], 480, "魏桓子悄悄用胳膊肘碰韩康子，又马上站得笔直",
               acts=[act(D(0.1), swap="chars/wgh_elbow.png"), act(D(1.2), swap="chars/wgh_reins.png")]),
             P("zb", ZB, "chars/zb_b_cheer.png", [640, 1330], 500, "智伯回过头，斜着眼一脸怀疑地看着车上那两个人",
               acts=[act(D(0.9), swap="chars/zb_b_glance.png", h=520)])],
     fg=chariot_fg(),
     fx=[st("exclaim", [0, 0], D(0.12), 90, follow="wgh", attach="head"),
         st("exclaim", [0, 0], D(0.47), 90, follow="hkz", attach="head"),
         st("sweat", [0, 0], D(1.2), 90, follow="hkz", attach="head")],
     camera=cam(push(0.03)))

shot("s51", A(31), "medium",
     "心声（嘴不动，小声画外音）：魏桓子后背冒冷汗，头上冒出想象泡泡：一座城，城边一条大河，河水正漫到城墙脚下（不标河名）",
     bg=[sky(blur=5)] + ridges(520, 700, blur=5) + water(1180, 3, 0.6, 140, blur=5),
     actors=[P("wgh", "魏桓子", "chars/wgh_stand_hi.png", [330, 1500], 640, "魏桓子站着握着缰绳，眼睛发直，心里偷偷发慌")],
     fx=[fx("bubble", D(0.05), img="props/bubble_river_city.png", pos=[470, 860], w=820),
         st("sweat", [0, 0], D(0.4), 90, follow="wgh", attach="head")],
     grade="tense",
     camera=cam(push(0.04)))

shot("s52", A(32), "medium",
     "心声：韩康子也冒冷汗，头上也冒出一个想象泡泡：他的城脚下也是一片水",
     bg=[sky(blur=5)] + ridges(520, 700, blur=5) + water(1180, 3, 0.6, 140, blur=5),
     actors=[P("hkz", "韩康子", "chars/hkz_stand_l.png", [720, 1500], 700, "韩康子（朝左）抱着地图卷，咬着牙，心里偷偷发慌")],
     fx=[fx("bubble", D(0.05), img="props/bubble_river_city.png", pos=[600, 830], w=820, flip=True),
         st("sweat", [0, 0], D(0.4), 90, follow="hkz", attach="head")],
     grade="tense",
     camera=cam(push(0.04)))

shot("s53", A(32, word="下一步"), "medium",
     "魏桓子和韩康子偷偷对视，两个想象泡泡「啵」地碰在一起：下一步，大水就该淹他们的城了",
     bg=[sky(blur=5)] + ridges(520, 700, blur=5) + water(1180, 3, 0.6, 140, blur=5),
     actors=[P("wgh", "魏桓子", "chars/wgh_stand_hi.png", [270, 1500], 600, "魏桓子朝右，偷偷看向韩康子"),
             P("hkz", "韩康子", "chars/hkz_stand_l.png", [780, 1500], 640, "韩康子朝左，偷偷看向魏桓子",
               acts=[act(A(32, word="淹"), "nod")])],
     fx=[fx("bubble", D(0.05), img="props/bubble_river_city.png", pos=[390, 900], w=520),
         fx("bubble", D(0.25), img="props/bubble_river_city.png", pos=[660, 900], w=520, flip=True),
         st_text("啵！", [540, 560], D(0.5), 110)],
     grade="tense",
     camera=cam(push(0.04)))

shot("s54", A(33), "wide",
     "深夜：月亮挂上，张孟谈撑着一只黑色小竹筏，神不知鬼不觉地划向韩、魏的营帐；竹筏尾巴上蹲着一只青蛙，他「嘘」地让青蛙别出声（笑点）",
     transition={"type": "fade_paper", "dur": 0.6},
     bg=camp_night(),
     actors=[P("zmt", "张孟谈", "chars/zmt_raft.png", [360, 1470], 460, "张孟谈披着黑布，弯腰撑着竹篙，悄悄往前划",
               anim=[{"at": D(0.0), "dur": 2.3, "ease": "linear", "dpos": [240, 0]}])],
     fg=[L("props/frog_wait.png", [110, 1400], 1.0, [0.5, 1], w=130, anim=[{"at": D(0.0), "dur": 2.3, "ease": "linear", "dpos": [240, 0]}])] +
        water(1440, 3, 1.0, 150),
     fx=[plate("张孟谈", "赵襄子派的人", "赵家", [850, 400], D(0.1), dur=2.2),
         st_text("嘘……", [640, 900], D(0.9), 100)],
     grade="cool",
     camera=cam(push(0.03)))

shot("s55", A(34), "close",
     "营帐里，张孟谈一手按住嘴唇、一手指着牙齿，恳切地说：「唇亡齿寒！」——嘴唇没了，牙齿就冷",
     bg=camp_night(),
     actors=[P("zmt", "张孟谈", "chars/zmt_hi_teeth.png", [540, 1940], 1100, "张孟谈披着黑布，一手按嘴唇、一手指牙齿，严肃恳切",
               acts=[act(A(34, word="赵家"), "nod")])],
     fx=[fx("smash", A(34, dt=0.02), text="唇亡齿寒", pos=[540, 520], size=190),
         st_text("好冷！", [880, 820], A(34, word="赵家"), 100, color="blue")],
     grade="cool",
     camera=cam(push(0.04)))

shot("s56", A(34, word="下一个"), "medium",
     "张孟谈站在中间告诉韩康子、魏桓子：赵家要是被智伯打败了，智伯下一个就要来收拾你们两家。身后赵家的旗子「扑通」倒下；韩康子、魏桓子头上各弹出一张纸条「下一个就是你」，两人吓得直冒汗",
     bg=night_bg(1400, wall=False) + [L("props/flag_zhao.png", [480, 1330], 0.8, [0.5, 1], h=560,
                                        anim=[{"at": D(0.1), "dur": 0.5, "ease": "in", "rot": -80, "dpos": [-60, 60]}]),
                                      L("props/flag_wei.png", [200, 1330], 0.8, [0.5, 1], h=560),
                                      L("props/flag_han.png", [790, 1330], 0.8, [0.5, 1], h=560)],
     actors=[P("zmt", "张孟谈", "chars/zmt_bow.png", [480, 1560], 520, "张孟谈抱着拳站在中间，恳切地劝韩、魏两家",
               acts=[act(A(34, word="你们两家"), "bounce")]),
             P("wgh", "魏桓子", "chars/wgh_nod.png", [220, 1560], 540, "魏桓子站着，手按胸口，紧张地听张孟谈说"),
             P("hkz", "韩康子", "chars/hkz_stand_l.png", [790, 1560], 600, "韩康子（朝左）抱着地图卷，咬着牙紧张地听张孟谈说")],
     fg=[fore()],
     fx=[st_text("赵家倒了", [560, 700], D(0.4), 80, color="red"),
         st_text("下一个就是你", [0, 0], A(34, word="下一个", dt=0.5), 64, color="red", follow="hkz", attach="head"),
         st_text("下一个就是你", [0, 0], A(34, word="你们两家"), 64, color="red", follow="wgh", attach="head")],
     grade="cool",
     camera=cam(push(0.04)))

shot("s57", A(35), "close",
     "三只手「啪」地紧紧叠在一起：韩家的靛蓝袖子、魏家的橙黄袖子、张孟谈的灰绿袖子，最上面还搭着一只青蛙的小手（笑点）",
     bg=camp_night(),
     fg=[L("props/hands_stack.png", [540, 950], 1.0, [0.5, 0.5], w=760, enter={"type": "pop", "at": D(0.0)})],
     fx=[st("pa", [850, 620], D(0.12), 120)],
     grade="cool",
     camera=cam(push(0.05)))

shot("s58", A(36), "medium",
     "张孟谈、魏桓子、韩康子三人齐声：「今晚，看咱们联手大反击！」身后韩、赵、魏三面旗子「唰」地并排立起来",
     bg=night_bg(1400, wall=False) + [L(img, [x, 1300], 0.7, [0.5, 1], h=560, enter={"type": "pop", "at": A(36, word="联手", dt=0.12 * k)})
                                      for k, (img, x) in enumerate((("props/flag_zhao.png", 200), ("props/flag_wei.png", 540), ("props/flag_han.png", 880)))],
     actors=[P("zmt", "张孟谈", "chars/zmt_bow.png", [230, 1520], 540, "张孟谈抱拳，恳切又坚定",
               acts=[act(A(36, word="反击"), "bounce")]),
             P("wgh", "魏桓子", "chars/wgh_nod.png", [500, 1520], 540, "魏桓子认真点头，手按胸口",
               acts=[act(A(36, word="反击"), "bounce")]),
             P("hkz", "韩康子", "chars/hkz_stand_l.png", [790, 1520], 580, "韩康子（朝左）咬着牙，下定决心",
               acts=[act(A(36, word="反击"), "bounce")])],
     fg=[fore()],
     fx=[fx("lines_radial", A(36, word="反击"), pos=[540, 900])],
     sfx=[{"name": "pop", "at": A(36, word="联手")}],
     grade="cool",
     camera=cam(push(0.04)))

shot("s59", A(37), "medium",
     "燃点（快切）：半夜，赵襄子站在城头用力一挥手：派人悄悄挖开土堤（只下命令，不画守堤的人）；远处堤上两个赵家的人举着青铜镐开挖",
     bg=night_bg(1420) +
        [L("chars/zhao_dig.png", [x, 1470], 0.5, [0.5, 1], h=300,
           anim=[{"at": D(0.1 + 0.1 * k), "dur": 0.2, "rot": 8}, {"at": D(0.3 + 0.1 * k), "dur": 0.15, "rot": -6}, {"at": D(0.45 + 0.1 * k), "dur": 0.2, "rot": 6}])
         for k, x in enumerate((790, 920))],
     actors=[P("zxz", "赵襄子", "chars/zxz_hi_order.png", [440, 1940], 1080, "赵襄子（原来的造型）右手用力往前一挥，坚定地下命令：夜里挖开堤",
               acts=[act(D(0.15), "bounce")])],
     fx=[fx("lines_speed", D(0.1), dir="right", y0=400, y1=900)],
     sfx=[{"name": "whoosh", "at": D(0.15)}],
     grade="cool",
     camera=cam(push(0.05)))

shot("s60", A(37, dt=1.0), "medium",
     "燃点：堤口「轰隆隆」裂开，大水改道，浪花卷成一条白色的纸龙（笑眯眯，不凶），掉头扑向智伯的军营",
     bg=[sky(True)] + ridges(560, 700) + [L("sets/camp/dike_breach.png", [540, 1300], 0.9, [0.5, 1], w=1040)] + water(1300, 4, 0.9, 150),
     fg=[L("props/wave_dragon.png", [400, 1400], 1.0, [0.5, 1], w=1400, alpha=0.0,
           anim=[{"at": D(0.1), "dur": 0.1, "alpha": 1.0}, {"at": D(0.1), "dur": 0.9, "ease": "out", "dpos": [420, -160]}])],
     fx=[fx("lines_radial", D(0.05), pos=[540, 1100]), st_text("轰隆隆！", [540, 560], D(0.1), 150)],
     sfx=[{"name": "whoomp", "at": D(0.1)}],
     grade="cool",
     camera=cam(push(0.06), shake(D(0.1), 0.4, 14)))

shot("s61", A(38, dt=-0.3), "wide",
     "燃点：大水冲垮智伯的营帐，帐篷东倒西歪，智伯的兵丢了兵器四散跑开（不画人被淹）",
     bg=camp_night()[:3] +
        [L("sets/camp/tent_big.png", [300, 1260], 0.5, [0.5, 1], w=560, anim=[{"at": D(0.25), "dur": 0.5, "ease": "in", "rot": 35, "dpos": [140, 40]}]),
         L("sets/camp/tent_s1.png", [720, 1250], 0.5, [0.5, 1], w=480, anim=[{"at": D(0.35), "dur": 0.5, "ease": "in", "rot": 40, "dpos": [120, 40]}]),
         L("chars/sold_run1.png", [420, 1400], 0.9, [0.5, 1], h=420, anim=[{"at": D(0.0), "dur": 1.2, "ease": "linear", "dpos": [420, 0]}]),
         L("chars/sold_run2.png", [200, 1420], 0.9, [0.5, 1], h=420, anim=[{"at": D(0.0), "dur": 1.2, "ease": "linear", "dpos": [380, 0]}])] +
        water(1300, 4, 0.8, 150),
     fg=[L("props/wave_dragon.png", [300, 1500], 1.0, [0.5, 1], w=1300, enter={"type": "slide_left", "at": D(0.0), "dur": 0.4}, anim=[{"at": D(0.4), "dur": 0.8, "ease": "out", "dpos": [500, -40]}])],
     fx=[fx("splash", D(0.4), pos=[760, 1220], size=1.0)],
     grade="cool",
     camera=cam(push(0.06), shake(D(0.35), 0.3, 12)))

shot("s62", A(38, dt=0.9), "medium",
     "智伯穿着满印「智」字的名牌睡衣、戴着睡帽，抱着一根浮木在水里扑腾划水，嘴里「噗」地喷水（只是泡在水里，不喊救命）；韩、魏的帅旗从左右两边、赵的帅旗从后面「啪、啪、啪」围上来（笑点，出糗的是智伯）",
     bg=[sky(True)] + ridges(560, 700) + water(1150, 2, 0.6, 140) +
        [L("props/flag_zhao.png", [540, 1180], 0.8, [0.5, 1], h=500, enter={"type": "pop", "at": D(0.5)}),
         L("props/flag_han.png", [150, 1300], 0.9, [0.5, 1], h=560, enter={"type": "pop", "at": D(0.25)}),
         L("props/flag_wei.png", [900, 1300], 0.9, [0.5, 1], h=560, enter={"type": "pop", "at": D(0.38)})],
     actors=[P("zb", ZB, "chars/zb_b_float.png", [540, 1360], 480, "智伯穿着满印「智」字的名牌睡衣和睡帽，趴在浮木上扑腾划水，鼓着腮帮喷出一小股水，一脸发懵",
               anim=[{"at": D(0.0), "dur": 0.9, "dpos": [0, -12]}, {"at": D(0.9), "dur": 0.9, "dpos": [0, 12]}])],
     fg=water(1330, 3, 1.0, 150),
     fx=[st_text("噗！", [880, 820], D(0.2), 110)],
     sfx=[{"name": "pop", "at": D(0.25)}, {"name": "pop", "at": D(0.38)}, {"name": "pop", "at": D(0.5)}],
     grade="cool",
     camera=cam(push(0.04)))

shot("s63", A(39), "close",
     "「曾经最不可一世的智伯」：回忆色（旧纸黄）里，智伯还是那个叉着腰、鼻孔朝天大笑的样子",
     transition={"type": "ink_wipe", "dur": 0.7},
     bg=ext_bg(1290, blur=6),
     actors=[P("zb", ZB, "chars/zb_hi_brand.png", [560, 1940], 1100, "智伯（回忆里）双手叉腰、鼻孔朝天大笑")],
     fx=[fx("sparkle", D(0.1), area=[100, 400, 980, 1300])],
     grade="memory",
     camera=cam(pull(0.05)))

shot("s64", A(39, word="彻底"), "medium",
     "开场那张落汤鸡照片又定格在画面上，大字「出局」像印章一样「咚」地盖上去（呼应开头）",
     bg=copy.deepcopy(hook_bg),
     actors=[P("zb", ZB, "chars/zb_b_soaked.png", [540, 1430], 900, "智伯浑身湿透，垂头丧气站着")],
     fg=[L("props/frog_wait.png", [560, 548], 1.0, [0.5, 1], w=190), fore()],
     fx=[fx("freeze", D(0.0), dur=1.3),
         fx("smash", A(39, word="出局"), text="出局", pos=[540, 1140], size=280, color="red", shake=12)],
     camera=cam(push(0.03)))

# ======================================================== 结尾：司马光点题
card_rows = [{"label": "聪明度", "stars": 5, "icon": "props/icon_speech.png"},
             {"label": "勇敢度", "stars": 5, "icon": "props/icon_resolve.png"},
             {"label": "才能", "stars": 5, "icon": "props/icon_qin.png"},
             {"label": "尊重", "stars": 0, "icon": "props/icon_heart.png"}]
shot("s65", A(40), "medium",
     "知识：回到书房，司马光低头看书；身旁「啪」地弹出智伯的属性卡（像游戏里的成绩单）：聪明度、勇敢度、才能都是满星，最后一行「尊重」一颗星都没有——0 分（出糗的是智伯）",
     transition={"type": "page_turn", "dur": 0.7},
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_read.png", [270, 1760], 780, "司马光低头看书，一根手指点在书页上")],
     fg=[desk()],
     fx=[fx("stat_card", D(0.05), name="智伯", rows=card_rows, pos=[690, 790], w=520, gap=0.45),
         st_text("0 分！", [870, 1030], D(2.3), 110, color="red")],
     camera=cam(push(0.03)))

shot("s66", A(41), "medium",
     "司马光按一下遥控器，笑呵呵地说：「我在《资治通鉴》里写过一句大实话」",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [300, 1760], 860, "司马光举着遥控器按了一下，笑呵呵",
               acts=[act(A(41, word="大实话"), "nod")])],
     fg=[desk()],
     fx=[fx("remote_click", D(0.15), pos=[547, 1296]),
         st_text("大实话", [800, 640], A(41, word="大实话"), 120)],
     camera=cam(push(0.04)))

shot("s67", A(42), "close",
     "知识（点题）：书页上浮出司马光的原话；「德」字走在前面领路，「才」字跟在后面（德者，才之帅也：好品德领着本事走）",
     transition={"type": "page_turn", "dur": 0.6},
     bg=[L("sets/study/book_page_hi.png", [0, 0], 1.0, w=1080)],
     fg=[L("props/char_de.png", [560, 1080], 1.0, [0.5, 0.5], w=300, anim=[{"at": D(0.8), "dur": 4.0, "ease": "linear", "dpos": [160, 0]}]),
         L("props/char_cai.png", [240, 1120], 1.0, [0.5, 0.5], w=270, anim=[{"at": D(1.0), "dur": 4.0, "ease": "linear", "dpos": [160, 0]}])],
     fx=[fx("big_title", A(42, dt=0.05), text="才者，德之资也；\n德者，才之帅也。", pos=[540, 600], size=110, deco="none")],
     camera=cam(push(0.03)),
     notes={"jev_allow": ["kid"], "why": "系列固定的点题：司马光念一句原文，下一句马上用白话（赛车和司机）再说一遍"})

shot("s68", A(43), "close",
     "书页上，一只戴小帽子的青蛙也跟在「才」字后面，一蹦一蹦地排队走（笑点）",
     bg=[L("sets/study/book_page_hi.png", [0, 0], 1.0, w=1080)],
     fg=[L("props/char_de.png", [740, 1080], 1.0, [0.5, 0.5], w=300, anim=[{"at": D(0.0), "dur": 1.3, "ease": "linear", "dpos": [50, 0]}]),
         L("props/char_cai.png", [420, 1120], 1.0, [0.5, 0.5], w=270, anim=[{"at": D(0.0), "dur": 1.3, "ease": "linear", "dpos": [50, 0]}]),
         L("props/frog_hat.png", [150, 1180], 1.0, [0.5, 0.5], w=190,
           anim=[{"at": D(0.1), "dur": 0.3, "ease": "out", "dpos": [50, -60]}, {"at": D(0.4), "dur": 0.3, "ease": "in", "dpos": [50, 60]},
                 {"at": D(0.7), "dur": 0.3, "ease": "out", "dpos": [50, -60]}, {"at": D(1.0), "dur": 0.3, "ease": "in", "dpos": [50, 60]}])],
     fx=[st_text("呱", [260, 960], D(0.4), 100)],
     sfx=[{"name": "frog_croak", "at": D(0.45)}],
     camera=cam(push(0.03)))

shot("s69", A(44), "close",
     "司马光笑眯眯地指着观众：「意思就是：才能——」大字「才能」砸下来",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_point.png", [540, 1760], 800, "司马光笑眯眯，伸出食指指着观众")],
     fg=[desk()],
     fx=[fx("smash", A(44, word="才能"), text="才能", pos=[540, 540], size=230)],
     camera=cam(push(0.03)))

shot("s70", A(44, word="就像"), "medium",
     "司马光头顶冒出想象泡泡（赛车只在泡泡里）：一条赛道上，一辆红色的高级赛车飞快地冲出起跑线，车身上写着「才能」",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [230, 1760], 700, "司马光举着遥控器，笑呵呵地看着泡泡")],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_race_track.png", pos=[370, 1000], w=820),
         st_text("才能", [610, 760], A(44, word="赛车"), 80, color="red"),
         fx("lines_speed", A(44, word="飞快"), dir="right", y0=700, y1=980)],
     camera=cam(push(0.03)))

shot("s71", A(45), "medium",
     "泡泡里是驾驶座特写：戴头盔的司机双手稳稳握住方向盘，胸口写着「人品和尊重」（金句）",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_finger.png", [240, 1720], 570, "司马光举起食指讲道理",
               acts=[act(A(45, word="司机"), "nod")])],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_race_driver.png", pos=[380, 1060], w=820),
         st_text("人品和尊重", [680, 1010], A(45, word="人品"), 60, color="red")],
     camera=cam(push(0.04)))

shot("s72", A(46), "medium",
     "金句大字卡「人品和尊重，才是握着方向盘的司机」砸下来停住，让孩子看清；司马光竖起大拇指",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_thumb.png", [540, 1700], 600, "司马光一手竖大拇指，笑眯眯",
               acts=[act(A(47), "bounce")])],
     fg=[desk()],
     fx=[fx("big_title", D(0.05), text="人品和尊重，\n才是握着方向盘的司机", pos=[540, 700], size=100, deco="rays")],
     camera=cam(push(0.03)))

shot("s73", A(47, word="越要"), "close",
     "司马光举着遥控器，认真地点点头：「越要握稳方向盘」",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_remote.png", [540, 1760], 860, "司马光举着遥控器，认真地点头",
               acts=[act(A(47, word="握稳"), "nod")])],
     fg=[desk()],
     fx=[st_text("握稳！", [840, 640], A(47, word="握稳"), 120)],
     camera=cam(push(0.04)))

shot("s74", A(47, word="不然"), "medium",
     "泡泡里：旁边一辆没握稳方向盘的蓝色小赛车「滋——」地滑出跑道，停在草地上，车顶冒出一个问号（没撞、没翻；笑点）",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_frown.png", [250, 1700], 560, "司马光捋着胡子，皱眉看着泡泡")],
     fg=[desk()],
     fx=[fx("bubble", D(0.05), img="props/bubble_race_track.png", pos=[370, 1000], w=820),
         st("question", [880, 740], A(47, word="冲出"), 90)],
     camera=cam(push(0.04)))

shot("s75", A(48), "medium",
     "知识（行动呼吁）：司马光捧着书冲镜头笑，三张小纸条一条条亮起来：「读历史」「懂大智慧」「做清醒人」",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_book.png", [270, 1700], 570, "司马光双手捧着书，笑着看观众",
               acts=[act(A(48, word="读历史"), "bounce"), act(A(48, word="懂大智慧"), "nod"), act(A(48, word="做清醒人"), "bounce")])],
     fg=[desk()],
     fx=[fx("checklist", A(48, word="读历史"), items=["读历史"], pos=[720, 640], w=440, mark="star"),
         fx("checklist", A(48, word="懂大智慧"), items=["懂大智慧"], pos=[720, 790], w=440, mark="star"),
         fx("checklist", A(48, word="做清醒人"), items=["做清醒人"], pos=[720, 940], w=440, mark="star")],
     camera=cam(push(0.03)))

shot("s76", A(49), "medium",
     "「点赞并收藏」：一颗大红心（点赞）和一颗金星星（收藏）按钮贴纸弹出来，一只青蛙跳上去按了一下（笑点）；司马光竖起大拇指",
     bg=study_bg(),
     actors=[P("sgm", SGM, "chars/sgm_thumb.png", [270, 1700], 600, "司马光竖起大拇指，笑眯眯",
               acts=[act(A(49, word="收藏"), "bounce")])],
     fg=[desk(),
         L("props/frog_jump.png", [920, 1350], 1.0, [0.5, 0.5], w=180, flip=True,
           anim=[{"at": A(49, word="收藏", dt=0.3), "dur": 0.45, "ease": "out", "dpos": [-230, -380]}])],
     fx=[st("heart", [680, 640], A(49, word="点赞"), 220),
         st("star", [860, 860], A(49, word="收藏"), 200)],
     camera=cam(push(0.04)))

shot("s77", A(49, word="带孩子"), "medium",
     "「什么叫德不配位」：智伯的属性卡又弹出来——本事三行满星，「尊重」一颗都没有；大字「德不配位」砸下来（本事大，人品和尊重跟不上）",
     bg=study_bg(blur=5),
     actors=[P("zb", ZB, "chars/zb_hi_brand.png", [280, 1900], 900, "智伯双手叉腰、鼻孔朝天大笑，还不知道自己哪里不及格")],
     fx=[fx("stat_card", D(0.05), name="智伯", rows=card_rows, pos=[730, 880], w=480, gap=0.3),
         fx("smash", A(49, word="德不配位"), text="德不配位", pos=[540, 470], size=170, color="red"),
         st_text("本事大，尊重跟不上", [700, 1260], A(49, word="德不配位", dt=0.6), 54, color="red")],
     camera=cam(push(0.03)))

shot("s78", A(50), "close",
     "司马光笑眯眯地指着观众：「关注我们，下一集带你看——」",
     bg=study_bg(blur=5),
     actors=[P("sgm", SGM, "chars/sgm_hi_point.png", [540, 1760], 800, "司马光笑眯眯，伸出食指指着观众",
               acts=[act(A(50, word="关注"), "bounce"), act(A(50, word="下一集"), "nod")])],
     fg=[desk()],
     fx=[st_text("关注！", [830, 620], A(50, word="关注"), 120), st("heart", [240, 640], A(50, word="下一集"), 130)],
     camera=cam(push(0.04)))

shot("s79", A(50, word="三家里"), "wide",
     "下集预告：整屏压暗，韩、赵、魏三面旗子并排站着，一面接一面抖一抖；一个大问号弹出来：三家里，谁最先强起来？",
     transition={"type": "iris", "dur": 0.7},
     bg=[sky(True)] + ridges(560, 700) + ground(1330) +
        [L(img, [x, 1420], 0.9, [0.5, 1], h=600,
           anim=[{"at": D(0.3 + 0.35 * k), "dur": 0.15, "rot": -6}, {"at": D(0.45 + 0.35 * k), "dur": 0.15, "rot": 5}, {"at": D(0.6 + 0.35 * k), "dur": 0.15, "rot": 0}])
         for k, (img, x) in enumerate((("props/flag_han.png", 240), ("props/flag_zhao.png", 540), ("props/flag_wei.png", 840)))],
     fg=[fore()],
     fx=[st("question", [540, 560], A(50, word="强起来"), 180)],
     grade="tense",
     camera=cam(push(0.04)))

shot("s80", A(51), "wide",
     "下集预告：魏家的旗子往前一步；下雨的树林边，雨点落在一套猎具上，一顶竹编斗笠从上面落下来：魏家一个神秘的「雨天约定」（只画雨、猎具和斗笠，不画魏文侯的脸）",
     transition={"type": "fade_paper", "dur": 0.6},
     bg=[L("props/teaser_rain.png", [0, 0], 1.0, w=1080)],
     fg=[L("props/flag_wei.png", [230, 1500], 1.0, [0.5, 1], h=640, enter={"type": "slide_left", "dur": 0.5}),
         L("props/douli.png", [720, 1150], 1.0, [0.5, 0.5], w=380, enter={"type": "drop", "at": A(51, word="雨天")})],
     fx=[fx("rain", D(0.0), dim=0.12)],
     camera=cam(push(0.05)))

CTA_WHY = "旁白对家长的行动呼吁（PITFALLS S25，Chris 定稿原话），台词里没有故事人物；由系列讲解人司马光在书房里出镜串场"
ALLOW = {
    "s11": {"jev_allow": ["meme"], "why": "「作死」是 Chris 09-30 明确同意用的孩子都懂的口语（PITFALLS S26），剧本原话，不是成人梗"},
    "s16": {"jev_allow": ["meme"], "why": "「小弱鸡」是 Chris 定稿剧本的原话：反派智伯嘲笑人的台词，用来表现他不尊重人；被取笑的人不当笑点（S19），这个词不上贴纸"},
    "s17": {"jev_allow": ["meme"], "why": "同 s16：「小弱鸡」是剧本原话，智伯嘲笑人的台词，不上贴纸"},
    "s41": {"jev_allow": ["meme"], "why": "「红温」是 Chris 09-30 明确同意用的口语（S26），剧本画面备注写着智伯瞬间「红温」"},
    "s56": {"jev_allow": ["kid"], "why": "台词里的「唇亡齿寒」是张孟谈的原话（通鉴「臣闻唇亡则齿寒」），这一句跨 s55、s56 两镜：s55 用砸字加「按嘴唇、指牙齿、好冷」的动作讲字面意思，s56 用赵家旗子倒下、韩魏头上「下一个就是你」纸条演出它的道理；Jev 两镜都拿到整句台词"},
    "s75": {"jev_allow": ["subject"], "why": CTA_WHY},
    "s76": {"jev_allow": ["subject", "kid"], "why": CTA_WHY + "；「德不配位」紧接着在 s77 用属性卡（本事满星、尊重 0 星）和字卡解释"},
}
for s in SH:
    if s["id"] in ALLOW:
        s["notes"] = ALLOW[s["id"]]

# 每个出场 / 飞进来的东西都配音效（精美标准：每个特效都有音效而且卡点）
EXTRA_SFX = {
    "s19": [{"name": "pop", "at": A(10, word="小蚂蚁", dt=0.1)}],
    "s26": [{"name": "whoosh", "at": A(14, word="交出")}, {"name": "plate_drop", "at": A(14, word="交出", dt=0.05)}],
    "s36": [{"name": "pop", "at": D(0.15)}],
    "s37": [{"name": "pop", "at": D(0.05)}],
    "s57": [{"name": "pop", "at": D(0.0)}],
    "s61": [{"name": "whoosh", "at": D(0.0)}],
    "s80": [{"name": "whoosh", "at": D(0.0)}, {"name": "pop", "at": A(51, word="雨天", dt=0.3)}],
}
for s in SH:
    if s["id"] in EXTRA_SFX:
        s.setdefault("sfx", []).extend(EXTRA_SFX[s["id"]])
    if s["id"] == "s05":
        s.setdefault("fx", []).append(fx("dust", D(0.8), mode="float", area=[80, 400, 1000, 1300]))
    if s["id"] == "s79":
        for k, layer in enumerate(x for x in s["bg"] if x["img"].startswith("props/flag_")):
            layer["sway"] = {"x": 0, "y": 5, "period": 2.4 + 0.3 * k, "phase": k}

sb = {
    "episode": "tj01", "no": 1, "name": "三家分晋",
    "title": ["最强的智伯，", "为什么一夜之间全部输光？"],
    "voice": "video/out/tj01_voice_g",
    "speakers": {"智伯": "智家", "智国": "智家", "韩康子": "韩家", "段规": "韩家", "魏桓子": "魏家", "赵襄子": "赵家", "张孟谈": "赵家"},
    "note": "tj01 G 版分镜表（剧本 G_尊重.json，配音 video/out/tj01_voice_g，全长 206.1 秒）。智伯一律用名牌造型（zb_hi_brand、zb_b_*）；赵襄子原来的造型；交领人物不翻转。素材见 video/stories/tj01/素材清单.md 的 G 版一节",
    "shots": SH,
}
OUT.write_text(json.dumps(sb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("shots", len(SH))
