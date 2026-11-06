"""QR 대기표 서버.  실행: python app.py  (PORT, PUBLIC_URL 환경변수 지원)"""
import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import segno

from waiting_queue import WaitingQueue

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
PORT = int(os.environ.get("PORT", 3000))
PUBLIC_URL = os.environ.get("PUBLIC_URL")  # QR에 들어갈 주소 (예: http://192.168.0.10:3000)
queue = WaitingQueue(os.path.join(HERE, "data.json"))
PAGES = {"/": "admin.html", "/admin": "admin.html", "/join": "join.html"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = min(int(self.headers.get("Content-Length") or 0), 10000)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _base(self):
        return PUBLIC_URL or f"http://{self.headers.get('Host')}"

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p == "/api/queue":
            return self._send(200, queue.snapshot())
        if p == "/api/status":
            try:
                id = int(parse_qs(u.query).get("id", ["0"])[0])
            except ValueError:
                id = 0
            return self._send(200, queue.status(id))
        if p == "/api/info":
            return self._send(200, {"joinUrl": self._base() + "/join"})
        if p == "/qr.svg":
            buf = io.BytesIO()
            segno.make(self._base() + "/join").save(buf, kind="svg", scale=10, border=2)
            return self._send(200, buf.getvalue(), "image/svg+xml")
        if p in PAGES:
            with open(os.path.join(PUB, PAGES[p]), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/join":
            b = self._body()
            try:
                return self._send(200, queue.add(b.get("name"), b.get("size")))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
        if p == "/api/complete":
            return self._send(200, {"done": queue.complete()})
        if p == "/api/remove":
            try:
                id = int(self._body().get("id"))
            except (TypeError, ValueError):
                id = 0
            return self._send(200, {"ok": queue.remove(id)})
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"대기표 서버 실행: http://localhost:{PORT}  (관리 화면 /, 손님 등록 /join)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
