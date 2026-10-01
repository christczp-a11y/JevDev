"""配音：逐句合成台词（Qwen3-TTS，本地显卡），量出每句的真实时长，排出全片时间线。

先配音、后排画面（动画的常规做法）：画面、字幕、口型都按真实的配音时长来对齐，不再用「每秒 4.8 个字」估算。
「动作」行没有台词，沿用剧本里写的时长。

引擎：Qwen3-TTS（阿里 Qwen 团队，Apache 2.0，可商用），在独立环境 .venv-tts（Python 3.12 + CUDA 版 PyTorch + qwen-tts）里跑；
voice.py 在主环境 .venv 里跑，用子进程调 video/tts/qwen_worker.py：一次启动、一次加载模型、批量生成。只在有显卡的本地电脑上跑。

用法（Git Bash，Python 用 .venv/Scripts/python，设 PYTHONIOENCODING=utf-8）
  python video/voice.py <定稿剧本.json> <输出目录> [动作行号=秒 ...]
    例：python video/voice.py video/stories/tj01/<定稿>.json video/out/tj01_voice 2=1.0 9=1.2
    动作行号是剧本 lines 的下标，从 0 数；插句、删句以后要按新的下标重写。
    加 --redesign 角色 [角色 ...]：删掉这几个本集角色的参考音（含语气变体）重新设计（改了声音描述以后用）。
  python video/voice.py --make-series-voices [--force]
    只在系列声音定稿时用一次：设计旁白、司马光（和仪式录音用到的语气变体）的参考音，存进 video/assets/audio/voices/，打印要登记进
    series_voice.json 的 files 的 sha256。已有的不重做，要重做先问 Chris，再加 --force。
  python video/voice.py --make-ceremony [--force]
    只在系列声音定稿时用一次：合成两段仪式录音存进 video/assets/audio/，打印要登记的 sha256 和 ref_sha256。已有的不覆盖，同上。
输出：<目录>/NN.mp3（这次配音每句一个）、<目录>/cache/<哈希>.mp3（合成缓存）、<目录>/timeline.json

声音怎么来的（克隆参考音：VoiceDesign 设计一段参考音，Base 模型克隆它去念每一句）
  实测（GTX 1660 Ti，见 PITFALLS）：只用文字描述、每句都让 VoiceDesign 现设计，同一个角色前后两句的音色会飘（说话人向量余弦
  同角色两句平均 0.24；克隆参考音是 0.57，Edge 的固定声音是 0.68）；所以每个角色先设计一段固定的参考音，以后所有句子都克隆它。
  Base 模型没有语气指令：克隆的音色和语气都跟着参考音走（速度、轻重、起伏）。所以：
    · 参考音要用角色的默认语气设计（"tone" 字段）；
    · 某一句要换语气（剧本 "tone"），就为（角色，语气）另外设计一段「语气变体」参考音，存成 <角色>@<语气>.wav，
      一次设计 3 个候选，用说话人向量挑和默认参考音最像的那个（把音色拉回同一个人），以后复用。

声音分两层，都是「声音描述」（一段中文话，不是引擎参数）
  1. 系列固定声音：旁白、司马光和句间停顿 0.3 秒，写在 video/series_voice.json 的 characters（改动要先问 Chris）：
       "司马光": {"desc": "一位慈祥爽朗的老爷爷……", "tone": "默认语气", "ref_text": "参考音念的那段话"}
  2. 本集角色：写在这一集 episode.json（和剧本同一个目录）的 "cast" 里，只配本集角色，不写旁白和司马光。
       "cast": {"智伯": "一位四十多岁的贵族男性，嗓音洪亮……", "段规": {"desc": "……", "tone": "克制谨慎", "ref_text": "……"}}
     值可以直接是一段声音描述，也可以是 {"desc", "tone", "ref_text"}（tone 不写 = 没有默认语气；ref_text 不写用 DEFAULT_REF_TEXT）。
     第一次用到某个角色，自动设计参考音存进 video/assets/audio/voices/<角色>.wav + .json（描述、参考文字、设计参数），以后每一集复用：
     同一个角色名全系列同一个声音。json 里记着当时的描述，cast 里的描述后来改了就报错（要换声音用 --redesign）。
     会报错的：cast 里出现旁白、司马光；剧本里有说话人没有声音；声音描述或语气里有 BANNED_DESC 里的词
     （低沉、沙哑、气声、阴森、阴冷、邪恶、恐怖、神秘、阴沉：儿童节目会做出吓人的声音，PITFALLS A4；老人写「慈祥爽朗」，反派写「傲慢、洪亮」）。
     只打印警告的：整集里有两个说话的角色用了一模一样的声音描述。

语气（剧本每句可以带）
  剧本 JSON 的顶层加 "tone"，写成 {"台词原文": "语气"}，键是这一句台词的原文，一个字都不能差（同 voice_text；story.py 会照常忽略这个字段）：
      "tone": {"这块地，我要了！你给不给？": "得意、霸道", "……我忍。": "压着火气、小声"}
  没写的句子用说话人的默认语气（cast / series_voice.json 里的 tone）。语气和默认语气一样（去掉标点后）也用默认参考音。
  仪式句用系列录音，不许写语气。timeline.json 里 tts.tone 记这一句用的语气。

心声（语气里写「心声」）
  剧本 "tone" 里写 "心声、小声、紧张"：这一句是心里话。声音用去掉「心声」后的语气（这里是「小声、紧张」，没剩下就用默认语气），不另外设计；
  念完按缓存里的原句加一点处理（INNER_FILTER：高频压到 3.5 kHz 以下 + 两个很轻的回声），孩子听得出是在心里说。缓存里的原句不动，
  NN.mp3 是加了处理的；timeline.json 里 tts.effect = "心声"，时长按处理后的文件量。

齐声（说话人写成「甲+乙+丙」）
  例：["韩康子+魏桓子+张孟谈", "今晚，看咱们联手大反击！"]。每个角色各按这一句的语气念一遍（各自的声音、各自的语气变体、各自的缓存），
  起点对齐叠在一起，总长按最长的那条；每条先压低（乘 1/√n），再把几个声音都在念的那一段的响度调到各条的平均，合起来和普通一句差不多响。
  角色都要有声音（cast 里或系列声音）；timeline.json 里这一句的 who 照剧本写（"甲+乙+丙"），tts.voice 是几个声音名用 + 连起来，
  tts.chorus 列出每个声音和缓存键。voice_text、tone 对三个声音都生效。下游（口型、字幕）按 "+" 拆开，才知道是谁在说话。

时间线按「真正说完话的时刻」算（不按整段 mp3 的时长）
  每句的 t1 = 有声部分的结束 + TAIL_KEEP（0.15 秒）；下一句仍是 t1 + 句间停顿（series_voice.json 的 gap，0.3 秒）接上。
  有声部分怎么量：ffmpeg 把 mp3 解成 16 kHz 单声道 PCM，每 FRAME（10 毫秒）一帧，一帧里最大的采样比 SILENCE_DB（−50 dBFS）大就算有声，
  最后一个有声帧的结束就是有声部分的结束。整段都在阈值以下（读不到声音）就不裁。
  Qwen 克隆出来的句子开头常有 0.2–1 秒的静音（参考音的尾巴），所以合成后转 mp3 时句首静音只留 HEAD_KEEP（0.08 秒）；
  系列录音也是这样处理过的。mp3 文件进了缓存以后就不再改（NN.mp3、缓存、系列录音的 sha256 都不变）；
  每句在 timeline.json 里另有 dur_raw（整段 mp3 的时长）、voiced_end（有声部分的结束，从句首算）、
  trim（裁掉的结尾静音长度 = dur_raw − (t1 − t0)），方便核对。语速报警也按裁掉之后的 t1 − t0 算。
  timeline.json 的格式没变（t0、t1、who、text、visual、audio、tts……），下游的 script_check.py 和合成器不用改；
  每个字的时间由使用方按字数比例估算。tts 里现在是 {voice: 声音名, tone, text, key, from}（不再有 Edge 的 rate、pitch）。

缓存
  合成缓存按（要念的文字、声音名、参考音的 sha256、模型、种子）算哈希，文件名是哈希：任何一样变了就重新合成，其余不动。
  同一个（声音，文字）只念一次。插句、删句、挪句都不会用错录音（不看行号）。NN.mp3 是这次运行按行号排好的副本，
  每次运行都会重写，剧本里已经没有的行号会删掉。

配音用的文字（多音字、生僻字读错时用；没有指定读音的参数，只能换同音字）
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
  timeline.json 里这一句有 series_audio 字段（录音路径），tts.from 是「系列录音」。仪式句不许再写 voice_text 和语气。
  每条仪式记录写着录音用的语气（tone）和参考音的 sha256（ref_sha256）：系列声音改了、录音没重录就报错。

检查（都在合成之前，报错的会一次列完再退出，退出码 1）
  cast 规则、说话人有没有声音、声音描述和语气的禁用词、已存的参考音和现在的描述对不对得上、voice_text 的键对不对和只许换同音字、
  语气的键对不对、禁用词、仪式录音是不是用现在的系列声音录的、
  series_voice.json 的 files 里登记的 sha256 和 video/assets/ 里的文件对得上（不对就是文件被人改过）。
合成后
  语速：每句字数 ÷ (t1 − t0) 超过每秒 5 个字打印报警（规则用 story.py 的 checks()，不打印就是没超；只报警，退出码仍是 0）。
  多音字：读这一集 <剧本目录>/source.md「### 多音字（第 4 步配音用）」的表，台词里出现表里的词、而这一句没写配音用的文字，
  就打印提示（不拦截）；source.md 不存在就跳过并说一句。表里的词是繁体写法时，用下面 TRAD2SIMP 转成简体再对台词。
  括号里的别名也拿去匹配：括号里的字是这个词的一部分、至少两个字才算，例如「中行氏（中行）」的「中行」；
  「长子（地名）」「好利（智伯好利）」这类括号里的说明不算别名。
  仪式句近似写法（不拦截）：一句台词包含仪式句、去掉标点后和仪式句一样、或者字面一样但说话人不对，都不会用系列录音，打印警告（A5）。
  语速报警、多音字提示、仪式句近似写法、同声音描述警告，同时写进 timeline.json 顶层的 warnings。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SERIES = ROOT / "series_voice.json"
ASSETS = ROOT / "assets"
VOICES = ASSETS / "audio" / "voices"          # 每个声音一对文件：<声音名>.wav（参考音）+ <声音名>.json（描述、参考文字、设计参数）
WORKER = ROOT / "tts" / "qwen_worker.py"
MODELS = {"design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base"}
SEED = 20260929
LANGUAGE = "Chinese"
LEAD, TAIL = 0.3, 0.5   # 片头留白、片尾余量（秒），和旧版一样
ACTION = "动作"
MAX_CPS = 5.0           # 只在导入不了 story.py 时用，和 story.py 的 MAX_RATE 一样
TAIL_KEEP = 0.15        # 有声部分结束后再留多久才算这一句结束（秒）
HEAD_KEEP = 0.08        # 每句开头的静音只留这么长（秒）
SILENCE_DB = -50        # 一帧里最大的采样低于这个电平（dBFS，满量程 = 0）就算静音
FRAME = 0.01            # 量有声部分时一帧多长（秒）
MAX_VT_CHANGES = 3      # voice_text 最多改几个字（去掉标点以后逐字比）：只许换同音字，不许改写句子
VARIANT_CANDIDATES = 3  # 一个语气变体的参考音设计几个候选（挑和默认参考音最像的）
DEFAULT_REF_TEXT = "大家好呀，今天我有一个有趣的故事，想讲给你们听。"
BANNED_DESC = ("低沉", "沙哑", "气声", "阴森", "阴冷", "邪恶", "恐怖", "神秘", "阴沉")   # PITFALLS A4
CHORUS = "+"            # 说话人写成「甲+乙+丙」= 齐声：每个声音各念一遍，起点对齐叠在一起
INNER = "心声"          # 语气里写「心声」= 这一句是心里话：声音还用去掉「心声」后的语气，念完加一点混响、压低高频
INNER_FILTER = "lowpass=f=3500,aecho=0.8:0.85:45|90:0.25|0.12"   # 心声的处理：高频压到 3.5 kHz 以下 + 两个很轻的回声（约 45、90 毫秒）
AUDIO_SR = 24000        # 合成出来的 mp3 都是 24 kHz 单声道（to_mp3）

# 多音字表里常见的繁体写法 → 简体（够用就行，不是完整的繁简转换；不在表里的繁体字会打印一句说明）
_PAIRS = (
    "驂骖 晉晋 陽阳 難难 帥帅 長长 韓韩 趙赵 魏魏 國国 車车 馬马 門门 問问 開开 時时 書书 說说 話话 們们 來来 過过 還还 這这 從从 "
    "後后 為为 與与 無无 歲岁 傳传 義义 樂乐 權权 選选 進进 軍军 戰战 將将 諸诸 齊齐 鄭郑 衛卫 鄲郸 絳绛 瑤瑶 鐸铎 蠆虿 藺蔺 竈灶 產产 "
    "幾几 兒儿 頭头 點点 實实 動动 種种 讓让 請请 謀谋 議议 識识 記记 論论 謂谓 誰谁 語语 該该 認认 讀读 變变 買买 賣卖 貴贵 賢贤 "
    "賞赏 財财 貨货 資资 質质 貪贪 貧贫 賊贼 費费 鄰邻 鄉乡 縣县 紀纪 約约 級级 絕绝 給给 統统 經经 結结 緊紧 織织 總总 終终 繼继 "
    "網网 維维 羅罗 習习 聖圣 聞闻 聽听 聲声 職职 臨临 興兴 舉举 藥药 處处 號号 補补 規规 視视 覺觉 親亲 觀观 誠诚 護护 農农 遠远 "
    "適适 遲迟 遺遗 邊边 鋒锋 鐘钟 鐵铁 銀银 錢钱 錯错 閉闭 閒闲 間间 關关 陣阵 隊队 陰阴 陸陆 隨随 險险 雖虽 雙双 離离 雲云 電电 "
    "靈灵 靜静 順顺 須须 預预 領领 題题 願愿 類类 風风 飛飞 飯饭 飲饮 餓饿 驕骄 驗验 驚惊 鬥斗 魚鱼 鳥鸟 麥麦 黃黄 齒齿 龍龙 "
    "會会 獵猎 罷罢 駕驾 豈岂"
).split()
TRAD2SIMP = {p[0]: p[1] for p in _PAIRS}   # 每个词两个字：繁体、简体


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core(s):
    """去掉标点和空白，只留字（和 story.py 数字数的规则一样）。"""
    return re.sub(r"[^\w]", "", s)


def die(*msgs):
    sys.exit("错误：" + "\n".join(str(m) for m in msgs))


def desc_word_errors(where, s, errs):
    """声音描述、语气里不许出现会做出吓人声音的词（PITFALLS A4）。"""
    for w in BANNED_DESC:
        if w in s:
            errs.append(f"{where}里有「{w}」：儿童节目不许用这类词（模型会做出阴沉可怕的声音，PITFALLS A4）。"
                        f"老人写「慈祥爽朗的爷爷」，反派写「傲慢、洪亮」，声音要「温暖、明亮、带笑、有精神」")


def parse_voice(where, v, errs):
    """一个声音配置 → {"desc", "tone", "ref_text"}；格式不对就往 errs 里记，返回 None。
    v 可以直接是一段声音描述，也可以是 {"desc": 声音描述, "tone": 默认语气, "ref_text": 参考音念的那段话}。"""
    if isinstance(v, str):
        v = {"desc": v}
    if not isinstance(v, dict) or not isinstance(v.get("desc"), str) or not v["desc"].strip():
        old = "（Edge TTS 的 voice / rate / pitch 已经不用了，改成一段中文的声音描述）" if isinstance(v, dict) and "voice" in v else ""
        errs.append(f"{where}：要写成一段声音描述，或 {{\"desc\": \"声音描述\", \"tone\": \"默认语气\", \"ref_text\": \"参考音念的话\"}}，现在是 {v!r}{old}")
        return None
    bad = [f"{k} {v[k]!r}" for k in ("tone", "ref_text") if k in v and not isinstance(v[k], str)]
    unknown = sorted(k for k in v if k not in ("desc", "tone", "ref_text") and not k.startswith("_"))
    if bad or unknown:
        errs.append(f"{where}：" + "；".join([f"{b} 要是字符串" for b in bad] + [f"多了没用的字段 {k}" for k in unknown]))
        return None
    c = {"desc": v["desc"].strip(), "tone": v.get("tone", "").strip(), "ref_text": v.get("ref_text", DEFAULT_REF_TEXT).strip() or DEFAULT_REF_TEXT}
    desc_word_errors(f"{where} 的 desc", c["desc"], errs)
    desc_word_errors(f"{where} 的 tone", c["tone"], errs)
    return c


def norm_tone(t):
    return core(t or "")


def vid_for(who, tone, default_tone):
    """一句话用哪个声音：没写语气、或语气和默认语气一样（去掉标点后）→ 角色名；否则 角色名@语气（太长的截断加哈希）。"""
    t = norm_tone(tone)
    if not t or t == norm_tone(default_tone):
        return who
    return f"{who}@{t[:12]}" + (("_" + hashlib.sha1(t.encode('utf-8')).hexdigest()[:4]) if len(t) > 12 else "")


def compose_instruct(desc, tone):
    """喂给 VoiceDesign 的指令：声音描述 + 语气。"""
    return desc.strip().rstrip("。") + "。" + (tone.strip().rstrip("。") + "。" if tone.strip() else "")


def speaker_parts(who):
    """剧本里的说话人 → 角色列表：「甲+乙+丙」是齐声（三个声音一起念），别的都是一个角色。"""
    return [p.strip() for p in who.split(CHORUS)] if CHORUS in who else [who]


def split_inner(tone):
    """语气 → (去掉「心声」的语气, 是不是心声)。「心声、小声、紧张」→（「小声、紧张」, True）；声音跟去掉「心声」后的语气走，不另外设计。"""
    t = (tone or "").strip()
    if INNER not in t:
        return t, False
    return re.sub(r"^[\s，,、；;：:]+|[\s，,、；;：:]+$", "", t.replace(INNER, "", 1)), True


def make_voice(who, base, line_tone=""):
    """（角色, 这一句的语气）→ 声音：vid（文件名）、设计用的描述/语气/参考文字/指令、是不是语气变体、是不是心声（inner）。
    语气里写了「心声」：声音用去掉「心声」后的语气（没剩下就用默认语气），inner=True，念完由 apply_inner 加处理。"""
    line_tone, inner = split_inner(line_tone)
    vid = vid_for(who, line_tone, base["tone"])
    tone = base["tone"] if vid == who else line_tone.strip()
    return {"vid": vid, "who": who, "desc": base["desc"], "tone": tone, "ref_text": base["ref_text"],
            "instruct": compose_instruct(base["desc"], tone), "variant": vid != who, "inner": inner}


def voice_files(vid):
    return VOICES / f"{vid}.wav", VOICES / f"{vid}.json"


def voice_exists(vid):
    return all(p.exists() for p in voice_files(vid))


def voice_problems(v):
    """已存的参考音和现在的描述对不对得上；返回问题列表（空 = 没问题或者还没有）。"""
    wav, js = voice_files(v["vid"])
    if wav.exists() != js.exists():
        return [f"{v['vid']}：{wav.name} 和 {js.name} 只有一个（要成对存在）：都删掉重新设计，或者补齐"]
    if not wav.exists():
        return []
    meta = json.loads(js.read_text(encoding="utf-8"))
    diff = [k for k in ("desc", "tone", "ref_text") if meta.get(k) != v[k]]
    if not diff:
        return []
    who = v["who"]
    return [f"{v['vid']}：参考音是按另一份{'、'.join({'desc': '声音描述', 'tone': '语气', 'ref_text': '参考文字'}[k] for k in diff)}设计的"
            f"（{js} 里记着：{'；'.join(f'{k}={meta.get(k)!r}' for k in diff)}），现在的是 {'；'.join(f'{k}={v[k]!r}' for k in diff)}。"
            f"要换声音：本集角色加 --redesign {who}（旧参考音会被删掉，这个角色在别的集里的配音要重配才一致）；"
            f"系列声音（旁白、司马光）要先问 Chris；不想换就把描述改回 {js.name} 里记的"]


def load_series(check_files=True):
    """video/series_voice.json → (旁白和司马光的声音, 句间停顿, 仪式录音表)。
    check_files=False：不核对 files 的 sha256、不要求仪式录音已登记、不核对 ref_sha256（--make-series-voices / --make-ceremony 用：
    这时候正是要生成这些文件、再把 sha256 登记进去）。"""
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
        if check_files and f.exists() and sha256_file(f) != want:
            errs.append(f"{f} 的 sha256 是 {sha256_file(f)}，和 {SERIES.name} 的 files 里登记的 {want} 不一样：文件被改过。"
                        f"系列固定，重录要先问 Chris，同意后把新的 sha256 写进 files")
    ceremony = {}
    for rec in s["ceremony"]:
        if check_files and rec["file"] not in files:
            errs.append(f"{SERIES.name} 的 files 里没有登记 {rec['file']} 的 sha256（voice.py --make-ceremony 会打印这一行）")
        who, text = rec["who"], rec["text"]
        if who not in chars:
            errs.append(f"{SERIES.name} 的 ceremony「{text}」说话人 {who} 不是系列固定声音（{'、'.join(chars)}）")
        else:
            desc_word_errors(f"{SERIES.name} 的 ceremony「{text}」的 tone", rec.get("tone", ""), errs)
            wav, _ = voice_files(vid_for(who, rec.get("tone", ""), chars[who]["tone"]))
            if check_files and wav.exists() and rec.get("ref_sha256") != sha256_file(wav):   # 录音是用哪段参考音录的，要和现在的一致
                errs.append(f"仪式录音「{text}」（{rec['file']}）是用 sha256 为 {rec.get('ref_sha256')} 的参考音录的，"
                            f"现在 {wav.name} 是 {sha256_file(wav)}。改系列声音要先问 Chris，同意后把 ceremony 里的 ref_sha256 改成新的，再 --make-ceremony --force 重录")
        ceremony[(who, text)] = rec
    if errs:
        die(f"{SERIES}：", *("  " + e for e in errs))
    return chars, gap, ceremony


def load_story(path):
    """剧本 JSON → (lines, voice_text 原样, tone 原样)。lines 格式不对就直接退出（后面什么都查不了）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = data["lines"]
    bad = [i for i, r in enumerate(lines) if not (isinstance(r, list) and len(r) == 5)]
    if bad:
        die(f"{path}：lines[{bad[0]}] 等 {len(bad)} 句不是 [开始秒, 结束秒, 谁, 台词, 画面] 五项")
    return lines, data.get("voice_text", {}), data.get("tone", {})


