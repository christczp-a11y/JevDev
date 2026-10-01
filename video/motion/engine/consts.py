"""合成器的系列常量。全系列统一：改这里就是改整个系列的样子，要 Chris 同意（镜头参数照《节奏和特效》第三节，版式照《版式和画风》）。
所有坐标都是设计坐标：1080×1920 的竖屏，预览时引擎自己按比例缩小，分镜表和特效函数永远用设计坐标。"""
import os
from pathlib import Path

MOTION = Path(__file__).resolve().parents[1]          # video/motion
VIDEO = MOTION.parent                                 # video
ROOT = VIDEO.parent                                   # 仓库根
ASSETS = VIDEO / "assets"
FONT_DIR = VIDEO / "vendor" / "fonts"
SFX_DIR = MOTION / "sfx"
FONT_TITLE = FONT_DIR / "ZCOOLKuaiLe-Regular.ttf"     # 标题、砸字、贴纸字
FONT_BODY = FONT_DIR / "NotoSansSC-Bold.ttf"          # 字幕、正文字
BGM = ASSETS / "audio" / "bgm_main.mp3"
SERIES_STYLE = VIDEO / "series_style.json"
OUT_ROOT = Path(os.environ.get("MOTION_OUT_ROOT") or VIDEO / "out" / "motion")   # 默认输出和缓存（video/out 不进 git）；环境变量 MOTION_OUT_ROOT 可以改

ENGINE_VERSION = 1    # 画面算法有改动、但代码哈希看不出来时手动加一（缓存整体作废）

# ---------- 画面 ----------
W, H, FPS = 1080, 1920, 30
PAPER = (230, 220, 200)                # RGB：底色，图层没盖满时露出来的纸色
INK, RED, CREAM, NARR = (42, 35, 32), (200, 55, 45), (244, 232, 208), (122, 104, 86)
WHITE_EDGE = (255, 252, 244)           # 纸边的白
HEADROOM = 1.3                         # 图层预缩放留的余量：屏幕显示 ÷ 原图 ≤ 1.3（版式和画风）
MAX_UPSCALE = 1.3                      # 超过就报警（不拦：分镜检查工具第 C 阶段会拦）

# ---------- 镜头运动（节奏和特效 第三节）----------
DEFAULT_PUSH = 0.05                    # 缓推：每镜默认放大 5%（3–8%）
PUSH_RANGE = (0.03, 0.08)              # 超出范围报警
PAN_MAX_FRAC_PER_S = 0.15              # 摇 / 移：每秒不超过画面宽度的 15%
PUNCH_AMOUNT = 0.10                    # 冲击推：0.15 秒放大 8–15%，再用 0.3 秒回弹一半
PUNCH_RANGE = (0.08, 0.15)
PUNCH_IN, PUNCH_OUT, PUNCH_KEEP = 0.15, 0.30, 0.5
SHAKE_DUR, SHAKE_AMP = 0.30, 12.0      # 震屏：0.25–0.4 秒，振幅 ≤ 画面宽度的 1.5%，衰减
SHAKE_DUR_RANGE = (0.25, 0.40)
SHAKE_AMP_MAX = 0.015 * W
SHAKE_FREQS = (9.0, 13.7)              # Hz，两个正弦叠加当作平滑的伪随机
WHIP_DUR, WHIP_DIST = 0.20, 0.60       # 甩镜：0.2 秒，位移 = 画面宽度的 60%，带运动模糊
WHIP_BLUR_GAIN = 0.9                   # 模糊核长度 = 每帧位移 × 这个数
DRIFT_AMP, DRIFT_PERIOD = 4.0, 4.0     # 呼吸漂移：振幅 3–6 像素、周期 3–5 秒，全片统一（按整集绝对时间，切镜头不断）

# ---------- 人物表演（第四节）----------
SPEAK_BOB_AMP, SPEAK_BOB_HZ = 3.0, 2.4  # 说话时上下起伏 2–4 像素
BREATH_AMP, BREATH_PERIOD = 0.008, 3.6  # 没说话的人：呼吸（高度 ±0.8%）
ENTER_DUR = {"pop": 0.45, "slide_left": 0.5, "slide_right": 0.5, "drop": 0.7, "flip": 0.4, "fade": 0.3}
SWAP_SFX = "pop"                       # 换表情自动配的音效（acts 里写 "sfx": null 关掉）
BOUNCE_DUR, BOUNCE_AMP = 0.32, 18.0

