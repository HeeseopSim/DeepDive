"""대기표 PC 서버 (TCP 소켓 통신 + 대기표 화면).  외부 모듈 없음 (tkinter 내장).
실행: python queue_board_pc.py
 - PC가 TCP 소켓 서버(기본 포트 9000)를 열고, 모바일 앱(Daegi-mobile.apk)이 "IP:포트"로 접속해 연동
 - 화면 위쪽의 노란 글씨 '서버 주소(IP:포트)'를 모바일 앱에 입력 (모바일 앱에 서로 연결용 QR이 표시됨)
 - K: 다음 손님 호출 · N: 수동 추가 · F11: 전체화면 · Esc: 해제 · 목록 항목 클릭: 삭제
 - 화면 아래에 모바일 접속/등록 로그가 표시됨
 - 환경변수: PORT (기본 9000)
통신 규약: 한 줄에 JSON 하나 (UTF-8, 줄바꿈 \\n 으로 끝남), 요청 1개당 응답 1줄.
  {"cmd":"hello"} / {"cmd":"board"} / {"cmd":"join","name":..,"size":..}
  {"cmd":"status","id":..} / {"cmd":"cancel","id":..,"token":..}
"""
import json
import os
import secrets
import socket
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 9000))
ACTUAL_PORT = PORT

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


queue = WaitingQueue(os.path.join(HERE, "data.json"))
EVENTS = []  # (시각, 내용) 최근 접속/등록 로그


def log_event(text):
    EVENTS.append((time.strftime("%H:%M:%S"), text))
    del EVENTS[:-50]


# ---------------- TCP 소켓 서버 (줄 단위 JSON) ----------------
def handle_msg(req, peer):
    cmd = req.get("cmd")
    if cmd == "hello":
        log_event(f"📱 {peer} 연결됨")
        return {"ok": True, "app": "waiting-queue", "ver": 1}
    if cmd == "board":
        snap = queue.snapshot()
        items = snap["items"]
        view = lambda x: {"id": x["id"], "name": x["name"], "size": x["size"]}
        return {"ok": True, "current": view(items[0]) if items else None,
                "next": [view(x) for x in items[1:6]], "more": max(0, len(items) - 6),
                "count": len(items), "people": snap["totalPeople"]}
    if cmd == "join":
        try:
            item = queue.add(req.get("name"), req.get("size"))
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        log_event(f"📱 {peer} 대기 등록: {item['id']}번 {item['name']} {item['size']}명")
        return {"ok": True, **item}
    if cmd == "status":
        try:
            id = int(req.get("id", 0))
        except (TypeError, ValueError):
            id = 0
        return {"ok": True, **queue.status(id)}
    if cmd == "cancel":
        try:
            id = int(req.get("id", 0))
        except (TypeError, ValueError):
            id = 0
        ok = queue.remove(id, token=req.get("token"), admin=False)
        if ok:
            log_event(f"📱 {peer} 대기 취소: {id}번")
        return {"ok": ok}
    return {"ok": False, "error": "알 수 없는 명령"}


def serve_conn(conn, addr):
    try:
        conn.settimeout(10)
        buf = b""
        while b"\n" not in buf:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 8192:
                return
        line = buf.split(b"\n", 1)[0].strip()
        if not line:
            return
        try:
            req = json.loads(line.decode("utf-8"))
            resp = handle_msg(req if isinstance(req, dict) else {}, addr[0])
        except ValueError:
            resp = {"ok": False, "error": "잘못된 요청"}
        except Exception as e:  # noqa: BLE001
            print("처리 오류:", repr(e))
            resp = {"ok": False, "error": "서버 오류"}
        conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
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
            conn, addr = sock.accept()
        except OSError:
            return
        threading.Thread(target=serve_conn, args=(conn, addr), daemon=True).start()


