"""QR 대기표 (단일 파일).
설치: pip install segno
실행: python queue_app.py   (환경변수: PORT, PUBLIC_URL=http://<PC의 IP>:3000)
관리 화면: /   손님 등록: /join   K키 = 맨 위 사람 삭제
"""
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import segno

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 3000))
PUBLIC_URL = os.environ.get("PUBLIC_URL")

ADMIN_HTML = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>대기표 관리</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}
.wrap{display:grid;grid-template-columns:1fr 280px;gap:24px;max-width:1100px;margin:auto}
@media(max-width:800px){.wrap{grid-template-columns:1fr}}
.panel{background:#1e293b;border-radius:16px;padding:20px}
h2{margin:0 0 12px}.now{background:#16a34a;border-radius:14px;padding:20px;margin-bottom:14px}
.now .n{font-size:56px;font-weight:800;line-height:1}.now .who{font-size:24px;margin-top:6px}
.empty{padding:30px;text-align:center;color:#94a3b8}
.row{display:flex;align-items:center;gap:12px;padding:12px;border-radius:10px;background:#0f172a;margin-bottom:8px}
.row .no{font-weight:800;font-size:22px;width:56px;color:#60a5fa}.row .nm{flex:1;font-size:18px}.row .sz{color:#94a3b8}
button{cursor:pointer;border:0;border-radius:10px;padding:10px 14px;font-size:15px;font-weight:600}
.done{background:#fff;color:#0f172a;width:100%;padding:16px;font-size:18px;margin-bottom:14px}
.x{background:#334155;color:#e2e8f0}
.qr{background:#fff;border-radius:12px;padding:8px}.qr img{width:100%;display:block}
.url{word-break:break-all;font-size:12px;color:#94a3b8;margin-top:8px}
.add{display:flex;gap:8px;margin-top:16px}.add input{padding:10px;border-radius:8px;border:0;font-size:15px}
.add input[name=size]{width:70px}.add input[name=name]{flex:1;min-width:0}.add button{background:#2563eb;color:#fff}
kbd{background:#334155;border-radius:6px;padding:2px 8px;font-weight:700}
.stat{color:#94a3b8;margin-bottom:12px}
</style></head><body><div class="wrap">
<div class="panel">
  <h2>대기 현황</h2><div class="stat" id="stat"></div>
  <div id="now"></div>
  <button class="done" id="done">✔ 완료 — 맨 위 삭제 (<kbd>K</kbd>)</button>
  <div id="list"></div>
  <form class="add" id="addf"><input name="name" placeholder="이름 (직접 추가)" maxlength="30"><input name="size" type="number" min="1" max="99" value="1"><button>추가</button></form>
</div>
<div class="panel"><h2>QR로 대기 등록</h2><div class="qr"><img src="/qr.svg" alt="QR"></div><div class="url" id="url"></div></div>
</div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
  const d=await (await fetch('/api/queue')).json();
  $('stat').textContent=`총 ${d.items.length}팀 · ${d.totalPeople}명 대기 중`;
  const [top,...rest]=d.items;
  $('now').innerHTML=top?`<div class="now"><div>현재 차례</div><div class="n">${top.id}번</div><div class="who">${esc(top.name)} · ${top.size}명</div></div>`:'<div class="empty">대기 중인 손님이 없습니다</div>';
  $('list').innerHTML=rest.map(x=>`<div class="row"><span class="no">${x.id}</span><span class="nm">${esc(x.name)}</span><span class="sz">${x.size}명</span><button class="x" data-id="${x.id}">삭제</button></div>`).join('');
}
async function complete(){await fetch('/api/complete',{method:'POST'});load()}
$('done').onclick=complete;
$('list').onclick=async e=>{const id=e.target.dataset.id;if(!id)return;
  await fetch('/api/remove',{method:'POST',body:JSON.stringify({id:Number(id)})});load()};
$('addf').onsubmit=async e=>{e.preventDefault();const f=e.target;
  const r=await fetch('/api/join',{method:'POST',body:JSON.stringify({name:f.name.value,size:f.size.value})});
  if(!r.ok)return alert((await r.json()).error);f.name.value='';f.size.value=1;load()};
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.ctrlKey||e.metaKey||e.altKey)return;
  if(e.key==='k'||e.key==='K'||e.key==='ㅏ'){e.preventDefault();complete()}
});
fetch('/api/info').then(r=>r.json()).then(d=>$('url').textContent=d.joinUrl);
load();setInterval(load,2000);
</script></body></html>
'''

JOIN_HTML = r'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>대기 등록</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#f3f6fb;color:#1b2430;display:flex;justify-content:center;padding:20px}
.card{background:#fff;border-radius:16px;box-shadow:0 4px 20px #0001;padding:24px;width:100%;max-width:420px}
h1{margin:0 0 16px;font-size:22px}label{display:block;margin:14px 0 6px;font-weight:600}
input{width:100%;padding:14px;font-size:18px;border:1px solid #c8d1de;border-radius:10px}
.stepper{display:flex;gap:10px;align-items:center}.stepper button{width:52px;height:52px;font-size:24px;border-radius:10px;border:1px solid #c8d1de;background:#fff}
.stepper input{text-align:center}
.go{margin-top:22px;width:100%;padding:16px;font-size:18px;font-weight:700;color:#fff;background:#2563eb;border:0;border-radius:12px}
.err{color:#c0392b;margin-top:10px;min-height:20px}
.big{font-size:64px;font-weight:800;color:#2563eb;text-align:center;margin:8px 0}
.sub{text-align:center;color:#556}.now{background:#16a34a;color:#fff;border-radius:12px;padding:16px;text-align:center;font-size:20px;font-weight:700;margin-top:14px}
.cancel{margin-top:18px;width:100%;padding:12px;border:1px solid #c8d1de;background:#fff;border-radius:10px}
</style></head><body><div class="card" id="app"></div>
<script>
const app=document.getElementById('app');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let myId=Number(localStorage.getItem('queueId'))||null;
function form(){
  app.innerHTML=`<h1>대기 등록</h1>
  <label>이름</label><input id="name" maxlength="30" placeholder="홍길동" autocomplete="off">
  <label>인원</label><div class="stepper"><button id="m">−</button><input id="size" type="number" inputmode="numeric" min="1" max="99" value="1"><button id="p">+</button></div>
  <button class="go" id="go">대기표 받기</button><div class="err" id="err"></div>`;
  const size=document.getElementById('size');
  m.onclick=()=>size.value=Math.max(1,Number(size.value)-1);
  p.onclick=()=>size.value=Math.min(99,Number(size.value)+1);
  go.onclick=async()=>{
    const r=await fetch('/api/join',{method:'POST',body:JSON.stringify({name:name.value,size:size.value})});
    const d=await r.json();
    if(!r.ok){err.textContent=d.error;return}
    myId=d.id;localStorage.setItem('queueId',myId);track();
  };
}
async function track(){
  const s=await (await fetch('/api/status?id='+myId)).json();
  if(!s.waiting){
    localStorage.removeItem('queueId');
    app.innerHTML=`<h1>대기 종료</h1><p class="sub">대기표가 완료/취소되었습니다.</p><button class="go" id="again">다시 등록</button>`;
    again.onclick=()=>{myId=null;form()};return;
  }
  const first=s.position===1;
  app.innerHTML=`<h1>대기표</h1><div class="sub">대기번호</div><div class="big">${s.item.id}</div>
  <div class="sub">${esc(s.item.name)}님 · ${s.item.size}명</div>
  ${first?'<div class="now">🔔 곧 입장 차례입니다!</div>':`<div class="now" style="background:#2563eb">내 앞 ${s.teamsAhead}팀 (${s.peopleAhead}명)</div>`}
  <button class="cancel" id="c">대기 취소</button>`;
  c.onclick=async()=>{if(!confirm('대기를 취소할까요?'))return;
    await fetch('/api/remove',{method:'POST',body:JSON.stringify({id:myId})});track()};
  clearTimeout(window.t);window.t=setTimeout(track,3000);
}
myId?track():form();
</script></body></html>
'''


class WaitingQueue:
    def __init__(self, file=None):
        self.file = file
        self.items = []
        self.next_number = 1
        self.last_called = None
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        if not self.file or not os.path.exists(self.file):
            return
        try:
            with open(self.file, encoding="utf-8") as f:
                d = json.load(f)
            self.items = d.get("items", [])
            self.next_number = d.get("next_number", 1)
            self.last_called = d.get("last_called")
        except (OSError, ValueError):
            pass  # 손상된 파일은 무시

    def _save(self):
        if not self.file:
            return
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump({"items": self.items, "next_number": self.next_number,
                       "last_called": self.last_called}, f, ensure_ascii=False)

    def add(self, name, size):
        name = str(name or "").strip()[:30]
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 0
        if not name:
            raise ValueError("이름을 입력해주세요")
        if not 1 <= size <= 99:
            raise ValueError("인원은 1~99명이어야 합니다")
        with self.lock:
            item = {"id": self.next_number, "name": name, "size": size,
                    "createdAt": int(time.time() * 1000)}
            self.next_number += 1
            self.items.append(item)
            self._save()
            return item

    def complete(self):
        """K키: 맨 위 사람 삭제 → 다음 사람이 맨 위로."""
        with self.lock:
            done = self.items.pop(0) if self.items else None
            if done:
                self.last_called = done["id"]
            self._save()
            return done

    def remove(self, id):
        with self.lock:
            for i, x in enumerate(self.items):
                if x["id"] == id:
                    del self.items[i]
                    self._save()
                    return True
            return False

    def status(self, id):
        with self.lock:
            for i, x in enumerate(self.items):
                if x["id"] == id:
                    return {"waiting": True, "position": i + 1, "teamsAhead": i,
                            "peopleAhead": sum(y["size"] for y in self.items[:i]),
                            "item": x, "lastCalled": self.last_called}
            return {"waiting": False, "lastCalled": self.last_called}

    def snapshot(self):
        with self.lock:
            return {"items": list(self.items),
                    "totalPeople": sum(x["size"] for x in self.items),
                    "lastCalled": self.last_called}


queue = WaitingQueue(os.path.join(HERE, "data.json"))
PAGES = {"/": ADMIN_HTML, "/admin": ADMIN_HTML, "/join": JOIN_HTML}


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
            return self._send(200, PAGES[p].encode(), "text/html; charset=utf-8")
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
