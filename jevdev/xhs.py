"""小红书 MCP（本地 HTTP 服务，默认 localhost:18060）的最小客户端。

启动服务：C:\\Users\\Chris\\xhs\\bin\\start-mcp-rednote.cmd
"""
import json
import random
import re
import time
import urllib.request

URL = "http://localhost:18060/mcp"


def _post(payload, session_id=None, timeout=300):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        sid = resp.headers.get("Mcp-Session-Id")
        body = resp.read().decode()
        if "text/event-stream" in resp.headers.get("Content-Type", ""):
            for line in body.splitlines():
                if line.startswith("data:"):
                    body = line[5:].strip()
                    break
    return (json.loads(body) if body.strip() else None), sid


def call(tool, args=None, timeout=300):
    """调用一个 MCP 工具。返回解析后的 JSON；工具返回的不是 JSON 时，抛出带原文的 RuntimeError。"""
    _, sid = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "jevdev", "version": "0.1"}}})
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    res, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": tool, "arguments": args or {}}}, sid, timeout=timeout)
    text = res["result"]["content"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"{tool}: {text[:300]}")


def polite_sleep(lo=8.0, hi=20.0):
    """两次操作之间随机停顿，控制请求节奏。"""
    time.sleep(random.uniform(lo, hi))


def parse_count(s):
    """'2.7万' -> 27000，'1.2k' -> 1200，'' / None -> None。"""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.fullmatch(r"([\d.]+)\s*([万wWkK千]?)\+?", s)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2)
    if unit in ("万", "w", "W"):
        n *= 10000
    elif unit in ("k", "K", "千"):
        n *= 1000
    return int(n)