# ---------- 版式（版式和画风）----------
TITLE_Y0, TITLE_Y1 = 90, 330           # 顶部问句标题条
SUB_BOTTOM_Y = 1615                   # 字幕卡底边：贴着平台遮挡区上沿（最下面 300 → y 1620），一行、两行都从底边往上长（M6，09-30 Chris：原来中心 1480 经常挡人）
SUB_CENTER_X = 520                     # 比画面中线偏左 20：15 字一行时卡片右边不压平台遮挡区（右边 140）
SUB_FONT, SUB_LINE_CHARS, SUB_MAX_LINES = 50, 15, 2
SUB_FADE = 0.10
WM_TEXT = "光爷爷的资治通鉴大冒险"       # 水印（右上角，每集一样）
KICKER_FMT = "第 {no} 集 · {name}"                # 标题条上面的小字；{name} = 分镜表顶层的 name（本集名）。系列名只在右上角水印里出现一次（09-29 主会话定：同屏两个系列名）

# ---------- 声音（节奏和特效 第六节，7-成片检查）----------
SR = 44100
LUFS_TARGET, LUFS_TOL = -16.0, 1.0     # 整集响度，容差 ±1 LU
PEAK_MAX_DB = -1.5                     # 真峰值上限
VOICE_TARGET_DB = -21.0                # 每句配音先调到这个有声部分 RMS（dBFS），再一起归一
VOICE_GAIN_LIMIT_DB = 8.0
BGM_OPEN_DB = -13.0                    # 没人说话时音乐比配音低多少
BGM_DUCK_DB = -10.0                    # 说话时再压低多少（合计比配音低 23 dB）
DUCK_ATTACK, DUCK_RELEASE, DUCK_LOOKAHEAD = 0.08, 0.60, 0.06
DUCK_HOLD = 0.35                       # 字与字之间小于这么长的停顿不放开音乐
BGM_FADE_IN, BGM_FADE_OUT = 0.6, 1.5
BGM_LOOP_XFADE = 2.0
SFX_GAIN_DB = -6.0                     # 音效相对配音的电平（音效文件本身按峰值 0.5 合成）
VOICE_SILENCE_DB = -50.0               # 有声判定（同 voice.py）
HEAD_KEEP, TAIL_KEEP = 0.08, 0.15      # 同 voice.py：句首留白、句尾余量，用来估每个字的时间

# ---------- 出片时的自动检查（6-合成）----------
FLASH_DELTA = 0.10                     # 相邻两帧平均亮度差 ≥ 10% 算一次亮度突变（WCAG 的 10%）
FLASH_MAX_PER_SEC = 3                  # 1 秒内超过 3 次就不过
STATIC_MAX_SEC = 1.5                   # 完全不动的画面不许超过 1.5 秒
STATIC_EPS = 0.03                      # 相邻两帧（1/8 分辨率灰度）平均差小于这个算「没动」（0–255）
VOICE_MIN_DB = -55.0                   # 一句台词的时段里，配音轨道的 RMS 至少要有这么响

# ---------- 编码 ----------
# 每个镜头（含它的转场和界面）单独编码成一个片段，片段之间用 concat 拷贝流拼接：所有片段必须同一套编码参数（SPS / PPS 一样），每段从 IDR 开始、闭合 GOP（x264 默认），
# 才能无缝拼接。所以参数只在这里写一份；预览 / 默认整集 / 发布版各一套，缓存按模式分开。
VENC = {
    "preview": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p"],
    "normal": ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"],
    "final": ["-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p"],
}
ABITRATE = {"preview": "128k", "normal": "192k", "final": "256k"}   # 音频整条单独混好，最后一次编码成 aac
CHUNK_FRAMES = 50                      # 一个镜头的片段再按这么多帧切成几段并行渲染、各自缓存（每段从 IDR 开始，拼接照样无缝）：改一个长镜头不用一个进程从头渲到尾
SEG_THREADS = 2                        # 每个片段的 x264 线程数（多个片段并行编码）
COLOR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
RGB2YUV = "scale=out_color_matrix=bt709:out_range=tv"   # BGR → YUV 用 bt709，和上面的标签一致

