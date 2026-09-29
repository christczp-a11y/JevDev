"""B、C 版：Qwen3-TTS（用 .venv-tts 跑，GTX 1660 Ti 6GB，fp16）。
  .venv-tts/Scripts/python experiments/tts_compare/gen_qwen.py design   # B 版 + C 版参考音（VoiceDesign 1.7B）
  .venv-tts/Scripts/python experiments/tts_compare/gen_qwen.py clone    # C 版（Base 克隆参考音）
    可加 --size 0.6B 用 0.6B-Base
输出 video/out/tts_compare/：
  B_design_<序号>_<角色>.wav          B 版六句
  B2_design_<角色>_第二句.wav          同一角色的第二句（查音色稳不稳）
  ref_<角色>.wav                      C 版参考音（VoiceDesign 生成）
  C_clone_<序号>_<角色>.wav           C 版六句（ICL：克隆音色和语气）
  C2_clone_<角色>_第二句.wav
  Cx_xvec_<序号>_<角色>.wav           C 版变体：只用说话人向量（不带参考语气）
  timing_<stage>.json                 每次生成的耗时、音频时长、显存峰值
"""
import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES, VOICES, SECOND, REF_TEXT, REF_MOOD  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "video" / "out" / "tts_compare"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260929
MAX_TOK = 260   # 12 Hz 编码，260 帧约 21 秒；短句跑飞时截断


def load(repo):
    from qwen_tts import Qwen3TTSModel
    t = time.time()
    m = Qwen3TTSModel.from_pretrained(repo, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa")
    # fp16 下语音解码器（speech_tokenizer）整段输出 NaN（实测），必须用 fp32；主体 talker 用 fp16 没问题
    m.model.speech_tokenizer.model.float()
    torch.cuda.synchronize()
    print(f"loaded {repo} in {time.time()-t:.1f}s, vram alloc {torch.cuda.memory_allocated()/2**30:.2f} GiB", flush=True)
    return m


class Log:
    def __init__(self, stage, model_name):
        self.rows = []
        self.stage = stage
        self.model = model_name
        torch.cuda.reset_peak_memory_stats()

    def run(self, name, fn, seed=SEED):
        torch.manual_seed(seed)
        torch.cuda.synchronize()
        t = time.time()
        wavs, sr = fn()
        torch.cuda.synchronize()
        dt = time.time() - t
        w = np.asarray(wavs[0], dtype=np.float32)
        dur = len(w) / sr
        row = dict(name=name, gen_s=round(dt, 2), audio_s=round(dur, 2), rtf=round(dt / dur, 2) if dur else None,
                   peak_alloc_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2),
                   peak_reserved_gib=round(torch.cuda.max_memory_reserved() / 2**30, 2),
                   nan=bool(np.isnan(w).any()))
        self.rows.append(row)
        print(row, flush=True)
        return w, sr

    def save(self):
        p = OUT / f"timing_{self.stage}.json"
        p.write_text(json.dumps(dict(model=self.model, rows=self.rows), ensure_ascii=False, indent=1), encoding="utf-8")


def parse_plan(txt):
    """'司马光:line,second,ref;旁白:line' -> {角色: {项}}；None = 全部。"""
    if not txt:
        return None
    plan = {}
    for part in txt.split(";"):
        who, _, what = part.partition(":")
        plan[who] = set(what.split(","))
    return plan


def want(plan, who, what):
    return plan is None or what in plan.get(who, ())


def stage_design(plan=None, suffix=""):
    repo = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    m = load(repo)
    log = Log("design" + suffix, repo)
    # 预热一次（不计入）：第一次调用有 cuda 初始化开销
    m.generate_voice_design(text="你好。", language="Chinese", instruct="女声", max_new_tokens=40)
    log.rows.clear()
    torch.cuda.reset_peak_memory_stats()
    for ln in LINES:
        if not want(plan, ln["who"], "line"):
            continue
        ins = f"{VOICES[ln['who']]}{ln['mood']}。"
        w, sr = log.run(f"B_{ln['id']}_{ln['who']}",
                        lambda: m.generate_voice_design(text=ln["text"], language="Chinese", instruct=ins, max_new_tokens=MAX_TOK))
        sf.write(OUT / f"B_design_{ln['id']}_{ln['who']}.wav", w, sr)
    for who, text in SECOND.items():
        if not want(plan, who, "second"):
            continue
        ins = f"{VOICES[who]}语气自然。"
        w, sr = log.run(f"B2_{who}",
                        lambda: m.generate_voice_design(text=text, language="Chinese", instruct=ins, max_new_tokens=MAX_TOK))
        sf.write(OUT / f"B2_design_{who}_第二句.wav", w, sr)
    for who, text in REF_TEXT.items():
        if not want(plan, who, "ref"):
            continue
        ins = f"{VOICES[who]}{REF_MOOD[who]}。"
        w, sr = log.run(f"ref_{who}",
                        lambda: m.generate_voice_design(text=text, language="Chinese", instruct=ins, max_new_tokens=MAX_TOK))
        sf.write(OUT / f"ref_{who}.wav", w, sr)
    log.save()


