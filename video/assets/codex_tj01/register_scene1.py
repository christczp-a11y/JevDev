"""tj01 第 5 步（第一场）：把第一场拆出来的图登记进 video/assets/REGISTRY.md（幂等：已登记的跳过，文件还没画好的也跳过）。

  .venv/Scripts/python video/assets/codex_tj01/register_scene1.py

只登记第一场这几张，不动别人的（register_tj01.py 会把 SETS 里的老书房也登记上，所以这里不用它）。
朝向是逐张看图定的（PITFALLS T13、T25）；尺寸从文件里读；屏幕显示上限 = 原图 × 1.3（规则：显示 ÷ 原图 ≤ 1.3）。
"""
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
REG = ASSETS / "REGISTRY.md"
sys.stdout.reconfigure(encoding="utf-8")

# 路径: (属于, 朝向, 备注, 范围)
CHARS = {
    "chars/sgm_hi_point.png": ("司马光 `sgm_`", "正面", "**高清半身特写**：正面，笑眯眯，食指指向观众（开场、每次「考你」），另一手叉腰，帽翅完整；圆领", "系列"),
    "chars/sgm_hi_read.png": ("司马光 `sgm_`", "右", "**高清半身特写**：低头看书、一根手指点在书页上讲解（第 81 句）；圆领；3/4，脸和视线朝右下", "系列"),
    "chars/sgm_hi_shock.png": ("司马光 `sgm_`", "右", "**高清半身特写**：刚被吓醒，眼睛圆睁（瞳孔往左瞟）、眉毛竖起、一手扶帽子；圆领；头 3/4 朝右", "系列"),
    "chars/zgo_shadow.png": ("智果 `zgo_`", "右", "**皮影**（前史，第 5–9 句）：整个人拼好，纯侧面朝右，站得笔直、一手前举掌心向前（阻拦）、另一手在身侧；透光的赭红皮子、镂空云纹回纹、铆钉；带两根竹签操纵杆（一根接在放下的手上、一根接在举起的手腕上，都垂到图的底边；幕布下沿的红布帘可以盖住）；交领右衽、小冠；拆开的部件没登记（动态漫画不用）", "tj01"),
    "chars/zxu_shadow.png": ("智宣子 `zxu_`", "右", "**皮影**（前史，第 5–9 句）：智宣子（智瑶的父亲），老、驼背、白长须、拄木杖，纯侧面朝右；透光的赭红皮子、镂空花纹；带两根竹签操纵杆（左上那根被原图左边缘截断，是斜着的一根直线，可以用布帘或画外盖住）；原图里胳膊和竹签之间被抠成了一块棕色半透明的光晕，已挖掉（`split_scene1.py` 的 `fix_zxu`）；拆开的部件没登记", "tj01"),
    "chars/zb_shadow_young.png": ("智伯 `zb_`", "右", "**皮影**（前史第 5 句）：年轻时的智伯，纯侧面朝右，挺胸昂头、下巴抬高、迈半步；又长又亮的乌黑鬓发垂到胸前；赭红透光皮子的交领右衽长袍、领口袖口墨黑边加金回纹、小冠加一条飘起的红缨；一手握一张小木弓垂在身侧（不搭箭、不对人）；一整个人，没有竹签、没有拆开的部件；镂空处是透明的（叠在幕布上会透出幕布的光）；场景里翻过来朝左对着爸爸时在分镜表里翻转", "tj01"),
}
PROPS = {
    "props/frog_wait.png": ("正面", "青蛙（全集笑点担当）：蹲着，脸正对观众、歪头等你；嫩绿身、浅黄肚"),
    "props/frog_croak.png": ("右", "青蛙「呱！」：鸣囊鼓圆、嘴张开，头顶右边两道黄色小火花（已并进图里）"),
    "props/frog_tongue.png": ("右", "青蛙伸出长长粉红舌头，舌尖卷起"),
    "props/frog_wave.png": ("右", "青蛙举一条前腿挥手"),
    "props/frog_shoe.png": ("右", "青蛙两前腿抱着一只小草鞋（第 48 句「提着他的鞋跟在后面」）；草鞋是编织草鞋，无字"),
    "props/frog_hat.png": ("右", "青蛙戴迷你黑色小冠（有红缨），神气（第 82 句「船头的青蛙也戴上帽子」）"),
    "props/frog_flat.png": ("正面", "青蛙被踩扁：贴在地上、脸正对观众、眼睛转圈，头顶三颗黄色小星星（已并进图里；第 64 句被踩）"),
    "props/frog_jump.png": ("右", "青蛙跳在空中，四肢舒展，头朝右"),
    "props/hand_grab.png": ("右", "智伯的大手：**赭红**宽袖口（墨黑边、金线）伸出，五指张开向右前方抓（一只大手去抓地图，第 1、20 句）"),
    "props/hand_open.png": ("右", "智伯的大手：赭红袖口，手心向上摊开要东西（第 36 句）"),
    "props/ant.png": ("右", "一只小黑蚂蚁，侧面朝右（第 14、18 句：爬上智伯的鞋）"),
    "props/towel.png": ("正面", "白棉布手巾，折成长方形，蓝边（现代，只用在解说台屏幕里）"),
    "props/cup_plain.png": ("正面", "白色陶瓷马克杯，立着，杯耳在右（现代，只用在想象泡泡或屏幕里；无方向）"),
    "props/cup_plain_spill.png": ("左", "同一个马克杯倒下，杯口朝**左**，水（蓝纸片）向左流成一滩（现代；只用在屏幕里）"),
    "props/gauge_wall_hi.png": ("正面", "**高清**夯土城墙正面特写（竖版，第 3、54 句：特写数「三版」）：7 层夹板印（每层一整条夯土、横缝上一排方孔），顶上一排垛口；没有字、数字、刻度线；水用 sets/jin_land/water 盖上去；左右两边没有白纸边（按整幅宽度铺满屏幕用，左右各超出约 4 像素）"),
    "props/icon_bow.png": ("正面", "图标贴纸「射御」：弓、箭、木车轮；圆形米黄底"),
    "props/icon_qin.png": ("正面", "图标贴纸「才艺」：古琴加毛笔；圆形米黄底"),
    "props/icon_heart.png": ("正面", "图标贴纸「好心」：红色爱心；圆形米黄底（金句卡里第六格是暗的，用亮度压暗）"),
    "props/plaque_zhi.png": ("正面", "木牌正面：一个「智」字加赭红菱形（本图唯一带字的素材：「智」字是画进去的）；第 6、73 句"),
    "props/plaque_back.png": ("正面", "木牌背面：空白，只有木纹（第 6、73 句）"),
    "props/icon_look.png": ("正面", "图标贴纸「个子高、鬓发美」：一缕又长又亮的乌黑鬓发（系红带）、一把木梳、一颗金黄闪光星；Q 版纸艺，圆形米黄底、白纸边；替掉停用的 icon_tall（写实线描）"),
    "props/icon_speech.png": ("正面", "图标贴纸「口才好、会写文章」：一卷摊开的竹简，上面飘出三个空白的圆形对话泡泡（泡泡里没有字）；圆形米黄底；替掉停用的 icon_mouth"),
    "props/icon_resolve.png": ("正面", "图标贴纸「果断」：Q 版握紧的拳头从赭红袖口（墨黑边、金色回纹）伸出，旁边三道动作线；圆形米黄底；替掉停用的 icon_fist"),
    "props/stove_flooded.png": ("正面", "泡在水里的战国陶灶（第 0、55 句）：土黄陶土灶身、正面半圆灶门（灶门里黑洞洞，没有火）、灶面一口**灰黑**陶釜（一圈三角纹，不冒热气）；灶身下半截泡在三层蓝绿波浪纸片里，灶门淹了一半，水上两片小落叶；水面左右两端和底边是平直的切边（已补白纸边）；不画青蛙（青蛙用 frog_*，从灶门里跳出来）；替掉停用的 props/stove"),
    "props/bubble_nickname.png": ("正面", "椭圆小画面（想象泡泡里的画，第 12 句古今对照 1「给同学起外号」）：现代小学教室，蓝白校服、红领巾；**左**大个子男生站着朝**右**、伸长胳膊指着右边、张大嘴喊（大大咧咧，不凶）；**右**瘦小男生坐在课桌后朝**左**、低着头缩着肩、眼角一滴泪；后面两个同学皱眉摇头，没有人笑；黑板空白；外面是透明底、边缘一圈白纸边；图里的小孩是现代的，只能放在泡泡里；不翻转"),
}
SETS = {
    "sets/shadow/screen.png": ("布景 shadow（皮影戏幕布，前史用）", "正面", "皮影戏幕布（竖版整张不透明，第 5–9 句）：正中一大块发光的米黄色半透明幕布，中间最亮、四角琥珀色变暗，四边深褐色木框（榫卯拼角），下沿垂一截暗红色布帘；幕布上什么都不画，皮影人另外叠上去；1024×1536 铺满 1920 高放大 1.25，推镜不要超过 1.04 倍"),
    "sets/lantai/banquet_row.png": ("布景 lantai", "正面", "蓝台宴席一长排矮案（宴会中景，第 10–18 句）：正面略俯视，3 张黑漆红边矮案一字排开，每张案上两只红黑漆耳杯加一小盘黄色果子，每张案**后面**（画面上方）铺一块编织草席（人跪坐在草席上，图叠在这张图上面，人的膝盖对齐案的后沿）；不画人、不画爵、不画椅子；三张案之间是透明的，可以拆开单用；宽 1970，按 1080 屏宽用时缩小，不会放大"),
}
PEOPLE_ROW = ("智宣子（智瑶的父亲，只在前史里出现）", "`zxu_`", "tj01", "皮影：老、驼背、白长须、拄木杖，赭红透光皮子；只有皮影，没有彩色姿势图", "—（皮影另定）", "定稿")


