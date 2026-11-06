'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const QRCode = require('qrcode');
const { WaitingQueue } = require('./queue');

const PORT = process.env.PORT || 3000;
const PUBLIC_URL = process.env.PUBLIC_URL; // 예: https://my-queue.example.com (QR에 들어갈 주소)
const queue = new WaitingQueue(path.join(__dirname, 'data.json'));
const PUB = path.join(__dirname, 'public');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };

const json = (res, code, body) => {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(body));
};
const readBody = (req) => new Promise((resolve, reject) => {
  let s = '';
  req.on('data', (c) => { s += c; if (s.length > 10000) req.destroy(); });
  req.on('end', () => { try { resolve(s ? JSON.parse(s) : {}); } catch (e) { reject(e); } });
});
const baseUrl = (req) => PUBLIC_URL || `http://${req.headers.host}`;

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  try {
    if (p === '/api/queue' && req.method === 'GET') return json(res, 200, queue.snapshot());
    if (p === '/api/join' && req.method === 'POST') {
      const b = await readBody(req);
      try { return json(res, 200, queue.add(b.name, b.size)); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if (p === '/api/status' && req.method === 'GET') return json(res, 200, queue.status(Number(url.searchParams.get('id'))));
    if (p === '/api/complete' && req.method === 'POST') return json(res, 200, { done: queue.complete() });
    if (p === '/api/remove' && req.method === 'POST') {
      const b = await readBody(req);
      return json(res, 200, { ok: queue.remove(Number(b.id)) });
    }
    if (p === '/qr.svg') {
      const svg = await QRCode.toString(`${baseUrl(req)}/join`, { type: 'svg', margin: 1 });
      res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
      return res.end(svg);
    }
    if (p === '/api/info') return json(res, 200, { joinUrl: `${baseUrl(req)}/join` });

    const page = { '/': 'admin.html', '/admin': 'admin.html', '/join': 'join.html' }[p];
    if (page) {
      res.writeHead(200, { 'Content-Type': TYPES['.html'] });
      return res.end(fs.readFileSync(path.join(PUB, page)));
    }
    res.writeHead(404); res.end('Not found');
  } catch (e) {
    json(res, 500, { error: '서버 오류' });
  }
});

if (require.main === module) {
  server.listen(PORT, () => console.log(`대기표 서버 실행: http://localhost:${PORT}  (관리 화면 /, 손님 등록 /join)`));
}
module.exports = { server };
