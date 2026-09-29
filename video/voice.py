"""配音：逐句合成台词（Edge TTS，和 MoneyPrinterTurbo 用的是同一个免费配音引擎），量出每句的真实时长，排出全片时间线。

先配音、后排画面（动画的常规做法）：画面、字幕、口型都按真实的配音时长来对齐，不再用「每秒 4.8 个字」估算。
「动作」行没有台词，沿用剧本里写的时长。

用法（Git Bash，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）
  python video/voice.py <定稿剧本.json> <输出目录> [动作行号=秒 ...]
    例：python video/voice.py video/stories/tj01/<定稿>.json video/out/tj01_voice 2=1.0 9=1.2
    动作行号是剧本 lines 的下标，从 0 数；插句、删句以后要按新的下标重写。
    旁白和司马光的声音不用另外设，也不再认 NARRATOR_RATE 环境变量（设了会打印一句「已不用」并忽略）。
  python video/voice.py --make-ceremony [--force]
    只在系列声音定稿时用一次：合成两段仪式录音存进 video/assets/audio/。已有的文件不覆盖，要重录先问 Chris，再加 --force。
输出：<目录>/NN.mp3（这次配音每句一个）、<目录>/cache/<哈希>.mp3（合成缓存）、<目录>/timeline.json

时间线按「真正说完话的时刻」算（不按整段 mp3 的时长）
  Edge TTS 给每句 mp3 的结尾补 0.5–1.0 秒静音（系列录音「考考你！」有声部分只到约 1.05 秒，后面 1.04 秒是静音）。
  所以每句的 t1 = 有声部分的结束 + TAIL_KEEP（0.15 秒）；下一句仍是 t1 + 句间停顿（series_voice.json 的 gap，0.3 秒）接上。
  有声部分怎么量：ffmpeg 把 mp3 解成 16 kHz 单声道 PCM，每 FRAME（10 毫秒）一帧，一帧里最大的采样比 SILENCE_DB（−50 dBFS）大就算有声，
  最后一个有声帧的结束就是有声部分的结束。整段都在阈值以下（读不到声音）就不裁。
  mp3 文件本身不改（NN.mp3、缓存、系列录音的 sha256 都不变）；混音照旧从 t0 放整段 mp3，被裁掉的只是结尾的静音，叠在下一句上没有声音。
  句首的静音不裁。每句在 timeline.json 里另有 dur_raw（整段 mp3 的时长）、voiced_end（有声部分的结束，从句首算）、
  trim（裁掉的静音长度 = dur_raw − (t1 − t0)），方便核对。语速报警也按裁掉之后的 t1 − t0 算。

声音分两层
  1. 系列固定声音：旁白（zh-CN-XiaoxiaoNeural、+6%）、司马光（zh-CN-YunxiNeural、-10%、-12Hz）、句间停顿 0.3 秒，
     都在 video/series_voice.json（工作流第七节；改动要先问 Chris）。
  2. 本集角色：写在这一集 episode.json（和剧本同一个目录）的 "cast" 里，只配本集角色，不写旁白和司马光：
       "cast": {"商鞅": {"voice": "zh-CN-YunyangNeural", "rate": "-4%", "pitch": "-6Hz"}, "大婶": {"voice": "zh-CN-liaoning-XiaobeiNeural", "rate": "+4%"}}
     rate 不写是 +0%，pitch 不写是 +0Hz；写成 ["声音", "语速", "音高"] 三项的列表也认。
     会报错的：cast 里出现旁白、司马光；本集角色用了 YunxiNeural（只给司马光）；剧本里有说话人没有声音。
     只打印警告的：整集里有两个说话的角色用了同一个声音（工作流第 2 步：同一场里不能有两个角色用同一个声音，这里还没有分场，只能整集查）。

缓存
  合成缓存按（要合成的文字、声音、语速、音高）四样算哈希，文件名是哈希：任何一样变了就重新合成，其余不动。
  插句、删句、挪句都不会用错录音（不看行号）。NN.mp3 是这次运行按行号排好的副本，每次运行都会重写，剧本里已经没有的行号会删掉。

配音用的文字（多音字、生僻字读错时用；Edge TTS 没有指定读音的参数，只能换同音字）
  在剧本 JSON 的顶层加一个 "voice_text"，写成 {"台词原文": "配音用的文字"}：
      "voice_text": {"长子的人来了！": "涨子的人来了！"}
  键是这一句台词的原文，一个字都不能差（标点也要一样）。不用行号：插句、删句、挪句以后，配音文字跟着台词走。
  键在剧本台词里找不到（台词改过了）会报错。同一句原文出现几次，每次都用这条配音文字。
  字幕和 timeline.json 里的 text 仍是原文；配音用的字记在 timeline.json 这一句的 voice_text 和 tts.text 里。
  story.py 读剧本时不认识这个顶层字段，会照常忽略。
  只许换同音字（都是报错、退出码 1）：
    · 去掉标点以后，配音文字和原文一样长（不许加字、减字）；改动的字不超过 MAX_VT_CHANGES（3）个；
    · 配音文字里不许有这一集 episode.json 的 banned（禁用词）：voice_text 不是绕过禁用词的后门（S2、S13）。
      banned 的写法同 story.py：{"词": "为什么禁"}；配音时也会查每一句台词本身。

仪式录音（video/series_voice.json 的 ceremony）
  字面完全相同的（说话人、台词）——司马光「考考你！」、旁白「写书的人，来了——」——直接用 video/assets/audio/ 里的录音，不重新合成。
  timeline.json 里这一句有 series_audio 字段（录音路径），tts.from 是「系列录音」。仪式句不许再写 voice_text。

检查（都在合成之前，报错的会一次列完再退出，退出码 1）
  cast 规则、说话人有没有声音、voice_text 的键对不对和只许换同音字、禁用词、仪式录音是不是用现在的系列声音录的、
  series_voice.json 的 files 里登记的 sha256 和 video/assets/audio/ 里的文件对得上（不对就是文件被人改过）。
合成后
  语速：每句字数 ÷ (t1 − t0) 超过每秒 5 个字打印报警（规则用 story.py 的 checks()，不打印就是没超；只报警，退出码仍是 0）。
  多音字：读这一集 <剧本目录>/source.md「### 多音字（第 4 步配音用）」的表，台词里出现表里的词、而这一句没写配音用的文字，
  就打印提示（不拦截）；source.md 不存在就跳过并说一句。表里的词是繁体写法时，用下面 TRAD2SIMP 转成简体再对台词。
  括号里的别名也拿去匹配：括号里的字是这个词的一部分、至少两个字才算，例如「中行氏（中行）」的「中行」；
  「长子（地名）」「好利（智伯好利）」这类括号里的说明不算别名。
  仪式句近似写法（不拦截）：一句台词包含仪式句、去掉标点后和仪式句一样、或者字面一样但说话人不对，都不会用系列录音，打印警告（A5）。
  语速报警、多音字提示、仪式句近似写法、同声音警告，同时写进 timeline.json 顶层的 warnings。
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import edge_tts
import numpy as np

ROOT = Path(__file__).resolve().parent
SERIES = ROOT / "series_voice.json"
ASSETS = ROOT / "assets"
LEAD, TAIL = 0.3, 0.5   # 片头留白、片尾余量（秒），和旧版一样
ACTION = "动作"
MAX_CPS = 5.0           # 只在导入不了 story.py 时用，和 story.py 的 MAX_RATE 一样
TAIL_KEEP = 0.15        # 有声部分结束后再留多久才算这一句结束（秒）
SILENCE_DB = -50        # 一帧里最大的采样低于这个电平（dBFS，满量程 = 0）就算静音
FRAME = 0.01            # 量有声部分时一帧多长（秒）
MAX_VT_CHANGES = 3      # voice_text 最多改几个字（去掉标点以后逐字比）：只许换同音字，不许改写句子
RATE_RE, PITCH_RE = re.compile(r"^[+-]\d+%$"), re.compile(r"^[+-]\d+Hz$")
# 多音字表里常见的繁体写法 → 简体（够用就行，不是完整的繁简转换；不在表里的繁体字会打印一句说明）
_PAIRS = (
    "驂骖 晉晋 陽阳 難难 帥帅 長长 韓韩 趙赵 魏魏 國国 車车 馬马 門门 問问 開开 時时 書书 說说 話话 們们 來来 過过 還还 這这 從从 "
    "後后 為为 與与 無无 歲岁 傳传 義义 樂乐 權权 選选 進进 軍军 戰战 將将 諸诸 齊齐 鄭郑 衛卫 鄲郸 絳绛 瑤瑶 鐸铎 蠆虿 藺蔺 竈灶 產产 "
    "幾几 兒儿 頭头 點点 實实 動动 種种 讓让 請请 謀谋 議议 識识 記记 論论 謂谓 誰谁 語语 該该 認认 讀读 變变 買买 賣卖 貴贵 賢贤 "
    "賞赏 財财 貨货 資资 質质 貪贪 貧贫 賊贼 費费 鄰邻 鄉乡 縣县 紀纪 約约 級级 絕绝 給给 統统 經经 結结 緊紧 織织 總总 終终 繼继 "
    "網网 維维 羅罗 習习 聖圣 聞闻 聽听 聲声 職职 臨临 興兴 舉举 藥药 處处 號号 補补 規规 視视 覺觉 親亲 觀观 誠诚 護护 農农 遠远 "
    "適适 遲迟 遺遗 邊边 鋒锋 鐘钟 鐵铁 銀银 錢钱 錯错 閉闭 閒闲 間间 關关 陣阵 隊队 陰阴 陸陆 隨随 險险 雖虽 雙双 離离 雲云 電电 "
    "靈灵 靜静 順顺 須须 預预 領领 題题 願愿 類类 風风 飛飞 飯饭 飲饮 餓饿 驕骄 驗验 驚惊 鬥斗 魚鱼 鳥鸟 麥麦 黃黄 齒齿 龍龙"
).split()
TRAD2SIMP = {p[0]: p[1] for p in _PAIRS}   # 每个词两个字：繁体、简体


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(s):
    """去掉标点和空白，只留字（和 story.py 数字数的规则一样）。"""
    return re.sub(r"[^\w]", "", s)


def die(*msgs):
    sys.exit("错误：" + "\n".join(str(m) for m in msgs))


def parse_voice(where, v, errs):
    """一个声音配置 → (voice, rate, pitch)；格式不对就往 errs 里记，返回 None。"""
    if isinstance(v, (list, tuple)):
        v = dict(zip(("voice", "rate", "pitch"), v))
    if not isinstance(v, dict) or not isinstance(v.get("voice"), str) or not v["voice"].strip():
        errs.append(f"{where}：要写成 {{\"voice\": \"zh-CN-XxxNeural\", \"rate\": \"+4%\", \"pitch\": \"+0Hz\"}}，现在是 {v!r}")
        return None
    voice, rate, pitch = v["voice"].strip(), v.get("rate", "+0%"), v.get("pitch", "+0Hz")
    bad = [f"{k} {x!r}（要写成 +6%、-10%、+0Hz、-12Hz 这样，带正负号）" for k, x, ok in (("rate", rate, RATE_RE), ("pitch", pitch, PITCH_RE))
           if not (isinstance(x, str) and ok.match(x))]
    if bad:
        errs.append(f"{where}：" + "；".join(bad))
        return None
    return voice, rate, pitch


def load_series():
    """video/series_voice.json → (旁白和司马光的声音, 句间停顿, cast 不许用的声音, 仪式录音表)。"""
    if not SERIES.exists():
        die(f"{SERIES} 不存在（旁白、司马光的系列固定声音写在这里）")
    s = json.loads(SERIES.read_text(encoding="utf-8"))
    errs, chars = [], {}
    for who, v in s["characters"].items():
        c = parse_voice(f"{SERIES.name} 的 characters.{who}", v, errs)
        if c:
            chars[who] = c
    gap = s["gap"]
    if not isinstance(gap, (int, float)) or isinstance(gap, bool) or gap < 0:
        errs.append(f"{SERIES.name} 的 gap 要是不小于 0 的数字（秒），现在是 {gap!r}")
    files = s.get("files", {})
    for rel, want in files.items():   # 系列固定的音频文件登记了 sha256：文件被改过（重录、被人覆盖）就报错
        f = ASSETS / rel
        if f.exists() and sha256_file(f) != want:
            errs.append(f"{f} 的 sha256 是 {sha256_file(f)}，和 {SERIES.name} 的 files 里登记的 {want} 不一样：文件被改过。"
                        f"系列固定，重录要先问 Chris，同意后把新的 sha256 写进 files")
    ceremony = {}
    for rec in s["ceremony"]:
        if rec["file"] not in files:
            errs.append(f"{SERIES.name} 的 files 里没有登记 {rec['file']} 的 sha256（voice.py --make-ceremony 会打印这一行）")
        who, text = rec["who"], rec["text"]
        if who not in chars:
            errs.append(f"{SERIES.name} 的 ceremony「{text}」说话人 {who} 不是系列固定声音（{'、'.join(chars)}）")
        elif parse_voice("ceremony", rec, errs) != chars[who]:   # 录音是用哪个声音录的，要和现在的系列声音一致
            errs.append(f"仪式录音「{text}」（{rec['file']}）是用 {rec['voice']} {rec['rate']} {rec['pitch']} 录的，"
                        f"和现在 {who} 的系列声音 {' '.join(chars[who])} 不一致。改系列声音要先问 Chris，同意后改 ceremony 里的三项再 --make-ceremony --force 重录")
        ceremony[(who, text)] = rec
    if errs:
        die(f"{SERIES}：", *("  " + e for e in errs))
    return chars, gap, s["cast_forbidden_voices"], ceremony


def load_story(path):
    """剧本 JSON → (lines, voice_text 原样)。lines 格式不对就直接退出（后面什么都查不了）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = data["lines"]
    bad = [i for i, r in enumerate(lines) if not (isinstance(r, list) and len(r) == 5)]
    if bad:
        die(f"{path}：lines[{bad[0]}] 等 {len(bad)} 句不是 [开始秒, 结束秒, 谁, 台词, 画面] 五项")
    return lines, data.get("voice_text", {})