def load_episode(ep_path, errs, notes):
    """这一集的 episode.json → (cast 原表, banned 词表)。没有这个文件，两个都是空的。banned 的格式同 story.py：{"词": "为什么禁"}。"""
    if not ep_path.exists():
        notes.append(f"{ep_path} 不存在，没有本集 cast，也没有 banned（禁用词没查）")
        return {}, {}
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    cast, banned = ep.get("cast", {}), ep.get("banned", {})
    if not isinstance(cast, dict):
        errs.append(f"{ep_path.name} 的 cast 要写成 {{\"角色\": \"声音描述\"}}（或 {{\"desc\": ..., \"tone\": ..., \"ref_text\": ...}}），现在是 {type(cast).__name__}")
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


def load_cast(raw, ep_path, series_chars, speakers, errs, notes):
    """这一集的角色声音（只含本集角色）；问题记进 errs。cast 里写错了的角色算「写了」，不再多报一条「没有声音」。"""
    cast = {}
    for who, v in raw.items():
        if who in series_chars or who == ACTION:
            errs.append(f"{ep_path.name} 的 cast 里不许写「{who}」：" + (f"{who} 是系列固定声音，写在 {SERIES.name}" if who in series_chars else "动作行没有声音"))
            continue
        c = parse_voice(f"{ep_path.name} 的 cast.{who}", v, errs)
        if c:
            cast[who] = c
    missing = sorted(w for w in speakers if w not in series_chars and w not in raw)
    if missing:
        errs.append(f"剧本里的说话人 {'、'.join(missing)} 没有声音：在 {ep_path} 的 cast 里补上声音描述（只配本集角色；旁白、司马光是系列固定声音）")
    for w in sorted(set(raw) - speakers - set(series_chars)):
        notes.append(f"cast 里的 {w} 在这个剧本里没有台词")
    return cast


