"""대기열 로직 (저장 포함). 맨 앞(0번)이 현재 차례."""
import json
import os
import threading
import time


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
