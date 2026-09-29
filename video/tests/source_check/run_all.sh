#!/bin/bash
# 跑全部测试简报，对照期望的退出码和关键输出行。用法：bash video/tests/source_check/run_all.sh
# ok*.md / variant.md 应该退出 0；bad_*.md 每份只坏一处，应该退出 1 并报出对应原因。
# 第 2 轮新增的样例由 gen_samples.py 生成（改了要重新生成）；r2_*.md 是 reviewer 第 2 轮的样例（原样拷来）。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
T=video/tests/source_check
PORT=18765
fail=0

t() {  # t 简报 期望退出码 关键输出 [额外参数...]
  local md=$1 want=$2 key=$3; shift 3
  local out; out=$($PY video/source_check.py "$md" "$@" 2>&1); local got=$?
  if [ "$got" = "$want" ] && grep -qF -- "$key" <<<"$out"; then
    echo "PASS  $(basename "$md") $*  退出码 $got  含「$key」"
  else
    echo "FAIL  $(basename "$md") $*  退出码 $got（期望 $want），关键输出「$key」$(grep -qF -- "$key" <<<"$out" && echo 有 || echo 没有)"
    echo "$out" | sed 's/^/      /'
    fail=1
  fi
}

inputs_sum() { md5sum $T/*.md | md5sum | cut -d' ' -f1; }
before=$(inputs_sum)

# --check-links 重试测试用的本地小服务器（测完 /quit 关掉）
$PY $T/flaky_server.py $PORT >/dev/null 2>&1 &
trap 'curl -s -o /dev/null http://127.0.0.1:$PORT/quit' EXIT
up=0
for _ in $(seq 1 40); do curl -s -o /dev/null http://127.0.0.1:$PORT/reset && { up=1; break; }; sleep 0.25; done
[ $up = 1 ] || { echo "FAIL  本地测试服务器没起来（端口 $PORT）"; fail=1; }

echo "---- 第 1 轮的 29 项 ----"
t $T/ok.md               0 "7 条引文，0 个错误"
t $T/ok.md               0 "网1 200" --check-links
t $T/ok_symbols.md       0 "[跳过] 第3行 「」  <- 没有汉字，不算引文"
t $T/ok_symbols.md       0 "7 条引文，0 个错误"
t $T/variant.md          0 "[异体匹配] 第8行"
t $T/variant.md          0 "[通过] 第17行 「歳餘」（史43）"
t $T/variant.md          0 "[通过] 第16行 「絺，抽遲翻，姓也」（胡1）"
t $T/variant.md          0 "胡1 原文作：初命晉大夫魏斯、趙籍、韓虔爲諸侯"
t $T/bad_typo.md         1 "在 鉴1 里找不到「天子之職莫大於理」"
t $T/bad_long.md         1 "引文 22 字，超过 20 字上限"
t $T/bad_code.md         1 "短码「鉴9」不在来源里"
t $T/bad_nocode.md       1 "没有出处短码"
t $T/bad_webquote.md     1 "网1 是普通网页"
t $T/bad_pinyin.md       1 "第四节下面缺小节「### 多音字（第 4 步配音用）」"
t $T/bad_pinyin_empty.md 1 "「多音字」下面的表格是空的"
t $T/bad_weihe.md        1 "裸的【未核实】"
t $T/bad_url.md          1 "不是完整的 http(s) URL"
t $T/bad_link.md         1 "返回 HTTP 404" --check-links
t $T/bad_link.md         0 "0 个错误"
t $T/bad_unclosed.md     1 "没有配对的 」"
t $T/bad_nopage.md       1 "史200 下载失败"
t $T/bad_family.md       1 "短码 史43 应指向维基文库《史記》卷43"
t $T/bad_multicode.md    1 "短码「胡9」不在来源里"
# reviewer 临时脚本里的 54 条引文：应该和 reviewer 的结果一致（2 条找不到、2 条异体匹配）
t $T/reviewer_list.md    1 "54 条引文，3 个错误"
t $T/reviewer_list.md    1 "在 史43 里找不到「飲器」"
t $T/reviewer_list.md    1 "史86 原文作：士爲知己者死"
t $T/v1_source.md 1 "第14行 「自智宣子立瑤，至豫讓報仇，其事皆在威烈王二十三年之前，故先以『初』字發之」  <- 引文 31 字，超过 20 字上限"
t $T/v1_source.md 1 "缺小节「### 注音（人名、地名、生僻字）」"
t $T/v1_source.md 1 "没有出处短码"

echo "---- 第 2 轮 1：多个短码，每一个都要找到 ----"
t $T/bad_multi_each.md   1 "在 韩非喻老 里找不到「飲器」"          # 鉴1 里有，韩非子里是溲器
t $T/bad_multi_each.md   1 "1 条引文，1 个错误"
t $T/bad_multi_both.md   1 "在 鉴1 里找不到「天子之職莫大於理」"    # 两本都没有：逐个报错
t $T/bad_multi_both.md   1 "在 胡1 里找不到「天子之職莫大於理」"
t $T/bad_multi_both.md   1 "1 条引文，2 个错误"
t $T/r2_loophole_multi.md 1 "在 韩非喻老 里找不到「飲器」"         # reviewer 的坏样例
t $T/ok_multi.md         0 "[通过] 第6行 「天子之職莫大於禮」（鉴1；胡1）"
t $T/ok_multi.md         0 "[通过] 第7行 「臣聞脣亡則齒寒」（鉴1；策赵一）"
t $T/ok_multi.md         0 "5 条引文，0 个错误"

echo "---- 2：没有卷号的短码也要核到具体一卷 ----"
t $T/bad_ce2.md          1 "短码 策赵一 应指向维基文库《戰國策》趙策一"
t $T/r2_loophole_ce2.md  1 "短码 策赵一 应指向维基文库《戰國策》趙策一"   # reviewer 的坏样例
t $T/bad_hanfei_page.md  1 "短码 韩非喻老 应指向维基文库《韓非子》喻老"
# 好样例：ok_multi.md 里的 策赵一（趙/一）、韩非喻老（韓非子/喻老）都通过（上面 5 条引文 0 个错误）

echo "---- 3：校勘记号，保留〔X〕、删掉(Y) ----"
t $T/ok_collation.md     0 "[通过] 第6行 「智伯又求藺、皋狼之地」（鉴1）"
t $T/ok_collation.md     0 "[通过] 第10行 「吳公吮其父，其父戰不還踵」（鉴1）"
t $T/ok_collation.md     0 "6 条引文，0 个错误"
t $T/r2_collation_ok.md  0 "[通过] 第4行 「智伯又求藺、皋狼之地」（鉴1）"      # reviewer：校勘本读法
t $T/bad_collation.md    1 "在 鉴1 里找不到「智伯又求藺蔡、皋狼之地」"
t $T/bad_collation.md    1 "在 鉴1 里找不到「智伯又求蔡、皋狼之地」"
t $T/bad_collation.md    1 "在 鉴1 里找不到「吳公吮其父疽」"
t $T/bad_collation.md    1 "4 条引文，4 个错误"
t $T/r2_collation_bogus.md 1 "在 鉴1 里找不到「智伯又求藺蔡」"                # reviewer：假读法
# reviewer 的 r2_collation_jiuding.md 标题行自己写了「九鼎震」（應當通过），被当成一条没有出处的引文，所以整份退出 1；
# 正文那条（第 4 行）是通过的
t $T/r2_collation_jiuding.md 1 "[通过] 第4行 「九鼎震，初命晉大夫」（鉴1）"

echo "---- 4：「……」省略要在原文同一处 ----"
t $T/bad_ellipsis_far.md   1 "每段都找得到，但不在原文的同一处"
t $T/r2_loophole_ellipsis.md 1 "「天子之職」「才勝德也」每段都找得到，但不在原文的同一处"   # reviewer 的坏样例
t $T/bad_ellipsis_order.md 1 "「初命晉大夫」「九鼎震」每段都找得到，但不在原文的同一处"
t $T/bad_ellipsis_note.md  1 "「城不浸者三版」「高二尺爲一版」每段都找得到，但不在原文的同一处"
t $T/ok_ellipsis.md        0 "[通过] 第7行 「天子之職……禮莫大於分……分莫大於名」（鉴1）"
t $T/ok_ellipsis.md        0 "[通过] 第9行 「絺，抽遲翻……姓也」（胡1）"
t $T/ok_ellipsis.md        0 "4 条引文，0 个错误"
# 间隔上限的边界：隔 200 个汉字找得到，隔 201 个找不到
out=$($PY $T/unit_ellipsis_gap.py 2>&1); got=$?
if [ $got = 0 ] && grep -qF "间隔边界测试：全部符合" <<<"$out"; then echo "PASS  unit_ellipsis_gap.py  间隔 200 找得到、201 找不到、顺序颠倒找不到"
else echo "FAIL  unit_ellipsis_gap.py  退出码 $got"; echo "$out" | sed 's/^/      /'; fail=1; fi

echo "---- 5：「」里没有汉字，只有符号才跳过 ----"
t $T/bad_nonhan.md         1 "「」里没有汉字，只有「Zhi Bo」"
t $T/r2_loophole_nonhan.md 1 "「」里没有汉字，只有「Zhi Bo」"                   # reviewer 的坏样例
t $T/bad_nonhan_punct.md   1 "「」里没有汉字，只有「，」"
t $T/bad_nonhan_mixed.md   1 "引文里有汉字以外的字母或数字（Zhi、Bo）"
t $T/ok_symbols2.md        0 "[跳过] 第12行 「...」"
t $T/ok_symbols2.md        0 "0 条引文，0 个错误"

echo "---- 6：{{參|字|说明}}保留第一个参数；--check-links 重试 ----"
t $T/ok_can.md             0 "[通过] 第6行 「於是韓縣之，有能言殺相俠累者予千金」（史86）"
t $T/bad_can.md            1 "在 史86 里找不到「於是韓購縣之」"
t $T/bad_can.md            1 "2 条引文，2 个错误"
t $T/ok_link_flaky.md      0 "重试后成功" --check-links          # 服务器对 /flaky 的第 1 次请求回 503（只能跑这一次）
t $T/ok_link_flaky.md      0 "0 个错误"                           # 不加 --check-links 不发请求
t $T/bad_link_dead.md      1 "返回 HTTP 500（已重试 1 次；每次的结果：HTTP 500；HTTP 500）" --check-links
t $T/bad_link_refused.md   1 "请求失败（已重试 1 次；每次的结果：URLError：" --check-links

echo "---- 7：--strict ----"
t $T/variant.md            1 "--strict：异体匹配按错误算" --strict
t $T/variant.md            0 "[异体匹配] 第8行"                   # 不加 --strict 还是 0
t $T/r2_variant_yu.md      0 "[异体匹配] 第4行 「天子之職莫大于禮」（鉴1）"   # reviewer：於→于，异体表里有
t $T/r2_variant_yu.md      1 "--strict：异体匹配按错误算" --strict
t $T/ok_multi.md           0 "5 条引文，0 个错误" --strict

echo "---- reviewer 第 2 轮的其余坏样例：全都要报错 ----"
t $T/r2_bad_fanqie_as_jian.md 1 "在 鉴1 里找不到「絺，抽遲翻」"
t $T/r2_bad_hu_as_jian.md     1 "在 鉴1 里找不到「高二尺爲一版；三版，六尺」"
t $T/r2_bad_onechar.md        1 "在 胡1 里找不到「高三尺爲一版；三版，六尺」"
t $T/r2_bad_realtypo.md       1 "在 鉴1 里找不到「魏於是始大於三晉」"
t $T/r2_bad_splice.md         1 "在 胡1 里找不到「城不浸者三版；高二尺爲一版」"
t $T/r2_bad_splice2.md        1 "在 胡1 里找不到「城不浸者三版高二尺」"

echo "---- 脚本不改输入 ----"
after=$(inputs_sum)
if [ "$before" = "$after" ]; then echo "PASS  测试目录里所有 .md 跑完前后一字不差"; else echo "FAIL  有 .md 被改了"; fail=1; fi

[ $fail = 0 ] && echo "全部符合期望" || echo "有不符合期望的"
exit $fail