def check_tones(lines, tones, ceremony, errs):
    """剧本顶层 tone：键要是一句台词的原文，值是非空字符串、没有 BANNED_DESC 里的词，仪式句不许写。"""
    if not isinstance(tones, dict):
        errs.append(f"tone 要写成 {{\"台词原文\": \"语气\"}}，现在是 {type(tones).__name__}")
        return {}
    spoken = {r[3] for r in lines if r[2] != ACTION and r[3]}
    for k, v in tones.items():
        if not (isinstance(v, str) and v.strip()):
            errs.append(f"tone 里「{k}」的语气要是非空字符串，现在是 {v!r}")
        elif k not in spoken:
            errs.append(f"tone 里的「{k}」在剧本台词里找不到（台词改过了？键要和台词原文一字不差）")
        elif any(r[3] == k and (r[2], k) in ceremony for r in lines):
            errs.append(f"「{k}」是系列仪式句，用系列录音，不许写语气（tone）")
        else:
            desc_word_errors(f"tone「{k}」的语气", v, errs)
    return {k: v.strip() for k, v in tones.items() if isinstance(v, str)}


def same_voice_warnings(specs, speakers):
    """整集里说话的角色，两个以上用一模一样的声音描述（和默认语气）就警告：会听不出是谁在说话（工作流第 2 步 cast 规则）。"""
    by = {}
    for w in sorted(speakers):
        by.setdefault((specs[w]["desc"], specs[w]["tone"]), []).append(w)
    return [f"{'、'.join(ws)} 的声音描述一模一样（{d[:24]}…）：同一场里不能有两个角色用同一个声音，请换描述"
            for (d, _), ws in by.items() if len(ws) > 1]


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