def load_episode(ep_path, errs, notes):
    """这一集的 episode.json → (cast 原表, banned 词表)。没有这个文件，两个都是空的。banned 的格式同 story.py：{"词": "为什么禁"}。"""
    if not ep_path.exists():
        notes.append(f"{ep_path} 不存在，没有本集 cast，也没有 banned（禁用词没查）")
        return {}, {}
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    cast, banned = ep.get("cast", {}), ep.get("banned", {})
    if not isinstance(cast, dict):
        errs.append(f"{ep_path.name} 的 cast 要写成 {{\"角色\": {{\"voice\": ..., \"rate\": ..., \"pitch\": ...}}}}，现在是 {type(cast).__name__}")
        cast = {}
    if not isinstance(banned, dict):
        errs.append(f"{ep_path.name} 的 banned 要写成字典 {{\"词\": \"为什么禁\"}}，现在是 {type(banned).__name__}")
        banned = {}
    bad = [k for k, v in banned.items() if not (isinstance(k, str) and k.strip() and k == k.strip() and isinstance(v, str))]
    if bad:
        errs.append(f"{ep_path.name} 的 banned 里 {bad} 不合格：词要是非空字符串（前后不带空格），原因要是字符串（可以写空串）")
        banned = {k: v for k, v in banned.items() if k not in bad}
    if "banned" not in ep:
        notes.append(f"{ep_path.name} 没有 banned 字段，配音文字和台词里的禁用词没查")
    return cast, banned


