"""草稿选稿分：用赛道数据验证过的复合分（rubrics/selection_composite_v1.json，见 scripts/composite.py）。

草稿会被整理成和赛道笔记一样的形状再打分：
  标题 = title；正文 = body + 话题标签；封面 = 已渲染的封面卡片交给 Claude 描述（和赛道封面同一个描述员）
复合分 = 每条规则（方向 × 标准化值）的平均。留出测试集上它和「扣掉采样来源、发布天数后的互动」的 Spearman ≈ +0.29。
为什么不用 39 个特征的回归：它在留出测试集上过拟合，比基线还差。
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import autoresearch as ar  # noqa: E402
import covers  # noqa: E402
from jevdev import cards, jev  # noqa: E402

SPEC = ROOT / "rubrics" / "selection_composite_v1.json"


def note_of(draft, cover_desc):
    tags = " ".join(f"#{t}" for t in draft["tags"])
    return {"id": "draft", "title": draft["title"], "desc": f"{draft['body']}\n{tags}",
            "cover": cover_desc, "cover_w": 1080, "cover_h": 1440, "note_type": "normal",
            "image_count": 1 + len(draft["pages"]), "from_latest": 1, "from_top": 0,
            "publish_ts": time.time() * 1000 - 7 * 86400000}


def composite(note, spec, questions):
    """返回 (复合分, 每条规则的明细)。"""
    need = {f["feature"] for f in spec["features"]}
    feats = ar.base_features(note)
    for inp in ("title", "body", "cover"):
        qs = {qid: {k: q[k] for k in ("type", "instructions", "criteria") if k in q}
              for qid, q in questions.items() if qid in need and q["input"] == inp and ar.applicable(note, q)}
        if qs:
            a, _ = jev.ask(ar.build_state(note, inp), qs)
            feats.update(jev.flatten(a))
    parts = {}
    for f in spec["features"]:
        if f["feature"] in feats:
            z = f["sign"] * (feats[f["feature"]] - f["mean"]) / f["std"]
            parts[f["feature"]] = round(float(np.clip(z, -3, 3)), 3)  # 和 scripts/composite.py 同样截断
    return round(float(np.mean(list(parts.values()))), 3), parts


def score_drafts(drafts, work_dir, theme="warm"):
    """渲染每篇草稿的卡片 → Claude 描述封面 → Jev 答复合分用到的题 → 复合分。结果写回每篇草稿：
    d["pred"]、d["pred_parts"]、d["cover_desc"]、d["card_paths"]。"""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    questions = json.loads(ar.RUBRIC.read_text(encoding="utf-8"))["questions"]
    work_dir = Path(work_dir)
    cover_dir = work_dir / "covers"
    cover_dir.mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(drafts):
        d["card_paths"] = cards.render([d["cover"]] + d["pages"], work_dir / f"d{i}", theme)
        shutil.copy(d["card_paths"][0], cover_dir / f"d{i}.png")
    desc = covers.describe_batch(sorted(cover_dir.glob("d*.png")), add_dir=cover_dir)
    desc = {c["note_id"]: {k: v for k, v in c.items() if k != "note_id"} for c in desc}
    for i, d in enumerate(drafts):
        d["cover_desc"] = desc.get(f"d{i}")
        d["pred"], d["pred_parts"] = composite(note_of(d, d["cover_desc"]), spec, questions)
    return len(spec["features"])