def _loud(path):
    """ffmpeg 把音频解成 16 kHz 单声道 PCM，每 FRAME 一帧，返回「有声」的帧号（帧内最大采样 >= SILENCE_DB）。"""
    sr = 16000
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 解不开 {path}（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    x = np.abs(np.frombuffer(p.stdout, dtype=np.int16).astype(np.int32))
    fr = int(sr * FRAME)
    x = np.pad(x, (0, -len(x) % fr)).reshape(-1, fr).max(axis=1)
    return np.nonzero(x >= 32768 * 10 ** (SILENCE_DB / 20))[0]


def voiced_end(path):
    """这一句有声部分的结束时刻（秒，从句首算）：最后一个有声帧的结束。整段都是静音返回 0.0。"""
    loud = _loud(path)
    return float((loud[-1] + 1) * FRAME) if len(loud) else 0.0


def voiced_start(path):
    """这一句有声部分的开始时刻（秒）：第一个有声帧的开始。整段都是静音返回 0.0。"""
    loud = _loud(path)
    return float(loud[0] * FRAME) if len(loud) else 0.0


def to_mp3(wav, mp3):
    """wav → mp3（24 kHz 单声道 64 kbps）；句首静音只留 HEAD_KEEP 秒。先写临时文件再改名：中断了不会留下截断的文件被当成缓存。"""
    mp3 = Path(mp3)
    mp3.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp3.with_name(mp3.name + ".part")
    start = max(0.0, voiced_start(wav) - HEAD_KEEP)
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(wav), "-ac", "1", "-ar", "24000", "-b:a", "64k", "-f", "mp3", str(tmp)],
                       capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 转不了 {wav}（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    os.replace(tmp, mp3)