def load_cast(raw, ep_path, series_chars, forbidden, speakers, errs, notes):
    """这一集的角色声音（只含本集角色）；问题记进 errs。cast 里写错了的角色算「写了」，不再多报一条「没有声音」。"""
    cast = {}
    for who, v in raw.items():
        if who in series_chars or who == ACTION:
            errs.append(f"{ep_path.name} 的 cast 里不许写「{who}」：" + (f"{who} 是系列固定声音，写在 {SERIES.name}" if who in series_chars else "动作行没有声音"))
            continue
        c = parse_voice(f"{ep_path.name} 的 cast.{who}", v, errs)
        if not c:
            continue
        if c[0] in forbidden:
            errs.append(f"{ep_path.name} 的 cast.{who} 用了 {c[0]}：{forbidden[c[0]]}")
        cast[who] = c
    missing = sorted(w for w in speakers if w not in series_chars and w not in raw)
    if missing:
        errs.append(f"剧本里的说话人 {'、'.join(missing)} 没有声音：在 {ep_path} 的 cast 里补上（只配本集角色；旁白、司马光是系列固定声音）")
    for w in sorted(set(raw) - speakers - set(series_chars)):
        notes.append(f"cast 里的 {w} 在这个剧本里没有台词")
    return cast


def check_texts(lines, vt, banned, errs):
    """voice_text（只许换同音字：去掉标点后一样长、改动 <= MAX_VT_CHANGES 个字、不含禁用词）和每句台词里的禁用词；问题记进 errs。"""
    if not isinstance(vt, dict):
        errs.append(f"voice_text 要写成 {{\"台词原文\": \"配音用的文字\"}}，现在是 {type(vt).__name__}")
        vt = {}
    spoken = {r[3] for r in lines if r[2] != ACTION and r[3]}
    for k, v in vt.items():
        if not (isinstance(v, str) and v.strip()):
            errs.append(f"voice_text 里「{k}」的配音文字要是非空字符串，现在是 {v!r}")
            continue
        if k not in spoken:
            errs.append(f"voice_text 里的「{k}」在剧本台词里找不到（台词改过了？键要和台词原文一字不差）")
            continue
        a, b = core(k), core(v)
        if len(a) != len(b):
            errs.append(f"voice_text「{k}」→「{v}」：配音文字去掉标点后 {len(b)} 个字，原文 {len(a)} 个字。只许把字换成同音字，不许加字、减字")
        elif sum(x != y for x, y in zip(a, b)) > MAX_VT_CHANGES:
            errs.append(f"voice_text「{k}」→「{v}」：改了 {sum(x != y for x, y in zip(a, b))} 个字，超过 {MAX_VT_CHANGES} 个。只许换读错的那几个字的同音字，不许改写句子")
        errs += [f"voice_text「{k}」→「{v}」：配音文字里有禁用词「{w}」（{why or '没写原因'}）。配音用的文字也不许绕过 banned（S2、S13）"
                 for w, why in banned.items() if core(w) in core(v)]   # 去掉标点再比：「豫、让」也算命中
    for i, (_, _, who, text, _) in enumerate(lines):
        if who != ACTION and text:
            errs += [f"lines[{i}]（{who}）台词里有禁用词「{w}」（{why or '没写原因'}）：{text}（story.py --lint 应该已经拦住，配音这里再查一遍）"
                     for w, why in banned.items() if core(w) in core(text)]
    return vt


