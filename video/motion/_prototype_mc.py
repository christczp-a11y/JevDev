"""【原型，施工参考用】2026-09-29 给 Chris 看的 17 秒动态漫画小样（tj01 开头）。镜头写死在代码里；正式引擎见 docs/施工计划-动态漫画引擎.md。
动态漫画小样：tj01 开头约 17 秒。只读仓库素材和配音，输出在本目录。
做法：每个镜头 = 几层整幅画（天、远山、城墙、水、前景、人物），镜头只做推拉平移；分层视差；人物弹出和轻微呼吸；字幕和界面叠在最上面。
"""
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

R = Path(r"C:\Users\Chris\Claude x Jev\JevDev")
A = R / "video/assets"
V = R / "video/out/tj01_voice"
OUT = Path(__file__).resolve().parents[1] / "out" / "motion_prototype"; OUT.mkdir(parents=True, exist_ok=True)
FF = r"C:\Users\Chris\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
W, H, FPS, DUR = 1080, 1920, 30, 17.2
C = (W / 2, H / 2)
INK, RED, CREAM, NARR = (42, 35, 32), (200, 55, 45), (244, 232, 208), (122, 104, 86)
FB = r"C:\Windows\Fonts\msyhbd.ttc"


def font(sz):
    return ImageFont.truetype(FB, sz)


def img(p, flip=False):
    im = Image.open(A / p).convert("RGBA")
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def fit_w(im, w):
    return im.resize((round(w), round(im.height * w / im.width)), Image.LANCZOS)


def fit_h(im, h):
    return im.resize((round(im.width * h / im.height), round(h)), Image.LANCZOS)


def clamp(u):
    return max(0.0, min(1.0, u))


def smooth(u):
    u = clamp(u)
    return u * u * u * (u * (6 * u - 15) + 10)


def back(u):   # 弹出：带一点过冲
    u = clamp(u)
    c = 1.70158
    return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2


# ---------- 素材 ----------
sky = fit_w(img("sets/jin_land/sky.png"), 1080)
far = fit_w(img("sets/jin_land/ridge_far.png"), 1080)
mid = fit_w(img("sets/jin_land/ridge_mid.png"), 1080)
near = fit_w(img("sets/jin_land/ridge_near.png"), 1080)
ground = fit_w(img("sets/jin_land/ground.png"), 1200)
water = fit_w(img("sets/jin_land/water.png"), 1300)
fore = fit_w(img("sets/jin_land/fore.png"), 1200)
wall = fit_w(img("sets/jinyang/wall.png"), 1200)
gate = fit_w(img("sets/jinyang/gate.png"), 900)
terrace = fit_w(img("sets/lantai/terrace.png"), 980)
table = fit_w(img("sets/lantai/table.png"), 330)
cup = fit_w(img("sets/lantai/cup.png"), 120)
sgm = fit_h(img("chars/sgm_finger.png"), 520)            # 原图朝右：指向城
zb_hi = fit_h(img("chars/zb_hi_laugh.png"), 1000)        # 高清特写，朝右
dg_hi = fit_h(img("chars/dg_hi_tight.png", flip=True), 980)   # 翻成朝左，对着智伯
zb_pt = fit_h(img("chars/zb_point.png"), 380)            # 跪坐指着人，朝右
hkz = fit_h(img("chars/hkz_low.png", flip=True), 360)    # 朝左
dg_kn = fit_h(img("chars/dg_kneel.png", flip=True), 360)  # 朝左
mapi = fit_w(img("props/map_silk.png"), 540)
flag_zhi = fit_h(img("props/flag_zhi.png"), 520)
blur = lambda im, r: im.filter(ImageFilter.GaussianBlur(r))


def make_page():
    w, h = W + 240, 700
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(3)
    top = [18 + 6 * math.sin(x / 37) + rng.normal(0, 1.2) for x in range(w)]
    for x in range(w):
        d.line((x, top[x] - 10, x, top[x]), fill=(80, 60, 40, 60))          # 页边的一点影子
        d.line((x, top[x], x, h), fill=(239, 228, 204, 255))
    for i in range(6):
        y = 120 + i * 70
        d.line((140, y, w - 140, y), fill=(220, 205, 178, 255), width=3)    # 书页上的淡线
    return im
page = make_page()
gblur = blur(ground, 8)
bg_close = [(blur(sky, 3), 0, 0, 0.05), (blur(far, 5), 0, 420, 0.15), (blur(mid, 7), 0, 720, 0.3), (blur(near, 9), 0, 820, 0.45)] + [(gblur, -60, 1120 + i * (gblur.height - 20), 0.5) for i in range(7)]


# ---------- 界面（预先画好） ----------
def rounded(w, h, fill, r=28, border=None, bw=5):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=fill, outline=border, width=bw if border else 0)
    return im


