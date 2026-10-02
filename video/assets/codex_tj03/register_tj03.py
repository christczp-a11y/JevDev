"""tj03 第 5 步（提前）：把新角色、新姿势登记进 video/assets/REGISTRY.md（幂等：已经登记的跳过；文件还没画出来的也跳过），并把脸框写进 faces.json。

  .venv/Scripts/python video/assets/codex_tj03/register_tj03.py

朝向是逐张看图定的（PITFALLS T13、T25）：朝右的记 `右`，要朝左的姿势（交领人物不许 flip）都是重新画的，记 `左`；群像记它朝的那一侧。
尺寸从文件里读。PX 从 tj03_meta.py 算（目标身高 ÷ 站姿图高）。
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
REG = ASSETS / "REGISTRY.md"
FACES = ASSETS / "faces.json"
sys.path.insert(0, str(HERE))
import tj03_meta as M  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OWNER = {
    "wuh": "魏武侯 `wuh_`", "wq": "吴起 `wq_`", "rower": "划桨的士兵 `rower_`",
    "zs": "子思 `zs_`", "gb": "苟变 `gb_`", "wh": "卫侯 `wh_`",
}
# 文件名(不含 .png) -> (朝向, 带别人, 备注, 脸框 [x0, x1, y0, y1] 或 None)
CH = {}
PEOPLE = {}
exec((HERE / "register_tj03_rows.py").read_text(encoding="utf-8"))   # 填 CH、PEOPLE：每张图看过以后的备注都在那个文件里

DIR_ROW = ("| `video/assets/codex_tj03/` | tj03 第 5 步（提前）：Codex 提示词（`*.txt`）、日志、原始素材表（`wuh_pose_a/b`、`wq_pose`、`preview_chars`、`rower_row`、`rower_stop`、`wuh_hi_a/b/c`、`wq_hi_a/b/c`；`*_v1.png` 是被重画换掉的旧版）、"
           "`run_tj03.sh`（并行调 Codex）、`split_tj03.py`（拆图、表情组对位）、`register_tj03.py` + `register_tj03_rows.py`（登记 + 脸框）、`tj03_meta.py`（目标身高、PX）、"
           "`board_tj03.py`（阵容总览 `video/out/tj03/lineup.png`、新姿势总览 `poses_new.png`，不进 git） |")


def size_of(rel):
    im = Image.open(ASSETS / rel)
    return f"{im.width}×{im.height}"


def owner_of(stem):
    for k in sorted(OWNER, key=len, reverse=True):
        if stem.startswith(k + "_"):
            return OWNER[k]
    raise KeyError(stem)


def main():
    md = REG.read_text(encoding="utf-8")
    if "--redo" in sys.argv:        # 备注改了要重写：先把本脚本以前登记的 tj03 行删掉（魏武侯、吴起的人物表行是手改的，不动）
        keep = []
        for l in md.split("\n"):
            if re.match(r"^\| `chars/(wuh|wq|rower|zs|gb|wh)_[^`]*\.png` \|", l) and l.rstrip().endswith("| tj03 |"):
                continue
            if l.startswith("| ") and "| tj03 |" in l and not l.startswith("| `") and any(f"`{k}_`" in l.split("|")[2] for k in PEOPLE):
                continue
            if l.startswith("| `video/assets/codex_tj03/`"):
                continue
            keep.append(l)
        md = "\n".join(keep)
    lines = md.split("\n")
    registered = set(re.findall(r"^\| `((?:chars|props|rig|sets|brand)/[^`]+\.png)`", md, re.M))
    new_chars = []
    faces = json.loads(FACES.read_text(encoding="utf-8"))
    nface = 0
    for stem, (face, baked, note, box) in CH.items():
        rel = f"chars/{stem}.png"
        if not (ASSETS / rel).exists():
            continue
        if box is not None and faces.get(rel) != list(box):
            faces[rel] = list(box)
            nface += 1
        if rel in registered:
            continue
        new_chars.append(f"| `{rel}` | {owner_of(stem)} | {face} | {size_of(rel)} | {baked} | 定稿 | {note} | tj03 |")
    new_people = []
    for pre, (nm, code, look, pxs) in PEOPLE.items():
        if f"`{pre}_`" in md.split("## 二、素材表")[0]:
            continue
        if not any((ASSETS / "chars").glob(f"{pre}_*.png")):
            continue
        new_people.append(f"| {nm} | {code} | tj03 | {look} | {pxs} | 定稿 |")

    def insert_before(prefix, rows):
        if not rows:
            return
        j = next(k for k, l in enumerate(lines) if l.startswith(prefix))
        k = j - 1
        while k > 0 and not lines[k].startswith("|"):
            k -= 1
        lines[k + 1:k + 1] = rows

    insert_before("### 2.2", new_chars)
    insert_before("tj01 的新角色（智、赵、韩、魏各家的人物）画完以后", new_people)
    if "`video/assets/codex_tj03/`" not in md:
        j = next(k for k, l in enumerate(lines) if l.startswith("| `video/assets/codex_tj02/`"))
        lines.insert(j + 1, DIR_ROW)
    REG.write_text("\n".join(lines), encoding="utf-8")
    # faces.json 的格式：每个键一行（数组不折行）、键按字母排序，「_说明」在最前面——照原样写回，git diff 里只多新增的行
    entries = [f' {json.dumps(k, ensure_ascii=False)}: {json.dumps(faces[k])}' for k in sorted(faces) if not k.startswith("_")]
    heads = [f' {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}' for k, v in faces.items() if k.startswith("_")]
    FACES.write_text("{\n" + ",\n".join(heads + entries) + "\n}\n", encoding="utf-8")
    print(f"登记：人物 {len(new_people)} 行，姿势图 {len(new_chars)}；faces.json 新增/更新 {nface} 张")


if __name__ == "__main__":
    main()
