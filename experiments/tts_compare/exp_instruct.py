"""试验：Base 克隆模型能不能同时吃「参考音（音色）」和「语气指令」？
官方 API 的 generate_voice_clone 没有 instruct 参数，但底层 model.generate 同时收 instruct_ids 和 voice_clone_prompt。
这里绕过 API 直接调底层：ICL 模式 + instruct、只用说话人向量 + instruct，和不加 instruct 的 C 对比。
输出 video/out/tts_compare/exp/Ci_<模式>_<序号>_<角色>.wav
"""
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import LINES, REF_TEXT  # noqa: E402
from gen_qwen import load, MAX_TOK, SEED, OUT as OUT0  # noqa: E402

OUT = OUT0 / "exp"
OUT.mkdir(exist_ok=True)


def gen(m, text, prompt_items, icl, instruct):
    vcp = m._prompt_items_to_voice_clone_prompt(prompt_items)
    input_ids = m._tokenize_texts([m._build_assistant_text(text)])
    ref_ids = [m._tokenize_texts([m._build_ref_text(prompt_items[0].ref_text)])[0]] if icl else None
    inst = [m._tokenize_texts([m._build_instruct_text(instruct)])[0]] if instruct else None
    kw = m._merge_generate_kwargs(max_new_tokens=MAX_TOK)
    codes, _ = m.model.generate(input_ids=input_ids, instruct_ids=inst, ref_ids=ref_ids, voice_clone_prompt=vcp,
                                languages=["Chinese"], non_streaming_mode=False, **kw)
    c = codes[0]
    rc = vcp.get("ref_code")
    full = torch.cat([rc[0].to(c.device), c], dim=0) if (rc is not None and rc[0] is not None) else c
    wavs, sr = m.model.speech_tokenizer.decode([{"audio_codes": full}])
    w = wavs[0]
    if rc is not None and rc[0] is not None:
        w = w[int(rc[0].shape[0] / max(full.shape[0], 1) * w.shape[0]):]
    return np.asarray(w, dtype=np.float32), sr


def main():
    m = load("Qwen/Qwen3-TTS-12Hz-1.7B-Base")
    for ln in LINES:
        if ln["id"] not in ("1", "2", "3", "4", "6"):
            continue
        who = ln["who"]
        ref = str(OUT0 / f"ref_{who}.wav")
        for mode, icl in (("icl", True), ("xvec", False)):
            items = m.create_voice_clone_prompt(ref_audio=ref, ref_text=REF_TEXT[who], x_vector_only_mode=not icl)
            for tag, ins in (("ins", ln["mood"]),):
                torch.manual_seed(SEED)
                t = time.time()
                w, sr = gen(m, ln["text"], items, icl, ins)
                print(f"{mode}+{tag} {ln['id']} {who}: {len(w)/sr:.2f}s in {time.time()-t:.1f}s nan={bool(np.isnan(w).any())}", flush=True)
                sf.write(OUT / f"Ci_{mode}_{ln['id']}_{who}.wav", w, sr)


if __name__ == "__main__":
    main()
