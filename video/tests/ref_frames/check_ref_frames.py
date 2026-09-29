"""系列参考帧（video/assets/ref/series/，8 张）的检查。
1 自检（很快，不渲染）：8 张的卷号胶囊宽度和字形像素数一致，而且是 ZCOOL KuaiLe 的（宽 338、字形约 2630），不是备用字体的（宽 356、约 2420）。
  E1 再犯（09-29）时，参考帧就是在 ZCOOL KuaiLe 没加载成功时截的，8 张里 5 张是备用字体，没有人在截完以后量过，README 写的却是 ZCOOL。
2 --render：用现在的代码按 README 里的命令重截这 8 个时刻（输出在 video/out/tests/ref_frames/stage3d/），和参考帧带容差对比
  （video/imgdiff.py：差值 > 32 的像素连成片，面积 ≥ 50 像素的片才算变化；同时报出是不是逐像素相同）。
用法（仓库根目录）：
  python video/tests/ref_frames/check_ref_frames.py [--render] [--dir 别的目录]    退出码 0 = 通过
  （--dir：自检别的目录里同名的 8 张图，例如旧参考帧 video/out/tests/ref_frames/old_refs，用来证明检查确实抓得到备用字体）"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "video"))
sys.stdout.reconfigure(encoding="utf-8")
import imgdiff  # noqa: E402

NAMES = ["ep01_s1_t1.5", "ep01_s1_t6.5", "ep01_s1_t13.5", "ep01_s1_t20", "ep01_s4_t10", "ep01_s4_t13.9", "ep01_s6_t1.2", "ep01_s6_t5"]
STILLS = [("1", "1.5 6.5 13.5 20"), ("4", "10 13.9"), ("6", "1.2 5")]
RENDERED = {"ep01_s1_t1.5": "still_1_001.50", "ep01_s1_t6.5": "still_1_006.50", "ep01_s1_t13.5": "still_1_013.50", "ep01_s1_t20": "still_1_020.00",
            "ep01_s4_t10": "still_4_010.00", "ep01_s4_t13.9": "still_4_013.90", "ep01_s6_t1.2": "still_6_001.20", "ep01_s6_t5": "still_6_005.00"}


def kicker_metrics(path):
    """卷号胶囊的宽度（第 124 行上底色最左到最右）和里面米色字形的像素数。ZCOOL KuaiLe：宽 338、字形约 2620–2640；备用无衬线字体：宽 356、约 2420。"""
    a = np.asarray(Image.open(path).convert("RGB")).astype(int)
    dark = (a[124, :, 0] < 95) & (a[124, :, 1] < 95) & (a[124, :, 2] < 95)
    xs = np.nonzero(dark[250:830])[0] + 250
    x0, x1 = int(xs.min()), int(xs.max())
    box = a[92:154, max(x0, 300):min(x1, 780) + 1]   # 背景是深色的帧（拉远到书桌外，s4_t13.9）量不出胶囊的边，宽度只在 300–780 内取，字形像素照样能量
    if x1 - x0 + 1 > 420:
        return None, int(((abs(box[..., 0] - 244) < 24) & (abs(box[..., 1] - 232) < 24) & (abs(box[..., 2] - 208) < 28)).sum())
    cream = (abs(box[..., 0] - 244) < 24) & (abs(box[..., 1] - 232) < 24) & (abs(box[..., 2] - 208) < 28)
    return x1 - x0 + 1, int(cream.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--dir", default=str(ROOT / "video/assets/ref/series"))
    args = ap.parse_args()
    d = Path(args.dir)
    ok = True
    ms = {n: kicker_metrics(d / f"{n}.jpg") for n in NAMES}
    bad = [n for n, (w, g) in ms.items() if not ((w is None or abs(w - 338) <= 4) and abs(g - 2630) <= 80)]
    for n, (w, g) in ms.items():
        print(f"  {n}：卷号胶囊宽 {w if w else '（背景太暗，量不出）'}、字形像素 {g}" + ("" if n not in bad else "   <- 不是 ZCOOL KuaiLe"))
    print(f"{'PASS' if not bad else 'FAIL'}  {d} 里 8 张的卷号胶囊都是 ZCOOL KuaiLe（宽 338、字形约 2630；备用字体是 356 / 约 2420）" + (f"：{len(bad)} 张不是 {bad}" if bad else ""))
    ok &= not bad
    ws = [w for w, _ in ms.values() if w]
    spread = (max(ws) - min(ws), max(g for _, g in ms.values()) - min(g for _, g in ms.values()))
    good = spread[0] <= 4 and spread[1] <= 120
    print(f"{'PASS' if good else 'FAIL'}  8 张的卷号胶囊宽度、字形像素数一致（宽度差 {spread[0]}、字形像素差 {spread[1]}）")
    ok &= good
    if args.render:
        out = ROOT / "video/out/tests/ref_frames/stage3d"
        out.mkdir(parents=True, exist_ok=True)
        for f in out.glob("still_*.jpg"):
            f.unlink()
        env = {**os.environ, "STAGE3D_OUT": str(out), "PYTHONIOENCODING": "utf-8"}
        for k, ts in STILLS:
            r = subprocess.run([str(ROOT / ".venv/Scripts/python"), str(ROOT / "video/stage3d/build_stage3d.py"), "stills", k, *ts.split()], env=env, cwd=ROOT)
            if r.returncode:
                print(f"FAIL  build_stage3d.py stills {k} {ts} 退出码 {r.returncode}")
                return 1
        exact = 0
        for n in NAMES:
            rep = imgdiff.report(imgdiff.load(d / f"{n}.jpg"), imgdiff.load(out / f"{RENDERED[n]}.jpg"))
            exact += rep["exact"]
            print(f"{'PASS' if rep['same'] else 'FAIL'}  重截 {n}：{imgdiff.describe(rep)}")
            ok &= rep["same"]
        print(f"     其中逐像素完全相同的 {exact}/8 张")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
