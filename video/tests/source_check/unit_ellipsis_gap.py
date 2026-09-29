#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「A……B」间隔上限的边界测试：中间恰好隔 MAX_ELLIPSIS_GAP 个汉字要找得到，多隔 1 个就找不到。
在缓存的鉴1 原文里取两段只出现一次的 6 字，按需要的间隔配对，直接调 source_check.match_code。
用法：.venv/Scripts/python video/tests/source_check/unit_ellipsis_gap.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
import source_check as sc  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
# 下载缓存和 source_check.py 处理本目录简报时用的是同一个：video/out/source_check/source_check/（缺了会下载）
cache_dir = HERE.parent.parent / "out" / HERE.name / "source_check"
raw, _ = sc.load_raw("鉴1", "https://zh.wikisource.org/wiki/資治通鑑/卷001", cache_dir, False)
v = sc.View(sc.wiki_views(raw)[0])
h = v.han
L = 6  # 每段 6 个汉字


def pair(gap):
    """返回 (A, B)：都只在原文出现一次，A 之后隔 gap 个汉字就是 B。"""
    for i in range(len(h) - 2 * L - gap):
        a, b = h[i:i + L], h[i + L + gap:i + 2 * L + gap]
        if h.count(a) == 1 and h.count(b) == 1:
            return a, b
    raise SystemExit("没找到合适的两段")


bad = 0
for gap, want in [(0, "exact-or-variant"), (sc.MAX_ELLIPSIS_GAP, "found"), (sc.MAX_ELLIPSIS_GAP + 1, None)]:
    a, b = pair(gap)
    kind, res = sc.match_code([a, b], [v])
    got = "found" if kind else None
    ok = (got == "found") if want else (got is None)
    bad += not ok
    print("%s  间隔 %d（上限 %d）：%s" % ("PASS" if ok else "FAIL", gap, sc.MAX_ELLIPSIS_GAP,
                                       "找到了" if kind else "找不到（%s）" % res[:20]))
# 顺序反过来：B 在 A 后面隔 0 个字，引文写成 B、A，不该找到
a, b = pair(0)
kind, res = sc.match_code([b, a], [v])
ok = kind is None
bad += not ok
print("%s  顺序颠倒：%s" % ("PASS" if ok else "FAIL", "找不到" if ok else "居然找到了"))
print("间隔边界测试：%s" % ("全部符合" if not bad else "有 %d 项不符" % bad))
sys.exit(1 if bad else 0)
