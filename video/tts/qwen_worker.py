"""Qwen3-TTS 配音 worker：在 .venv-tts（Python 3.12 + CUDA 版 PyTorch + qwen-tts）里跑，voice.py 用子进程调它。
一次启动、一次加载模型、批量生成，不要手动跑（voice.py 会写好 job 文件再调用）：
  .venv-tts/Scripts/python video/tts/qwen_worker.py <job.json>

job.json（voice.py 写）
  seed         全局随机种子（每条生成前都重设，同样的输入同样的结果）
  language     "Chinese"
  models       {"design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", "clone": "Qwen/Qwen3-TTS-12Hz-1.7B-Base"}
  design       要设计的参考音 [{"id", "wav", "instruct", "text", "n", "anchor"}]
                 用 VoiceDesign 按「声音描述 + 语气」念一段参考文本，出 n 个候选（换种子），过滤掉太短/太长/有 NaN/无声的；
                 n == 1 直接当成 wav；n > 1 时要有 anchor（这个角色的默认参考音的 id），
                 在克隆模型加载好以后用说话人向量挑和 anchor 最像的那个（语气变体的音色靠这一步拉回同一个人）。
  voices       这次用到的所有声音（已有的 + 上面要设计的）{id: {"wav", "ref_text"}}
  speak        要念的句子 [{"job", "voice", "text", "out", "seed"}]  用 Base 模型克隆 voices[voice] 的参考音（ICL 模式：音色和语气都跟着参考音走）
  result       结果 JSON 的路径
result.json：{"design": {id: {"chosen", "cands": [{"seed", "dur", "score"}]}}, "speak": {job: {"dur", "gen_s"}}, "load_s", "peak_alloc_gib", "peak_reserved_gib"}

踩过的坑（实测，GTX 1660 Ti 6GB，Turing 不支持 bf16）
  · 主模型用 float16、attn_implementation="sdpa"（不装 flash-attn）。
  · 语音解码器（speech_tokenizer）在 fp16 下整段输出 NaN，必须转 float32（占约 0.35 GB）。
  · 1.7B 的两个模型（VoiceDesign、Base）不能同时放进 6 GB 显存：设计阶段用完先释放，再加载克隆模型。
  · 句子太短或语气指令太怪时偶尔不收尾（一直生成到 max_new_tokens），所以 max_new_tokens 按字数限制，撞上限就换种子重试。
"""
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

REF_MIN, REF_MAX = 2.5, 10.0     # 参考音的合格时长（秒）
RETRIES = 3                      # 一句撞上限/时长不合格时最多换几次种子


def log(*a):
    print(*a, flush=True)


def load(repo):
    from qwen_tts import Qwen3TTSModel
    t = time.time()
    m = Qwen3TTSModel.from_pretrained(repo, device_map="cuda:0", dtype=torch.float16, attn_implementation="sdpa")
    m.model.speech_tokenizer.model.float()   # 见文件头：fp16 解码器输出 NaN
    torch.cuda.synchronize()
    log(f"加载 {repo}：{time.time() - t:.1f} 秒，显存 {torch.cuda.memory_allocated() / 2**30:.2f} GiB")
    return m, time.time() - t


def free(m):
    """释放模型显存。调用方要写成 m = free(m)：函数里 del 只删自己这一份引用，调用方手里那份不放，显存不会还。
    （第一版没这么写，加载 Base 时 VoiceDesign 还占着，显存 8.45 GiB > 6 GB，靠 Windows 共享显存硬撑才没崩，很慢。）"""
    del m
    gc.collect()
    torch.cuda.empty_cache()
    return None


def max_tokens(text):
    """12 Hz 编码 = 每秒 12 个 token。每个字最多给 0.7 秒（每秒 1.4 字，比最慢的慈祥老人还慢），另加 2 秒余量。"""
    n = sum(1 for c in text if c.isalnum())
    return int(12 * (2 + 0.7 * n))


def gen(fn, seed):
    torch.manual_seed(seed)
    wavs, sr = fn()
    w = np.asarray(wavs[0], dtype=np.float32)
    if np.isnan(w).any():
        raise RuntimeError("生成结果里有 NaN（fp16 溢出）：speech_tokenizer 没转成 float32？")
    return w, sr


def save(path, w, sr):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".part")
    sf.write(tmp, w, sr, format="WAV", subtype="PCM_16")
    tmp.replace(path)