def stage_seeds(n=2, roles=None, suffix=""):
    """B 版每句再用另外 n 个随机种子各生成一次：看同一段描述抽几次，音色和语气差多少。"""
    repo = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    m = load(repo)
    log = Log("seeds" + suffix, repo)
    for ln in LINES:
        if roles and ln["who"] not in roles:
            continue
        ins = f"{VOICES[ln['who']]}{ln['mood']}。"
        for k in range(1, n + 1):
            w, sr = log.run(f"B_{ln['id']}_{ln['who']}_s{k}",
                            lambda: m.generate_voice_design(text=ln["text"], language="Chinese", instruct=ins, max_new_tokens=MAX_TOK),
                            seed=SEED + k)
            sf.write(OUT / f"Bs_design_{ln['id']}_{ln['who']}_s{k}.wav", w, sr)
    log.save()


def stage_refs(roles, suffix=""):
    """只重做参考音（改了参考文本或语气描述时用）。"""
    repo = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    m = load(repo)
    log = Log("refs" + suffix, repo)
    for who in (roles or list(REF_TEXT)):
        ins = f"{VOICES[who]}{REF_MOOD[who]}。"
        w, sr = log.run(f"ref_{who}",
                        lambda: m.generate_voice_design(text=REF_TEXT[who], language="Chinese", instruct=ins, max_new_tokens=MAX_TOK))
        sf.write(OUT / f"ref_{who}.wav", w, sr)
    log.save()


def stage_clone(size, roles=None, suffix=""):
    repo = f"Qwen/Qwen3-TTS-12Hz-{size}-Base"
    tag = "" if size == "1.7B" else f"_{size}"
    m = load(repo)
    log = Log("clone" + tag + suffix, repo)
    m.generate_voice_clone(text="你好。", language="Chinese", ref_audio=str(OUT / "ref_旁白.wav"), ref_text=REF_TEXT["旁白"], max_new_tokens=40)
    log.rows.clear()
    torch.cuda.reset_peak_memory_stats()
    prompts, xprompts = {}, {}
    for who in VOICES:
        if roles and who not in roles:
            continue
        ref = str(OUT / f"ref_{who}.wav")
        prompts[who] = m.create_voice_clone_prompt(ref_audio=ref, ref_text=REF_TEXT[who], x_vector_only_mode=False)
        xprompts[who] = m.create_voice_clone_prompt(ref_audio=ref, ref_text=REF_TEXT[who], x_vector_only_mode=True)
    for ln in LINES:
        if roles and ln["who"] not in roles:
            continue
        w, sr = log.run(f"C_{ln['id']}_{ln['who']}",
                        lambda: m.generate_voice_clone(text=ln["text"], language="Chinese", voice_clone_prompt=prompts[ln["who"]], max_new_tokens=MAX_TOK))
        sf.write(OUT / f"C_clone{tag}_{ln['id']}_{ln['who']}.wav", w, sr)
    for who, text in SECOND.items():
        if roles and who not in roles:
            continue
        w, sr = log.run(f"C2_{who}",
                        lambda: m.generate_voice_clone(text=text, language="Chinese", voice_clone_prompt=prompts[who], max_new_tokens=MAX_TOK))
        sf.write(OUT / f"C2_clone{tag}_{who}_第二句.wav", w, sr)
    for ln in LINES:
        if roles and ln["who"] not in roles:
            continue
        w, sr = log.run(f"Cx_{ln['id']}_{ln['who']}",
                        lambda: m.generate_voice_clone(text=ln["text"], language="Chinese", voice_clone_prompt=xprompts[ln["who"]], max_new_tokens=MAX_TOK))
        sf.write(OUT / f"Cx_xvec{tag}_{ln['id']}_{ln['who']}.wav", w, sr)
    log.save()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["design", "clone", "refs", "seeds"])
    ap.add_argument("--roles", nargs="*", default=None, help="只做这些角色（refs / seeds / clone 阶段）")
    ap.add_argument("--plan", default=None, help="design 阶段：'司马光:line,second,ref;旁白:line'，不写 = 全部")
    ap.add_argument("--suffix", default="", help="timing 文件名后缀（重做时不覆盖第一次的耗时记录）")
    ap.add_argument("--size", default="1.7B", choices=["1.7B", "0.6B"])
    a = ap.parse_args()
    print("torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.get_device_name(0), flush=True)
    if a.stage == "design":
        stage_design(parse_plan(a.plan), a.suffix)
    elif a.stage == "seeds":
        stage_seeds(roles=a.roles, suffix=a.suffix)
    elif a.stage == "refs":
        stage_refs(a.roles, a.suffix)
    else:
        stage_clone(a.size, a.roles, a.suffix)