def same_voice_warnings(voices, speakers):
    """整集里说话的角色，两个以上用同一个声音就警告（工作流第 2 步 cast 规则；还没有分场，查不到「同一场」）。"""
    by = {}
    for w in sorted(speakers):
        by.setdefault(voices[w][0], []).append(w)
    return [f"{'、'.join(f'{w}（{voices[w][1]} {voices[w][2]}）' for w in ws)} 用了同一个声音 {v}：同一场里不能有两个角色用同一个声音，"
            f"这里没有分场，请确认它们不在同一场出场，否则换声音或合并台词" for v, ws in by.items() if len(ws) > 1]


def ceremony_near(lines, ceremony):
    """近似仪式句的写法（A5）：一句台词包含仪式句、去掉标点后和仪式句一样、或者字面一样但说话人不对，都不会用系列录音。返回警告。"""
    out = []
    for i, (_, _, who, text, _) in enumerate(lines):
        if who == ACTION or not text:
            continue
        for (cw, ct) in ceremony:
            if (who, text) == (cw, ct) or core(ct) not in core(text):
                continue
            if core(text) == core(ct):
                why = f"字面和仪式句一样，但说话人是{who}，仪式句是{cw}说的" if text == ct else "去掉标点后和仪式句一样，但标点或写法不是一字不差"
            else:
                why = "这句话里含有仪式句，但整句不是仪式句"
            out.append(f"lines[{i}]（{who}）「{text}」和系列仪式句「{ct}」（{cw}）很像：{why}。不会用系列录音，会另外合成，"
                       f"声音和别的集的仪式句会不一样。要用系列录音，就把它单独成一句、一字不差、说话人写{cw}；确实要另说就忽略这条")
    return out


