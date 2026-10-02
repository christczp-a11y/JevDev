"""背景音乐候选生成：ACE-Step 1.5（turbo DiT，不用 LM，6 GB 显存：CPU offload + 半精度）。环境、安装和速度见 memory/CONTEXT.md「背景音乐：ACE-Step 1.5」。
用独立的环境跑（不是 .venv）：
    export PYTHONIOENCODING=utf-8
    .venv-music/Scripts/python video/music_gen.py --ids 1 2 3              # 按下面表里的提示词出这几首（默认 --duration 210 秒）
    .venv-music/Scripts/python video/music_gen.py --ids 1 --duration 30    # 先出 30 秒试一下
    .venv-music/Scripts/python video/music_gen.py --caption "..." --bpm 100 --key "D Major" --seed 7 --name mytry   # 临时提示词
输出到 --out（默认 video/out/bgm_cands/raw/，不进 git）：cand_<id>.flac + cand_<id>.json（提示词、种子、时长、用时、显存峰值）。
用完显卡就放开：脚本退出即释放，不留常驻进程。筛选和响度归一见 video/music_screen.py。
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACE = ROOT / "video" / "out" / "acestep" / "ACE-Step-1.5"          # 官方仓库的克隆（权重在它的 checkpoints/ 里），不进 git
sys.path.insert(0, str(ACE))
os.environ.setdefault("ACESTEP_DISABLE_TQDM", "0")

# 提示词只正面描述想要的音色（模型对「不要合成器」这类否定词不灵，写了反而会把词带进来）；节拍、调式、拍号走专门的参数，不写进提示词。
BASE = ("instrumental children's storybook animation score, warm, light-hearted, whimsical and a little mischievous, "
        "acoustic, organic, live-recorded traditional Chinese instruments, close and dry, gentle")
CANDIDATES = {
    1: dict(bpm=100, key="D Major", seed=1001, caption=BASE + ", plucked guzheng melody with a bamboo flute dizi answering, soft wood block muyu on the beat, light small hand drum"),
    2: dict(bpm=96, key="G Major", seed=1002, caption=BASE + ", pipa leading a playful melody, pizzicato strings, soft wooden clapper bangzi accents, guzheng arpeggios underneath"),
    3: dict(bpm=104, key="C Major", seed=1003, caption=BASE + ", bamboo flute dizi playing a cheerful tune, guzheng arpeggios, small hand drum, wood block"),
    4: dict(bpm=92, key="F Major", seed=1004, caption=BASE + ", xiao flute and guzheng telling a gentle story, warm, soft hand percussion, pizzicato"),
    5: dict(bpm=108, key="G Major", seed=1005, caption=BASE + ", tiptoeing pizzicato strings with guzheng and wood block, bouncy and curious, bamboo flute colors"),
    6: dict(bpm=110, key="D Major", seed=1006, caption=BASE + ", folk dance feeling, small hand drum and wooden clappers, dizi bamboo flute and pipa trading phrases, cheerful"),
    7: dict(bpm=100, key="A Major", seed=1007, caption=BASE + ", pipa and guzheng duet, flowing and adventurous, soft muyu pulse, bamboo flute in the distance"),
    8: dict(bpm=90, key="D Major", seed=1008, caption=BASE + ", tender guzheng with xiao, spacious and sincere, light hand percussion, pizzicato accents"),
    9: dict(bpm=106, key="E Major", seed=1009, caption=BASE + ", mischievous staccato dizi, pipa plucks, muyu wood fish rhythm, playful, guzheng glissandi"),
    10: dict(bpm=98, key="G Major", seed=1010, caption=BASE + ", guzheng and pipa arpeggios with a lyrical bamboo flute melody, small hand drum, warm and heroic but gentle"),
    # 第二批（10-02 第一批筛完：凡是提示词里有 hand drum / hand percussion 的，频谱上都出现了每拍一下的 55–65 Hz 低频冲击或宽带噪声，像底鼓；
    # 只有拨弦 + 木鱼 / 梆子的 cand_5、cand_8 最干净）→ 第二批不写任何鼓，只留拨弦、笛 / 箫、木鱼 / 梆子的轻敲
    11: dict(bpm=100, key="D Major", seed=1011, caption=BASE + ", guzheng arpeggios and a bamboo flute dizi melody, soft muyu wood block ticks on the beat, pizzicato accents"),
    12: dict(bpm=96, key="G Major", seed=1012, caption=BASE + ", pipa and guzheng playing a playful dialogue, wooden clapper bangzi accents, light airy pizzicato strings"),
    13: dict(bpm=94, key="F Major", seed=1013, caption=BASE + ", xiao flute and guzheng telling a warm story, gentle plucks, soft wood block, spacious"),
    14: dict(bpm=104, key="D Major", seed=1014, caption=BASE + ", whimsical pizzicato strings and pipa tiptoeing along, bamboo flute colors, wood block ticks, bouncy and curious"),
}

# 对照组（只用来给 music_screen.py 标定「电子味」阈值，不是候选）：故意写成电子音乐，各 30 秒
CONTROLS = {
    "ctrl_edm": dict(bpm=128, key="A minor", seed=2001, caption="electronic dance music, sawtooth synthesizer lead, heavy sub bass, four on the floor kick drum, 808 hi-hats, energetic EDM drop"),
    "ctrl_synthwave": dict(bpm=100, key="C minor", seed=2002, caption="synthwave, warm analog synthesizer pad, arpeggiated synth, drum machine, retro electronic"),
    "ctrl_lofi": dict(bpm=90, key="F Major", seed=2003, caption="lo-fi electronic chill beat, electric piano, synth bass, soft drum machine, vinyl crackle"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", type=int, nargs="*", default=[], help="出表里的第几首")
    ap.add_argument("--controls", action="store_true", help="先出 3 首故意电子的对照组（各 30 秒，文件名 ctrl_*），用来标定筛选阈值")
    ap.add_argument("--duration", type=float, default=210.0)
    ap.add_argument("--out", default=str(ROOT / "video" / "out" / "bgm_cands" / "raw"))
    ap.add_argument("--caption"), ap.add_argument("--bpm", type=int), ap.add_argument("--key", default=""), ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--name", default="try")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--shift", type=float, default=3.0)
    ap.add_argument("--timesig", default="4")
    ap.add_argument("--no-offload", action="store_true", help="不做 CPU offload（显存够才用）")
    ap.add_argument("--vae-fp16", action="store_true", help="VAE 用 fp16（官方默认；本机会出 NaN）")
    ap.add_argument("--quant", default=None, help="int8_weight_only 之类（需要 torchao；默认不量化）")
    a = ap.parse_args()
    jobs = [(n, c, 30.0) for n, c in CONTROLS.items()] if a.controls else []
    jobs += [(f"cand_{i}", CANDIDATES[i], a.duration) for i in a.ids]
    if a.caption:
        jobs.append((a.name, dict(caption=a.caption, bpm=a.bpm, key=a.key, seed=a.seed), a.duration))
    if not jobs:
        ap.error("--ids 或 --caption 至少给一个")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    # 官方的「主模型是否齐全」检查把 5Hz LM（3.7 GB）也算进去，缺了就自动整库下载。我们只装 DiT + VAE + 文本编码器（6 GB 显存放不下 LM），所以把检查换成只看这三样。
    import acestep.core.generation.handler.init_service_downloads as _dl
    ck = ACE / "checkpoints"
    need = [ck / "acestep-v15-turbo" / "model.safetensors", ck / "vae" / "diffusion_pytorch_model.safetensors", ck / "Qwen3-Embedding-0.6B" / "model.safetensors"]
    missing = [str(f) for f in need if not f.exists()]
    if missing:
        print("权重不齐（安装步骤见 memory/CONTEXT.md「背景音乐：ACE-Step 1.5」）：", *missing, sep="\n  ")
        return 2
    _dl.check_main_model_exists = lambda *_a, **_k: True
    from acestep.gpu_config import get_gpu_config, set_global_gpu_config
    gcfg = get_gpu_config()                                          # 按显存自动分档（6 GB = tier2：不用 LM、INT8 + 全 CPU offload 是它的默认；时长上限 10 分钟）
    set_global_gpu_config(gcfg)
    print(f"显卡 {gcfg.gpu_memory_gb:.1f} GB，档位 {gcfg.tier}", flush=True)
    if not a.vae_fp16:                                               # 这张卡（Turing，没有 bf16）上 VAE 用 fp16 解码出 NaN，整首是静音 / 报错：VAE 只有 0.34 GB，改用 fp32
        AceStepHandler._get_vae_dtype = lambda self, device=None: torch.float32
    dit = AceStepHandler()
    dit._progress_estimates_path = str(ACE / ".cache" / "acestep" / "progress_estimates.json")     # 官方把进度估计写在当前目录的 .cache/ 里（会在仓库根目录留下一个没人要的文件夹），挪到 acestep 目录下
    t0 = time.time()
    status, ok = dit.initialize_service(project_root=str(ACE), config_path="acestep-v15-turbo", device="cuda", use_flash_attention=False, compile_model=False,
                                        offload_to_cpu=not a.no_offload, offload_dit_to_cpu=not a.no_offload, quantization=a.quant)
    print(f"载入模型 {time.time() - t0:.1f} 秒：{status}", flush=True)
    if not ok:
        return 2
    llm = LLMHandler()                                              # 不初始化：6 GB 显存放不下 LM，thinking=False
    for name, c, dur in jobs:
        torch.cuda.reset_peak_memory_stats()
        p = GenerationParams(caption=c["caption"], lyrics="[Instrumental]", instrumental=True, bpm=c.get("bpm"), keyscale=c.get("key", ""), timesignature=a.timesig,
                             duration=dur, inference_steps=a.steps, shift=a.shift, seed=c.get("seed", -1), thinking=False, use_cot_metas=False,
                             use_cot_caption=False, use_cot_language=False, vocal_language="unknown", enable_normalization=True, normalization_db=-1.0)
        cfg = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[c.get("seed", -1)] if c.get("seed", -1) >= 0 else None, audio_format="flac")
        t = time.time()
        res = generate_music(dit, llm, p, cfg, save_dir=None)           # 不让它存文件：它存盘走 torchaudio → torchcodec，本机 torchcodec 加载不了（缺 FFmpeg 4–8 的 dll）。张量拿回来自己用 soundfile 存
        sec = time.time() - t
        if not res.success or not res.audios:
            print(f"{name} 失败：{res.error}")
            continue
        import soundfile as sf
        dst = out / f"{name}.flac"
        sf.write(str(dst), res.audios[0]["tensor"].cpu().float().transpose(0, 1).numpy(), res.audios[0]["sample_rate"], format="FLAC", subtype="PCM_24")
        info = dict(name=name, caption=c["caption"], bpm=c.get("bpm"), key=c.get("key", ""), timesignature=a.timesig, seed=res.audios[0]["params"].get("seed", c.get("seed")),
                    duration_req=dur, steps=a.steps, shift=a.shift, gen_sec=round(sec, 1), peak_vram_gb=round(torch.cuda.max_memory_allocated() / 2 ** 30, 2),
                    model="ACE-Step/Ace-Step1.5 acestep-v15-turbo", file=dst.name)
        (out / f"{name}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}：{sec:.1f} 秒，显存峰值 {info['peak_vram_gb']} GB → {dst}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
