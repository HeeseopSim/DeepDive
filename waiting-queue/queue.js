'use strict';
const fs = require('fs');

// 대기열 로직 (저장소 포함). 순번은 계속 증가하고, 맨 위(0번)가 현재 차례.
class WaitingQueue {
  constructor(file) {
    this.file = file || null;
    this.items = [];
    this.nextNumber = 1;
    this.lastCalled = null;
    this._load();
  }
  _load() {
    if (!this.file || !fs.existsSync(this.file)) return;
    try {
      const d = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      this.items = d.items || [];
      this.nextNumber = d.nextNumber || 1;
      this.lastCalled = d.lastCalled || null;
    } catch (_) { /* 손상된 파일은 무시 */ }
  }
  _save() {
    if (!this.file) return;
    fs.writeFileSync(this.file, JSON.stringify({
      items: this.items, nextNumber: this.nextNumber, lastCalled: this.lastCalled,
    }));
  }
  add(name, size) {
    name = String(name || '').trim().slice(0, 30);
    size = Math.floor(Number(size));
    if (!name) throw new Error('이름을 입력해주세요');
    if (!(size >= 1 && size <= 99)) throw new Error('인원은 1~99명이어야 합니다');
    const item = { id: this.nextNumber++, name, size, createdAt: Date.now() };
    this.items.push(item);
    this._save();
    return item;
  }
  // K키: 맨 위 사람 완료 → 삭제, 다음 사람이 맨 위로
  complete() {
    const done = this.items.shift() || null;
    if (done) this.lastCalled = done.id;
    this._save();
    return done;
  }
  remove(id) {
    const i = this.items.findIndex((x) => x.id === id);
    if (i < 0) return false;
    this.items.splice(i, 1);
    this._save();
    return true;
  }
  // 대기번호 id 의 현재 상태 (앞에 몇 팀 / 몇 명 남았는지)
  status(id) {
    const i = this.items.findIndex((x) => x.id === id);
    if (i < 0) return { waiting: false, lastCalled: this.lastCalled };
    return {
      waiting: true,
      position: i + 1,
      teamsAhead: i,
      peopleAhead: this.items.slice(0, i).reduce((s, x) => s + x.size, 0),
      item: this.items[i],
      lastCalled: this.lastCalled,
    };
  }
  snapshot() {
    return {
      items: this.items,
      totalPeople: this.items.reduce((s, x) => s + x.size, 0),
      lastCalled: this.lastCalled,
    };
  }
}
module.exports = { WaitingQueue };