def text_img(txt, sz, color, pad=0):
    f = font(sz)
    x0, y0, x1, y1 = f.getbbox(txt)
    im = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - x0, pad - y0), txt, font=f, fill=color)
    return im


def card(lines, sz, fg, bg, border, padx=46, pady=26, r=30):
    ts = [text_img(t, sz, fg) for t in lines]
    w = max(t.width for t in ts) + 2 * padx
    h = sum(t.height for t in ts) + (len(ts) - 1) * 18 + 2 * pady
    im = rounded(w, h, bg, r, border, 6)
    y = pady
    for t in ts:
        im.alpha_composite(t, ((w - t.width) // 2, y))
        y += t.height + 18
    # 纸边：外面一圈白边
    edge = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((0, 0, w + 15, h + 15), r + 8, fill=(255, 252, 244, 255))
    edge.alpha_composite(im, (8, 8))
    return edge


def subtitle(who, text):
    lines = [text[i:i + 15] for i in range(0, len(text), 15)]
    body = card(lines, 52, INK, CREAM + (255,), (90, 70, 55, 255), padx=40, pady=24)
    tag = card([who], 34, (255, 255, 255), (RED if who == "司马光" else NARR) + (255,), None, padx=22, pady=10, r=18)
    im = Image.new("RGBA", (max(body.width, tag.width + 40), body.height + tag.height - 14), (0, 0, 0, 0))
    im.alpha_composite(body, ((im.width - body.width) // 2, tag.height - 14))
    im.alpha_composite(tag, (30, 0))
    return im


SUBS = [(0.30, 1.50, "司马光", "考考你！"), (1.80, 3.40, "旁白", "要地，给不给？"),
        (7.48, 10.30, "旁白", "智伯有五样本事，样样比别人强！"),
        (10.80, 16.30, "旁白", "宴会上，智伯当众取笑韩康子，羞辱替韩康子出主意的段规！")]
SUB_IMG = [(a, b, subtitle(w, t)) for a, b, w, t in SUBS]
kicker = card(["资治通鉴 · 卷一"], 34, (255, 250, 238), (60, 48, 40, 255), None, padx=26, pady=10, r=22)
ask = card(["有人跟你要地！"], 64, (255, 255, 255), RED + (255,), None, padx=40, pady=18)
btn_give = card(["给"], 70, (255, 255, 255), (47, 125, 91, 255), None, padx=70, pady=16)
btn_no = card(["不给"], 70, (255, 255, 255), RED + (255,), None, padx=56, pady=16)
bigq = card(["最强的智伯，", "为什么输了？"], 84, (255, 255, 255), RED + (255,), None, padx=50, pady=30)
level1 = card(["第 1 关：忍"], 60, (255, 250, 238), (60, 48, 40, 255), None, padx=40, pady=16)
BADGES = []
for t in ["高大", "射箭", "才艺", "口才", "果断"]:
    b = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.ellipse((4, 4, 185, 185), fill=(255, 252, 244))
    d.ellipse((14, 14, 175, 175), fill=(233, 178, 60), outline=(150, 95, 30), width=5)
    ti = text_img(t, 52, INK)
    b.alpha_composite(ti, ((190 - ti.width) // 2, (190 - ti.height) // 2 - 4))
    BADGES.append(b)


def ring(u):   # 倒计时圈
    im = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, 145, 145), fill=(255, 252, 244))
    d.arc((16, 16, 133, 133), -90, -90 + 360 * (1 - u), fill=RED, width=16)
    return im


# ---------- 合成 ----------
def put(canvas, im, x, y, f, cam, k=1.0, anchor=(0.0, 0.0)):
    """把 im 放到底图坐标 (x, y)（anchor 是 im 上的锚点比例），f = 视差系数，k = 额外缩放（弹出用）。"""
    zoom, px, py = cam
    Z = 1 + (zoom - 1) * f
    s = Z * k
    # 锚点在底图上的位置 → 屏幕位置
    ax, ay = x, y
    sx = C[0] + Z * (ax - C[0]) - f * px
    sy = C[1] + Z * (ay - C[1]) - f * py
    tx, ty = sx - anchor[0] * im.width * s, sy - anchor[1] * im.height * s   # 左上角
    bw, bh = im.width * s, im.height * s
    x0, y0 = max(0, math.floor(tx)), max(0, math.floor(ty))
    x1, y1 = min(W, math.ceil(tx + bw)), min(H, math.ceil(ty + bh))
    if x1 <= x0 or y1 <= y0:
        return
    tile = im.transform((x1 - x0, y1 - y0), Image.AFFINE, (1 / s, 0, (x0 - tx) / s, 0, 1 / s, (y0 - ty) / s), resample=Image.BILINEAR)
    canvas.alpha_composite(tile, (x0, y0))


def jinyang(cv, t, cam, water_y):
    put(cv, sky, 0, 0, 0.05, cam)
    put(cv, far, 0, 430, 0.15, cam)
    put(cv, mid, 0, 740, 0.3, cam)
    put(cv, near, 0, 830, 0.45, cam)
    put(cv, wall, 540, 1330, 0.75, cam, anchor=(0.5, 1.0))
    put(cv, gate, 540, 1340, 0.75, cam, anchor=(0.5, 1.0))
    put(cv, ground, 540, 1330, 0.9, cam, anchor=(0.5, 0.0))
    wx = 540 + 28 * math.sin(t * 1.7)
    put(cv, water, wx, water_y + 8 * math.sin(t * 2.3), 1.0, cam, anchor=(0.5, 0.0))
    put(cv, water, wx + 90, water_y + 60 + 8 * math.sin(t * 2.3 + 1.3), 1.05, cam, anchor=(0.5, 0.0))
    put(cv, ground, 540, 1330 + ground.height - 20, 0.9, cam, anchor=(0.5, 0.0))
    put(cv, page, 540, 1440, 1.15, cam, anchor=(0.5, 0.0))


def lantai(cv, t, cam):
    put(cv, sky, 0, 0, 0.05, cam)
    put(cv, far, 0, 420, 0.15, cam)
    put(cv, mid, 0, 720, 0.3, cam)
    put(cv, near, 0, 820, 0.45, cam)
    put(cv, terrace, 540, 1350, 0.7, cam, anchor=(0.5, 1.0))
    put(cv, flag_zhi, 170, 1360, 0.75, cam, anchor=(0.5, 1.0))
    put(cv, ground, 540, 1320, 0.9, cam, anchor=(0.5, 0.0))
    put(cv, ground, 540, 1320 + ground.height - 20, 0.9, cam, anchor=(0.5, 0.0))
    b = 3 * math.sin(t * 5)
    put(cv, zb_pt, 300, 1545 + b, 1.0, cam, anchor=(0.5, 1.0))
    put(cv, hkz, 700, 1540, 1.0, cam, anchor=(0.5, 1.0))
    put(cv, dg_kn, 900, 1550, 1.0, cam, anchor=(0.5, 1.0))
    put(cv, table, 250, 1640, 1.15, cam, anchor=(0.5, 1.0))
    put(cv, cup, 200, 1575, 1.15, cam, anchor=(0.5, 1.0))
    put(cv, page, 540, 1665, 1.2, cam, anchor=(0.5, 0.0))


def close_bg(cv, cam, tint=None):
    for im, x, y, f in bg_close:
        put(cv, im, x, y, f, cam)
    if tint:
        cv.alpha_composite(Image.new("RGBA", (W, H), tint))


def frame(t):
    cv = Image.new("RGBA", (W, H), (230, 220, 200, 255))
    if t < 4.93:                                   # 镜头 1：晋阳城大水 + 司马光「考考你」+ 二选一
        u = t / 4.93
        cam = (1.0 + 0.07 * smooth(u), 0, -40 * smooth(u))
        wy = 1480 - 250 * smooth((t - 0.2) / 1.6)
        jinyang(cv, t, cam, wy)
        k = back((t - 0.1) / 0.45)
        if k > 0.01:
            put(cv, sgm, 235, 1585 + 4 * math.sin(t * 4), 1.15, cam, k=k, anchor=(0.5, 1.0))
        if t > 1.75:
            put(cv, ask, 540, 250, 0, cam, k=back((t - 1.75) / 0.35), anchor=(0.5, 0.5))
            mx = 1500 - 740 * smooth((t - 1.8) / 0.5)
            put(cv, mapi, mx, 560, 0, cam, anchor=(0.5, 0.5))
            kb = back((t - 2.1) / 0.35)
            put(cv, btn_give, 620, 860, 0, cam, k=kb, anchor=(0.5, 0.5))
            put(cv, btn_no, 890, 860, 0, cam, k=back((t - 2.25) / 0.35), anchor=(0.5, 0.5))
        if 3.6 < t < 4.7:
            put(cv, ring(clamp((t - 3.63) / 1.0)), 760, 1010, 0, cam, anchor=(0.5, 0.5))
    elif t < 7.30:                                 # 镜头 2：大问题；水退，城墙露出夹板印
        u = (t - 4.93) / (7.30 - 4.93)
        cam = (1.32 + 0.05 * smooth(u), 0, 150)
        jinyang(cv, t, cam, 1230 + 180 * smooth((t - 5.0) / 1.8))
        put(cv, bigq, 540, 360 - 300 * (1 - back((t - 4.95) / 0.5)), 0, cam, anchor=(0.5, 0.5))
    elif t < 10.50:                                # 镜头 3：智伯特写（背景虚化）+ 五样本事
        u = (t - 7.30) / 3.2
        cam = (1.0 + 0.06 * smooth(u), 0, 0)
        close_bg(cv, cam)
        put(cv, zb_hi, 560, 1560 + 5 * math.sin(t * 3), 1.0, cam, anchor=(0.5, 1.0))
        pos = [(160, 520), (330, 360), (540, 300), (750, 360), (920, 520)]
        for i, (x, y) in enumerate(pos):
            kk = back((t - (7.95 + 0.45 * i)) / 0.3)
            if kk > 0.01:
                put(cv, BADGES[i], x, y, 0, cam, k=kk * 0.95, anchor=(0.5, 0.5))
    elif t < 13.20:                                # 镜头 4：蓝台宴会全景
        u = (t - 10.5) / 2.7
        cam = (1.0 + 0.06 * smooth(u), -20 * smooth(u), 40 * smooth(u))
        lantai(cv, t, cam)
        put(cv, level1, 540, 250 - 250 * (1 - back((t - 10.6) / 0.45)), 0, cam, anchor=(0.5, 0.5))
    elif t < 15.30:                                # 镜头 5：智伯得意大笑（特写）
        u = (t - 13.2) / 2.1
        cam = (1.10 + 0.06 * smooth(u), 0, -60)
        close_bg(cv, cam, tint=(255, 190, 150, 40))
        put(cv, zb_hi, 520, 1560 + 6 * math.sin(t * 9), 1.0, cam, anchor=(0.5, 1.0))
    else:                                          # 镜头 6：段规忍着（反应特写，朝左对着智伯）
        u = (t - 15.3) / (DUR - 15.3)
        cam = (1.0 + 0.05 * smooth(u), 0, 0)
        close_bg(cv, cam, tint=(120, 140, 170, 40))
        put(cv, dg_hi, 560, 1560, 1.0, cam, anchor=(0.5, 1.0))
    # 顶部卷号标签 + 字幕
    cv.alpha_composite(kicker, ((W - kicker.width) // 2, 60))
    for a, b, im in SUB_IMG:
        if a <= t < b:
            al = min(1, (t - a) / 0.12, (b - t) / 0.12)
            tmp = im.copy()
            if al < 1:
                tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * al)))
            cv.alpha_composite(tmp, ((W - im.width) // 2, 1560))
    return cv.convert("RGB")


# ---------- 声音 ----------
def sfx_wav(path):
    sr = 44100
    n = int(DUR * sr)
    y = np.zeros(n)

    def add(t0, sig):
        i = int(t0 * sr)
        y[i:i + len(sig)] += sig[: n - i]
    tt = lambda d: np.arange(int(d * sr)) / sr
    tick = np.sin(2 * np.pi * 1800 * tt(0.05)) * np.exp(-tt(0.05) * 60) * 0.5
    ding = lambda f: np.sin(2 * np.pi * f * tt(0.35)) * np.exp(-tt(0.35) * 9) * 0.35
    whoosh = np.random.default_rng(1).normal(0, 1, len(tt(0.35))) * np.hanning(len(tt(0.35))) * 0.12
    for s in (3.63, 4.13, 4.63):
        add(s, tick)
    for i in range(5):
        add(7.95 + 0.45 * i, ding(880 * 2 ** (i / 12 * 2)))
    for s in (1.75, 2.1, 4.95, 10.6):
        add(s, whoosh)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())


def build_audio(path):
    sfx = OUT / "sfx.wav"
    sfx_wav(sfx)
    clips = [(A / "audio/sgm_pop.wav", 0.12), (V / "00.mp3", 0.30), (V / "01.mp3", 1.80), (V / "03.mp3", 4.93), (V / "04.mp3", 7.48), (V / "08.mp3", 10.80), (sfx, 0.0)]
    args = [FF, "-y", "-loglevel", "error"]
    for p, _ in clips:
        args += ["-i", str(p)]
    parts = [f"[{i}:a]aresample=44100,adelay={int(d * 1000)}:all=1[a{i}]" for i, (_, d) in enumerate(clips)]
    mix = "".join(f"[a{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0,atrim=0:{DUR}[out]"
    args += ["-filter_complex", ";".join(parts) + ";" + mix, "-map", "[out]", "-ac", "2", str(path)]
    subprocess.run(args, check=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        for t in [0.2, 0.8, 2.6, 4.2, 6.0, 9.8, 12.0, 14.0, 16.5]:
            frame(t).save(OUT / f"still_{t:05.2f}.jpg", quality=85)
        sys.exit()
    wav = OUT / "audio.wav"
    build_audio(wav)
    out = OUT / "tj01_动态漫画小样.mp4"
    ff = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out)],
                          stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        ff.stdin.write(frame(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"{i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("->", out)
