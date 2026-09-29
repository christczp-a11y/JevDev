"""分场脚本模板（工作流第 0 步第 7 项）：从试做集的 build_ep01_v2.py 抽出来的通用部分——
按配音时间线分场、写场景 JSON、逐场渲染 2D、拼接、混音。每集只写自己的 shotN() 和一份配置（video/episodes/<集>.py）。

每集的分场脚本长这样（试做集见 video/build_ep01_v2.py，第一集的样板见 video/build_tj01.py）：

    import episode_build as eb
    from episode_build import actor, sprite, choice
    CFG = eb.load_config("tj01")             # video/episodes/tj01.py 里的 CFG
    def shot1(ep):                            # ep 是读好配音时间线的 Episode
        B, T0, T1, at, base = ep.tools()      # 场次边界、第 i 句的开始/结束秒、第 i 句里某个词的时刻、场景外壳
        ...
        return base(0, "布景名", camera, hud, actors, props, events)
    SHOTS = [shot1, ...]
    if __name__ == "__main__":
        eb.main(CFG, SHOTS)

用法：python video/build_<集>.py [--only 场号,...] [--no-render] [--check-config]
  --no-render     只写出每场的场景 JSON（CFG["SCENES"]），不渲染
  --only 2,3      只渲染这几场（其余沿用已渲染的片段；没渲过的还是会渲）
  --shots 1       只做这几场（第一场样片用）：只渲这几场、只拼这几场、声音也只混这几场（时间线按场裁），成片叫 <FINAL 去掉后缀>_shots<场号>.mp4
  --check-config  只检查配置读得出来、哪些项还没填，不读配音、不写文件
  --voice / --scenes-out / --out   临时换掉配置里的 VOICE / SCENES / OUT（回归对比时输出到临时目录用）

系列固定的东西留在这里，不进每集的配置（工作流第七节）：背景音乐、混音比例（有人说话音乐 0.07，平时 0.20，音效 ×0.45）、
人名牌停留时长；家族颜色在系列表 video/series_style.json；人物比例：每集配置的 PX > video/assets/REGISTRY.md 人物表的 PX 列 > 默认 0.42。

每场戏是一个独立剧本（自己的时间从 0 开始），场与场之间整条画面像纸片一样翻过去。
小伙这类纸偶用关节动画，其他角色是 Codex 画的整身姿势图，靠弹出、换姿势时的挤压回弹、说话时的起伏、摇头点头来表演。
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # video/
sys.path.insert(0, str(ROOT))
import episode_config as ec  # noqa: E402
import glyph_check  # noqa: E402
from episode_config import ConfigError, load_config  # noqa: E402

BGM = Path.home() / "MoneyPrinterTurbo/resource/songs/output009.mp3"   # MPT 自带曲库（来源不明，仅内部预览，发布前必须换）
DEFAULT_PX = 0.42       # 新前缀不在配置的 PX 里登记时，人物用这个比例
NAMETAG_LEAD = 0.3      # 人名牌在角色出场（弹出约 0.32 秒）之后 0.3 秒出现
NAMETAG_HOLD = 2.0      # 人名牌停留的秒数（系列固定）


class Episode:
    """一集：配置 + 配音时间线 → 场次边界和分场脚本要用的小工具。"""

    def __init__(self, cfg, voice=None, scenes=None, out=None):
        self.cfg = cfg
        self.voice = Path(voice or cfg["VOICE"])
        self.scenes = Path(scenes or cfg["SCENES"])
        self.out = Path(out or cfg["OUT"])
        tl_path = self.voice / "timeline.json"
        if not tl_path.exists():
            raise ConfigError(f"找不到配音时间线 {tl_path}：先按工作流第 4 步跑 voice.py 配音，或者用 --voice 指定目录")
        self.TL = json.loads(tl_path.read_text(encoding="utf-8"))
        self.L = self.TL["lines"]
        n = len(self.L)
        for i, j in cfg["B"]:
            if not (0 <= i < j < n):
                raise ConfigError(f"配置里 B 的 ({i}, {j}) 超出了时间线的台词行数（共 {n} 行，行号从 0 数）")
        self.B = [0, *[self.mid(i, j) for i, j in cfg["B"]], self.TL["duration"]]

    def T0(self, i):
        return self.L[i]["t0"]

    def T1(self, i):
        return self.L[i]["t1"]

    def mid(self, i, j):
        return round((self.T1(i) + self.T0(j)) / 2, 2)

    def at(self, i, word):
        """第 i 句台词里说到 word 的大致时刻（按字数比例估算）。"""
        text = self.L[i]["text"]
        return round(self.T0(i) + text.index(word) / len(text) * (self.T1(i) - self.T0(i)), 2)

    def subs(self, k):
        s0, s1 = self.B[k], self.B[k + 1]
        label = self.cfg.get("LABEL") or {}
        return [[round(x["t0"] - s0, 2), round(x["t1"] - s0, 2), label.get(x["who"], x["who"]), x["text"]]
                for x in self.L if x["audio"] and s0 <= x["t0"] < s1]

    def base(self, k, set_name, camera, hud, actors, props=(), events=()):
        d = round(self.B[k + 1] - self.B[k], 2)
        return {"about": f"{self.cfg['EP_LABEL']} · 第 {k + 1} 场", "duration": d, "title": self.cfg["TITLE"], "footer": self.cfg["FOOTER"], "set": set_name,
                "flip": [k > 0, k < len(self.B) - 2], "camera": camera, "hud": hud, "actors": actors,
                "props": list(props), "events": list(events), "subtitles": self.subs(k)}

    def tools(self):
        """分场脚本每个 shotN(ep) 开头用：B, T0, T1, at, base = ep.tools()"""
        return self.B, self.T0, self.T1, self.at, self.base


# ---- 和时间线无关的积木 ----
def actor(x, pose, show, flip=1, px=DEFAULT_PX, speaker=None, native=1, phase=0.0, **kw):
    a = {"keys": [[0, x, "", flip]], "poses": [[0, pose]], "show": show, "px": px, "native": native, "phase": phase}
    if speaker:
        a["speaker"] = speaker
    a.update(kw)
    return a


def sprite(img, x, y, h, show, **kw):
    return {"type": "sprite", "img": img, "x": x, "y": y, "h": h, "show": show, **kw}


def choice(t0, options, reveal=None, pick=None, t1=None, label="考你！", after="看答案！"):
    """四次提问用同一个仪式（儿童动画调研规则 2）：同一句「考你！」、同一种按钮、同一组提示音；揭晓后只说「看答案！」，不说谁错。"""
    ev = {"type": "choice", "t0": t0, "options": options, "reveal": reveal, "pick": pick, "label": label, "after": after}
    if t1 is not None:
        ev["t1"] = t1
    return ev


def restyle(scene, px_map):
    """新角色的素材比例和旧素材不同：按姿势图的名字前缀统一设 px（前缀在配置的 PX 里登记，没登记的用 actor() 里的默认比例）。"""
    for a in scene["actors"].values():
        poses = [n for _, n in a.get("poses", [])]
        for pre, px in px_map.items():
            if poses and all(n.startswith(pre) for n in poses):
                a["px"] = px
                break
    return scene


def fix_fly(scene):
    """乌鸦从右上方飞进来（from 是相对落点的位移）。"""
    for p in scene["props"]:
        if p.get("type") == "sprite" and p.get("enter") == "fly" and not p.get("from"):
            p["from"] = [420, -260]
        p.pop("from_", None)
    return scene


def attach_nametags(scenes, tags, style=None):
    """人名牌：人物第一次入画时，名字和家名一起出现约 2 秒。tags = 配置的 NAMETAGS（只有 name、house）；家族颜色按家名从系列表 style（video/series_style.json）取，
    颜色还是占位（null）时人名牌用墨色，家名不在表里报错。空的话什么都不加，场景 JSON 和没有这个功能时完全一样。
    在每场的 scene["nametags"] 里写 [{id, name, house, color, t0, t1, hold}]（时间是这一场自己的时间）：
    t0 = 最早可以出现的时刻（角色弹出之后 0.3 秒），t1 = 最晚必须结束的时刻（角色退场前 0.2 秒、整页折倒前），hold = 停留秒数。
    「第一次入画」的时刻由画面决定：2D 看角色在不在闯关画面里，3D 看角色的脚在不在安全区里（stage.html），从那一刻起计 hold 秒——
    镜头没拍到他的时候牌子不会白白过期（T24）。同一个人用了几个角色 id（分几段出场）时，按名字只算整集里第一次出场。"""
    if not tags:
        return
    if style is None:
        style = ec.load_series_style()
    seen, used = set(), set()
    for k, sc in enumerate(scenes, 1):
        lst = []
        for id_, a in sc["actors"].items():
            tag = tags.get(id_)
            if not tag:
                continue
            used.add(id_)
            if tag["name"] in seen:
                continue
            seen.add(tag["name"])
            house = tag.get("house") or ""
            if house and house not in style["houses"]:
                sys.exit(f"错误：NAMETAGS[{id_!r}] 的家名「{house}」不在系列表 video/series_style.json 里（现有：{'、'.join(style['houses'])}）")
            show = a.get("show")
            start = show[0] if show else a["keys"][0][0]
            end = show[1] if show else sc["duration"]
            t0 = round(start + NAMETAG_LEAD, 2)
            t1 = round(min(end - 0.2, sc["duration"] - 0.45), 2)   # 场尾 0.45 秒整页折倒，人名牌不跨过去
            if t1 - t0 < 1.5:
                print(f"[人名牌警告] 第 {k} 场 {tag['name']}：出场到退场（或整页折倒）只有 {t1 - t0:.1f} 秒，够不到 1.5 秒", file=sys.stderr)
            lst.append({"id": id_, "name": tag["name"], "house": house, "color": (style["houses"].get(house) or {}).get("color"), "t0": t0, "t1": t1, "hold": NAMETAG_HOLD})
        if lst:
            sc["nametags"] = lst
    lost = [i for i in tags if i not in used]
    if lost:
        print(f"[人名牌警告] 名单里的角色 id 没有出现在任何一场：{lost}（id 写错了？）", file=sys.stderr)


def px_defaults(cfg):
    """人物比例的查表顺序：这一集配置的 PX（写的是这一集要改的）> 登记表 video/assets/REGISTRY.md 人物表的 PX 列（系列固定，例如司马光 sgm_ 0.62）> actor() 的默认 DEFAULT_PX。
    合并成一张表：这一集的先，登记表的按前缀从长到短（d2_teen 要排在 d2_ 前面）。"""
    px = dict(cfg.get("PX") or {})
    for pre, v in sorted(ec.registry_px().items(), key=lambda kv: -len(kv[0])):
        px.setdefault(pre, v)
    return px


def build_scenes(ep, shots, style=None):
    """跑每个 shotN(ep)，套上统一比例和乌鸦飞入，再加人名牌。返回场景字典的列表。style：系列表，默认读 video/series_style.json。"""
    px = px_defaults(ep.cfg)
    scenes = [restyle(fix_fly(fn(ep)), px) for fn in shots]
    attach_nametags(scenes, ep.cfg.get("NAMETAGS"), style)
    return scenes


def render_shot(path, out_mp4):
    import render
    from playwright.sync_api import sync_playwright
    scene = render.load_scene(path)
    with sync_playwright() as p:
        browser, page = render.open_page(p, scene)
        ff = subprocess.Popen([render.FFMPEG, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(render.FPS), "-vcodec", "mjpeg",
                               "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(out_mp4)],
                              stdin=subprocess.PIPE)
        n = int(round(scene["duration"] * render.FPS))
        for i in range(n):
            ff.stdin.write(render.grab(page, i / render.FPS))
        ff.stdin.close()
        ff.wait()
        steps = page.evaluate("() => footsteps()")
        browser.close()
    return n, steps


def decode(path, sr):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def shot_of(ep, t):
    """时间线上 t 时刻属于第几场（1 起）：B[k-1] <= t < B[k]，和 Episode.subs 的划分一样。"""
    return next((k for k in range(1, len(ep.B)) if ep.B[k - 1] <= t < ep.B[k]), len(ep.B) - 1)


def build_voice(ep, shot_ids, frames_per_shot, sr, n):
    """配音轨和「有人说话」的时段（给背景音乐压低用）。shot_ids：混进来的是第几场（按渲出来的顺序），frames_per_shot：这几场各渲了多少帧。
    全集（shot_ids 是 1..n 全部）：台词按时间线上的绝对时刻放，和以前逐样本一样。
    只混其中几场（第一场样片）：时间线按场裁——只放属于这几场的台词，每场按渲出来的帧数首尾相接，台词在场内的位置不变，不再拿整集的时刻去放（A6：以前 i > n 时崩溃）；
    每句最多放到它这一场的结尾，不会漏到后面的场里。返回 (voice 数组, [(起点样本, 终点样本), ...])。"""
    import numpy as np
    n_all = len(ep.B) - 1
    full = list(shot_ids) == list(range(1, n_all + 1))
    out_start, acc = {}, 0.0
    for k, frames in zip(shot_ids, frames_per_shot):
        out_start[k] = acc
        acc += frames / 30
    voice, talk = np.zeros(n), []
    for x in ep.L:
        if not x["audio"]:
            continue
        k = shot_of(ep, x["t0"])
        if k not in out_start:
            continue
        off = 0 if full else out_start[k] - ep.B[k - 1]
        i, j = int((x["t0"] + off) * sr), int((x["t1"] + off) * sr)
        end = n if full else min(n, int((out_start[k] + frames_per_shot[list(shot_ids).index(k)] / 30) * sr))
        if i >= end:
            continue
        clip = decode(ep.voice / x["audio"], sr)
        voice[i:i + len(clip)] += clip[: end - i]
        talk.append((i, min(j, n)))
    return voice, talk


def mix(ep, frames_per_shot, steps_per_shot, out_wav, shot_ids=None):
    """混音：配音 + 背景音乐（有人说话压低）+ 音效。shot_ids 不写 = 整集（frames_per_shot 是每一场渲了多少帧）；
    写了就只混这几场（第一场样片），时间线按场裁，见 build_voice。"""
    import numpy as np
    import audio
    sr = audio.SR
    shot_ids = list(shot_ids) if shot_ids is not None else list(range(1, len(frames_per_shot) + 1))
    total = sum(frames_per_shot) / 30
    n = int(sr * total)
    voice, talk = build_voice(ep, shot_ids, frames_per_shot, sr, n)
    # 背景音乐：有人说话时压低（0.15 秒渐变），开头淡入、结尾淡出
    bgm = decode(BGM, sr) if BGM.exists() else np.zeros(n)
    bgm = np.tile(bgm, int(np.ceil(n / max(len(bgm), 1))))[:n]
    env = np.full(n, 0.20)
    for i, j in talk:
        env[i:j] = 0.07
    k = int(0.15 * sr)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    env[: sr] *= np.linspace(0, 1, sr)
    env[-2 * sr:] *= np.linspace(1, 0, 2 * sr)
    sfx = np.zeros(n)
    start = 0
    for shot, frames, steps in zip(shot_ids, frames_per_shot, steps_per_shot):
        scene = json.loads((ep.scenes / f"shot{shot}.json").read_text(encoding="utf-8"))
        scene["_steps"] = steps
        m = int(sr * frames / 30)
        part = audio.sfx(scene, m)
        i = int(start / 30 * sr)
        sfx[i:i + m] += part[: n - i]
        start += frames
    out = voice * 1.0 + bgm * env + sfx * 0.45
    out = out / max(1e-6, np.abs(out).max()) * 0.92
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def check_config(cfg, name):
    errors, todos, notes = ec.check(cfg)
    print(f"配置 {name}：{'写法没问题' if not errors else f'{len(errors)} 处写法不对'}；{len(todos)} 项还没填")
    for e in errors:
        print(f"  [写法] {e}")
    for t in todos:
        print(f"  [待填] {t}")
    for n in notes:
        print(f"  [提示] {n}")
    return errors, todos


def main(cfg, shots, argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--shots")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--check-config", action="store_true")
    ap.add_argument("--strict", action="store_true", help="配合 --check-config：有没填的项也退出 1")
    ap.add_argument("--voice")
    ap.add_argument("--scenes-out")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.check_config:
        errors, todos = check_config(cfg, Path(str(cfg.get("SCENES") or "?")).name)
        sys.exit(1 if errors or (args.strict and todos) else 0)
    errors, todos, _ = ec.check(cfg)
    if errors or todos or not shots:
        for e in errors:
            print(f"配置写法不对：{e}", file=sys.stderr)
        for t in todos:
            print(f"配置还没填：{t}", file=sys.stderr)
        if not shots:
            print("这一集还没有 shotN()：SHOTS 是空的", file=sys.stderr)
        sys.exit("分场脚本没有跑：先把上面的问题补齐（--check-config 可以只看配置）")
    try:
        ep = Episode(cfg, args.voice, args.scenes_out, args.out)
    except ConfigError as e:
        sys.exit(f"错误：{e}")
    ep.scenes.mkdir(parents=True, exist_ok=True)
    ep.out.mkdir(parents=True, exist_ok=True)
    for k, sc in enumerate(build_scenes(ep, shots), 1):
        (ep.scenes / f"shot{k}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("场次边界：", [round(b, 2) for b in ep.B])
    issues = glyph_check.check_files([ep.scenes / f"shot{k}.json" for k in range(1, len(shots) + 1)])   # 要上画面的字有没有缺在字体子集外面
    if issues:
        glyph_check.print_report(issues)
        sys.exit(1)
    if args.no_render:
        return
    n_shots = len(shots)
    sel = sorted({int(x) for x in args.shots.split(",")}) if args.shots else list(range(1, n_shots + 1))
    if not sel or any(not 1 <= k <= n_shots for k in sel):
        sys.exit(f"错误：--shots {args.shots} 里的场号要在 1–{n_shots} 之间")
    partial = sel != list(range(1, n_shots + 1))
    tag = "_shots" + "-".join(map(str, sel)) if partial else ""   # 只做几场时输出文件加后缀，不覆盖整集的
    only = {int(x) for x in args.only.split(",")} if args.only else set(sel)
    meta_path = ep.out / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for k in sel:
        if k in only or str(k) not in meta:
            print(f"渲染第 {k} 场…", flush=True)
            frames, steps = render_shot(ep.scenes / f"shot{k}.json", ep.out / f"shot{k}.mp4")
            meta[str(k)] = {"frames": frames, "steps": steps}
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
    frames = [meta[str(k)]["frames"] for k in sel]
    steps = [meta[str(k)]["steps"] for k in sel]
    (ep.out / f"list{tag}.txt").write_text("".join(f"file 'shot{k}.mp4'\n" for k in sel), encoding="utf-8")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(ep.out / f"list{tag}.txt"), "-c", "copy",
                    str(ep.out / f"silent{tag}.mp4")], check=True)
    mix(ep, frames, steps, ep.out / f"mix{tag}.wav", shot_ids=sel)
    final = Path(cfg.get("FINAL", "full.mp4"))
    final = ep.out / f"{final.stem}{tag}{final.suffix}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(ep.out / f"silent{tag}.mp4"), "-i", str(ep.out / f"mix{tag}.wav"), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)], check=True)
    print(final)


if __name__ == "__main__":
    # python video/episode_build.py <集> --check-config：只看某一集的配置读不读得出来、哪些项没填
    ap = argparse.ArgumentParser()
    ap.add_argument("ep", help="集名，例如 tj01、ep01v2（video/episodes/<集>.py）")
    ap.add_argument("--check-config", action="store_true", required=True)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        c = load_config(a.ep)
    except ConfigError as e:
        sys.exit(f"错误：{e}")
    errs, tds = check_config(c, a.ep)
    sys.exit(1 if errs or (a.strict and tds) else 0)
