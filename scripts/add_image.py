"""给已有的草稿包（重新）配封面主图，不用重跑整个 make_post。

用法：
  python scripts/add_image.py data/posts/<草稿包>                  # Codex 画插画
  python scripts/add_image.py data/posts/<草稿包> --photos <文件夹>  # 换成 Chris 的实拍
  python scripts/add_image.py data/posts/<草稿包> --photos <文件夹> --photo-credit "Tourism Richmond"  # 已获授权的图
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import make_post  # noqa: E402
from jevdev import stock  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--photos")
    ap.add_argument("--photo-credit")
    args = ap.parse_args()
    pkg_dir = Path(args.package)
    pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
    chosen = pkg["drafts"][pkg["chosen_index"]]
    # 重新配图：去掉上一次的图和图片说明，免得重复
    chosen["body"] = "\n".join(ln for ln in chosen["body"].split("\n")
                               if ln not in ("🎨 封面为 AI 插画，仅作示意", stock.BODY_NOTE)
                               and not ln.startswith("📷 图片来源："))
    for k in ("image", "image_label", "cutout"):
        chosen["cover"].pop(k, None)
    for old in pkg_dir.glob("card_*.png"):
        old.unlink()
    make_post.finalize(chosen, pkg_dir, args.photos, args.photo_credit)
    (pkg_dir / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("完成：", *chosen["images"], sep="\n  ")


if __name__ == "__main__":
    main()
