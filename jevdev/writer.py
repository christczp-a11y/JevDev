"""用 Claude（本机 `claude -p`，走会员额度）按写作规范批量写草稿。"""
import json
import shutil
import subprocess
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
MODEL = "claude-opus-5-5"
_WIN_CLAUDE = Path.home() / "AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
CLAUDE_EXE = str(_WIN_CLAUDE) if _WIN_CLAUDE.exists() else (shutil.which("claude") or "claude")   # 本地 Windows / 云端 Linux

_CARD = {
    "type": "object",
    "properties": {
        "kicker": {"type": "string"}, "title": {"type": "string"}, "subtitle": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "meta": {"type": "string"}}, "required": ["name"]}},
        "footer_left": {"type": "string"},
    },
    "required": ["kicker", "title", "subtitle", "items", "footer_left"],
}
SCHEMA = {
    "type": "object",
    "properties": {"drafts": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "angle": {"type": "string"}, "target_keyword": {"type": "string"}, "title": {"type": "string"},
            "cover": _CARD, "pages": {"type": "array", "items": _CARD},
            "body": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["angle", "target_keyword", "title", "cover", "pages", "body", "tags"],
    }}},
    "required": ["drafts"],
}


def write_drafts(facts, n=4, extra_instructions=""):
    """facts：餐厅数据（dict）。返回 (drafts 列表, 本次调用的元信息)。"""
    user = (f"请写 {n} 篇角度不同的草稿。\n{extra_instructions}\n\n餐厅数据：\n"
            + json.dumps(facts, ensure_ascii=False, indent=1))
    out, meta = _run(user)
    return out["drafts"], meta


def revise_draft(draft, issues, facts):
    """只修改有问题的行（括号里写了问题：无依据 / 含禁用词），其他内容保持不变。返回修改后的一篇草稿。"""
    keep = {k: draft[k] for k in ("angle", "target_keyword", "title", "cover", "pages", "body", "tags")}
    user = ("下面这篇草稿里，这些内容有问题（括号里是问题）：\n"
            + "\n".join(f"- {line}" for line in issues)
            + "\n\n请只修改这些内容：无依据的改写成数据能支撑的说法或删掉，含禁用词的换一种说法；其他部分保持原样。"
              "输出 drafts 数组，里面只放修改后的这一篇。\n\n草稿：\n"
            + json.dumps(keep, ensure_ascii=False, indent=1)
            + "\n\n餐厅数据：\n" + json.dumps(facts, ensure_ascii=False, indent=1))
    out, _ = _run(user)
    return out["drafts"][0]


def _run(user):
    system = (PROMPT_DIR / "xhs_writer.md").read_text(encoding="utf-8")
    # 直接调用 claude.exe（绕开 claude.cmd 的 cmd 转义问题）；用户提示走 stdin，避免命令行长度上限
    proc = subprocess.run(
        [CLAUDE_EXE, "-p", "--model", MODEL, "--output-format", "json", "--tools", "",
         "--system-prompt", system, "--json-schema", json.dumps(SCHEMA, ensure_ascii=False)],
        input=user, capture_output=True, text=True, encoding="utf-8", timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p 失败：{proc.stderr[:500] or proc.stdout[:500]}")
    out = json.loads(proc.stdout)
    if out.get("is_error") or not out.get("structured_output"):
        raise RuntimeError(f"claude -p 没有返回结构化结果：{str(out.get('result'))[:500]}")
    meta = {k: out.get(k) for k in ("total_cost_usd", "duration_ms", "session_id")}
    return out["structured_output"], meta