def apply_inner(src, dst):
    """心声：把一句话（mp3）加一点混响、压低高频，存成 dst（mp3）。缓存里的原句不动；每次运行按缓存重做一遍。"""
    dst = Path(dst)
    tmp = dst.with_name(dst.name + ".part")
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", INNER_FILTER, "-ac", "1", "-ar", str(AUDIO_SR), "-b:a", "64k", "-f", "mp3", str(tmp)],
                       capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 给 {src} 加心声处理失败（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    os.replace(tmp, dst)


def _decode_f32(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(AUDIO_SR), "-"], capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 解不开 {path}（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)


def _active_rms(x):
    """有声部分的均方根（只算绝对值大于峰值 2% 的采样，静音和尾巴不拉低响度）。"""
    a = np.abs(x)
    m = a > 0.02 * max(float(a.max()), 1e-9) if len(a) else a
    return float(np.sqrt(np.mean(x[m] ** 2))) if len(a) and m.any() else 0.0


def mix_chorus(srcs, dst):
    """齐声：几段 mp3 起点对齐叠在一起，总长按最长的那条。每条先乘 1/√n（几个声音各压低一点），再把叠出来的有声部分响度调到
    「各条有声响度的平均」——合起来和普通一句差不多响；峰值超过 0.97 就整体压回去。"""
    xs = [_decode_f32(p) for p in srcs]
    n = max(len(x) for x in xs)
    mix = sum(np.pad(x, (0, n - len(x))) for x in xs) / np.sqrt(len(xs))
    common = min(len(x) for x in xs)       # 几个声音都在念的那一段（最短那条的长度）；太短就量整段
    if common < 0.3 * AUDIO_SR:
        common = n
    target, have = float(np.mean([_active_rms(x[:common]) for x in xs])), _active_rms(mix[:common])
    if have > 1e-9:
        mix = mix * (target / have)
    peak = float(np.abs(mix).max())
    if peak > 0.97:
        mix = mix * (0.97 / peak)
    dst = Path(dst)
    tmp = dst.with_name(dst.name + ".part")
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(AUDIO_SR), "-ac", "1", "-i", "-", "-b:a", "64k", "-f", "mp3", str(tmp)],
                       input=mix.astype(np.float32).tobytes(), capture_output=True)
    if p.returncode != 0:
        die(f"ffmpeg 转不了齐声的混音（返回码 {p.returncode}）：{p.stderr.decode('utf-8', 'replace').strip()[:200]}")
    os.replace(tmp, dst)