def simp(s):
    """多音字表里常见的繁体写法转成简体（TRAD2SIMP 够用就行）。"""
    return "".join(TRAD2SIMP.get(c, c) for c in s)


def read_polyphones(src):
    """source.md「### 多音字（第 4 步配音用）」的表 → [(词, [别名], 拼音一栏, 依据一栏)]。
    词取「（」前面的部分；别名是括号里属于这个词的一部分、至少两个字的写法（「中行氏（中行）」的「中行」），
    「（地名）」「（智伯好利）」这类说明不是别名。"""
    rows, on = [], False
    for ln in src.read_text(encoding="utf-8").splitlines():
        if ln.startswith("#"):
            on = ln.lstrip("#").strip().startswith("多音字")
        elif on and ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            head = re.split(r"[（(]", cells[0])[0].strip()
            if len(cells) >= 2 and head and head != "字或词" and not set(head) <= set("-: "):
                inner = [x.strip() for grp in re.findall(r"[（(]([^）)]*)[）)]", cells[0]) for x in re.split(r"[，,、；;/\s]+", grp)]
                aliases = [x for x in inner if len(x) >= 2 and simp(x) in simp(head) and simp(x) != simp(head)]
                rows.append((head, aliases, cells[1], cells[2] if len(cells) > 2 else ""))
    return rows


