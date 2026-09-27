"""Jev（TypeSafe System One）调用与特征展开。

评分题目放在 rubrics/*.json 里（题目就是数据，改题不用改代码）。
API key 从环境变量 TYPESAFE_API_KEY 读取。
"""
import json
from pathlib import Path

from typesafe_sdk import TypeSafeClient

RUBRIC_DIR = Path(__file__).resolve().parent.parent / "rubrics"
MODEL = "jev-1.13.0"  # 固定版本，阈值和模型权重都是在这个版本上训练的；升级时有意识地切换

_client = None


def client():
    global _client
    if _client is None:
        _client = TypeSafeClient(model=MODEL, timeout=120.0)
    return _client


def load_rubric(name):
    return json.loads((RUBRIC_DIR / f"{name}.json").read_text(encoding="utf-8"))


def ask(state, questions):
    """一次请求问完所有问题（它们并行作答、互相看不到答案）。返回 (answers dict, usage dict)。"""
    r = client().system_one(state, questions)
    return {k: a.model_dump() for k, a in r.answers.items()}, r.usage.model_dump()


def flatten(answers):
    """把答案展开成数值特征：
    score  -> <id>（期望档位）和 <id>__conf
    noul   -> <id>（为「是」的概率）
    choice -> <id>=<option>（每个选项的概率）
    """
    out = {}
    for qid, a in answers.items():
        t = a.get("type")
        if t == "score":
            out[qid] = a["score"]
            out[f"{qid}__conf"] = a["confidence"]
        elif t == "noul":
            out[qid] = a["noul"]
        elif t == "choice":
            for opt, p in a["probabilities"].items():
                out[f"{qid}={opt}"] = p
    return out