# ---------------- 이 PC의 접속 주소 ----------------
def local_ips():
    """모바일이 접속할 수 있는 이 PC의 IPv4 주소 후보들 (핫스팟/Wi-Fi/랜)."""
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


# ---------------- 화면 (tkinter): 대기표만 ----------------
import tkinter as tk
from tkinter import messagebox, simpledialog

BG, PANEL, GREEN, GRAY = "#0b1220", "#111b30", "#16a34a", "#1e293b"
TEXT, MUTED, BLUE = "#e2e8f0", "#94a3b8", "#60a5fa"
FONT = "Malgun Gothic"
MAX_ROWS = 8


class App:
    def __init__(self, root, port):
        self.root = root
        self.port = port
        self.ip_index = 0
        self.fullscreen = False
        root.title("대기표")
        root.configure(bg=BG)
        root.geometry("1280x720")
        root.minsize(900, 560)

        head = tk.Frame(root, bg=PANEL)
        head.pack(fill="x")
        tk.Label(head, text="🏥 대기 현황", font=(FONT, 20, "bold"), fg="white", bg=PANEL).pack(side="left", padx=16, pady=10)
        self.addr_btn = tk.Button(head, text="주소 변경", command=self.next_ip, relief="flat", bg=GRAY, fg=TEXT)
        self.addr_btn.pack(side="right", padx=12)
        self.addr = tk.Label(head, text="", font=("Consolas", 16, "bold"), fg="#fbbf24", bg=PANEL)
        self.addr.pack(side="right", padx=8)
        self.hint = tk.Label(head, text="모바일 앱 서버 주소 ▶", font=(FONT, 11), fg=MUTED, bg=PANEL)
        self.hint.pack(side="right", padx=4)

        bottom = tk.Frame(root, bg=PANEL)
        bottom.pack(side="bottom", fill="x")
        tk.Button(bottom, text="▶ 다음 손님 호출 (K)", command=self.complete, font=(FONT, 16, "bold"),
                  bg="white", fg="#0f172a", relief="flat").pack(side="left", padx=12, pady=10, ipadx=14, ipady=8)
        tk.Button(bottom, text="＋ 추가 (N)", command=self.add_dialog, font=(FONT, 13),
                  bg=GRAY, fg=TEXT, relief="flat").pack(side="left", padx=4, pady=10, ipadx=10, ipady=8)
        self.evt = tk.Label(bottom, text="모바일 접속 대기 중… (F11 전체화면 · 목록 항목 클릭: 삭제)", fg=MUTED, bg=PANEL,
                            font=(FONT, 11), anchor="e", justify="right")
        self.evt.pack(side="right", padx=14)

        main = tk.Frame(root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=12)
        main.columnconfigure(0, weight=2, uniform="c")
        main.columnconfigure(1, weight=3, uniform="c")
        main.rowconfigure(0, weight=1)

        # 왼쪽: 현재 호출
        self.now = tk.Frame(main, bg=GREEN)
        self.now.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        inner = tk.Frame(self.now, bg=GREEN)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        self.now_lab = tk.Label(inner, text="현재 호출", font=(FONT, 22), fg="white", bg=GREEN)
        self.now_lab.pack()
        self.now_num = tk.Label(inner, text="-", font=(FONT, 120, "bold"), fg="white", bg=GREEN)
        self.now_num.pack()
        self.now_who = tk.Label(inner, text="", font=(FONT, 34, "bold"), fg="white", bg=GREEN)
        self.now_who.pack()

        # 오른쪽: 다음 순서
        nxt = tk.Frame(main, bg=PANEL)
        nxt.grid(row=0, column=1, sticky="nsew")
        tk.Label(nxt, text="다음 순서", font=(FONT, 18), fg=MUTED, bg=PANEL).pack(anchor="w", padx=22, pady=(16, 6))
        self.list_box = tk.Frame(nxt, bg=PANEL)
        self.list_box.pack(fill="both", expand=True, padx=22)
        self.more = tk.Label(nxt, text="", font=(FONT, 15), fg=MUTED, bg=PANEL)
        self.more.pack(anchor="w", padx=22)
        self.count = tk.Label(nxt, text="", font=(FONT, 20, "bold"), fg=TEXT, bg=PANEL)
        self.count.pack(anchor="w", padx=22, pady=(4, 16))

        root.bind("<Key>", self.on_key)
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Escape>", lambda e: self.set_fullscreen(False))
        self.refresh()

    # --- 입력 ---
    def on_key(self, e):
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
        self.refresh(once=True)

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
    def server_addr(self):
        ips = local_ips()
        ip = ips[self.ip_index % len(ips)]
        return f"{ip}:{self.port}", len(ips)

    def refresh(self, once=False):
        snap = queue.snapshot()
        items = snap["items"]
        n = len(items)
        if n == 0:
            self.now.configure(bg=GRAY)
            self.now.winfo_children()[0].configure(bg=GRAY)
            self.now_lab.configure(text="", bg=GRAY)
            self.now_num.configure(text="대기 없음", bg=GRAY, font=(FONT, 48, "bold"))
            self.now_who.configure(text="", bg=GRAY)
        else:
            top = items[0]
            self.now.configure(bg=GREEN)
            self.now.winfo_children()[0].configure(bg=GREEN)
            self.now_lab.configure(text="현재 호출", bg=GREEN)
            self.now_num.configure(text=f"{top['id']}번", bg=GREEN, font=(FONT, 120, "bold"))
            self.now_who.configure(text=f"{top['name']} 님 · {top['size']}명", bg=GREEN)

        for w in self.list_box.winfo_children():
            w.destroy()
        show = items[1:1 + MAX_ROWS]
        for it in show:
            row = tk.Frame(self.list_box, bg=PANEL, cursor="hand2")
            row.pack(fill="x", pady=3)
            labs = [
                tk.Label(row, text=f"{it['id']}번", width=5, anchor="w", font=(FONT, 24, "bold"), fg=BLUE, bg=PANEL),
                tk.Label(row, text=it["name"], anchor="w", font=(FONT, 22), fg="white", bg=PANEL),
                tk.Label(row, text=f"{it['size']}명", anchor="e", font=(FONT, 20), fg=MUTED, bg=PANEL),
            ]
            labs[0].pack(side="left")
            labs[1].pack(side="left", fill="x", expand=True)
            labs[2].pack(side="right")
            for w in [row] + labs:
                w.bind("<Button-1>", lambda e, i=it["id"], nm=it["name"]: self.remove(i, nm))
        rest = n - 1 - len(show)
        self.more.configure(text="다음 대기가 없습니다" if n <= 1 else (f"외 {rest}팀 대기 중" if rest > 0 else ""))
        self.count.configure(text=f"대기 {n}팀 · {snap['totalPeople']}명")

        addr, total = self.server_addr()
        self.addr.configure(text="📡 " + addr)
        self.addr_btn.configure(text=f"주소 변경 ({self.ip_index % total + 1}/{total})")
        if EVENTS:
            t, x = EVENTS[-1]
            self.evt.configure(text=f"[{t}] {x}")
        if not once:
            self.root.after(1500, self.refresh)


def main():
    global ACTUAL_PORT
    try:
        sock, ACTUAL_PORT = make_listener(PORT)
    except OSError as e:
        sys.exit(f"서버를 시작하지 못했습니다: {e}")
    threading.Thread(target=accept_loop, args=(sock,), daemon=True).start()
    ips = local_ips()
    print(f"소켓 서버 실행 중: 모바일 앱에 입력할 주소 → {ips[0]}:{ACTUAL_PORT}  (다른 후보: {', '.join(ips[1:]) or '없음'})")
    root = tk.Tk()
    App(root, ACTUAL_PORT)
    root.mainloop()


if __name__ == "__main__":
    main()
