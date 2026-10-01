"""特效的时间常数：特效（fx/）和固定音效（sfx/synth.py）共用，改一处两边一起对上。单位秒。
带「几下」的特效（砸字几个字、清单几条……）的音效按下数做成 slam_1 … slam_6 这样的文件，特效自己按下数选（见 README「音效」）。"""

SLAM_FALL, SLAM_STAG, SLAM_MAX = 0.14, 0.17, 6          # 砸字：每个字下落 0.14 秒，第 k 个字比第 k−1 个晚 0.17 秒落地
LIST_GAP, LIST_MAX = 0.55, 6                            # 清单：每条晚 0.55 秒弹出
STAT_GAP, STAT_MAX = 0.75, 6                            # 属性卡：每一行晚 0.75 秒亮（默认；stat_card 的 gap 参数可以改）
KAONI_BTN, KAONI_OPT, KAONI_RING, KAONI_COUNT, KAONI_ANS, KAONI_END = 0.0, 0.55, 1.1, 3, 4.1, 5.8
# 考你：0 秒「考你！」按钮弹出；0.55 秒起选项一个个弹出；1.1 秒倒计时圈出现，3、2、1 每秒一下（1.1 / 2.1 / 3.1）；4.1 秒「看答案！」；5.8 秒收掉
FLASH_DUR = 0.10                                        # 柔和闪白：3 帧
DRAW_DUR = 0.8                                          # 地图虚线箭头画出来用的时间

# 翻日历（calendar_flip）：时间一律按「秒」排（和转场总长 dur 无关）：0–CAL_IN_S 日历落下；翻页 CAL_N 张从 CAL_START_S 开始，一张比一张晚一点（先快后慢，最后一张落在 stop_text 那页），
# 翻完以后停住不动（停页时间 = dur − 翻页结束 − CAL_OUT_S，默认 dur 2.5 秒时约 1.66 秒，字看得清）；最后 CAL_OUT_S 日历放大淡出，露出下一镜。
# 音效 calendar_flip 按这个翻页时刻做，在翻第一张的那一刻响（转场登记 sfx_dt = CAL_START_S − dur/2）。下面的 p 版本是「按默认 dur 折成 0..1」，给音效脚本用。
CAL_DUR, CAL_N = 2.5, 7
CAL_IN_S, CAL_START_S, CAL_SPAN_S, CAL_OUT_S = 0.12, 0.06, 0.312, 0.3
CAL_START = CAL_START_S / CAL_DUR


def cal_starts_s(n=CAL_N):
    """第 i 张翻页开始的时刻（秒，从转场开头算）：先快后慢。"""
    return [CAL_START_S + CAL_SPAN_S * (1 - (1 - i / n) ** 1.6) for i in range(n)]


def cal_flip_dur_s(i, n=CAL_N):
    """第 i 张翻页翻多久（秒）：越到后面越慢。"""
    return 0.096 + 0.072 * (i / max(n - 1, 1)) ** 2


def cal_flips_end_s(n=CAL_N):
    return cal_starts_s(n)[-1] + cal_flip_dur_s(n - 1, n)


def cal_starts(n=CAL_N):
    return [s / CAL_DUR for s in cal_starts_s(n)]


def cal_flip_dur(i, n=CAL_N):
    return cal_flip_dur_s(i, n) / CAL_DUR
