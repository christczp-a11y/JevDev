"""分场脚本模板（video/episode_build.py、video/episode_config.py）的测试：
1 试做集用新模板生成的场景 JSON = 已提交的 video/scenes/ep01v2/（配音时间线用 video/tests/fixtures/ep01v2_voice/），逐字节一致；
2 tj01 空配置能读、没填完不许开跑；配置写法检查（NAMETAGS 不许写 color、家名要在系列表里）；
3 人物比例：PX 没配的前缀取 REGISTRY.md 人物表的 PX 列，配了的以配置为准（第 2 轮问题 9）；
4 混音：只混渲了的那几场时，时间线按场裁，不再崩（A6，第 2 轮问题 5），整集混音和老算法逐样本一致；单场混音和 --shots 单场出片。
用法（仓库根目录）：python video/tests/episode_build/check_episode_build.py    退出码 0 = 全过。输出在 video/out/tests/episode_build/。"""
import copy
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "video/out/tests/episode_build"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "video")); sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
import audio  # noqa: E402
import build_ep01_v2 as b  # noqa: E402
import episode_build as eb  # noqa: E402
import episode_config as ec  # noqa: E402
import render  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"：{detail}" if detail else ""))


FIX = ROOT / "video/tests/fixtures/ep01v2_voice"
py = str(ROOT / ".venv/Scripts/python")

