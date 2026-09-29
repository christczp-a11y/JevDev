"""从真的 REGISTRY.md 造一份「故意改坏的」副本，给 run_all.sh 做反向试验。
用法：python video/tests/registry/mutate.py <改法> <原登记表> <输出>
每种改法只坏一处，registry_check.py 必须拦住并报出对应的原因。改法的名字见 CASES。
"""
import sys
from pathlib import Path


def row_idx(lines, path):
    """第二节素材表里 path 那一行的下标。"""
    hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{path}` |")]
    assert len(hits) >= 1, f"登记表里没有 {path}"
    return hits[0]


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def join(c):
    return "| " + " | ".join(c) + " |"


def edit(path, col, value):
    def f(lines):
        i = row_idx(lines, path)
        c = cells(lines[i])
        c[col] = value
        lines[i] = join(c)
        return lines
    return f


def delete_row(path):
    def f(lines):
        del lines[row_idx(lines, path)]
        return lines
    return f


def replace_text(old, new):
    def f(lines):
        text = "\n".join(lines)
        assert old in text, f"登记表里找不到「{old}」"
        return text.replace(old, new, 1).split("\n")
    return f


def insert_after(path, new_line):
    def f(lines):
        lines.insert(row_idx(lines, path) + 1, new_line)
        return lines
    return f


def append(new_line):
    def f(lines):
        return lines + [new_line]
    return f


def dup_row(path):
    def f(lines):
        i = row_idx(lines, path)
        lines.insert(i + 1, lines[i])
        return lines
    return f


def drop_last_col(path):
    def f(lines):
        i = row_idx(lines, path)
        lines[i] = join(cells(lines[i])[:-1])
        return lines
    return f


GHOST = "| `chars/ghost.png` | x | 右 | 10×10 | 无 | 定稿 | x | 试做集 |"

# 列：0 路径 1 属于 2 朝向 3 尺寸 4 内含别的角色 5 状态 6 备注 7 范围
CASES = {
    "delete_row": delete_row("chars/kid_give.png"),
    "delete_coin_row": delete_row("props/coin.png"),
    "bad_facing": edit("chars/kid_give.png", 2, "向右"),
    "empty_facing": edit("chars/kid_give.png", 2, ""),
    "bad_size": edit("chars/kid_give.png", 3, "395×484"),
    "bad_size_format": edit("chars/kid_give.png", 3, "394x"),
    "bad_status": edit("chars/kid_give.png", 5, "大概定稿"),
    "bad_scope": edit("chars/kid_give.png", 7, "以后再说"),
    "bad_baked_cell": edit("chars/kid_give.png", 4, "不知道"),
    "coin_final": edit("props/coin.png", 5, "定稿"),
    "yuanbao_final": edit("chars/d2_gold_yuanbao.png", 5, "定稿"),
    "baked_missing": edit("chars/dad2_grab.png", 4, "无"),
    "baked_extra": edit("chars/kid_give.png", 4, "有：小豆子（d2_）"),
    "dup_prefix": replace_text("| 商鞅旧版 | `sy_` |", "| 商鞅旧版 | `sy2_` |"),
    "prefix_of_other": replace_text("| 商鞅旧版 | `sy_` |", "| 商鞅旧版 | `sy2_x` |"),
    "stop_prefix_mismatch": edit("chars/douzi_run.png", 5, "定稿"),
    "ghost_outside": append(GHOST),
    "ghost_inside": insert_after("chars/kid_give.png", GHOST),
    "dup_row": dup_row("chars/kid_give.png"),
    "missing_column": drop_last_col("chars/kid_give.png"),
    "warn_unfinished": edit("chars/sgm_frown.png", 5, "未定稿"),
}


def main():
    case, src, dst = sys.argv[1:4]
    if case not in CASES:
        sys.exit(f"没有这种改法：{case}（可用：{'、'.join(CASES)}）")
    lines = Path(src).read_text(encoding="utf-8").split("\n")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text("\n".join(CASES[case](lines)), encoding="utf-8")


if __name__ == "__main__":
    main()
