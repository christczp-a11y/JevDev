"""给已有的草稿包（重新）配封面主图，不用重跑整个 make_post。

用法：
  python scripts/add_image.py data/posts/<草稿包>                  # Codex 画插画
  python scripts/add_image.py data/posts/<草稿包> --photos <文件夹>  # 换成 Chris 的实拍
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import make_post  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--photos")
    args = ap.parse_args()
    pkg_dir = Path(args.package)
    pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
    chosen = pkg["drafts"][pkg["chosen_index"]]
    # 重新配图时去掉上一次加的插画说明，免得重复
    chosen["body"] = chosen["body"].replace("\n🎨 封面为 AI 插画，仅作示意", "")
    for old in pkg_dir.glob("card_*.png"):
        old.unlink()
    make_post.finalize(chosen, pkg_dir, args.photos)
    (pkg_dir / "package.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    print("完成：", *chosen["images"], sep="\n  ")


if __name__ == "__main__":
    main()