# ---- 1 场景 JSON 和已提交的一致 ----
sd = OUT / "scenes"
ep = eb.Episode(b.CFG, FIX, sd, OUT / "out")
sd.mkdir(exist_ok=True)
scenes = eb.build_scenes(ep, b.SHOTS)
same = 0
for k, sc in enumerate(scenes, 1):
    (sd / f"shot{k}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    same += (sd / f"shot{k}.json").read_bytes() == (ROOT / f"video/scenes/ep01v2/shot{k}.json").read_bytes()
check("试做集：新模板生成的六个场景 JSON 和已提交的 video/scenes/ep01v2/ 逐字节一致", same == 6, f"{same}/6")
check("试做集配置：没有 NAMETAGS，场景 JSON 里没有 nametags 字段", all("nametags" not in s for s in scenes))

# ---- 2 配置 ----
errs, todos, notes = ec.check(ec.load_config("ep01v2"))
check("ep01v2 配置：写法没问题，没有待填项", not errs and not todos, str((errs, todos)))
errs, todos, notes = ec.check(ec.load_config("tj01"))
check("tj01 空配置：写法没问题，待填项是 B、TITLE.lines[0]、FOOTER、NAMETAGS", not errs and todos == ["B（还没有场次边界）", "TITLE.lines[0]", "FOOTER", "NAMETAGS"], str((errs, todos)))
r = subprocess.run([py, str(ROOT / "video/build_tj01.py"), "--check-config"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
r2 = subprocess.run([py, str(ROOT / "video/build_tj01.py"), "--check-config", "--strict"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
r3 = subprocess.run([py, str(ROOT / "video/build_tj01.py")], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
check("build_tj01.py：--check-config 退出码 0；加 --strict 退出码 1；没填完直接跑：拒绝开跑，退出码 1", (r.returncode, r2.returncode, r3.returncode) == (0, 1, 1) and "配置还没填" in r3.stderr, str((r.returncode, r2.returncode, r3.returncode)))
cfg = copy.deepcopy(b.CFG)
cfg["NAMETAGS"] = {"host": {"name": "司马光", "house": "智家", "color": "#123456"}, "dad": {"name": "爹", "house": "没有这一家"}, "youth": {"name": "小伙", "house": "赵家"}}
errs, _, notes = ec.check(cfg)
check("NAMETAGS 里写 color：报错，说明家族颜色写在系列表里", any("host" in e and "color" in e and "series_style.json" in e for e in errs))
check("NAMETAGS 里的家名不在系列表里：报错，列出现有的家", any("没有这一家" in e and "智家" in e for e in errs))
check("家名在系列表里、颜色还是占位（null）：允许，只提示", not any("'youth'" in e for e in errs) and any("「赵家」" in n for n in notes), str(notes))
try:
    eb.attach_nametags(copy.deepcopy(scenes), cfg["NAMETAGS"])
    check("attach_nametags：家名不在系列表里：退出", False, "没有退出")
except SystemExit as e:
    check("attach_nametags：家名不在系列表里：退出并点名", "没有这一家" in str(e), str(e)[:80])
style = ec.load_series_style()
ss = copy.deepcopy(scenes)
eb.attach_nametags(ss, {"youth": {"name": "小伙", "house": "赵家"}}, style)
tg = ss[0]["nametags"][0]
check("attach_nametags：颜色按家名从系列表取（现在是占位 null）；时间字段 t0 / t1 / hold", tg["color"] is None and tg["hold"] == eb.NAMETAG_HOLD and tg["t0"] < tg["t1"] and tg["house"] == "赵家", str(tg))

# ---- 3 人物比例 ----
cfg = copy.deepcopy(b.CFG); cfg["PX"] = {}
ep2 = eb.Episode(cfg, FIX, OUT / "scenes_px", OUT / "out")
sc = eb.build_scenes(ep2, b.SHOTS)
check("配置里一个 PX 都不写：靠登记表 video/assets/REGISTRY.md 的 PX 列，六个场景 JSON 和写了 PX 的逐字一致（司马光 sgm_ 0.62 不用每集重填）",
      all(json.dumps(x, ensure_ascii=False, indent=1) == (ROOT / f"video/scenes/ep01v2/shot{k}.json").read_text(encoding="utf-8").replace("\r\n", "\n") for k, x in enumerate(sc, 1)))
cfg = copy.deepcopy(b.CFG); cfg["PX"] = {"sgm_": 0.5}
sc = eb.build_scenes(eb.Episode(cfg, FIX, OUT / "scenes_px", OUT / "out"), b.SHOTS)
check("配置里写了 PX：以配置为准（sgm_ 写 0.5 → 司马光 px 0.5）", sc[0]["actors"]["host"]["px"] == 0.5, str(sc[0]["actors"]["host"]["px"]))
a_new = eb.actor(100, "brand_new_pose", [0, 1])
check("登记表和配置里都没有的前缀：用默认比例 0.42（actor() 的默认值）", a_new["px"] == 0.42 == eb.DEFAULT_PX)
check("登记表 PX 列读得对（司马光 0.62、小豆子少年版 d2_teen 0.40 排在 d2_ 前面）", ec.registry_px().get("sgm_") == 0.62 and ec.registry_px().get("d2_teen") == 0.4 and ec.registry_px().get("d2_") == 0.28)

# ---- 4 混音 ----
sr = audio.SR
vdir = OUT / "voice"
vdir.mkdir(exist_ok=True)
for i, f in enumerate((440, 880)):
    subprocess.run([render.FFMPEG, "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={f}:duration=1.0", "-ar", str(sr), str(vdir / f"a{i}.wav")], check=True)
tl = {"duration": 6.0, "lines": [
    {"i": 0, "t0": 0.5, "t1": 1.5, "who": "旁白", "text": "甲", "audio": "a0.wav"},
    {"i": 1, "t0": 3.5, "t1": 4.5, "who": "旁白", "text": "乙", "audio": "a1.wav"}]}
(vdir / "timeline.json").write_text(json.dumps(tl), encoding="utf-8")
cfg2 = {"EP_LABEL": "测试", "TITLE": {"kicker": "k", "lines": ["a"]}, "FOOTER": "f", "B": [(0, 1)], "VOICE": vdir, "OUT": OUT / "out", "SCENES": ROOT / "video/scenes/ep01v2"}
ep3 = eb.Episode(cfg2)
check("测试用的两场时间线：场次边界 [0, 2.5, 6.0]", ep3.B == [0, 2.5, 6.0], str(ep3.B))
energy = lambda v, a, c: float(np.abs(v[int(a * sr): int(c * sr)]).sum())

# 老算法（第 1 轮之前 mix() 里的写法）：台词按时间线上的绝对时刻放
def old_voice(ep_, n):
    v = np.zeros(n)
    for x in ep_.L:
        if x["audio"]:
            clip = eb.decode(ep_.voice / x["audio"], sr)
            i = int(x["t0"] * sr)
            v[i:i + len(clip)] += clip[: n - i]
    return v

full, _ = eb.build_voice(ep3, [1, 2], [75, 105], sr, int(6.0 * sr))
check("整集混音：配音轨和老算法逐样本一致（整集的行为没变）", np.array_equal(full, old_voice(ep3, int(6.0 * sr))))
check("整集混音：两句台词在 0.5 秒和 3.5 秒", energy(full, 0.5, 1.5) > 100 and energy(full, 3.5, 4.5) > 100 and energy(full, 1.6, 3.4) == 0)
try:
    old_voice(ep3, int(3.0 * sr))
    old_crash = False
except ValueError:
    old_crash = True
check("（复现 A6）老算法：只混第 2 场（3 秒）时，第 2 句的位置 3.5 秒 > 3 秒，ValueError 崩溃", old_crash)
part, talk = eb.build_voice(ep3, [2], [90], sr, int(3.0 * sr))
check("只混第 2 场：不崩；第 2 句放在这一场里的 1.0–2.0 秒（不是整集时间线上的 3.5 秒），第 1 句不在里面", energy(part, 1.0, 2.0) > 100 and energy(part, 0, 1.0) == 0 and energy(part, 2.0, 3.0) == 0 and len(part) == 3 * sr, f"talk={talk}")
part, _ = eb.build_voice(ep3, [1], [75], sr, int(2.5 * sr))
check("只混第 1 场：第 1 句在 0.5–1.5 秒，第 2 句不在里面", energy(part, 0.5, 1.5) > 100 and energy(part, 1.5, 2.5) == 0)
part, _ = eb.build_voice(ep3, [1, 2], [75, 100], sr, int(6.0 * sr) - 150)
check("（帧数比时间线短一点：第 2 场少渲了 5 帧）：只混两场也不崩", len(part) > 0)
# 端到端 mix：单场 + 不连续
for ids, frames in (([1], [75]), ([2], [90]), ([1, 2], [75, 105])):
    wav = OUT / f"mix_{'_'.join(map(str, ids))}.wav"
    try:
        eb.mix(ep3, frames, [{} for _ in frames], wav, shot_ids=ids)
        with wave.open(str(wav)) as w:
            dur = w.getnframes() / w.getframerate()
        check(f"mix(shot_ids={ids})：不崩，成品时长 = 渲出来的帧数 / 30", abs(dur - sum(frames) / 30) < 0.02, f"{dur:.3f} 秒")
    except Exception as e:   # noqa: BLE001
        check(f"mix(shot_ids={ids})：不崩", False, f"{type(e).__name__}: {e}")

# --shots：只做第 6 场（下集预告）：渲、拼、混都只这一场，成片 <FINAL>_shots6.mp4，时长 = 这一场的时长
out = OUT / "shots6"
r = subprocess.run([py, str(ROOT / "video/build_ep01_v2.py"), "--shots", "6", "--voice", str(FIX), "--scenes-out", str(OUT / "scenes_shots6"), "--out", str(out)],
                   capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
final = out / "ep01_full_shots6.mp4"
dur = None
if final.exists():
    p = subprocess.run([render.FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)], capture_output=True, text=True)
    dur = float(p.stdout.strip() or 0)
sc6 = json.loads((ROOT / "video/scenes/ep01v2/shot6.json").read_text(encoding="utf-8"))["duration"]
check("build_ep01_v2.py --shots 6：只渲第 6 场，出 ep01_full_shots6.mp4，时长 = 第 6 场的时长，没有整集的文件被覆盖", r.returncode == 0 and dur is not None and abs(dur - sc6) < 0.15 and not (out / "ep01_full.mp4").exists() and not (out / "shot1.mp4").exists(),
      f"退出码 {r.returncode}，时长 {dur}（第 6 场 {sc6} 秒）{r.stderr[-200:] if r.returncode else ''}")

print(f"\n{sum(results)}/{len(results)} 项通过")
sys.exit(0 if all(results) else 1)