def ok_ref(w, sr):
    d = len(w) / sr
    return REF_MIN <= d <= REF_MAX and float(np.abs(w).max()) > 0.02


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    seed, lang = job["seed"], job.get("language", "Chinese")
    res = {"design": {}, "speak": {}, "load_s": 0.0}
    if not torch.cuda.is_available():
        sys.exit("错误：CUDA 不可用（.venv-tts 里装的是 CPU 版 PyTorch，或者没有显卡）")
    torch.cuda.reset_peak_memory_stats()

    # ---- 1. VoiceDesign：设计参考音（缺的才设计）
    cands = {}      # id -> [(候选 wav 路径, seed, dur)]
    if job["design"]:
        m, ls = load(job["models"]["design"])
        res["load_s"] += ls
        for d in job["design"]:
            cs = []
            tries = 0
            while len(cs) < d["n"] and tries < d["n"] * RETRIES:
                s = seed + int(d.get("seed_off", 0)) + tries
                tries += 1
                t = time.time()
                w, sr = gen(lambda: m.generate_voice_design(text=d["text"], language=lang, instruct=d["instruct"],
                                                            max_new_tokens=max_tokens(d["text"]) + 60), s)
                dur = len(w) / sr
                log(f"设计 {d['id']} 候选 {len(cs) + 1}/{d['n']}（seed {s}）：{dur:.1f} 秒，生成 {time.time() - t:.1f} 秒" + ("" if ok_ref(w, sr) else "  ← 时长/音量不合格，重抽"))
                if not ok_ref(w, sr):
                    continue
                p = Path(d["wav"]).with_name(Path(d["wav"]).stem + f".cand{len(cs)}.wav")
                save(p, w, sr)
                cs.append((str(p), s, dur))
            if not cs:
                sys.exit(f"错误：{d['id']} 的参考音连抽 {tries} 次都不合格（{REF_MIN}–{REF_MAX} 秒、有声）。检查声音描述和参考文本")
            cands[d["id"]] = cs
            if d["n"] == 1 or len(cs) == 1:
                Path(cs[0][0]).replace(d["wav"])
                res["design"][d["id"]] = {"chosen": 0, "cands": [{"seed": cs[0][1], "dur": round(cs[0][2], 2), "score": None}]}
                cands.pop(d["id"])
        m = free(m)

    # ---- 2. Base：挑语气变体的候选（说话人向量），然后念句子
    if cands or job["speak"]:
        m, ls = load(job["models"]["clone"])
        res["load_s"] += ls
        tsr = m.model.speaker_encoder_sample_rate

        def spk(path):
            w, sr = sf.read(str(path), dtype="float32")
            if w.ndim > 1:
                w = w.mean(axis=1)
            if sr != tsr:
                import librosa
                w = librosa.resample(w, orig_sr=sr, target_sr=tsr)
            e = m.model.extract_speaker_embedding(audio=w, sr=tsr).float().flatten().cpu().numpy()
            return e / (np.linalg.norm(e) + 1e-9)

        anchors = {d["id"]: d["anchor"] for d in job["design"]}
        for vid, cs in cands.items():
            a = job["voices"][anchors[vid]]["wav"]
            ea = spk(a)
            scores = [float(np.dot(ea, spk(p))) for p, _, _ in cs]
            best = int(np.argmax(scores))
            log(f"挑 {vid}：候选相似度 {[round(x, 3) for x in scores]}，选第 {best + 1} 个（和 {anchors[vid]} 的默认参考音比）")
            wav = next(d["wav"] for d in job["design"] if d["id"] == vid)
            Path(cs[best][0]).replace(wav)
            for i, (p, _, _) in enumerate(cs):
                if i != best:
                    Path(p).unlink(missing_ok=True)
            res["design"][vid] = {"chosen": best, "cands": [{"seed": s, "dur": round(dd, 2), "score": round(sc, 3)} for (_, s, dd), sc in zip(cs, scores)]}

        prompts = {}
        for j in sorted(job["speak"], key=lambda x: x["voice"]):
            v = j["voice"]
            if v not in prompts:
                vv = job["voices"][v]
                prompts[v] = m.create_voice_clone_prompt(ref_audio=vv["wav"], ref_text=vv["ref_text"], x_vector_only_mode=False)
            t = time.time()
            for attempt in range(RETRIES):
                s = j["seed"] + attempt
                mt = max_tokens(j["text"])
                w, sr = gen(lambda: m.generate_voice_clone(text=j["text"], language=lang, voice_clone_prompt=prompts[v], max_new_tokens=mt), s)
                if len(w) / sr < (mt - 2) / 12:    # 没撞上限才算好
                    break
                log(f"  {j['job']} 撞上 max_new_tokens，换种子重试（{attempt + 1}/{RETRIES}）")
            else:
                sys.exit(f"错误：「{j['text']}」连试 {RETRIES} 次都没能收尾（一直生成到上限）")
            save(j["out"], w, sr)
            gs = time.time() - t
            res["speak"][j["job"]] = {"dur": round(len(w) / sr, 2), "gen_s": round(gs, 2)}
            log(f"念 {j['job']}（{v}）：{len(w) / sr:.2f} 秒，用时 {gs:.1f} 秒（{gs / max(len(w) / sr, 0.1):.1f} 秒/秒）：{j['text'][:20]}")
        m = free(m)

    res["peak_alloc_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    res["peak_reserved_gib"] = round(torch.cuda.max_memory_reserved() / 2**30, 2)
    Path(job["result"]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"完成：显存峰值 {res['peak_alloc_gib']} GiB（保留 {res['peak_reserved_gib']} GiB）")


if __name__ == "__main__":
    main()
