"""video/board.py 的测试（不要网络、不要 key）：用合成的登记表和小图，不依赖真实素材。
测：这一集的定稿人物 / 系列角色 / 别集的、未定稿的不进；家族怎么认（家族名、颜色、提到同集的人、名字第一个字、认不出来）；PX 缺省 0.42；
皮影图不算站姿；布景按目录分（共用背景不单独出、停用的和别集的不进）；三种图都出得来；分镜表里同镜的人拼进剪影图；输入错误退出码 2；board_tj01.py 还在。
用法（仓库根目录）：.venv/Scripts/python video/tests/board/test_board.py     退出码 0 = 全过。"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "video"))
import board  # noqa: E402

OUT = ROOT / "video" / "out" / "tests" / "board"
CASE = OUT / "case"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

IMGS = {   # 路径: (宽, 高, 朝向, 状态, 范围, 属于)
    "chars/ja_stand.png": (300, 480, "右", "定稿", "tj99", "甲 `ja_`"), "chars/ja_point.png": (300, 480, "右", "定稿", "tj99", "甲 `ja_`"),
    "chars/jb_stand.png": (250, 470, "右", "定稿", "tj99", "乙 `jb_`"), "chars/jc_stand.png": (260, 470, "右", "定稿", "tj99", "丙 `jc_`"),
    "chars/jd_stand.png": (240, 470, "右", "定稿", "tj99", "周某 `jd_`"), "chars/je_stand.png": (240, 470, "右", "定稿", "tj99", "无名氏 `je_`"),
    "chars/jf_shadow.png": (900, 1400, "右", "定稿", "tj99", "皮影人 `jf_`"),
    "chars/sg_pose.png": (400, 470, "右", "定稿", "系列", "讲解人 `sg_`"), "chars/xx_stand.png": (250, 470, "右", "定稿", "tj98", "别集的人 `xx_`"),
    "chars/yy_stand.png": (250, 470, "右", "未定稿", "tj99", "未定稿的人 `yy_`"),
    "sets/land/sky.png": (1024, 1536, "正面", "定稿", "tj99", "布景 land（共用）"), "sets/land/ground.png": (1528, 218, "正面", "定稿", "tj99", "布景 land"),
    "sets/land/ridge_far.png": (1016, 462, "正面", "定稿", "tj99", "布景 land"),
    "sets/hall/wall.png": (1528, 285, "正面", "定稿", "tj99", "布景 hall（大殿）"), "sets/hall/gate.png": (1410, 486, "正面", "定稿", "tj99", "布景 hall（大殿）"),
    "sets/hall/lamp.png": (200, 300, "正面", "定稿", "tj99", "布景 hall（大殿）"), "sets/hall/old.png": (300, 300, "正面", "停用", "tj99", "布景 hall（大殿）"),
    "sets/other/x.png": (300, 300, "正面", "定稿", "tj98", "布景 other（别集）"),
}
PERSONS = [
    ("甲（晋国智家的族长）", "ja_", "tj99", "赭红交领深衣", "0.5", "定稿"), ("乙（谋士）", "jb_", "tj99", "靛蓝 #2d5b9a 交领", "0.4", "定稿"),
    ("丙（甲的族人）", "jc_", "tj99", "浅色深衣", "—", "定稿"), ("周某（天子）", "jd_", "tj99", "黑衣", "0.3", "定稿"),
    ("无名氏", "je_", "tj99", "灰袍", "0.4", "定稿"), ("皮影人（前史）", "jf_", "tj99", "皮影", "—", "定稿"),
    ("讲解人（系列）", "sg_", "试做集", "紫袍", "0.62", "定稿"), ("别集的人", "xx_", "tj98", "灰", "0.4", "定稿"), ("未定稿的人", "yy_", "tj99", "灰", "0.4", "未定稿"),
]


def make_case():
    rows = ["## 一、历史人物表", "", "| 人物 | 定稿前缀 | 首次出现的集 | 朝代服饰要点 | PX | 状态 |", "|---|---|---|---|---|---|"]
    rows += [f"| {a} | `{b}` | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in PERSONS]
    rows += ["", "## 二、素材表", "", "| 路径 | 属于 | 朝向 | 尺寸 | 内含 | 状态 | 备注 | 范围 |", "|---|---|---|---|---|---|---|---|"]
    for path, (w, h, facing, status, scope, owner) in IMGS.items():
        f = CASE / "assets" / path
        f.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([w * 0.1, h * 0.05, w * 0.9, h * 0.95], fill=(180, 90, 60, 255))
        im.save(f)
        rows.append(f"| `{path}` | {owner} | {facing} | {w}×{h} | 无 | {status} | 测试图 | {scope} |")
    (CASE / "REGISTRY.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def cli(*args):
    p = subprocess.run([sys.executable, str(ROOT / "video" / "board.py"), *[str(a) for a in args]], capture_output=True, text=True, encoding="utf-8", env=ENV, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


ARGS = ["--registry", CASE / "REGISTRY.md", "--assets-root", CASE / "assets"]


def setUpModule():
    make_case()


class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.E = board.load_ep("tj99", CASE / "REGISTRY.md", CASE / "assets")

    def test_who_is_in_and_who_is_not(self):
        self.assertEqual([w["prefix"] for w in self.E.people], ["ja_", "jb_", "jc_", "jd_", "je_"])       # 皮影、别集、未定稿的不进
        self.assertEqual([w["prefix"] for w in self.E.refs], ["sg_"])                                        # 系列角色当参照

    def test_px_from_registry_and_default(self):
        px = {w["prefix"]: w["px"] for w in self.E.people}
        self.assertEqual(px["ja_"], 0.5)
        self.assertEqual(px["jc_"], board.DEFAULT_PX)

    def test_houses_are_recognised(self):
        # 甲：文字里有家族名；乙：文字里有家族颜色；丙：提到同集的人（甲）；周某：名字第一个字；无名氏：认不出来
        h = {w["prefix"]: w["house"] for w in self.E.people}
        self.assertEqual(h, {"ja_": "智家", "jb_": "韩家", "jc_": "智家", "jd_": "周王室", "je_": "其他"})

    def test_stand_image_prefers_stand_then_right_facing(self):
        img = {w["prefix"]: w["img"] for w in self.E.people + self.E.refs}
        self.assertEqual(img["ja_"], "chars/ja_stand.png")
        self.assertEqual(img["sg_"], "chars/sg_pose.png")

    def test_set_dirs(self):
        d = board.set_dirs(self.E)
        self.assertEqual(sorted(d), ["hall", "land"])                                                      # 别集的 other 不进
        self.assertEqual(sorted(Path(k).name for k, _ in d["hall"]), ["gate.png", "lamp.png", "wall.png"])   # 停用的 old 不进
        self.assertTrue(board.is_base(d["land"]) and not board.is_base(d["hall"]))


class TestCli(unittest.TestCase):
    def test_all_three_boards(self):
        out = OUT / "all"
        rc, text = cli("tj99", "all", "--out", out, *ARGS)
        self.assertEqual(rc, 0, text)
        for f in ("board_lineup.png", "board_silhouette.png", "board_set_hall.png"):
            with Image.open(out / f) as im:
                self.assertGreater(im.width, 800, f)
        self.assertFalse((out / "board_set_land.png").exists(), "共用背景不单独出")
        self.assertIn("没进阵容：皮影人", text)
        self.assertIn("5 个人物 + 1 个系列角色", text)
        with Image.open(out / "board_set_hall.png") as im:
            self.assertEqual(im.size, (1080 + 40 + 820, 1920))
        self.assertTrue((ROOT / "video" / "board_tj01.py").exists(), "board_tj01.py 保留不删")

    def test_silhouette_adds_shot_rows_from_storyboard(self):
        sb = OUT / "sb.json"
        sb.parent.mkdir(parents=True, exist_ok=True)
        sb.write_text('{"episode":"tj99","shots":[{"id":"a1","actors":[{"img":"chars/ja_stand.png"},{"img":"chars/jb_stand.png"}]},'
                      '{"id":"a2","actors":[{"img":"chars/ja_stand.png"},{"img":"chars/jb_stand.png"}]},{"id":"a3","actors":[{"img":"chars/jc_stand.png"}]}]}', encoding="utf-8")
        rc, text = cli("tj99", "silhouette", "--out", OUT / "sil", "--storyboard", sb, *ARGS)
        self.assertEqual(rc, 0, text)
        self.assertIn("2 行", text)                       # 阵容 + 「甲和乙同镜（2 镜）」
        rc, text = cli("tj99", "silhouette", "--out", OUT / "sil2", "--storyboard", OUT / "nope.json", *ARGS)
        self.assertIn("1 行", text)

    def test_sets_by_name(self):
        rc, text = cli("tj99", "sets", "hall", "--out", OUT / "sets", *ARGS)
        self.assertEqual(rc, 0, text)
        self.assertIn("board_set_hall.png", text)

    def test_errors_are_exit_2(self):
        rc, text = cli("tj99", "sets", "nowhere", "--out", OUT / "e", *ARGS)
        self.assertEqual(rc, 2, text)
        self.assertIn("没有这些布景", text)
        rc, text = cli("tj77", "lineup", "--out", OUT / "e", *ARGS)
        self.assertEqual(rc, 2, text)
        self.assertIn("没有 tj77 的定稿人物", text)
        rc, text = cli("tj99", "lineup", "--out", OUT / "e", "--registry", OUT / "no_such.md")
        self.assertEqual(rc, 2, text)
        self.assertIn("找不到素材登记表", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
