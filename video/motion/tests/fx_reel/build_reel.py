"""生成「特效样片合集」的分镜表和配音时间线（阶段 B 交付物，给 reviewer 看的）：
    .venv/Scripts/python video/motion/tests/fx_reel/build_reel.py       → storyboard.json、voice/timeline.json
出片：
    .venv/Scripts/python video/motion/render.py video/motion/tests/fx_reel/storyboard.json --final --out video/out/motion/fx_reel
每个镜头演一个特效（2–3 秒；清单、属性卡、地图、考你这几个一步一步出的要长一点），下面一个小标签写特效名。配音只有三句现成的（考考你 / 最强的智伯 / 智伯有五样本事），用来试字幕。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- 背景和人物预设
RIDGES = [
    {"img": "sets/jin_land/sky.png", "depth": 0.05, "pos": [0, 0], "w": 1080},
    {"img": "sets/jin_land/ridge_far.png", "depth": 0.15, "pos": [0, 430], "w": 1080},
    {"img": "sets/jin_land/ridge_mid.png", "depth": 0.3, "pos": [0, 740], "w": 1080},
    {"img": "sets/jin_land/ridge_near.png", "depth": 0.45, "pos": [0, 830], "w": 1080},
]
BUSH = {"img": "sets/jin_land/fore.png", "depth": 0.9, "pos": [540, 1075], "anchor": [0.5, 0], "w": 1500, "repeat": "x"}


def strip(img, top, w, flip=False, depth=0.9, **kw):
    """一条横向的地带（草 + 土 / 水波），锚在上沿。"""
    return dict({"img": f"sets/jin_land/{img}.png", "depth": depth, "pos": [540, top], "anchor": [0.5, 0], "w": w, "repeat": "x", "flip": flip}, **kw)


# 晋地外景：远山 → 灌木丛 → 四条一条比一条大的草土带（近大远小）。每一条的上沿（草）盖住上一条的平切下沿：相邻两条的间距 = 上一条高度的 0.8，
# 所以从地平线一直铺到画面底，没有空带、看不到平切边；最后一条的下沿在画面外面。
TERRAIN = RIDGES + [BUSH, strip("ground", 1275, 1300), strip("ground", 1423, 1500, True), strip("ground", 1594, 1700), strip("ground", 1786, 1900, True)]
SKY = TERRAIN
# 河边：草土带 + 三条一条比一条大的水波，水波的上沿盖住上一条的下沿
WATER = RIDGES + [BUSH, strip("ground", 1275, 1300)] + [
    strip("water", 1400, 1500, depth=1.0, sway={"x": 16, "y": 4, "period": 3.2}), strip("water", 1543, 1650, depth=1.0, sway={"x": 20, "y": 4, "period": 3.6, "phase": 1.0}),
    strip("water", 1701, 1800, depth=1.0, sway={"x": 24, "y": 4, "period": 4.0, "phase": 2.0}), strip("water", 1873, 1800, depth=1.0)]
STUDY = [{"img": "sets/study/wall.png", "depth": 0.1, "pos": [-100, 0], "w": 1280}]
DESK = [{"img": "sets/study/desk.png", "depth": 1.0, "pos": [540, 1690], "anchor": [0.5, 1.0], "w": 1160}]

SGM = {"id": "sgm", "who": "司马光", "img": "chars/sgm_finger.png", "pos": [270, 1600], "h": 540}
ZB = {"id": "zb", "who": "智伯", "img": "chars/zb_hi_laugh.png", "pos": [640, 1660], "h": 980}
ZXZ = {"id": "zxz", "who": "赵襄子", "img": "chars/zxz_stand.png", "pos": [330, 1610], "h": 560}
HKZ = {"id": "hkz", "who": "韩康子", "img": "chars/hkz_low.png", "pos": [760, 1570], "h": 400, "flip": True}
SGM_HI = {"id": "sgmhi", "who": "司马光", "img": "chars/sgm_hi_remote.png", "pos": [270, 1500], "h": 780}

SPEECH = {   # 现成的配音：名字 → (说话人, 字幕, audio, series_audio, dur_raw, voiced_end, trim, 时间线里占多长)
    "kaokaoni": ("司马光", "考考你！", None, "audio/ceremony_kaokaoni.mp3", 2.088, 1.05, 0.89, 1.2),
    "zhibo": ("旁白", "最强的智伯，为什么输了？", "03.mp3", None, 2.64, 2.1, 0.39, 2.25),
    "wuyang": ("旁白", "智伯有五样本事，样样比别人强！", "04.mp3", None, 3.144, 2.63, 0.36, 2.78),
}

# 背景音乐从第 13 秒开始放：背景音乐自己每隔十几秒有一段 1–2 秒的空拍；13 秒是把「空拍 ∧ 没有音效 ∧ 没有配音」的总时长压到最小（9.75 秒，最长一段 1.0 秒）的起点
# （一次性算的，改了镜头顺序 / 增减镜头要重算）。
BGM_START = 13.0

SHOTS = []


def shot(name, dur, bg=None, actors=(), fx=(), fg=None, grade=None, transition=None, camera=None, speech=None, pre=0.0, note=None, sfx=()):
    """加一个镜头。name = 标签上写的名字；fx 里的 at 一律写相对镜头开头的秒数（dt）。"""
    SHOTS.append(dict(name=name, dur=dur, bg=bg or SKY, actors=list(actors), fx=list(fx), fg=fg, grade=grade, transition=transition, camera=camera,
                      speech=speech, pre=pre, note=note, sfx=list(sfx)))


def F(type_, dt=0.0, **kw):
    return dict(type=type_, at={"dt": dt}, **kw)


# ---------------------------------------------------------------- 一、漫画线
shot("漫画线：集中线 lines_focus", 2.4, actors=[ZB], fx=[F("lines_focus", 0.25, pos=[540, 900], clear=[540, 800, 300], dur=1.6)])
shot("漫画线：放射速度线 lines_radial", 2.4, actors=[ZB], fx=[F("lines_radial", 0.25, pos=[540, 900], dur=1.6)])
shot("漫画线：横向速度线 lines_speed", 2.4, actors=[dict(SGM, pos=[540, 1600], enter=None)], fx=[F("lines_speed", 0.2, dir="left", dur=1.7)])
# ---------------------------------------------------------------- 二、贴纸
shot("贴纸：问号 汗滴 怒气 感叹号 sticker", 2.8, actors=[SGM], fx=[
    F("sticker", 0.25, name="question", pos=[560, 700], size=300), F("sticker", 0.8, name="sweat", pos=[400, 1050], size=230),
    F("sticker", 1.3, name="anger", pos=[780, 1000], size=240, rot=8), F("sticker", 1.8, name="exclaim", pos=[300, 700], size=280, rot=-8)])
shot("贴纸：灯泡 星星眼 小心心 星星 sticker", 2.8, actors=[SGM], fx=[
    F("sticker", 0.25, name="bulb", pos=[440, 640], size=320), F("sticker", 0.8, name="star_eyes", pos=[760, 880], size=190),
    F("sticker", 1.3, name="heart", pos=[300, 860], size=210, rot=-10), F("sticker", 1.8, name="star", pos=[790, 560], size=250)])
shot("贴纸：咚 啪 嗖（拟声字） sticker", 2.8, actors=[SGM], fx=[
    F("sticker", 0.25, name="dong", pos=[520, 640], size=330), F("sticker", 0.85, name="pa", pos=[760, 1000], size=300, rot=8),
    F("sticker", 1.45, name="sou", pos=[380, 950], size=250, rot=-6), F("sticker", 2.0, name="question3", pos=[800, 640], size=210)])
# ---------------------------------------------------------------- 三、砸字
shot("砸字：本事（带震屏） smash", 2.6, actors=[SGM], fx=[F("smash", 0.05, text="本事", pos=[540, 780], dur=2.1)])
shot("砸字：五样本事（四个字） smash", 2.8, actors=[ZB], fx=[F("smash", 0.05, text="五样本事", pos=[540, 760], color="gold", dur=2.4)])
# ---------------------------------------------------------------- 四、清单、属性卡、地图
shot("清单：一条条弹出 checklist", 3.9, actors=[], speech=("wuyang", 0.15), fx=[F("checklist", 0.25, items=["个子高", "鬓发美", "射箭赶车样样行", "琴棋书画都会", "做事果断"], pos=[540, 560])],
     note="知识")
shot("属性卡：本事 ★★★★★ / 好心 ★ stat_card", 3.6, fx=[F("stat_card", 0.2, name="智伯", pos=[560, 860], w=820, rows=[
    {"label": "本事", "stars": 5, "icon": "props/icon_bow.png"}, {"label": "口才", "stars": 4, "icon": "props/icon_speech.png"},
    {"label": "好心", "stars": 1, "icon": "props/icon_heart.png"}])], actors=[dict(SGM, pos=[170, 1700], h=340)], note="知识")
shot("地图：纸地图 城标 虚线箭头 map", 3.8, fx=[
    F("map", 0.1, pos=[540, 900], w=960), F("map_city", 0.9, pos=[350, 640], name="晋阳", house="赵家"), F("map_city", 1.4, pos=[760, 1180], name="智家", house="智家"),
    F("map_arrow", 1.9, pts=[[720, 1120], [640, 930], [500, 780], [390, 690]], house="智家")], note="知识")
# ---------------------------------------------------------------- 五、氛围
shot("氛围：光芒 rays", 2.6, actors=[dict(ZB, enter="pop")], fx=[F("rays", 0.1, pos=[600, 1000], dur=2.2)])
shot("氛围：闪粉 sparkle", 2.6, actors=[dict(ZB)], fx=[F("sparkle", 0.1, area=[100, 400, 980, 1400], dur=2.2)])
shot("氛围：纸屑彩带（喷起）confetti", 3.0, actors=[SGM], fx=[F("confetti", 0.15, mode="burst")])
shot("氛围：纸屑彩带（飘落）confetti", 2.8, actors=[SGM], fx=[F("confetti", 0.1, mode="fall", dur=2.4, count=90)])
shot("氛围：灰尘（float 飘 / puff 扬起） dust", 2.8, actors=[dict(SGM, enter=None)], fx=[F("dust", 0.0, mode="float", dur=2.5), F("dust", 0.7, mode="puff", pos=[260, 1600], size=170)])
shot("氛围：雨 rain", 2.8, actors=[SGM], fx=[F("rain", 0.1, dur=2.4)])
shot("氛围：水花 splash", 2.6, bg=WATER, actors=[], fx=[F("splash", 0.3, pos=[540, 1480]), F("splash", 1.3, pos=[300, 1520], size=0.7)])
shot("氛围：纸剪火焰（放在画面两边，不挡人） flame", 2.8, actors=[dict(ZXZ, pos=[540, 1610])], fx=[
    F("flame", 0.15, pos=[150, 1640], w=240, height=340, dur=2.4), F("flame", 0.3, pos=[930, 1640], w=240, height=340, dur=2.3, sfx=None)])
# ---------------------------------------------------------------- 六、调色、颜色分段、闪白
shot("调色：回忆 grade: memory（旧纸黄 + 颗粒 + 暗角）", 2.6, actors=[SGM], grade="memory")
shot("调色：紧张 grade: tense（稍暗 + 暗角）", 2.4, actors=[ZB], grade="tense")
shot("颜色分段：金色（得意）→ 蓝色夜晚（密谋） tone", 3.4, actors=[ZB], fx=[F("tone", 0.0, tone="night", **{"from": "gold"}, delay=1.1, ramp=1.0)])
shot("柔和闪白（≤60%，3 帧） flash", 2.2, actors=[dict(ZB, enter="pop")], fx=[F("flash", 0.7), F("sticker", 0.7, name="exclaim", pos=[820, 620], size=290)])
# ---------------------------------------------------------------- 七、系列仪式和信息物
shot("考你：「考你！」按钮 + 倒计时圈 + 「看答案！」 kaoni", 6.4, actors=[], speech=("kaokaoni", 0.05), fx=[F("kaoni", 0.05, options=["给", "不给"], answer=1, end_stamp="揭晓")])
shot("进度物：水位刻度（变化时弹一下） progress", 3.4, actors=[dict(SGM, pos=[270, 1600])], fx=[
    F("progress", 0.1, pos=[720, 980], title="水位", labels=["", "一版", "二版", "三版"], **{"from": 0.2, "to": 0.7}, size=1.25)])
shot("人物卡（片尾收藏卡） person_card", 3.3, fx=[F("person_card", 0.1, img="chars/sgm_hi_remote.png", name="司马光", line="光爷爷讲通鉴，每集一张卡", no=1, pos=[540, 900], w=700)])
shot("人名牌：竖排大字 + 身份，家族颜色 name_plate", 3.0, actors=[dict(ZB, pos=[720, 1400], h=800)], speech=("zhibo", 0.15),
     fx=[F("name_plate", 0.3, name="智伯", role="智家老大", house="智家", pos=[150, 380])])
shot("游戏卡片：任务 card_quest", 2.4, fx=[F("card_quest", 0.1, text="守住晋阳", pos=[540, 820])])
shot("游戏卡片：任务失败 card_fail", 2.4, fx=[F("card_fail", 0.1, text="守不住了", pos=[540, 820])])
shot("游戏卡片：获得称号 card_title", 2.6, fx=[F("card_title", 0.1, text="最会忍的人", pos=[540, 820])])
shot("游戏卡片：本集 MVP card_mvp", 2.8, fx=[F("card_mvp", 0.1, text="赵襄子", pos=[540, 800])])
shot("大字标题：第 1 关：忍（光芒） big_title", 2.4, fx=[F("big_title", 0.1, text="第 1 关：忍", pos=[540, 820], deco="rays")])
shot("大字标题：水，倒过来了！（纸剪火焰） big_title", 2.6, fx=[F("big_title", 0.1, text="水，倒过来了！", pos=[540, 780], deco="flame")])
# ---------------------------------------------------------------- 八、解说台
shot("解说台：书房 + 纸屏幕 + 按遥控器 screen / remote_click", 3.8, bg=STUDY, fg=DESK, actors=[dict(SGM_HI, enter="pop")], fx=[
    F("screen", 0.4, img="props/map_silk.png", pos=[800, 700], w=540), F("remote_click", 1.6, pos=[520, 1150]),
    F("screen", 1.75, img="props/cup_plain_spill.png", pos=[800, 700], w=540)])
shot("想象泡泡（尾巴指着司马光的头，自动夹进安全区） bubble", 2.8, actors=[SGM], fx=[F("bubble", 0.3, img="props/cup_plain_spill.png", pos=[345, 1050], w=820)])
shot("书页边（考你时司马光从书页后探出来） page_edge", 3.0, bg=STUDY, actors=[], fx=[F("page_edge", 0.3, y=1200, dur=1.7, peek="chars/sgm_hi_remote.png", peek_h=880, peek_x=540)])
# ---------------------------------------------------------------- 九、转场（写在后一镜里，下面每个镜头都是「怎么进来的」）
shot("转场：翻书页 page_turn", 2.2, bg=STUDY, fg=DESK, actors=[SGM_HI], transition={"type": "page_turn"})
shot("转场：纸片擦过 paper_wipe", 2.2, actors=[ZB], transition={"type": "paper_wipe"})
shot("转场：墨笔刷 ink_wipe", 2.2, bg=STUDY, fg=DESK, actors=[dict(SGM_HI, enter=None)], transition={"type": "ink_wipe"})
shot("转场：圆圈收拢 iris", 2.2, actors=[dict(ZXZ, pos=[540, 1610])], transition={"type": "iris", "pos": [540, 1150]})
shot("转场：淡到纸色 fade_paper", 2.2, actors=[ZB], transition={"type": "fade_paper"})
shot("转场：甩镜 whip", 2.0, bg=STUDY, fg=DESK, actors=[dict(SGM_HI, enter=None)], transition={"type": "whip", "dir": "left"},
     fx=[F("screen", 0.05, img="props/map_silk.png", pos=[800, 700], w=540)])
shot("转场：解说台切进故事 tv_switch", 2.4, actors=[ZB], transition={"type": "tv_switch", "pos": [797, 663], "w": 408})
# ---------------------------------------------------------------- 十、新增（第一场样片 reviewer 提的特效层需求）
shot("贴纸：挂在人物身上 follow + 撕掉 exit tear", 3.2, actors=[dict(ZB, pos=[700, 1500], h=820, enter="pop", acts=[{"at": {"dt": 1.0}, "do": "jump"}, {"at": {"dt": 1.9}, "do": "shake"}])], fx=[
    F("sticker", 0.6, follow="zb", attach="head", name="anger", size=250), F("sticker", 0.9, follow="zb", offset=[-250, -640], name="sweat", size=200, dur=1.4, exit="tear")])
shot("系列音效：蛙叫 frog_croak / 哼 hmph / 亮起来 light_up（分镜表 sfx 里按名字用）", 3.2, actors=[{"id": "frog", "img": "props/frog_croak.png", "pos": [540, 1450], "h": 330, "enter": "pop"}], fx=[
    F("sticker", 0.35, name="exclaim", pos=[790, 1050], size=220, sfx=None), F("sticker", 1.25, name="anger", pos=[300, 1050], size=230, sfx=None),
    F("sticker", 2.05, name="bulb", pos=[540, 760], size=280, sfx=None)], sfx=[{"name": "frog_croak", "at": {"dt": 0.35}}, {"name": "hmph", "at": {"dt": 1.25}}, {"name": "light_up", "at": {"dt": 2.05}}])


# ---------------------------------------------------------------- 十一、tj01 新剧本要的三个特效（弹幕、定格、翻日历）
shot("弹幕：纸条从右往左飞过，避开人物的脸 danmaku", 4.6, actors=[dict(SGM, pos=[300, 1620], h=560)], fx=[
    F("danmaku", 0.2, texts=["给！", "不给！", "给！", "我选不给", "不给！", "给！"], dur=3.0, density=1.4)])
shot("定格：司马光按遥控器，画面停住，叠上弹幕 freeze", 5.0, bg=STUDY, fg=DESK, actors=[dict(SGM_HI, pos=[300, 1500], h=800)],
     camera=[{"move": "push", "amount": 0.07}], fx=[
    F("sticker", 0.4, name="sweat", follow="sgmhi", offset=[250, -720], size=190, sfx=None), F("remote_click", 1.1, pos=[480, 1150]),
    F("freeze", 1.2, dur=2.4), F("danmaku", 1.5, texts=["给！", "不给！", "给！", "不给！"], dur=1.6, density=0.9, area=[0, 420, 1080, 1100])])
shot("转场：翻日历（飞快往前倒翻，停在「战国」） calendar_flip", 3.0, actors=[dict(ZB, pos=[540, 1620], h=900)], transition={"type": "calendar_flip", "stop_text": "两千四百多年前 · 战国"})


# ---------------------------------------------------------------- 生成
def build():
    lines, shots = [], []
    t = 0.0
    total = len(SHOTS)
    for n, s in enumerate(SHOTS, 1):
        first = len(lines)
        t0 = t
        if s["speech"]:
            key, off = s["speech"]
            who, text, audio, series, dur_raw, voiced_end, trim, span = SPEECH[key]
            if off > 0:
                lines.append({"t0": round(t, 3), "t1": round(t + off, 3), "who": "动作", "text": "", "audio": None, "i": len(lines)})
                t += off
            ln = {"t0": round(t, 3), "t1": round(t + span, 3), "who": who, "text": text, "audio": audio, "dur_raw": dur_raw, "voiced_end": voiced_end, "trim": trim, "i": len(lines)}
            if series:
                ln["series_audio"] = series
            lines.append(ln)
            t += span
        end = round(t0 + s["dur"], 3)
        if end - t > 0.01:
            lines.append({"t0": round(t, 3), "t1": end, "who": "动作", "text": "", "audio": None, "i": len(lines)})
        t = end
        sh = {"id": f"R{n:02d}", "from": {"line": first}, "bg": s["bg"], "actors": s["actors"],
              "fx": s["fx"] + [{"type": "label", "text": f"{n} / {total}  {s['name']}", "at": {"dt": 0}}]}
        if s["fg"]:
            sh["fg"] = s["fg"]
        if s["grade"]:
            sh["grade"] = s["grade"]
        if s["transition"]:
            sh["transition"] = s["transition"]
        if s["camera"]:
            sh["camera"] = s["camera"]
        if s["note"]:
            sh["note"] = s["note"]
        if s["sfx"]:
            sh["sfx"] = s["sfx"]
        shots.append(sh)
    for sh in shots:
        for a in sh["actors"]:
            if a.get("enter") is None:
                a.pop("enter", None)
    sb = {"episode": "fx_reel", "no": 0, "title": ["特效样片合集，", "每个特效 2–3 秒"], "name": "特效样片", "voice": "video/motion/tests/fx_reel/voice", "bgm_start": BGM_START,
          "note": "阶段 B 交付：特效包的全部特效和转场各演一遍。build_reel.py 生成本文件，别手改。", "shots": shots}
    (HERE / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "voice" / "timeline.json").write_text(json.dumps({"duration": round(t, 3), "lines": lines}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{total} 个镜头，{t:.1f} 秒，{len(lines)} 条时间线 → {HERE / 'storyboard.json'}")


if __name__ == "__main__":
    build()
