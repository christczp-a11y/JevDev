#!/bin/bash
# 一键重跑 video/jev_pick.py 的测试（工作流第 2 步、第 9 步；PITFALLS E6、P8）。
# 用法（仓库根目录）：bash video/tests/jev_pick/run_all.sh
# 分两段：
#   离线（一定跑，不要网络、不要真 key）：没有 key 立刻报错、输入格式错误、连不上 Jev 时报错（假 key + 指向本机没人听的端口）、test_logic.py（假 Jev：正反两个顺序、对照项、缓存、退出码）。
#   带 key 的真跑（有 TYPESAFE_API_KEY 才跑；没有就大声写「SKIP」，不算失败）：六个类别各真跑一次，对照项都要排最后（classify：对照评论要分对）；
#     analogy 里故意写歪的那个要被标「疑似歪曲史实」；classify 里几条一眼能看出类别的评论要分对；同样的输入再跑一次不再发请求。
#     结果和缓存在 video/out/tests/jev_pick/。第一次约 130 次请求、几秒；缓存在，之后重跑是 0 次请求。
cd "$(dirname "$0")/../../.." || exit 2
export PYTHONIOENCODING=utf-8
PY=.venv/Scripts/python
[ -x "$PY" ] || PY=.venv/bin/python
T=video/tests/jev_pick
O=video/out/tests/jev_pick
mkdir -p $O
fail=0

t() {  # t 名字 期望退出码 关键输出 命令...   （关键输出在标准输出或标准错误里都行）
  local name=$1 want=$2 key=$3; shift 3
  local out; out=$("$@" 2>&1); local got=$?
  if [ "$got" = "$want" ] && grep -qF -- "$key" <<<"$out"; then
    echo "PASS  $name  退出码 $got  含「$key」"
  else
    echo "FAIL  $name  退出码 $got（期望 $want），关键输出「$key」$(grep -qF -- "$key" <<<"$out" && echo 有 || echo 没有)"
    echo "$out" | sed 's/^/      /'
    fail=1
  fi
}

J="$PY video/jev_pick.py"
DUMMY=test-key-not-real-0000

echo "---- 离线：没有 key（P8）----"
t "没有 key（变量是空的）"    2 "TYPESAFE_API_KEY"  env TYPESAFE_API_KEY= $J title $T/title.json
t "没有 key（classify）"       2 "TYPESAFE_API_KEY"  env TYPESAFE_API_KEY= $J classify $T/classify.json

echo "---- 离线：输入格式 ----"
t "没有 context"              2 "要有 context"                       env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_no_context.json
t "只有一个候选"              2 "至少 2 个"                          env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_one_candidate.json
t "id 重复"                   2 "id「t1」重复了"                     env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_dup_id.json
t "id 叫 _ctrl"               2 "id「_ctrl」重复了"                  env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_ctrl_id.json
t "quiz 不是四段"             2 "共 4 段"                            env TYPESAFE_API_KEY=$DUMMY $J quiz $T/bad_quiz_parts.json
t "类别和文件里的不一致"      2 "命令行给的是「title」"              env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_category_mismatch.json
t "文件不是 JSON"             2 "读不了或不是 JSON"                  env TYPESAFE_API_KEY=$DUMMY $J title $T/bad_not_json.json
t "文件不存在"                2 "读不了或不是 JSON"                  env TYPESAFE_API_KEY=$DUMMY $J title $T/不存在.json
t "没有这个类别"              2 "invalid choice"                     env TYPESAFE_API_KEY=$DUMMY $J poem $T/title.json

echo "---- 离线：连不上 Jev ----"
t "连不上：退出码 3"          3 "Jev 调用失败，没有结果"             env TYPESAFE_API_KEY=$DUMMY TYPESAFE_BASE_URL=http://127.0.0.1:9 $J title $T/title.json --cache $O/offline_cache.json
out=$(env TYPESAFE_API_KEY=$DUMMY TYPESAFE_BASE_URL=http://127.0.0.1:9 $J title $T/title.json --cache $O/offline_cache.json 2>&1)
if grep -qF -- "$DUMMY" <<<"$out"; then echo "FAIL  连不上：key 出现在输出里"; fail=1; else echo "PASS  连不上：key 没有出现在输出里"; fi
rm -f $O/offline_cache.json

echo "---- 离线：逻辑（假 Jev）----"
out=$($PY $T/test_logic.py 2>&1); rc=$?
grep -v '^PASS' <<<"$out" | sed 's/^/      /'
echo "$(grep -c '^PASS' <<<"$out") 项 PASS"
[ $rc = 0 ] || { echo "FAIL  test_logic.py（退出码 $rc）"; fail=1; }

echo "---- 带 key 的真跑 ----"
if [ -z "$TYPESAFE_API_KEY" ]; then
  echo "SKIP  没有 TYPESAFE_API_KEY：六个类别的真跑（对照项要排最后）没有跑。有 key 的环境里一定要再跑一遍这个脚本。"
else
  live() {  # live 类别  ——  真跑一次，对照项排最后（退出码 0）
    local c=$1
    if [ "$c" = classify ]; then
      t "真跑 $c：对照评论分对了" 0 "对照评论分对了：这次的分类可信" $J $c $T/$c.json --out $O/$c.out.json --cache $O/cache.json
    else
      t "真跑 $c：对照项排最后" 0 "对照项排在最后：这次的排名可信" $J $c $T/$c.json --out $O/$c.out.json --cache $O/cache.json
    fi
  }
  for c in analogy quiz catchphrase title cover_text classify; do live $c; done
  # 具体的判断（几条一眼能看出的）
  out=$($J analogy $T/analogy.json --cache $O/cache.json 2>&1)
  grep -qE "^ +[0-9]+ +a4 .*疑似歪曲史实" <<<"$out" && echo "PASS  analogy：故意写歪的 a4（考试作弊被开除）被标「疑似歪曲史实」" || { echo "FAIL  analogy：a4 没被标「疑似歪曲史实」"; echo "$out" | sed 's/^/      /'; fail=1; }
  grep -qE "^ +1 +a[123] " <<<"$out" && echo "PASS  analogy：第 1 名不是那个歪的" || { echo "FAIL  analogy：第 1 名是歪的"; fail=1; }
  grep -qF "调用 0 次新请求" <<<"$out" && echo "PASS  缓存：同样的输入再跑一次，0 次新请求" || { echo "FAIL  缓存：重跑还在发请求"; fail=1; }
  out=$($J classify $T/classify.json --cache $O/cache.json 2>&1)
  for pair in "c1:→ 看懂了" "c2:→ 没看懂" "c3:→ 想看下一集" "c4:→ 有意见"; do
    id=${pair%%:*}; want=${pair#*:}
    grep -qE "^  $id .*$want" <<<"$out" && echo "PASS  classify：$id $want" || { echo "FAIL  classify：$id 没分到「$want」"; echo "$out" | sed 's/^/      /'; fail=1; }
  done
fi

echo
if [ $fail = 0 ]; then echo "run_all.sh：全过"; else echo "run_all.sh：有失败"; fi
exit $fail
