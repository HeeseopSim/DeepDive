"""QR 대기표 서버 (파이썬 소켓 직접 구현, 외부 모듈 없음).
실행: python queue_server.py
 - 브라우저가 자동으로 열리고, 시작하면 인터넷 주소(무료 Cloudflare 터널)를 만들어 QR에 넣음
   → 손님은 같은 Wi-Fi가 아니어도 폰 카메라로 QR을 찍으면 대기 등록
 - 환경변수: PORT(기본 3000), PUBLIC_URL(주소 직접 지정), NO_TUNNEL=1, NO_BROWSER=1
관리 화면(PC에서만): /   손님 등록: /join   K키 = 맨 위 사람 삭제
"""
import atexit
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 3000))
PUBLIC_URL = os.environ.get("PUBLIC_URL")
BUILD_ID = "socket-v1"
TUNNEL_PENDING = False

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
.qr{background:#fff;border-radius:12px;padding:8px}.qr svg{width:100%;height:auto;display:block}
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
<div class="panel"><h2>QR로 대기 등록</h2>
  <div class="qr" id="qrbox"><div style="color:#334155;padding:40px 0;text-align:center">QR 만드는 중…</div></div>
  <div id="qrmsg" style="margin:10px 0;font-weight:700"></div>
  <div class="url" id="url" style="font-size:15px;color:#e2e8f0"></div>
  <div style="margin-top:14px;font-size:11px;color:#64748b">build BUILD_ID</div></div>
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
let lastUrl=null;
async function refreshQR(){
  try{
    const d=await (await fetch('/api/info')).json();
    if(d.joinUrl!==lastUrl){lastUrl=d.joinUrl;$('qrbox').innerHTML=d.svg}
    $('url').textContent=d.joinUrl;
    $('qrmsg').textContent=d.tunnel?'🌐 인터넷 주소 · 같은 Wi-Fi가 아니어도 접속됩니다':(d.pending?'⏳ 인터넷 주소 만드는 중… QR이 곧 바뀝니다':'⚠ 이 PC와 같은 Wi-Fi에서만 접속됩니다');
  }catch(e){$('qrmsg').textContent='⚠ 서버와 연결이 끊겼습니다 (서버 창이 꺼졌는지 확인)'}
}
refreshQR();setInterval(refreshQR,3000);
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
    const r=await fetch('/api/join',{method:'POST',body:JSON.stringify({name:document.getElementById('name').value,size:document.getElementById('size').value})});
    const d=await r.json();
    if(!r.ok){err.textContent=d.error;return}
    myId=d.id;localStorage.setItem('queueId',myId);localStorage.setItem('queueToken',d.token);track();
  };
}
async function track(){
  const s=await (await fetch('/api/status?id='+myId)).json();
  if(!s.waiting){
    localStorage.removeItem('queueId');localStorage.removeItem('queueToken');
    app.innerHTML=`<h1>대기 종료</h1><p class="sub">대기표가 완료/취소되었습니다.</p><button class="go" id="again">다시 등록</button>`;
    again.onclick=()=>{myId=null;form()};return;
  }
  const first=s.position===1;
  app.innerHTML=`<h1>대기표</h1><div class="sub">대기번호</div><div class="big">${s.item.id}</div>
  <div class="sub">${esc(s.item.name)}님 · ${s.item.size}명</div>
  ${first?'<div class="now">🔔 곧 입장 차례입니다!</div>':`<div class="now" style="background:#2563eb">내 앞 ${s.teamsAhead}팀 (${s.peopleAhead}명)</div>`}
  <button class="cancel" id="c">대기 취소</button>`;
  c.onclick=async()=>{if(!confirm('대기를 취소할까요?'))return;
    await fetch('/api/remove',{method:'POST',body:JSON.stringify({id:myId,token:localStorage.getItem('queueToken')})});track()};
  clearTimeout(window.t);window.t=setTimeout(track,3000);
}
myId?track():form();
</script></body></html>
'''


# ---- 내장 QR 생성기 (바이트 모드, 오류정정 L, 버전 1~6 → 최대 134자) ----
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]
_QR_VER = {1: (19, 1, 7), 2: (34, 1, 10), 3: (55, 1, 15),
           4: (80, 1, 20), 5: (108, 1, 26), 6: (136, 2, 18)}  # (데이터 코드워드, 블록 수, 블록당 EC)
_QR_CAP = {1: 17, 2: 32, 3: 53, 4: 78, 5: 106, 6: 134}
_QR_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}
_QR_MASKS = [
    lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
]


def _rs_ec(data, n):
    gen = [1]
    for i in range(n):
        nxt = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            nxt[j] ^= c
            if c:
                nxt[j + 1] ^= _EXP[_LOG[c] + i]
        gen = nxt
    rem = [0] * n
    for b in data:
        f = b ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for j in range(n):
                if gen[j + 1]:
                    rem[j] ^= _EXP[_LOG[gen[j + 1]] + _LOG[f]]
    return rem


def _qr_matrix(text, mask=None):
    raw = text.encode("utf-8")
    ver = next((v for v in range(1, 7) if len(raw) <= _QR_CAP[v]), None)
    if ver is None:
        raise ValueError("주소가 너무 깁니다")
    cap, nblocks, ecn = _QR_VER[ver]
    bits = "0100" + format(len(raw), "08b") + "".join(format(b, "08b") for b in raw)
    bits += "0" * min(4, cap * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    data = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    k = 0
    while len(data) < cap:
        data.append((0xEC, 0x11)[k % 2])
        k += 1
    per = cap // nblocks
    blocks = [data[i * per:(i + 1) * per] for i in range(nblocks)]
    ecs = [_rs_ec(b, ecn) for b in blocks]
    cw = [b[i] for i in range(per) for b in blocks] + [e[i] for i in range(ecn) for e in ecs]
    stream = "".join(format(c, "08b") for c in cw)

    n = 17 + 4 * ver
    M = [[False] * n for _ in range(n)]
    F = [[False] * n for _ in range(n)]

    def setf(x, y, v):
        M[y][x] = v
        F[y][x] = True

    for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < n and 0 <= y < n:
                    setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    for i in range(8, n - 8):
        setf(i, 6, i % 2 == 0)
        setf(6, i, i % 2 == 0)
    ap = _QR_ALIGN[ver]
    for cy in ap:
        for cx in ap:
            if F[cy][cx]:
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    setf(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
    for i in range(9):
        F[8][i] = F[i][8] = True
    for i in range(8):
        F[8][n - 1 - i] = F[n - 1 - i][8] = True
    setf(8, n - 8, True)

    pos = []
    x = n - 1
    up = True
    while x > 0:
        if x == 6:
            x -= 1
        for r in range(n):
            y = n - 1 - r if up else r
            for xx in (x, x - 1):
                if not F[y][xx]:
                    pos.append((xx, y))
        up = not up
        x -= 2
    base = [r[:] for r in M]
    for i, (px, py) in enumerate(pos):
        base[py][px] = i < len(stream) and stream[i] == "1"

    def with_mask(m):
        A = [r[:] for r in base]
        for px, py in pos:
            if _QR_MASKS[m](px, py):
                A[py][px] = not A[py][px]
        fmt = (1 << 3) | m
        r = fmt << 10
        for i in range(14, 9, -1):
            if (r >> i) & 1:
                r ^= 0x537 << (i - 10)
        fb = ((fmt << 10) | r) ^ 0x5412
        g = lambda i: (fb >> i) & 1 == 1
        for i in range(6):
            A[i][8] = g(i)
        A[7][8] = g(6)
        A[8][8] = g(7)
        A[8][7] = g(8)
        for i in range(9, 15):
            A[8][14 - i] = g(i)
        for i in range(8):
            A[8][n - 1 - i] = g(i)
        for i in range(8, 15):
            A[n - 15 + i][8] = g(i)
        A[n - 8][8] = True
        return A

    def penalty(A):
        p = 0
        for rows in (A, [list(c) for c in zip(*A)]):
            for r in rows:
                run = 1
                for i in range(1, n):
                    if r[i] == r[i - 1]:
                        run += 1
                    else:
                        p += run - 2 if run >= 5 else 0
                        run = 1
                p += run - 2 if run >= 5 else 0
        for y in range(n - 1):
            for x in range(n - 1):
                if A[y][x] == A[y][x + 1] == A[y + 1][x] == A[y + 1][x + 1]:
                    p += 3
        dark = sum(sum(r) for r in A)
        p += abs(dark * 20 - n * n * 10) // (n * n) * 10
        return p

    if mask is not None:
        return with_mask(mask)
    return min((with_mask(m) for m in range(8)), key=penalty)


def make_qr_svg(text, scale=10, border=4):
    A = _qr_matrix(text)
    n = len(A)
    s = (n + border * 2) * scale
    rects = "".join(
        f'<rect x="{(x + border) * scale}" y="{(y + border) * scale}" width="{scale}" height="{scale}"/>'
        for y in range(n) for x in range(n) if A[y][x])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">'
            f'<rect width="{s}" height="{s}" fill="#fff"/><g fill="#000">{rects}</g></svg>')


def _public(x):
    """토큰(취소 권한)은 본인에게만 → 응답에서 제외."""
    return {k: v for k, v in x.items() if k != "token"}


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
                    "createdAt": int(time.time() * 1000),
                    "token": secrets.token_hex(8)}
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

    def remove(self, id, token=None, admin=False):
        with self.lock:
            for i, x in enumerate(self.items):
                if x["id"] == id:
                    if not admin and (not token or token != x.get("token")):
                        return False
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
                            "item": _public(x), "lastCalled": self.last_called}
            return {"waiting": False, "lastCalled": self.last_called}

    def snapshot(self):
        with self.lock:
            return {"items": [_public(x) for x in self.items],
                    "totalPeople": sum(x["size"] for x in self.items),
                    "lastCalled": self.last_called}


def _find_cloudflared():
    p = os.environ.get("CLOUDFLARED_PATH")
    if p and os.path.exists(p):
        return p
    local = os.path.join(HERE, "cloudflared.exe" if os.name == "nt" else "cloudflared")
    return shutil.which("cloudflared") or (local if os.path.exists(local) else None)


def _download_cloudflared():
    """Windows 전용: 공식 GitHub 릴리스에서 cloudflared.exe 내려받기 (사용자 동의 후)."""
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    dest = os.path.join(HERE, "cloudflared.exe")
    print("내려받는 중... (약 30MB)")
    urllib.request.urlretrieve(url, dest)
    return dest


def start_tunnel(port):
    """cloudflared 터널을 켜고 인터넷 주소를 PUBLIC_URL로 설정."""
    global PUBLIC_URL, TUNNEL_PENDING
    if PUBLIC_URL or os.environ.get("NO_TUNNEL"):
        return
    exe = _find_cloudflared()
    if not exe:
        if os.name != "nt" or not sys.stdin.isatty():
            print("[터널 없음] cloudflared를 설치하면 같은 Wi-Fi가 아니어도 QR로 접속할 수 있습니다.")
            return
        ans = input("인터넷용 주소를 만들려면 cloudflared(무료, Cloudflare 공식)가 필요합니다.\n"
                    "자동으로 내려받을까요? (y/n): ").strip().lower()
        if ans != "y":
            print("터널 없이 실행합니다 (같은 Wi-Fi에서만 접속 가능).")
            return
        try:
            exe = _download_cloudflared()
        except Exception as e:  # noqa: BLE001
            print("내려받기 실패:", e)
            return
    try:
        proc = subprocess.Popen([exe, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
    except OSError as e:
        print("터널 실행 실패:", e)
        return
    atexit.register(proc.terminate)
    TUNNEL_PENDING = True

    def watch():
        global PUBLIC_URL, TUNNEL_PENDING
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not PUBLIC_URL:
                PUBLIC_URL = m.group(0)
                TUNNEL_PENDING = False
                print(f"\n인터넷 주소 준비 완료: {PUBLIC_URL}")
                print("관리 화면을 새로고침하면 이 주소로 된 QR이 나옵니다.")
        TUNNEL_PENDING = False
        if PUBLIC_URL:
            print("\n⚠ 터널이 끊겼습니다. 서버를 껐다 다시 켜야 새 인터넷 주소가 만들어집니다.")
        else:
            print("터널을 만들지 못했습니다 (인터넷 연결/방화벽 확인). 같은 Wi-Fi에서만 접속됩니다.")
    threading.Thread(target=watch, daemon=True).start()
    print("인터넷 주소 만드는 중... (보통 5~10초)")



queue = WaitingQueue(os.path.join(HERE, "data.json"))
ADMIN_PAGE = ADMIN_HTML.replace("BUILD_ID", BUILD_ID)
STATUS_TEXT = {200: "OK", 204: "No Content", 400: "Bad Request", 403: "Forbidden",
               404: "Not Found", 405: "Method Not Allowed", 500: "Internal Server Error"}
ACTUAL_PORT = PORT


# ---------------- 소켓 HTTP 서버 ----------------
def read_request(conn):
    """요청 한 개를 읽어 (method, path, query, headers, body) 반환. 실패 시 None."""
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = conn.recv(4096)
        if not chunk:
            return None
        buf += chunk
        if len(buf) > 32768:
            return None
    head, _, rest = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    try:
        method, target, _ver = lines[0].split(" ", 2)
    except ValueError:
        return None
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    n = min(int(headers.get("content-length") or 0), 10000)
    while len(rest) < n:
        chunk = conn.recv(4096)
        if not chunk:
            break
        rest += chunk
    u = urlparse(target)
    return method.upper(), u.path, parse_qs(u.query), headers, rest[:n]


def respond(conn, code, body, ctype="application/json; charset=utf-8"):
    if isinstance(body, str):
        body = body.encode("utf-8")
    elif not isinstance(body, bytes):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    head = (f"HTTP/1.1 {code} {STATUS_TEXT.get(code, 'OK')}\r\n"
            f"Content-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n\r\n")
    conn.sendall(head.encode("latin-1") + body)


def is_local(peer_ip, headers):
    """PC 자신에서 온 요청만 True (터널/다른 기기 경유는 False)."""
    ip = peer_ip.replace("::ffff:", "")
    if ip not in ("127.0.0.1", "::1"):
        return False
    return not any(h in headers for h in ("cf-connecting-ip", "x-forwarded-for", "forwarded", "x-real-ip"))


def base_url(headers):
    if PUBLIC_URL:
        return PUBLIC_URL.rstrip("/")
    proto = headers.get("x-forwarded-proto") or "http"
    return f"{proto}://{headers.get('host') or 'localhost:' + str(ACTUAL_PORT)}"


def json_body(body):
    try:
        d = json.loads(body or b"{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def handle(method, path, query, headers, body, local):
    """라우팅. (상태코드, 본문, 타입) 반환."""
    J = "application/json; charset=utf-8"
    H = "text/html; charset=utf-8"
    admin_only = path in ("/", "/admin", "/api/queue", "/api/info", "/api/complete")
    if admin_only and not local:
        return 403, {"error": "관리 기능은 서버 PC에서만 사용할 수 있습니다"}, J
    if method == "GET":
        if path in ("/", "/admin"):
            return 200, ADMIN_PAGE, H
        if path == "/join":
            return 200, JOIN_HTML, H
        if path == "/api/queue":
            return 200, queue.snapshot(), J
        if path == "/api/status":
            try:
                id = int(query.get("id", ["0"])[0])
            except ValueError:
                id = 0
            return 200, queue.status(id), J
        if path == "/api/info":
            url = base_url(headers) + "/join"
            return 200, {"joinUrl": url, "svg": make_qr_svg(url, scale=10, border=2),
                         "tunnel": bool(PUBLIC_URL) and "trycloudflare.com" in PUBLIC_URL,
                         "pending": TUNNEL_PENDING}, J
        if path == "/favicon.ico":
            return 204, b"", "text/plain"
        return 404, b"Not found", "text/plain"
    if method == "POST":
        b = json_body(body)
        if path == "/api/join":
            try:
                return 200, queue.add(b.get("name"), b.get("size")), J
            except ValueError as e:
                return 400, {"error": str(e)}, J
        if path == "/api/complete":
            return 200, {"done": queue.complete()}, J
        if path == "/api/remove":
            try:
                id = int(b.get("id"))
            except (TypeError, ValueError):
                id = 0
            return 200, {"ok": queue.remove(id, token=b.get("token"), admin=local)}, J
    return 404, {"error": "not found"}, J


def serve_conn(conn, addr):
    try:
        conn.settimeout(10)
        req = read_request(conn)
        if not req:
            return
        method, path, query, headers, body = req
        try:
            code, out, ctype = handle(method, path, query, headers, body, is_local(addr[0], headers))
        except Exception as e:  # noqa: BLE001
            print("처리 오류:", repr(e))
            code, out, ctype = 500, {"error": "서버 오류"}, "application/json; charset=utf-8"
        respond(conn, code, out, ctype)
    except OSError:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def make_listener(port):
    """듀얼스택(IPv4+IPv6) 소켓 생성. 포트가 사용 중이면 다음 포트로."""
    for p in range(port, port + 20):
        for fam in (socket.AF_INET6, socket.AF_INET):
            s = None
            try:
                s = socket.socket(fam, socket.SOCK_STREAM)
                if os.name != "nt":
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if fam == socket.AF_INET6:
                    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                    s.bind(("::", p))
                else:
                    s.bind(("0.0.0.0", p))
                s.listen(64)
                return s, p
            except OSError:
                if s:
                    s.close()
    sys.exit("사용할 수 있는 포트를 찾지 못했습니다. 켜 둔 서버 창을 모두 닫고 다시 실행하세요.")


def main():
    global ACTUAL_PORT
    sock, ACTUAL_PORT = make_listener(PORT)
    url = f"http://localhost:{ACTUAL_PORT}"
    print(f"대기표 서버 실행 [{BUILD_ID}]  ->  {url}   (관리 화면은 이 PC에서만)")
    if ACTUAL_PORT != PORT:
        print(f"※ {PORT}번 포트는 이미 사용 중(이전 서버가 켜져 있을 수 있음) → {ACTUAL_PORT}번으로 실행합니다.")
    start_tunnel(ACTUAL_PORT)
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=serve_conn, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
