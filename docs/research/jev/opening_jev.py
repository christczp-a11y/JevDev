"""第 1 集开头 0–5 秒：15 个用司马光的方案 + 现版本 + 2 个反面对照，让 Jev 打分、两两对比（正反各问一次）。

用法（仓库根目录）：.venv/Scripts/python docs/research/jev/opening_jev.py
"""
import itertools
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jevdev import jev  # noqa: E402

ep = json.loads((ROOT / "video/stories/ep01/episode.json").read_text(encoding="utf-8"))
EPISODE = {"core_question": ep["core_question"], "source": ep["source"], "pitfalls": ep["pitfalls"]}
HOST = ("司马光：《资治通鉴》的作者，这个系列每一集的讲解人，Q 版老爷爷。紫色宋代官服，头戴两侧伸出长帽翅的黑色官帽（剪影像「T」字），"
        "粗灰眉、短胡子；小时候砸缸救人的故事孩子都知道；随身一个圆木「警枕」（睡着了枕头一滚就惊醒）。账号叫「光爷爷的资治通鉴大冒险」，头像就是他")
STORY = ("正片：秦国都城集市南门立起一根 7 米高的木杆，悬赏十金搬到北门，没人敢搬；加到五十金，一个小伙搬了，当场拿到五十金；"
         "商鞅借此让全城相信新法说到做到；后来太子犯法，太子的两位老师受罚；十年后秦国大治。中途 4 次「考你」让观众选择。"
         "结尾司马光正式亮相点题「说话算数，是最大的宝贝」，再回到现代：答应同桌的漫画书第二天带来了")

# 每个方案：0–1 秒 / 1–3 秒 / 3–5 秒（画面 + 声音 + 台词）
OPEN = {
    "B0 现版本（商鞅冷开场 + 小豆子考你，司马光不出现）": [
        "7 米高的木杆「咚」地从地里竖起来，告示弹出；商鞅大喊：「谁把这根木头搬到北门——」",
        "「赏十金！」秦国集市南门，人群张望",
        "小豆子（Q 版小孩）对着镜头：「考你：你搬不搬？」屏幕弹出【搬】【不搬】两个大按钮和倒计时"],
    "V1 警枕惊醒": [
        "黑底，「咚！」一个圆木枕头滚到镜头前；司马光猛地惊醒，帽翅一抖",
        "司马光：「哎呀，差点睡过头！」一把翻开大书，书页里「咚」地竖起一根 7 米高的木杆",
        "司马光指着木杆：「就是这根木头，让整个秦国开始守规矩！」"],
    "V2 爷爷考孙子（司马光考你）": [
        "司马光从书页里「啪」地弹出来，食指直指镜头：「考考你！」",
        "他身后 7 米木杆「咚」地竖起，告示弹出「搬到北门，赏十金」",
        "司马光：「搬根木头就给十金，你搬不搬？」屏幕弹出【搬】【不搬】和倒计时"],
    "V3 先抛怪事": [
        "金块哗啦啦砸满屏幕，司马光从金块堆里探出头，扶正帽子",
        "司马光：「我书里记过一件怪事——」",
        "镜头转到集市：木杆旁一个人都没有。司马光：「搬根木头就给十金，全城竟然没一个人敢搬！」"],
    "V4 结果前置": [
        "慢动作：一个小伙抱着 7 米木杆冲过北门，金块落进他怀里",
        "司马光从画面角落的书页里探出头：「他只是搬了根木头，就拿了五十金。」",
        "画面定格。司马光：「凭什么？别急，我从头讲。」"],
    "V5 砸缸认人": [
        "「哐啷！」一口大水缸碎开，水喷出来",
        "碎片中间站着司马光，帽翅上挂着水珠：「对，砸缸的就是我！」",
        "司马光翻开大书：「长大后我写了本书，里面有件更怪的事——搬根木头，给五十金！」"],
    "V6 猜猜我是谁（剪影游戏）": [
        "纸幕后面一个「T」字形帽翅剪影和一个大问号，音效「叮咚」",
        "画外音：「猜猜我是谁？提示：我小时候砸过缸！」",
        "纸幕拉开，司马光笑：「答对啦！今天考你一道题——搬根木头给十金，你搬不搬？」"],
    "V7 司马光自己搬不动": [
        "司马光抱着一根 7 米木杆，脸憋得通红，帽翅乱晃",
        "「哎哟我的老腰！」木杆「咚」地倒下，他一屁股坐在地上",
        "司马光指着镜头：「这木头谁搬得动？搬到北门，赏十金！你来不来？」"],
    "V8 和商鞅抬杠": [
        "商鞅站在木杆旁大喊：「谁把这根木头搬到北门，赏十金！」",
        "司马光从书页边探出头打断：「别信他——」商鞅瞪了他一眼",
        "司马光挠头：「……哦不对，这回好像可以信？到底信不信？你说呢！」"],
    "V9 生活代入（同桌不信你）": [
        "现代教室，同桌扭头：「哼，你说话不算数！」头顶一颗心「咔」地裂开",
        "司马光从课桌上的书里弹出来：「被人不信的滋味，不好受吧？」",
        "司马光翻书：「两千多年前，有个大官最怕的就是：说了话，没人信。」"],
    "V10 3 秒倒计时挑战": [
        "屏幕中间一个大大的「3」，司马光双手一拍：「3 秒抢答！」",
        "7 米木杆「咚」地竖起，告示「搬到北门，赏十金」",
        "司马光：「你搬不搬？3、2、1！」【搬】【不搬】按钮闪烁"],
    "V11 巨书奇观（1362 年）": [
        "一本巨大的书「砰」地落地，书页哗哗翻，纸片人物一个个弹起来",
        "司马光站在书顶：「1362 年的故事，我写了 19 年！」",
        "书停在一页，木杆「咚」地竖起：「今天这一页最怪——搬根木头，给五十金！」"],
    "V12 表情包反应": [
        "司马光特写：眼睛瞪圆、胡子炸开：「什么？！」",
        "镜头拉远：他面前的告示写着「搬木头，赏五十金」",
        "司马光：「搬根木头给五十金？这里面肯定有事！」"],
    "V13 课堂抽查": [
        "「啪！」司马光用书拍了一下讲台：「上课！」",
        "司马光：「今天这道题，全秦国没人敢答——」身后木杆「咚」地竖起",
        "司马光：「搬根木头给十金，你搬不搬？」"],
    "V14 冷开场 + 帽翅剪影悬念": [
        "7 米高的木杆「咚」地竖起，告示弹出；商鞅：「谁把这根木头搬到北门——赏十金！」",
        "小豆子对着镜头：「考你：你搬不搬？」【搬】【不搬】按钮",
        "书页边只露出一个「T」字帽翅剪影和一只手，画外音：「这事啊，我写在书里了。」"],
    "V15 冷开场 + 司马光接过考你": [
        "7 米高的木杆「咚」地竖起，告示弹出；商鞅：「谁把这根木头搬到北门——赏十金！」",
        "司马光从书页边探出半个身子，食指指着镜头：「考考你——」",
        "司马光：「你搬不搬？」屏幕弹出【搬】【不搬】和倒计时"],
    "C1 对照：自我介绍开场": [
        "司马光站在书房里微笑挥手",
        "司马光：「大家好，我是司马光，《资治通鉴》的作者。」",
        "司马光：「今天给小朋友们讲一个徙木立信的故事。」"],
    "C2 对照：交代背景开场": [
        "一张战国地图慢慢展开",
        "旁白：「战国时期，秦孝公任用商鞅变法。」",
        "旁白：「为了让百姓相信新法，商鞅想了一个办法。」"],
}