# ---------- 空白检测（M7：画面中间一大块淡色空白、分层之间露出白缝）----------
# 每个镜头抽几帧（只画背景 / 人物 / 前景，不含特效、调色、字幕和标题条），在 y 340–1400 里找「淡色 + 平涂」的大块或横贯画面的细缝。阈值用 tj01 成片（G 版）标定：
# 0:19–0:31（s08–s11）、1:47–1:52（s42–s43）远山和地面之间那条淡色空白，1:58–2:18（s46–s53）山和水之间的空白 / 白缝都要报出来；
# 天空（饱和度 55–90）、云（只占 0.5–0.9%）、淡色雪山（平均饱和度 28）不许误报。
BLANK_Y0, BLANK_Y1 = 340, 1400         # 标题条以下、字幕区以上
BLANK_SAMPLES = (0.15, 0.40, 0.65, 0.90)   # 每个镜头在这几个位置抽帧（避开转场混合的那几帧）
BLANK_SAT_MAX, BLANK_VAL_MIN = 20, 150     # 淡色：饱和度 < 20/255（≈ 8%）、亮度 > 150（天空 55–90、淡色雪山 ≈ 28，空白带 5–12）
BLANK_STD_MAX = 2.5                    # 平涂：1/4 分辨率灰度 5×5 的标准差 < 2.5（空白带 0.6–1.7；纸纹的天空 2.2–2.6，但饱和度已经把它挡掉了）
BLANK_BLOCK_AREA = 0.012               # 大块：占整幅画面面积 ≥ 1.2%（云只有 0.5–0.9%）、碰到左 / 右画面边缘、高 ≥ 60 像素、宽 ≥ 画面 40%
BLANK_BLOCK_H, BLANK_BLOCK_W = 60, 0.40
BLANK_SEAM_AREA = 0.003                # 细缝：横贯画面（碰到左右两边）、高 8–120 像素、上沿笔直（≥ 90% 的列上沿在同一行 ±8 像素）、面积 ≥ 0.3%
BLANK_SEAM_H = (8, 120)
BLANK_SEAM_STRAIGHT = 0.90

# ---------- 局部直边露缝（M7 再犯，待补 19：tj02 第 2 版 s68，近山下挪后中层山的平直底边从两座近山山峰之间露出一小块浅灰蓝平条）----------
# 和上面的「大块 / 横贯细缝」不同：不要求碰到画面边缘、不要求横贯，只认「一段水平直边 + 贴着它的一条淡色平条」。做法见 engine/blank.py 的 detect_strips。
# 在 540×960 上做（一个工作像素 = 2 个设计像素），只看 y 340–1400；阈值用 tj01 / tj02 整集的布景帧（逐镜头每 0.5 秒一帧）和 tj02 第 2 版 s68 标定。
STRIP_EDGE_STEP = 30                   # 边：竖向差分 |g[y+1] − g[y−1]| ≥ 30（阶跃边）
STRIP_EDGE_TOL = 0.3                   # 直边：边的亚像素位置在这一段里的漂移不超过 ±0.3 个工作像素（±0.6 设计像素）
STRIP_EDGE_W = 60                      # 直边宽（设计像素）
STRIP_W = 60                           # 平条宽（设计像素）
STRIP_H = (10, 60)                     # 平条厚（设计像素）
STRIP_FLAT_DIST = 16                   # 平条内每个像素和这一列参考色的最大通道差
STRIP_CONTRAST = 40                    # 直边两侧的颜色差（Chebyshev），≥ 70% 的列要满足
STRIP_VAL_MIN, STRIP_SAT_MAX = 150, 40   # 淡色：最大通道 ≥ 150、饱和度 ≤ 40/255（天空 55+；露缝实测 7–20；奶油卡片底 30 左右，靠下面的边框排除）
STRIP_STD_MAX = 3.4                    # 平涂：平条内灰度的稳健标准差（1.4826 × 中位数绝对偏差）≤ 3.4（露缝实测 1.0–3.0；3.2–3.6 之间结果不变，4.0 起屋顶上面的雨天空开始误报）
STRIP_BAR = 0.8                        # 两边都是直边的矩形条：≥ 80% 的列厚度和中位数差 ≤ 1 行，不报
STRIP_WHITE_MIN, STRIP_WHITE_H = 232, 24   # 纯白（最小通道 ≥ 232）而且厚 < 24 像素：贴纸描边、水波白线，不报
STRIP_WARM, STRIP_PAPER_TOL = 16, 8      # 暖色（R − B ≥ 16）的奶油色不报：天空图最下面一截的地平线雾（实测 R − B = 21–24）、UI 卡片底（32）；露缝的淡灰蓝是 −16 … +12。颜色在纸底色 PAPER ±8 以内的除外（那是图层没盖住，露出了画布）
STRIP_UI_BORDER_BGR, STRIP_UI_BORDER_TOL = (55, 70, 90), 28   # 成片里卡片 / 气泡的棕色边框（ui.py 的 (90, 70, 55) RGB，编码后 ≈ (53, 68, 86) BGR）