def size_of(rel):
    im = Image.open(ASSETS / rel)
    return im.width, im.height


def limit_note(rel):
    w, h = size_of(rel)
    return f"（原图 {w}×{h}，屏幕显示不超过 {int(w * 1.3)}×{int(h * 1.3)}）"


def main():
    md = REG.read_text(encoding="utf-8")
    lines = md.split("\n")
    registered = set(re.findall(r"^\| `((?:chars|props|rig|sets|brand)/[^`]+\.png)`", md, re.M))
    rows_c, rows_p, rows_s = [], [], []
    for rel, (own, face, note, scope) in CHARS.items():
        if (ASSETS / rel).exists() and rel not in registered:
            w, h = size_of(rel)
            rows_c.append(f"| `{rel}` | {own} | {face} | {w}×{h} | 无 | 定稿 | {note}{limit_note(rel)} | {scope} |")
    for rel, (face, note) in PROPS.items():
        if (ASSETS / rel).exists() and rel not in registered:
            w, h = size_of(rel)
            rows_p.append(f"| `{rel}` | 道具 | {face} | {w}×{h} | 无 | 定稿 | {note}{limit_note(rel)} | tj01 |")
    for rel, (own, face, note) in SETS.items():
        if (ASSETS / rel).exists() and rel not in registered:
            w, h = size_of(rel)
            rows_s.append(f"| `{rel}` | {own} | {face} | {w}×{h} | 无 | 定稿 | {note} | tj01 |")

    def insert_before(heading_prefix, rows):
        if not rows:
            return
        j = next(k for k, l in enumerate(lines) if l.startswith(heading_prefix))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = rows

    insert_before("### 2.2", rows_c)
    insert_before("### 2.3", rows_p)
    insert_before("### 2.5", rows_s)
    new_people = []
    if "`zxu_`" not in md and (ASSETS / "chars/zxu_shadow.png").exists():
        nm, code, ep, look, px, st = PEOPLE_ROW
        new_people.append(f"| {nm} | {code} | {ep} | {look} | {px} | {st} |")
    if new_people:
        j = next(k for k, l in enumerate(lines) if l.startswith("tj01 的新角色（智、赵、韩、魏各家的人物）画完以后"))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = new_people
    REG.write_text("\n".join(lines), encoding="utf-8")
    print(f"登记：人物 {len(new_people)} 行，姿势图 {len(rows_c)}，道具 {len(rows_p)}，布景 {len(rows_s)}")


if __name__ == "__main__":
    main()