Q = {
    "hook": {"type": "score", "instructions": "只看 `opening`（0–5 秒）的台词和画面：它给刷到这条视频的孩子和家长多强的「继续看下去」的理由？",
             "criteria": ["开头是年代、人物或背景介绍（如「东汉末年，曹操有个儿子叫曹冲」）",
                          "开头点明了主题，但没有提出问题（如「今天讲曹冲称象的故事」）",
                          "开头提出了问题，但问题抽象、和观众无关（如「曹冲为什么这么聪明？」）",
                          "开头是一个具体的怪事，或和观众生活有关的问题（如「一头大象有多重？那时候可没有这么大的秤」）",
                          "开头把具体的怪事和观众自己的切身问题连在一起（如「你能称出一头大象吗？一个六岁小孩做到了，大人们都没想到」）"]},
    "s_stop": {"type": "score", "instructions": "只看 `opening` 的第一段（0–1 秒）：一个正在快速往上划视频的 7 岁孩子，手指停下来的可能有多大？",
               "criteria": ["静止或普通的画面，只有人在说话", "画面有动作，但很常见", "有明显的动作或声音变化",
                            "一个让人意外的画面或声音（大东西砸下来、东西碎了、角色突然弹出来）",
                            "意外的画面和声音，同时有角色直接对着观众（指着镜头或提问）"]},
    "s_host": {"type": "score", "instructions": "看完 `opening`，观众对讲解人 `host` 的印象是？",
               "criteria": ["讲解人完全没出现", "出现了，但看不出他是谁、和故事什么关系", "能看出有一个讲故事的人",
                            "能认出是司马光，知道他是讲这个故事的人",
                            "司马光的形象和一个好玩的记忆点（动作、口头禅、剪影）一起留在脑子里，下次看到帽翅就能认出来"]},
    "s_clarity": {"type": "score", "instructions": "6–8 岁的孩子在 5 秒内能不能看懂 `opening` 里发生了什么、要他想什么？",
                  "criteria": ["完全看不懂", "要想一会儿才懂一部分", "大概懂", "懂", "一眼就懂"]},
    "s_parent": {"type": "score", "instructions": "陪孩子看的家长看到 `opening`，觉得有意思、愿意让孩子继续看的程度",
                 "criteria": ["反感（太吵、太低幼或说教）", "无感", "还行", "有意思", "家长自己也被逗笑或被勾起好奇"]},
    "n_intro": {"type": "noul", "instructions": "`opening` 的前 3 秒（前两段）主要在打招呼、自我介绍、报题目或交代时代背景，而不是一个怪事、冲突、奇观或直接抛给观众的问题"},
    "n_accuracy": {"type": "noul", "instructions": "`opening` 把史料里没有的内容当成历史事实来讲、和 `episode.source` 矛盾，或者踩了 `episode.pitfalls` 里的任何一条（讲解人司马光穿越出场、明显的玩笑、现代梗、比喻都不算）"},
    "n_unsafe": {"type": "noul", "instructions": "`opening` 里有不适合 6 岁孩子的内容：血腥、残酷刑罚的具体描写、恐怖画面或粗口"},
    "n_promise": {"type": "noul", "instructions": "`opening` 让观众期待看到的东西，在后面的 `story_after` 里没有兑现，或者和正片跑题"},
}
PAIR_Q = {
    "p_keep": {"type": "choice", "instructions": "同一集视频（`story_after`）有两个开头 `a` 和 `b`。一个 7 岁孩子刷到，看完前 3 秒后更可能继续看下去的是哪个？",
               "criteria": {"a": "开头 a", "b": "开头 b"}},
    "p_series": {"type": "choice", "instructions": "看完开头 `a` 和开头 `b`，哪一个更能让观众记住讲解人 `host`，下次刷到这个系列时认出来？",
                 "criteria": {"a": "开头 a", "b": "开头 b"}},
    "p_parent": {"type": "choice", "instructions": "陪孩子看的家长，看到哪个开头更愿意让孩子看完、自己也想关注这个账号？",
                 "criteria": {"a": "开头 a", "b": "开头 b"}},
}
SEG = ["0–1 秒", "1–3 秒", "3–5 秒"]


