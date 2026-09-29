"""build_stage3d.py 的退出码和初始化的测试（第 2 轮补充第 5 条、第 19 项）：
- 退出码 0 = 没问题、1 = 质检查出了问题、2 = 崩溃或环境有问题（不是质检结果）；
- 字体没加载成功：打印原因、退出码 2，不重试（不是偶发问题）；
- 初始化偶发失败（reviewer 遇到过 `Page.evaluate: Event`）：换新浏览器重试，第二次成功就往下走；
- 每次初始化完先空渲一帧。
用法（仓库根目录）：python video/tests/stage3d/check_stage3d.py    退出码 0 = 全过。输出在 video/out/tests/stage3d/。"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/stage3d"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["STAGE3D_OUT"] = str(OUT / "out")
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT / "video/stage3d"))
sys.stdout.reconfigure(encoding="utf-8")
import build_stage3d as bs  # noqa: E402
import render  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"：{detail}" if detail else ""))


env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
py = str(ROOT / ".venv/Scripts/python")
run = lambda *a, **e: subprocess.run([py, str(ROOT / "video/stage3d/build_stage3d.py"), *a], capture_output=True, text=True, encoding="utf-8", env={**env, **e}, cwd=ROOT)

# ---- 退出码 ----
r = run("frame", "99")
check("frame 99（没有这一场）：崩溃，退出码 2，说「不是质检查出的问题」", r.returncode == 2 and "崩溃了" in r.stderr and "Traceback" in r.stderr, f"退出码 {r.returncode}")
r = run("qa", "99")
check("qa 99：崩溃，退出码 2", r.returncode == 2, f"退出码 {r.returncode}")
r = run("stills", "1", "1.0", STAGE3D_SCENES=str(OUT / "no_such_dir"))
check("场景目录不存在：退出码 2（不是 1）", r.returncode == 2, f"退出码 {r.returncode}")
r = run("stills", "1", "1.0")
check("正常截一张静帧：退出码 0", r.returncode == 0 and (OUT / "out" / "still_1_001.00.jpg").exists(), f"退出码 {r.returncode}")

# ---- 字体没加载成功、初始化偶发失败（用一个包了一层的 playwright：新页面里拦掉 woff2 / 第一次 goto 报错）----
class Proxy:
    def __init__(self, real, block_fonts=False, fail_first=False):
        self.real, self.block, self.fail, self.launches = real, block_fonts, fail_first, 0
        self.chromium = self

    def launch(self, **kw):
        self.launches += 1
        outer, browser = self, self.real.chromium.launch(**kw)
        first = self.launches == 1

        class B:
            def new_page(_, **k):
                page = browser.new_page(**k)
                if outer.block:
                    page.route("**/*.woff2", lambda r: r.abort())
                if outer.fail and first:
                    def boom(*a, **kw):
                        raise PlaywrightError("Page.evaluate: Event")
                    page.goto = boom
                return page

            def close(_):
                browser.close()
        return B()


srv = bs.serve()
with sync_playwright() as p:
    try:
        bs.open_stage(Proxy(p, block_fonts=True), 1, srv)
        code = None
    except SystemExit as e:
        code = e.code
    check("3D：字体文件加载不出来：退出码 2，不重试", code == 2, f"退出码 {code}")
    try:
        render.open_page(Proxy(p, block_fonts=True), render.load_scene(ROOT / "video/scenes/ep01v2/shot1.json"))
        code = None
    except SystemExit as e:
        code = e.code
    check("2D：字体文件加载不出来：退出码 2", code == 2, f"退出码 {code}")
    # 3D 贴图读不到：报错带图的路径（reviewer 又碰到一次 `Page.evaluate: Event`，看不出是哪张图）
    class BlockFar(Proxy):
        def launch(self, **kw):
            browser = self.real.chromium.launch(**kw)

            class B:
                def new_page(_, **k):
                    page = browser.new_page(**k)
                    page.route("**/qin_gate/far.png", lambda r: r.abort())
                    return page

                def close(_):
                    browser.close()
            return B()
    try:
        bs.open_stage(BlockFar(p), 1, srv, tries=1)
        msg = None
    except PlaywrightError as e:
        msg = str(e)
    check("3D：贴图读不到：错误里带图的路径（贴图加载失败：…/qin_gate/far.png）", bool(msg) and "贴图加载失败" in msg and "qin_gate/far.png" in msg, (msg or "没有报错")[:160])
    px = Proxy(p, fail_first=True)
    browser, page, scene = bs.open_stage(px, 1, srv)
    ok_frame = page.evaluate("typeof window.nametagStats === 'function'")
    browser.close()
    check("3D：初始化第一次偶发失败（Page.evaluate: Event）：换新浏览器重试，第二次成功", px.launches == 2 and ok_frame, f"启动了 {px.launches} 次浏览器")
srv.shutdown()

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
