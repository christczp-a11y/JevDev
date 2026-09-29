#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测 source_check.py --check-links 重试用的本地小服务器（只监听 127.0.0.1）。
用法：python flaky_server.py <端口>
  /ok      永远 200
  /flaky   第 1 次请求回 503，之后 200（/reset 清零）
  /dead    永远 500
  /reset   计数清零，回 200
  /quit    关掉服务器
5 分钟后自己退出，免得测试中断后留下进程。
"""
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

hits = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        n = hits[path] = hits.get(path, 0) + 1
        code = 200
        if path == "/flaky" and n == 1:
            code = 503
        elif path == "/dead":
            code = 500
        elif path == "/reset":
            hits.clear()
        body = ("%s #%d -> %d" % (path, n, code)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if path == "/quit":
            threading.Thread(target=self.server.shutdown).start()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H)
    t = threading.Timer(300, lambda: os._exit(0))
    t.daemon = True
    t.start()
    srv.serve_forever()
