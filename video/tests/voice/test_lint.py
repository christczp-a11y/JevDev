"""story.py --lint 照旧能读带 voice_text 的剧本（story.py 不许为这一步改；voice_text 是它不认识、会忽略的顶层字段）。离线，不要 Jev key。"""
import json
import subprocess
import unittest

from harness import PY, ROOT, make_case, workdir

N6 = ROOT / "video" / "stories" / "ep01" / "N6_你搬不搬.json"


def lint(folder, *extra):
    return subprocess.run([PY, "video/story.py", str(folder), "--lint", *extra], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


class Lint(unittest.TestCase):
    def test_n6_lints_as_before(self):
        r = lint(ROOT / "video" / "stories" / "ep01", "--only", "N6")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("剧本检查通过", r.stdout)

    def test_scripts_with_voice_text_are_read(self):
        d = workdir("lint_vt")
        n6 = json.loads(N6.read_text(encoding="utf-8"))
        vt = {"搬根木头就给十金，你搬不搬？": "搬根木头就给十金，你搬不搬？"}
        a = dict(n6, id="N6vt", voice_text=vt)                                                   # voice_text 在 lines 前面
        b = {"id": "N6vt2", "name": "x", "title": n6["title"], "lines": n6["lines"], "voice_text": vt}   # 在 lines 后面
        (d / "N6vt.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "N6vt2.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "episode.json").write_text(json.dumps({"core_question": "x", "cast": {"商鞅": {"voice": "zh-CN-YunyangNeural"}},
                                                    "banned": {"知伯": "异名"}}, ensure_ascii=False), encoding="utf-8")
        r = lint(d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2 版（N6vt, N6vt2）", r.stdout)

    def test_lint_still_fails_on_bad_seconds(self):
        d = workdir("lint_bad")
        s = make_case(d, [("旁白", "一。"), ("旁白", "二。")])
        data = json.loads(s.read_text(encoding="utf-8")); data["lines"][1][0] = -1.0
        s.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(lint(d).returncode, 1)


if __name__ == "__main__":
    unittest.main()