def polyphone_hints(lines, vt, src):
    """台词里出现多音字表里的词（或括号里的别名）、而这一句没写配音用的文字：返回提示（不拦截）。每句每一行表只提示一次。"""
    if not src.exists():
        return [], [f"{src} 不存在，跳过多音字检查"]
    table, hints, notes = read_polyphones(src), [], []
    if not table:
        return [], [f"{src} 里没找到「### 多音字」的表，跳过多音字检查"]
    unknown = {c for head, al, _, _ in table for w in [head] + al for c in w if c not in TRAD2SIMP and not _gb2312(c)}
    if unknown:
        notes.append(f"多音字表里有 {''.join(sorted(unknown))} 这几个繁体字，voice.py 没法转成简体，含它们的词只按原样对台词")
    for i, (_, _, who, text, _) in enumerate(lines):
        if who == ACTION or not text or text in vt:
            continue
        for head, aliases, py, _ in table:
            hit = next((w for w in [head] + aliases if w in text or simp(w) in text), None)
            if hit:
                extra = f"，表里的词是「{simp(head)}」" if simp(hit) != simp(head) else ""
                hints.append(f"lines[{i}]（{who}）台词里有多音字词「{simp(hit)}」（{py}{extra}）：合成后请抽查这一句的读音；"
                             f"读错就在剧本 voice_text 里写配音用的文字（同音字）。台词：{text}")
    return hints, notes


def _gb2312(c):
    try:
        c.encode("gb2312")
        return True
    except UnicodeEncodeError:
        return False


def too_fast(rows):
    """语速：每句字数 ÷ 真实时长超过每秒 5 个字的。规则用 story.py 的 checks()；导入不了就用同样的规则自己算，并说一声。"""
    try:
        sys.path.insert(0, str(ROOT))
        from story import checks
    except Exception as e:   # story.py 正在被别人改、或者不是 .venv 的 Python
        print(f"提示：导入不了 story.py 的 checks（{type(e).__name__}: {e}），语速改用 voice.py 里同一条规则（每秒 {MAX_CPS:g} 字）", file=sys.stderr)
        checks = None
    out = []
    for r in rows:
        if not r["audio"]:
            continue
        spoken = r["tts"]["text"]
        d = r["t1"] - r["t0"]
        n = len(re.sub(r"[^\w]", "", spoken))
        over = bool(checks({"lines": [[r["t0"], r["t1"], r["who"], spoken, ""]]})["too_fast"]) if checks else n / max(d, 0.1) > MAX_CPS
        if over:
            out.append(f"lines[{r['i']}]（{r['who']}）{n} 字 / {d:.2f} 秒 = {n / max(d, 0.1):.1f} 字/秒，超过每秒 5 个字：{spoken[:24]}")
    return out


