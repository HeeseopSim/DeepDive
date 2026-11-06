"""대기표 + QR (PC용, 창 하나에 한 화면). 파이썬만 있으면 됨 (tkinter 내장, 외부 모듈 없음).
실행: python queue_board_pc.py
 - 한 창에 현재 호출 번호 / 다음 순서 / 등록 QR 이 같이 나옴 (안드로이드 Daegi-board 앱과 같은 구조)
 - 손님은 폰 카메라로 QR을 찍으면 등록 페이지가 열림 (같은 Wi-Fi 또는 이 PC의 핫스팟)
 - K 키: 다음 손님 호출 · N 키: 수동 추가 · F11: 전체화면 · Esc: 전체화면 해제
 - 환경변수: PORT(기본 8080), PUBLIC_URL(QR에 넣을 주소 직접 지정)
 - cloudflared(.exe)가 같은 폴더/PATH에 있으면 인터넷 주소(터널)를 자동으로 만들어 QR에 사용
"""
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
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8080))
PUBLIC_URL = os.environ.get("PUBLIC_URL")  # 터널/직접 지정 주소 (없으면 이 PC의 LAN 주소 사용)
ACTUAL_PORT = PORT

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
STATUS_TEXT = {200: "OK", 204: "No Content", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}


# ---------------- 소켓 HTTP 서버 (손님 등록 페이지용) ----------------
def read_request(conn):
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
    return method.upper(), u.path, parse_qs(u.query), rest[:n]


def respond(conn, code, body, ctype="application/json; charset=utf-8"):
    if isinstance(body, str):
        body = body.encode("utf-8")
    elif not isinstance(body, bytes):
        body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    head = (f"HTTP/1.1 {code} {STATUS_TEXT.get(code, 'OK')}\r\n"
            f"Content-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n\r\n")
    conn.sendall(head.encode("latin-1") + body)


def handle(method, path, query, body):
    J = "application/json; charset=utf-8"
    if method == "GET":
        if path in ("/", "/join"):
            return 200, JOIN_HTML, "text/html; charset=utf-8"
        if path == "/api/status":
            try:
                id = int(query.get("id", ["0"])[0])
            except ValueError:
                id = 0
            return 200, queue.status(id), J
        if path == "/favicon.ico":
            return 204, b"", "text/plain"
        return 404, b"Not found", "text/plain"
    if method == "POST":
        try:
            b = json.loads(body or b"{}")
            b = b if isinstance(b, dict) else {}
        except ValueError:
            b = {}
        if path == "/api/join":
            try:
                return 200, queue.add(b.get("name"), b.get("size")), J
            except ValueError as e:
                return 400, {"error": str(e)}, J
        if path == "/api/remove":  # 손님 본인 취소 (토큰 필요)
            try:
                id = int(b.get("id"))
            except (TypeError, ValueError):
                id = 0
            return 200, {"ok": queue.remove(id, token=b.get("token"), admin=False)}, J
    return 404, {"error": "not found"}, J


def serve_conn(conn):
    try:
        conn.settimeout(10)
        req = read_request(conn)
        if not req:
            return
        try:
            code, out, ctype = handle(*req)
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
    """이미 사용 중이면 다음 포트로. 듀얼스택(IPv4+IPv6) 시도 후 IPv4."""
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
    raise OSError("사용할 수 있는 포트를 찾지 못했습니다")


def accept_loop(sock):
    while True:
        try:
            conn, _addr = sock.accept()
        except OSError:
            return
        threading.Thread(target=serve_conn, args=(conn,), daemon=True).start()