def cache_key(spoken, vid, ref_sha):
    return hashlib.sha1("\n".join([spoken, vid, ref_sha or "", MODELS["clone"], str(SEED)]).encode("utf-8")).hexdigest()[:16]


def line_seed(vid, spoken):
    return SEED + int(hashlib.sha1(f"{vid}\n{spoken}".encode("utf-8")).hexdigest()[:6], 16) % 100000


def tts_python():
    p = os.environ.get("VOICE_TTS_PYTHON")
    if p:
        return p
    for rel in (".venv-tts/Scripts/python.exe", ".venv-tts/bin/python"):
        if (REPO / rel).exists():
            return str(REPO / rel)
    die("找不到配音环境 .venv-tts（Python 3.12 + CUDA 版 PyTorch + qwen-tts，装法见 requirements-tts.txt）。配音只在有显卡的本地电脑上跑")


def run_worker(job, workdir):
    """调 video/tts/qwen_worker.py（在 .venv-tts 里），返回它写的结果字典。测试里这个函数被 fake_run.py 换成假的（不用显卡）。"""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    jf, rf = workdir / "_tts_job.json", workdir / "_tts_result.json"
    job = dict(job, result=str(rf))
    jf.write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
    rf.unlink(missing_ok=True)
    print(f"调 Qwen3-TTS（设计参考音 {len(job['design'])} 个，念 {len(job['speak'])} 句；第一次加载模型要 20–30 秒）……", flush=True)
    p = subprocess.run([tts_python(), str(WORKER), str(jf)], env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if p.returncode != 0 or not rf.exists():
        die(f"Qwen3-TTS worker 失败（返回码 {p.returncode}）：看上面它打印的错误；job 文件在 {jf}，可以单独重跑：{tts_python()} {WORKER} {jf}")
    return json.loads(rf.read_text(encoding="utf-8"))


def build_job(design, speak_items, voices_all, tmp):
    """design：要设计的声音；speak_items：[(编号, 声音, 文字)]；voices_all：这次用到的所有声音（含语气变体的默认参考音）。"""
    return {"seed": SEED, "language": LANGUAGE, "models": MODELS,
            "design": [{"id": v["vid"], "wav": str(voice_files(v["vid"])[0]), "instruct": v["instruct"], "text": v["ref_text"],
                        "n": VARIANT_CANDIDATES if v["variant"] else 1, "anchor": v["who"] if v["variant"] else None,
                        "seed_off": int(hashlib.sha1(v["vid"].encode("utf-8")).hexdigest()[:6], 16) % 100000}
                       for v in sorted(design, key=lambda v: v["variant"])],   # 默认参考音在前，语气变体（要拿默认参考音当基准）在后
            "voices": {v["vid"]: {"wav": str(voice_files(v["vid"])[0]), "ref_text": v["ref_text"]} for v in voices_all},
            "speak": [{"job": str(n), "voice": v["vid"], "text": text, "out": str(Path(tmp) / f"{n}.wav"), "seed": line_seed(v["vid"], text)}
                      for n, v, text in speak_items]}


def write_metas(design, res):
    for v in design:
        wav, js = voice_files(v["vid"])
        if not wav.exists():
            die(f"worker 没有生成 {wav}")
        info = res.get("design", {}).get(v["vid"], {})
        meta = {"name": v["who"], "vid": v["vid"], "variant_of": v["who"] if v["variant"] else None,
                "desc": v["desc"], "tone": v["tone"], "ref_text": v["ref_text"], "instruct": v["instruct"],
                "model": MODELS["design"], "seed": SEED, "chosen": info.get("chosen"), "cands": info.get("cands"),
                "made": time.strftime("%Y-%m-%d")}
        voice_files(v["vid"])[1].write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def synthesize(design, speak_items, voices_all, tmp):
    """调一次 worker：先设计缺的参考音（写好 json），再念句子。返回 (结果, {编号: wav 路径})。"""
    VOICES.mkdir(parents=True, exist_ok=True)
    Path(tmp).mkdir(parents=True, exist_ok=True)
    res = run_worker(build_job(design, speak_items, voices_all, tmp), tmp)
    write_metas(design, res)
    outs = {n: Path(tmp) / f"{n}.wav" for n, _, _ in speak_items}
    for n, p in outs.items():
        if not p.exists():
            die(f"worker 没有生成第 {n} 句的音频 {p}")
    return res, outs


def print_stats(res):
    sp = res.get("speak", {})
    gen, dur = sum(x["gen_s"] for x in sp.values()), sum(x["dur"] for x in sp.values())
    print(f"Qwen3-TTS：设计参考音 {len(res.get('design', {}))} 个，念 {len(sp)} 句（音频共 {dur:.0f} 秒），模型加载 {res.get('load_s', 0):.0f} 秒，"
          f"生成 {gen:.0f} 秒（{gen / max(dur, 0.1):.1f} 秒/秒音频），显存峰值 {res.get('peak_alloc_gib', '?')} GiB")


def series_needs(chars, ceremony):
    """系列声音要有的参考音：旁白、司马光的默认参考音 + 仪式录音用的语气变体。"""
    need, seen = [], set()
    for who, spec in chars.items():
        for tone in [""] + [rec.get("tone", "") for (w, _), rec in ceremony.items() if w == who]:
            v = make_voice(who, spec, tone)
            if v["vid"] not in seen:
                seen.add(v["vid"])
                need.append(v)
    return need


def register_lines(vs):
    for v in vs:
        print(f"  \"audio/voices/{v['vid']}.wav\": \"{sha256_file(voice_files(v['vid'])[0])}\"")


def make_series_voices(force):
    chars, _, ceremony = load_series(check_files=False)
    need = series_needs(chars, ceremony)
    bad = [p for v in need if not force for p in voice_problems(v)]
    if bad:
        die("系列声音的参考音和 series_voice.json 里的描述对不上：", *("  " + b for b in bad))
    todo = [v for v in need if force or not voice_exists(v["vid"])]
    if not todo:
        print(f"系列声音的参考音都已经有了（{'、'.join(v['vid'] for v in need)}），不重做：系列固定，要重做先问 Chris，再加 --force")
        return
    for v in todo:
        for p in voice_files(v["vid"]):
            p.unlink(missing_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="voice_series_") as tmp:
        res, _ = synthesize(todo, [], need, tmp)
    print_stats(res)
    for v in todo:
        print(f"设计好 {voice_files(v['vid'])[0]}：{v['vid']}（{v['tone'] or '无默认语气'}）")
    print(f"把这几行写进 {SERIES.name} 的 files（以后每次读都会核对）：")
    register_lines(todo)
    for (who, text), rec in ceremony.items():
        vid = vid_for(who, rec.get("tone", ""), chars[who]["tone"])
        print(f"仪式录音「{text}」的 ref_sha256（写进 ceremony）：\"{sha256_file(voice_files(vid)[0])}\"")


def make_ceremony(force):
    chars, _, ceremony = load_series(check_files=False)
    todo = []
    for (who, text), rec in ceremony.items():
        dest = ASSETS / rec["file"]
        if dest.exists() and not force:
            print(f"已有 {dest}（{duration(dest):.2f} 秒），不重录：系列固定，要重录先问 Chris，再加 --force")
            continue
        v = make_voice(who, chars[who], rec.get("tone", ""))
        if not voice_exists(v["vid"]):
            die(f"{v['vid']} 的参考音不存在：先跑 voice.py --make-series-voices")
        bad = voice_problems(v)
        if bad:
            die("系列声音的参考音和 series_voice.json 里的描述对不上：", *("  " + b for b in bad))
        todo.append((who, text, rec, v, dest))
    if not todo:
        return
    import tempfile
    with tempfile.TemporaryDirectory(prefix="voice_ceremony_") as tmp:
        res, outs = synthesize([], [(n, v, text) for n, (_, text, _, v, _) in enumerate(todo)], [v for *_, v, _ in todo], tmp)
        print_stats(res)
        for n, (who, text, rec, v, dest) in enumerate(todo):
            to_mp3(outs[n], dest)
            print(f"录好 {dest}：{who}「{text}」{duration(dest):.2f} 秒（声音 {v['vid']}，语气：{v['tone'] or '默认'}）")
            print(f"  把这一行写进 {SERIES.name} 的 files（以后每次读都会核对）：\"{rec['file']}\": \"{sha256_file(dest)}\"")
            print(f"  ceremony 这一条的 ref_sha256 是：\"{sha256_file(voice_files(v['vid'])[0])}\"")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("story", nargs="?", help="定稿剧本 .json")
    ap.add_argument("out", nargs="?", help="输出目录")
    ap.add_argument("actions", nargs="*", help="动作行号=秒")
    ap.add_argument("--make-series-voices", action="store_true", help="设计旁白、司马光的参考音（系列声音定稿时用一次）")
    ap.add_argument("--make-ceremony", action="store_true", help="合成两段仪式录音（系列声音定稿时用一次）")
    ap.add_argument("--force", action="store_true", help="和上面两个一起：覆盖已有的（先问 Chris）；和 --redesign 一起：允许重设计系列声音")
    ap.add_argument("--redesign", nargs="+", metavar="角色", help="删掉这几个角色的参考音（含语气变体）重新设计；写在剧本和输出目录后面")
    a = ap.parse_args()
    if a.make_series_voices:
        return make_series_voices(a.force)
    if a.make_ceremony:
        return make_ceremony(a.force)
    if not (a.story and a.out):
        ap.error("要给剧本和输出目录：voice.py <定稿剧本.json> <输出目录> [动作行号=秒 ...]")
    story, out = Path(a.story), Path(a.out)

    # ---- 检查（合成之前）
    chars, gap, ceremony = load_series()
    lines, vt, raw_tones = load_story(story)
    act = {}
    for x in a.actions:
        k, _, v = x.partition("=")
        if not (k.isdigit() and re.match(r"^\d+(\.\d+)?$", v)):
            die(f"动作行号参数 {x!r} 要写成「行号=秒」，例如 13=8.6")
        act[int(k)] = float(v)
    speakers = {p for r in lines if r[2] != ACTION and r[3] for p in speaker_parts(r[2])}   # 齐声「甲+乙」里的每个角色都算说话人
    ep_path, errs, notes = story.parent / "episode.json", [], []
    raw_cast, banned = load_episode(ep_path, errs, notes)
    cast = load_cast(raw_cast, ep_path, chars, speakers, errs, notes)
    vt = check_texts(lines, vt, banned, errs)
    tones = check_tones(lines, raw_tones, ceremony, errs)
    for (who, text), rec in ceremony.items():
        if any(r[2] == who and r[3] == text for r in lines):
            if text in vt:
                errs.append(f"「{text}」是系列仪式句，用系列录音，不许写配音用的文字（voice_text）")
            if not (ASSETS / rec["file"]).exists():
                errs.append(f"仪式录音 {ASSETS / rec['file']} 不存在：先跑 voice.py --make-ceremony")
    specs = {**cast, **chars}
    redesign = set(a.redesign or [])
    for w in sorted(redesign):
        if w in chars and not a.force:
            errs.append(f"--redesign {w}：{w} 是系列固定声音，重设计要先问 Chris，同意后再加 --force")
        elif w not in specs:
            errs.append(f"--redesign {w}：{w} 不是这一集的角色")
    plan, voices = {}, {}      # plan：行号 → [(声音, 配音文字), ...]（齐声有几个角色就有几项，别的都是一项）；voices：声音名 → 声音
    for i, (_, _, who, text, _) in enumerate(lines):
        if who == ACTION or not text or (who, text) in ceremony:
            continue
        parts = speaker_parts(who)
        if CHORUS in who and (len(parts) < 2 or "" in parts or len(set(parts)) != len(parts)):
            errs.append(f"lines[{i}] 的说话人「{who}」：齐声要写成「甲+乙+丙」，至少两个、不能有空的、不能重复")
            continue
        if any(p not in specs for p in parts):
            continue
        plan[i] = []
        for p in parts:
            v = make_voice(p, specs[p], tones.get(text, ""))
            plan[i].append((v, vt.get(text, text)))
            voices[v["vid"]] = v
    for v in list(voices.values()):    # 语气变体要拿角色的默认参考音当基准
        if v["variant"] and v["who"] not in voices:
            voices[v["who"]] = make_voice(v["who"], specs[v["who"]], "")
    for vid, v in voices.items():
        if v["who"] in redesign:
            continue
        errs += voice_problems(v)
        if v["who"] in chars and not v["variant"] and not voice_exists(vid):
            errs.append(f"系列声音 {vid} 的参考音 {voice_files(vid)[0]} 不存在：先跑 voice.py --make-series-voices")
    if errs:
        die(f"配音前检查没过（{len(errs)} 处）：", *("  " + e for e in errs))
    for w in sorted(redesign):
        for p in list(VOICES.glob(f"{w}.*")) + list(VOICES.glob(f"{w}@*")):
            p.unlink()
            print(f"提示：--redesign {w}：删掉 {p.name}")
    warnings = {"same_voice": same_voice_warnings(specs, speakers), "ceremony_near": ceremony_near(lines, ceremony),
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

    # ---- 合成（缓存按 文字+声音+参考音+模型+种子）
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    tmp = out / "_tts"
    todo = {}       # （声音名, 配音文字）→ 编号：缓存里没有的，同一句只念一次
    for v, spoken in (x for parts in plan.values() for x in parts):
        if voice_exists(v["vid"]) and (cache / f"{cache_key(spoken, v['vid'], sha256_file(voice_files(v['vid'])[0]))}.mp3").exists():
            continue
        todo.setdefault((v["vid"], spoken), len(todo))
    design = [v for v in voices.values() if not voice_exists(v["vid"])]
    fresh = set()   # 这次刚合成的缓存键：第一次用记「合成」，同一句再出现记「缓存」
    if todo or design:
        res, outs = synthesize(design, [(n, voices[vid], spoken) for (vid, spoken), n in todo.items()], list(voices.values()), tmp)
        for (vid, spoken), n in todo.items():
            key = cache_key(spoken, vid, sha256_file(voice_files(vid)[0]))
            to_mp3(outs[n], cache / f"{key}.mp3")
            fresh.add(key)
        shutil.rmtree(tmp, ignore_errors=True)
        print_stats(res)
    ref_sha = {vid: sha256_file(voice_files(vid)[0]) for vid in voices}
    t, timeline, kept, count, trimmed = LEAD, [], set(), {"合成": 0, "缓存": 0, "系列录音": 0}, 0.0
    for i, (s0, s1, who, text, visual) in enumerate(lines):
        row = {"i": i, "t0": None, "t1": None, "who": who, "text": text, "visual": visual, "audio": None, "script_t0": s0}
        if who == ACTION or not text:
            d = act.get(i, s1 - s0)
        else:
            f = out / f"{i:02d}.mp3"
            rec = ceremony.get((who, text))
            if rec:
                shutil.copyfile(ASSETS / rec["file"], f)
                src, row["series_audio"], spoken, key, tone = "系列录音", rec["file"], text, None, rec.get("tone", "")
                vid = vid_for(who, tone, chars[who]["tone"])
            else:
                parts = plan[i]
                spoken = parts[0][1]
                keys = [cache_key(sp, v["vid"], ref_sha[v["vid"]]) for v, sp in parts]
                vid, tone, key = "+".join(v["vid"] for v, _ in parts), parts[0][0]["tone"], "+".join(keys)
                src = "合成" if any(k in fresh for k in keys) else "缓存"
                fresh.difference_update(keys)
                inner = any(v["inner"] for v, _ in parts)
                if len(parts) > 1:            # 齐声：每个声音各念一遍，起点对齐叠在一起
                    mix_chorus([cache / f"{k}.mp3" for k in keys], f)
                    if inner:
                        apply_inner(f, f)
                elif inner:                   # 心声：缓存里的原句不动，NN.mp3 是加了处理的
                    apply_inner(cache / f"{keys[0]}.mp3", f)
                else:
                    shutil.copyfile(cache / f"{keys[0]}.mp3", f)
            count[src] += 1
            kept.add(f.name)
            raw, end = duration(f), voiced_end(f)
            d = min(raw, end + TAIL_KEEP) if end > 0 else raw   # 有声部分的结束 + 一个小尾巴；读不到声音就不裁
            trimmed += raw - d
            row.update({"dur_raw": round(raw, 3), "voiced_end": round(end, 2), "trim": round(raw - d, 2)})
            row["audio"] = f.name
            row["tts"] = {"voice": vid, "tone": tone, "text": spoken, "key": key, "from": src}
            if not rec and len(plan[i]) > 1:
                row["tts"]["chorus"] = [{"voice": v["vid"], "key": k} for (v, _), k in zip(plan[i], keys)]
            if not rec and inner:
                row["tts"]["effect"] = INNER
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