def duration(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(p.stdout)
    except ValueError:
        die(f"ffprobe 量不出 {path} 的时长（返回码 {p.returncode}）：{p.stderr.strip()[:200]}")


def voiced_end(path):
    """这一句有声部分的结束时刻（秒，从句首算）：mp3 解成 16 kHz 单声道 PCM，每 FRAME 一帧，
    最后一个「帧内最大采样 >= SILENCE_DB」的帧的结束。整段都是静音返回 0.0。"""
    sr = 16000
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 解不开 {path}（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    x = np.abs(np.frombuffer(p.stdout, dtype=np.int16).astype(np.int32))
    fr = int(sr * FRAME)
    x = np.pad(x, (0, -len(x) % fr)).reshape(-1, fr).max(axis=1)
    loud = np.nonzero(x >= 32768 * 10 ** (SILENCE_DB / 20))[0]
    return float((loud[-1] + 1) * FRAME) if len(loud) else 0.0


def cache_key(text, voice, rate, pitch):
    return hashlib.sha1("\n".join([text, voice, rate, pitch]).encode("utf-8")).hexdigest()[:16]


async def synth(text, voice, rate, pitch, path):
    tmp = path.with_name(path.name + ".part")   # 先写临时文件再改名：合成中断了，不会留下截断的文件被当成缓存
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(tmp))
    os.replace(tmp, path)


