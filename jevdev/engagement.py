"""草稿互动预测：用赛道笔记学到的模型（scripts/autoresearch.py 的题目集 + 基线特征）给我们的草稿打分。

草稿会被整理成和赛道笔记一样的形状再预测：
  标题 = title；正文 = body + 话题标签；封面 = 已渲染的封面卡片交给 Claude 描述（和赛道封面同一个描述员）
控制变量固定为「同龄、未经热度筛选」，所以只比较草稿之间的相对高低。
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import autoresearch as ar  # noqa: E402
import covers  # noqa: E402
from jevdev import jev  # noqa: E402


class Predictor:
    def __init__(self, con):
        self.questions = json.loads(ar.RUBRIC.read_text(encoding="utf-8"))["questions"]
        # 用全部赛道笔记训练（上线用；留出测试集的评估由 autoresearch.py --final 单独做）
        dev = ar.Data(con, self.questions, "dev")
        test = ar.Data(con, self.questions, "test")
        notes = dev.notes + test.notes
        self.base_keys = dev.base_keys
        base = dev.base + test.base
        feats = dev.jev + test.jev
        cols = ar.cols_of(self.questions, dev)
        self.jev_keys = [k for qid in self.questions for k in cols[qid]]
        Xb, self.fill_b = ar.matrix(base, self.base_keys)
        Xj, self.fill_j = ar.matrix(feats, self.jev_keys)
        y = np.concatenate([dev.y, test.y])
        self.model = ar.model().fit(np.hstack([Xb, Xj]), y)
        self.n_train = len(notes)

    def note_of(self, draft, cover_desc):
        tags = " ".join(f"#{t}" for t in draft["tags"])
        return {"id": "draft", "title": draft["title"], "desc": f"{draft['body']}\n{tags}",
                "cover": cover_desc, "cover_w": 1080, "cover_h": 1440, "note_type": "normal",
                "image_count": 1 + len(draft["pages"]), "from_latest": 1, "from_top": 0,
                "publish_ts": time.time() * 1000 - 7 * 86400000}

    def features(self, note):
        out = {}
        for inp in ("title", "body", "cover"):
            qs = {qid: {k: q[k] for k in ("type", "instructions", "criteria") if k in q}
                  for qid, q in self.questions.items() if q["input"] == inp and ar.applicable(note, q)}
            if qs:
                a, _ = jev.ask(ar.build_state(note, inp), qs)
                out.update({k: v for k, v in jev.flatten(a).items() if not k.endswith("__conf")})
        return out

    def predict(self, draft, cover_desc):
        note = self.note_of(draft, cover_desc)
        f = self.features(note)
        xb, _ = ar.matrix([ar.base_features(note)], self.base_keys, self.fill_b)
        xj, _ = ar.matrix([f], self.jev_keys, self.fill_j)
        return float(self.model.predict(np.hstack([xb, xj]))[0]), f


def score_drafts(con, drafts, work_dir, theme="warm"):
    """渲染每篇草稿的卡片 → Claude 描述封面 → Jev 答题 → 模型预测。结果写回每篇草稿：
    d["pred"]（预测的 log 互动量）、d["cover_desc"]、d["features"]、d["card_paths"]。"""
    import shutil
    from jevdev import cards
    work_dir = Path(work_dir)
    cover_dir = work_dir / "covers"
    cover_dir.mkdir(parents=True, exist_ok=True)
    for i, d in enumerate(drafts):
        d["card_paths"] = cards.render([d["cover"]] + d["pages"], work_dir / f"d{i}", theme)
        shutil.copy(d["card_paths"][0], cover_dir / f"d{i}.png")
    desc = covers.describe_batch(sorted(cover_dir.glob("d*.png")), add_dir=cover_dir)
    desc = {c["note_id"]: {k: v for k, v in c.items() if k != "note_id"} for c in desc}
    p = Predictor(con)
    for i, d in enumerate(drafts):
        d["cover_desc"] = desc.get(f"d{i}")
        d["pred"], d["features"] = p.predict(d, d["cover_desc"])
        d["pred"] = round(d["pred"], 3)
    return p
