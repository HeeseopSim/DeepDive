const test = require('node:test');
const assert = require('node:assert');
const { WaitingQueue } = require('./queue');

test('K키(complete)는 맨 위를 삭제하고 다음 사람이 올라온다', () => {
  const q = new WaitingQueue();
  q.add('가', 2); q.add('나', 3); q.add('다', 1);
  assert.strictEqual(q.complete().name, '가');
  assert.strictEqual(q.items[0].name, '나');
  assert.deepStrictEqual(q.status(3), { ...q.status(3), position: 2, teamsAhead: 1, peopleAhead: 3 });
});
test('입력 검증', () => {
  const q = new WaitingQueue();
  assert.throws(() => q.add('', 1));
  assert.throws(() => q.add('a', 0));
  assert.strictEqual(new WaitingQueue().complete(), null);
});