def make_ceremony(force):
    chars, _, _, ceremony = load_series()
    for (who, text), rec in ceremony.items():
        dest = ASSETS / rec["file"]
        if dest.exists() and not force:
            print(f"已有 {dest}（{duration(dest):.2f} 秒），不重录：系列固定，要重录先问 Chris，再加 --force")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(synth(text, *chars[who], dest))
        print(f"录好 {dest}：{who}「{text}」{duration(dest):.2f} 秒（{' '.join(chars[who])}）")
        print(f"  把这一行写进 {SERIES.name} 的 files（以后每次读都会核对）：\"{rec['file']}\": \"{sha256_file(dest)}\"")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("story", nargs="?", help="定稿剧本 .json")
    ap.add_argument("out", nargs="?", help="输出目录")
    ap.add_argument("actions", nargs="*", help="动作行号=秒")
    ap.add_argument("--make-ceremony", action="store_true", help="合成两段仪式录音（系列声音定稿时用一次）")
    ap.add_argument("--force", action="store_true", help="和 --make-ceremony 一起：覆盖已有的仪式录音（先问 Chris）")
    a = ap.parse_args()
    if os.environ.get("HTTPS_PROXY") and not os.environ.get("WSS_PROXY"):
        os.environ["WSS_PROXY"] = os.environ["HTTPS_PROXY"]   # 云端：Edge TTS 走 wss://，aiohttp 只从 WSS_PROXY 读代理
    if os.environ.get("NARRATOR_RATE"):
        print(f"提示：NARRATOR_RATE 已不用（旁白语速固定写在 {SERIES.name}），当前值 {os.environ['NARRATOR_RATE']} 已忽略")
    if a.make_ceremony:
        return make_ceremony(a.force)
    if not (a.story and a.out):
        ap.error("要给剧本和输出目录：voice.py <定稿剧本.json> <输出目录> [动作行号=秒 ...]")
    story, out = Path(a.story), Path(a.out)

    # ---- 检查（合成之前）
    chars, gap, forbidden, ceremony = load_series()
    lines, vt = load_story(story)
    act = {}
    for x in a.actions:
        k, _, v = x.partition("=")
        if not (k.isdigit() and re.match(r"^\d+(\.\d+)?$", v)):
            die(f"动作行号参数 {x!r} 要写成「行号=秒」，例如 13=8.6")
        act[int(k)] = float(v)
    speakers = {r[2] for r in lines if r[2] != ACTION and r[3]}
    ep_path, errs, notes = story.parent / "episode.json", [], []
    raw_cast, banned = load_episode(ep_path, errs, notes)
    cast = load_cast(raw_cast, ep_path, chars, forbidden, speakers, errs, notes)
    vt = check_texts(lines, vt, banned, errs)
    for (who, text), rec in ceremony.items():
        if any(r[2] == who and r[3] == text for r in lines):
            if text in vt:
                errs.append(f"「{text}」是系列仪式句，用系列录音，不许写配音用的文字（voice_text）")
            if not (ASSETS / rec["file"]).exists():
                errs.append(f"仪式录音 {ASSETS / rec['file']} 不存在：先跑 voice.py --make-ceremony")
    if errs:
        die(f"配音前检查没过（{len(errs)} 处）：", *("  " + e for e in errs))
    voices = {**cast, **chars}
    warnings = {"same_voice": same_voice_warnings(voices, speakers), "ceremony_near": ceremony_near(lines, ceremony),
                "polyphone": [], "too_fast": []}
    hints, hint_notes = polyphone_hints(lines, vt, story.parent / "source.md")
    warnings["polyphone"] = hints
    for n in notes + hint_notes:
        print("提示：" + n)
    for w in warnings["same_voice"]:
        print("警告：" + w)
    for w in warnings["ceremony_near"]:
        print("警告：" + w)
    for h in hints:
        print("多音字提示：" + h)

    # ---- 合成（缓存按 文字+声音+语速+音高）
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    t, timeline, kept, count, trimmed = LEAD, [], set(), {"合成": 0, "缓存": 0, "系列录音": 0}, 0.0
    for i, (s0, s1, who, text, visual) in enumerate(lines):
        row = {"i": i, "t0": None, "t1": None, "who": who, "text": text, "visual": visual, "audio": None, "script_t0": s0}
        if who == ACTION or not text:
            d = act.get(i, s1 - s0)
        else:
            f = out / f"{i:02d}.mp3"
            rec = ceremony.get((who, text))
            voice, rate, pitch = voices[who]
            if rec:
                shutil.copyfile(ASSETS / rec["file"], f)
                src, row["series_audio"], spoken, key = "系列录音", rec["file"], text, None
            else:
                spoken = vt.get(text, text)
                key = cache_key(spoken, voice, rate, pitch)
                cf = cache / f"{key}.mp3"
                src = "缓存" if cf.exists() else "合成"
                if src == "合成":
                    asyncio.run(synth(spoken, voice, rate, pitch, cf))
                shutil.copyfile(cf, f)
            count[src] += 1
            kept.add(f.name)
            raw, end = duration(f), voiced_end(f)
            d = min(raw, end + TAIL_KEEP) if end > 0 else raw   # 有声部分的结束 + 一个小尾巴；读不到声音就不裁
            trimmed += raw - d
            row.update({"dur_raw": round(raw, 3), "voiced_end": round(end, 2), "trim": round(raw - d, 2)})
            row["audio"] = f.name
            row["tts"] = {"voice": voice, "rate": rate, "pitch": pitch, "text": spoken, "key": key, "from": src}
            if spoken != text:
                row["voice_text"] = spoken
        row["t0"], row["t1"] = round(t, 2), round(t + d, 2)
        timeline.append(row)
        t += d + gap
    for p in out.iterdir():   # 剧本里已经没有的行号：删掉旧的 NN.mp3，免得以为还有
        if re.fullmatch(r"\d+\.mp3", p.name) and p.name not in kept:
            p.unlink()
            print(f"提示：删掉 {p.name}（剧本里这一行现在没有台词）")

    warnings["too_fast"] = too_fast(timeline)
    (out / "timeline.json").write_text(json.dumps({"duration": round(t + TAIL, 2), "lines": timeline, "warnings": warnings},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    for x in timeline:
        tag = x["tts"]["from"] if x["audio"] else ""
        print(f"{x['t0']:6.2f}–{x['t1']:6.2f}  {x['who']:<4} {tag:<4} {x['text'][:30]}" + (f"  ⇒ 配音用「{x['voice_text'][:30]}」" if "voice_text" in x else ""))
    for w in warnings["too_fast"]:
        print("语速报警：" + w)
    print(f"全片 {t + TAIL:.1f} 秒（剧本估算 {lines[-1][1]:.1f} 秒；每句结尾的静音只留 {TAIL_KEEP:g} 秒，共裁掉 {trimmed:.1f} 秒）")
    print(f"合成 {count['合成']} 句，缓存命中 {count['缓存']} 句，系列录音 {count['系列录音']} 句；"
          f"语速报警 {len(warnings['too_fast'])} 处，多音字提示 {len(hints)} 处，同声音警告 {len(warnings['same_voice'])} 处，"
          f"仪式句近似写法警告 {len(warnings['ceremony_near'])} 处")


if __name__ == "__main__":
    main()