# ---------------- 이 PC의 접속 주소 ----------------
def local_ips():
    """손님 폰이 접속할 수 있는 이 PC의 IPv4 주소 후보들 (핫스팟/Wi-Fi/랜)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # 실제로 패킷을 보내지 않음 (기본 경로 확인용)
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in out:
            out.append(ip)
    return out or ["127.0.0.1"]


# ---------------- 선택: cloudflared 터널 ----------------
TUNNEL_URL = None


def start_tunnel(port):
    """cloudflared 가 같은 폴더/PATH 에 있을 때만 터널을 켜서 인터넷 주소를 만든다."""
    global TUNNEL_URL
    exe = shutil.which("cloudflared") or next(
        (p for p in (os.path.join(HERE, "cloudflared.exe"), os.path.join(HERE, "cloudflared")) if os.path.exists(p)), None)
    if not exe or PUBLIC_URL:
        return
    try:
        proc = subprocess.Popen([exe, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
    except OSError:
        return

    def watch():
        global TUNNEL_URL
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not TUNNEL_URL:
                TUNNEL_URL = m.group(0)
    threading.Thread(target=watch, daemon=True).start()


# ---------------- 화면 (tkinter) ----------------
import tkinter as tk
from tkinter import messagebox, simpledialog

BG, PANEL, GREEN, GRAY = "#0b1220", "#111b30", "#16a34a", "#1e293b"
TEXT, MUTED, BLUE = "#e2e8f0", "#94a3b8", "#60a5fa"


def mask(name):
    n = list(str(name))
    if len(n) <= 1:
        return "".join(n)
    if len(n) == 2:
        return n[0] + "*"
    return n[0] + "*" * (len(n) - 2) + n[-1]


class App:
    def __init__(self, root, port):
        self.root = root
        self.port = port
        self.ip_index = 0
        self.fullscreen = False
        self.last_qr = None
        root.title("대기표 + QR")
        root.configure(bg=BG)
        root.geometry("1280x720")
        root.minsize(900, 560)

        head = tk.Frame(root, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text="🏥 대기 현황", font=("Malgun Gothic", 20, "bold"), fg="white", bg=PANEL).pack(side="left", padx=16, pady=10)
        self.addr_btn = tk.Button(head, text="주소 변경", command=self.next_ip, relief="flat", bg=GRAY, fg=TEXT)
        self.addr_btn.pack(side="right", padx=12)
        self.hint = tk.Label(head, text="", font=("Malgun Gothic", 11), fg=MUTED, bg=PANEL)
        self.hint.pack(side="right", padx=4)

        bottom = tk.Frame(root, bg=PANEL)
        bottom.pack(side="bottom", fill="x")
        tk.Button(bottom, text="▶ 다음 손님 호출 (K)", command=self.complete, font=("Malgun Gothic", 16, "bold"),
                  bg="white", fg="#0f172a", relief="flat").pack(side="left", padx=12, pady=10, ipadx=14, ipady=8)
        tk.Button(bottom, text="＋ 추가 (N)", command=self.add_dialog, font=("Malgun Gothic", 13),
                  bg=GRAY, fg=TEXT, relief="flat").pack(side="left", padx=4, pady=10, ipadx=10, ipady=8)
        tk.Label(bottom, text="F11 전체화면 · 목록 항목을 클릭하면 삭제", fg=MUTED, bg=PANEL,
                 font=("Malgun Gothic", 10)).pack(side="right", padx=14)

        main = tk.Frame(root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=12)
        main.columnconfigure(0, weight=3, uniform="c")
        main.columnconfigure(1, weight=2, uniform="c")
        main.rowconfigure(0, weight=1)

        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.now = tk.Frame(left, bg=GREEN)
        self.now.pack(fill="x")
        self.now_lab = tk.Label(self.now, text="현재 호출", font=("Malgun Gothic", 18), fg="white", bg=GREEN)
        self.now_lab.pack(pady=(14, 0))
        self.now_num = tk.Label(self.now, text="-", font=("Malgun Gothic", 90, "bold"), fg="white", bg=GREEN)
        self.now_num.pack()
        self.now_who = tk.Label(self.now, text="", font=("Malgun Gothic", 26, "bold"), fg="white", bg=GREEN)
        self.now_who.pack(pady=(0, 16))

        nxt = tk.Frame(left, bg=PANEL)
        nxt.pack(fill="both", expand=True, pady=(12, 0))
        tk.Label(nxt, text="다음 순서", font=("Malgun Gothic", 15), fg=MUTED, bg=PANEL).pack(anchor="w", padx=18, pady=(12, 4))
        self.list_box = tk.Frame(nxt, bg=PANEL)
        self.list_box.pack(fill="both", expand=True, padx=18)
        self.more = tk.Label(nxt, text="", font=("Malgun Gothic", 13), fg=MUTED, bg=PANEL)
        self.more.pack(anchor="w", padx=18, pady=(0, 10))

        right = tk.Frame(main, bg=PANEL)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="📱 QR을 찍어 대기 등록", font=("Malgun Gothic", 18, "bold"), fg="white", bg=PANEL).pack(pady=(16, 8))
        self.qr_canvas = tk.Canvas(right, bg="white", highlightthickness=0)
        self.qr_canvas.pack(fill="both", expand=True, padx=18, pady=4)
        self.qr_canvas.bind("<Configure>", lambda e: self.draw_qr())
        self.url_var = tk.StringVar()
        tk.Entry(right, textvariable=self.url_var, state="readonly", justify="center", font=("Malgun Gothic", 12),
                 readonlybackground=PANEL, fg="white", relief="flat").pack(fill="x", padx=18, pady=(8, 0))
        self.count = tk.Label(right, text="", font=("Malgun Gothic", 18), fg=MUTED, bg=PANEL)
        self.count.pack(pady=(6, 14))

        root.bind("<Key>", self.on_key)
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Escape>", lambda e: self.set_fullscreen(False))
        self.refresh()

    # --- 입력 ---
    def on_key(self, e):
        if isinstance(e.widget, tk.Entry) and str(e.widget.cget("state")) == "normal":
            return
        ch = (e.char or "").lower()
        if ch in ("k", "ㅏ"):
            self.complete()
        elif ch in ("n", "ㅜ"):
            self.add_dialog()

    def set_fullscreen(self, on):
        self.fullscreen = on
        self.root.attributes("-fullscreen", on)

    def toggle_fullscreen(self, _e=None):
        self.set_fullscreen(not self.fullscreen)

    def next_ip(self):
        self.ip_index += 1
        self.refresh()

    # --- 동작 ---
    def complete(self):
        queue.complete()
        self.refresh(once=True)

    def add_dialog(self):
        name = simpledialog.askstring("대기 추가", "이름", parent=self.root)
        if not name:
            return
        size = simpledialog.askinteger("대기 추가", "인원", parent=self.root, initialvalue=1, minvalue=1, maxvalue=99)
        if size is None:
            return
        try:
            queue.add(name, size)
        except ValueError as e:
            messagebox.showwarning("입력 확인", str(e))
        self.refresh(once=True)

    def remove(self, id, name):
        if messagebox.askyesno("대기 삭제", f"{id}번 {name} 님을 삭제할까요?"):
            queue.remove(id, admin=True)
            self.refresh(once=True)

    # --- 그리기 ---
    def join_url(self):
        if PUBLIC_URL:
            return PUBLIC_URL.rstrip("/") + "/join", "직접 지정"
        if TUNNEL_URL:
            return TUNNEL_URL + "/join", "인터넷 주소 (같은 Wi-Fi 아니어도 OK)"
        ips = local_ips()
        ip = ips[self.ip_index % len(ips)]
        return f"http://{ip}:{self.port}/join", f"같은 Wi-Fi/핫스팟에서 접속 ({self.ip_index % len(ips) + 1}/{len(ips)})"

    def draw_qr(self):
        c = self.qr_canvas
        c.delete("all")
        url = self.url_var.get()
        if not url:
            return
        try:
            m = _qr_matrix(url)
        except Exception as e:  # noqa: BLE001
            c.create_text(10, 10, anchor="nw", text=f"QR 생성 오류: {e}")
            return
        n = len(m)
        border = 2
        size = min(c.winfo_width(), c.winfo_height())
        cell = max(1, size // (n + border * 2))
        total = cell * (n + border * 2)
        ox = (c.winfo_width() - total) // 2
        oy = (c.winfo_height() - total) // 2
        for y in range(n):
            for x in range(n):
                if m[y][x]:
                    x0 = ox + (x + border) * cell
                    y0 = oy + (y + border) * cell
                    c.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill="black", outline="black")

    def refresh(self, once=False):
        snap = queue.snapshot()
        items = snap["items"]
        n = len(items)
        if n == 0:
            self.now.configure(bg=GRAY)
            for w, t in ((self.now_lab, ""), (self.now_num, "대기 없음"), (self.now_who, "")):
                w.configure(text=t, bg=GRAY)
            self.now_num.configure(font=("Malgun Gothic", 40, "bold"))
        else:
            top = items[0]
            self.now.configure(bg=GREEN)
            self.now_lab.configure(text="현재 호출", bg=GREEN)
            self.now_num.configure(text=f"{top['id']}번", bg=GREEN, font=("Malgun Gothic", 90, "bold"))
            self.now_who.configure(text=f"{mask(top['name'])} 님 · {top['size']}명", bg=GREEN)

        for w in self.list_box.winfo_children():
            w.destroy()
        show = items[1:6]
        for it in show:
            row = tk.Frame(self.list_box, bg=PANEL, cursor="hand2")
            row.pack(fill="x", pady=2)
            labs = [
                tk.Label(row, text=f"{it['id']}번", width=5, anchor="w", font=("Malgun Gothic", 20, "bold"), fg=BLUE, bg=PANEL),
                tk.Label(row, text=mask(it["name"]), anchor="w", font=("Malgun Gothic", 18), fg="white", bg=PANEL),
                tk.Label(row, text=f"{it['size']}명", anchor="e", font=("Malgun Gothic", 16), fg=MUTED, bg=PANEL),
            ]
            labs[0].pack(side="left")
            labs[1].pack(side="left", fill="x", expand=True)
            labs[2].pack(side="right")
            for w in [row] + labs:
                w.bind("<Button-1>", lambda e, i=it["id"], nm=mask(it["name"]): self.remove(i, nm))
        rest = n - 1 - len(show)
        self.more.configure(text="다음 대기가 없습니다" if n <= 1 else (f"외 {rest}팀 대기 중" if rest > 0 else ""))
        self.count.configure(text=f"대기 {n}팀 · {snap['totalPeople']}명")

        url, how = self.join_url()
        self.hint.configure(text=how)
        if url != self.url_var.get():
            self.url_var.set(url)
            self.draw_qr()
        if not once:
            self.root.after(1500, self.refresh)


def main():
    global ACTUAL_PORT
    try:
        sock, ACTUAL_PORT = make_listener(PORT)
    except OSError as e:
        sys.exit(f"서버를 시작하지 못했습니다: {e}")
    threading.Thread(target=accept_loop, args=(sock,), daemon=True).start()
    start_tunnel(ACTUAL_PORT)
    print(f"등록 서버 실행 중: 포트 {ACTUAL_PORT}  (손님 등록 주소: http://{local_ips()[0]}:{ACTUAL_PORT}/join)")
    root = tk.Tk()
    App(root, ACTUAL_PORT)
    root.mainloop()


if __name__ == "__main__":
    main()
