#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成第 2 轮新增的测试简报（每份只坏一处，好样例各配一份）。
用法：.venv/Scripts/python video/tests/source_check/gen_samples.py
生成的 md 就放在这个目录里，run_all.sh 直接用；改了这里要重新生成。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

SOURCES = {
    "鉴1": "https://zh.wikisource.org/wiki/資治通鑑/卷001",
    "鉴2": "https://zh.wikisource.org/wiki/資治通鑑/卷002",
    "胡1": "https://zh.wikisource.org/wiki/資治通鑒_(胡三省音注)/卷001",
    "史86": "https://zh.wikisource.org/wiki/史記/卷086",
    "策赵一": "https://zh.wikisource.org/wiki/戰國策_(士禮居叢書本)/趙/一",
    "韩非喻老": "https://zh.wikisource.org/wiki/韓非子/喻老",
}

TEMPLATE = """# 测试简报（{kind}）：{what}

> 这份简报只用来测 `video/source_check.py`，由 gen_samples.py 生成。

## 一、事件和原文
{quotes}

## 四、人物
### 注音（人名、地名、生僻字）
| 字 | 拼音 | 说明 |
|---|---|---|
| 絺疵 | chī cī | 智伯的家臣 |

### 多音字（第 4 步配音用）
| 字 | 读音 | 用在 | 配音用的字 |
|---|---|---|---|
| 行 | xíng | “智伯行水” | 行 |

## 来源
{sources}
"""


def make(name, kind, what, quotes, sources=None, extra_sources=()):
    src = dict(SOURCES)
    src.update(sources or {})
    lines = ["- %s：%s" % (k, v) for k, v in src.items()]
    lines += list(extra_sources)
    text = TEMPLATE.format(kind=kind, what=what,
                           quotes="\n".join("- " + q for q in quotes),
                           sources="\n".join(lines))
    with open(HERE / name, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


OK, BAD = "合格样例", "坏样例"

# ---- 1. 多个短码：每一个都要找到
make("bad_multi_each.md", BAD, "两个短码，第二本里没有这句（韩非子写的是溲器）",
     ["「飲器」（鉴1；韩非喻老）"])
make("bad_multi_both.md", BAD, "两个短码，两本里都没有这句（理，应为禮）",
     ["「天子之職莫大於理」（鉴1；胡1）"])
make("ok_multi.md", OK, "多个短码，每一本里都逐字找得到；策赵一、韩非喻老指到具体一卷",
     ["「天子之職莫大於禮」（鉴1；胡1）",
      "「臣聞脣亡則齒寒」（鉴1；策赵一）",
      "「智伯之亡也，才勝德也」（鉴1；胡1）",
      "「圍晉陽三年」（策赵一）",
      "「趙襄子漆智伯之頭，以為飲器」（鉴1）"])

# ---- 2. 没有卷号的短码也要核到具体一卷
make("bad_ce2.md", BAD, "策赵一 的链接指到趙/二",
     ["「天子之職莫大於禮」（鉴1）"],
     sources={"策赵一": "https://zh.wikisource.org/wiki/戰國策_(士禮居叢書本)/趙/二"})
make("bad_hanfei_page.md", BAD, "韩非喻老 的链接指到韓非子/說林上",
     ["「天子之職莫大於禮」（鉴1）"],
     sources={"韩非喻老": "https://zh.wikisource.org/wiki/韓非子/說林上"})

# ---- 3. 校勘记号：〔X〕保留 X，(Y) 删掉（含单独出现的 (Y)）
make("ok_collation.md", OK, "按校勘本的读法（保留〔X〕、删掉(Y)），这些都该通过",
     ["「智伯又求藺、皋狼之地」（鉴1）",          # 〔藺〕(蔡)
      "「九鼎震，初命晉大夫」（鉴1）",            # 〔九鼎震〕 编者补的
      "「尊周室」（鉴1）",                        # 尊〔周〕(王)室
      "「豈非以禮為之紀綱哉」（鉴1）",            # 〔紀〕綱(紀)哉
      "「吳公吮其父，其父戰不還踵」（鉴1）",      # 其父(疽) 单独的删字
      "「匿奸者」（鉴2）"])                       # 〔匿〕(不告)-{奸}-者
make("bad_collation.md", BAD, "校勘记号的假读法：两个字都留下、或者用被改掉的字，都找不到",
     ["「智伯又求藺蔡、皋狼之地」（鉴1）",        # X、Y 都留下
      "「智伯又求蔡、皋狼之地」（鉴1）",          # 被改掉的误字
      "「尊王室」（鉴1）",                        # 被改掉的误字
      "「吳公吮其父疽」（鉴1）"])                 # 被删掉的字

# ---- 4. 「……」省略：要在原文同一处、顺序一致、间隔有上限、不跨正文和注文
make("bad_ellipsis_far.md", BAD, "省略号两头各自都找得到，但相隔很远",
     ["「天子之職……才勝德也」（鉴1）"])
make("bad_ellipsis_order.md", BAD, "省略号两头顺序颠倒（九鼎震在初命晉大夫之前）",
     ["「初命晉大夫……九鼎震」（鉴1）"])
make("bad_ellipsis_note.md", BAD, "省略号一头在正文、一头在紧跟着的注文",
     ["「城不浸者三版……高二尺爲一版」（胡1）"])
make("ok_ellipsis.md", OK, "省略号两头在原文同一处、顺序一致；三段的；整句在同一条注文里的",
     ["「吾與虞人期獵……豈可無一會期哉」（鉴1）",
      "「天子之職……禮莫大於分……分莫大於名」（鉴1）",
      "「九鼎震……初命晉大夫」（鉴1）",
      "「絺，抽遲翻……姓也」（胡1）"])

# ---- 5. 「」里没有汉字：只有符号才跳过，拼音等要报错
make("bad_nonhan.md", BAD, "里面只有拼音",
     ["「Zhi Bo」（鉴1）"])
make("bad_nonhan_punct.md", BAD, "里面只有一个标点（不是省略号）",
     ["「，」（鉴1）"])
make("bad_nonhan_mixed.md", BAD, "汉字里混着拼音",
     ["「智伯Zhi Bo」（鉴1）"])
make("ok_symbols2.md", OK, "只有符号、省略号、空白的都跳过",
     ["「」", "「 」", "「『』」", "「…」", "「……」", "「⋯⋯」", "「...」"])

# ---- 6. {{參|字|说明}} 保留第一个参数
make("ok_can.md", OK, "史86 的 參 模板：縣是正文，要能引到",
     ["「於是韓縣之，有能言殺相俠累者予千金」（史86）"])
make("bad_can.md", BAD, "史86 的 參 模板：说明文字（購縣）不是正文，不能引",
     ["「於是韓購縣之」（史86）",
      "「一作購縣」（史86）"])

# ---- 6. --check-links：失败先重试一次（flaky_server.py 在 18765 端口）
LOCAL = "http://127.0.0.1:18765"
make("ok_link_flaky.md", OK, "第 1 次请求 503，重试后 200，应该通过",
     ["「天子之職莫大於禮」（鉴1）"], extra_sources=["- 网1：%s/flaky" % LOCAL])
make("bad_link_dead.md", BAD, "一直 500，重试后还是失败，要写出原因",
     ["「天子之職莫大於禮」（鉴1）"], extra_sources=["- 网1：%s/dead" % LOCAL])
make("bad_link_refused.md", BAD, "连不上（端口没人听），要写出原因",
     ["「天子之職莫大於禮」（鉴1）"], extra_sources=["- 网1：http://127.0.0.1:9/nothing"])

print("已生成到", HERE)