def opening(k):
    return dict(zip(SEG, OPEN[k]))


def score(k):
    ans, _ = jev.ask({"episode": EPISODE, "host": HOST, "story_after": STORY, "opening": opening(k)}, Q)
    return k, jev.flatten(ans)


def comp(f):
    base = (f["hook"] + f["s_stop"] + f["s_host"] + f["s_clarity"] + f["s_parent"]) / 5
    return base - 2 * f["n_intro"] - 2 * f["n_accuracy"] - 3 * f["n_unsafe"] - 1.5 * f["n_promise"]


with ThreadPoolExecutor(8) as ex:
    scores = dict(ex.map(score, OPEN))
rows = sorted(scores.items(), key=lambda kv: -comp(kv[1]))
print(f"{'方案':<34} 综合  钩子 停手 讲解人 看懂 家长 | 自我介绍 史实 不宜 跑题")
for k, f in rows:
    print(f"{k:<34} {comp(f):5.2f}  {f['hook']:.2f} {f['s_stop']:.2f} {f['s_host']:.2f} {f['s_clarity']:.2f} {f['s_parent']:.2f} | "
          f"{f['n_intro']:.2f} {f['n_accuracy']:.2f} {f['n_unsafe']:.2f} {f['n_promise']:.2f}")

top = [k for k, _ in rows if not k.startswith("C")][:6]
if not any(k.startswith("B0") for k in top):
    top.append(next(k for k in OPEN if k.startswith("B0")))   # 现版本一定参加两两对比


def pair(ab):
    a, b = ab
    st = {"host": HOST, "story_after": STORY}
    r1, _ = jev.ask({**st, "a": opening(a), "b": opening(b)}, PAIR_Q)
    r2, _ = jev.ask({**st, "a": opening(b), "b": opening(a)}, PAIR_Q)
    f1, f2 = jev.flatten(r1), jev.flatten(r2)
    return a, b, {q: (f1[f"{q}=a"] + f2[f"{q}=b"]) / 2 for q in PAIR_Q}


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(pair, itertools.combinations(top, 2)))
win = {k: {q: 0.0 for q in PAIR_Q} for k in top}
for a, b, p in res:
    for q, v in p.items():
        win[a][q] += v
        win[b][q] += 1 - v
m = len(top) - 1
print(f"\n两两对比（{m} 场平均胜率）：继续看 / 记住讲解人 / 家长")
for k in sorted(top, key=lambda k: -sum(win[k].values())):
    print(f"{k:<34} {win[k]['p_keep'] / m:.2f} / {win[k]['p_series'] / m:.2f} / {win[k]['p_parent'] / m:.2f}")
(Path(__file__).parent / "opening_result.json").write_text(
    json.dumps({"scores": scores, "top": top, "pairs": res, "win": win}, ensure_ascii=False, indent=1), encoding="utf-8")
