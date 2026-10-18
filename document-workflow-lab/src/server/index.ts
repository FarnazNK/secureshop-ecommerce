import 'dotenv/config';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { nodeHTTPRequestHandler } from '@trpc/server/adapters/node-http';
import { appRouter } from './router.js';
import { pool } from './db.js';

const port = Number(process.env.PORT ?? 3001);
const dist = resolve(process.cwd(), 'dist');
const mime: Record<string,string> = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

async function initialize() {
  if (!process.env.DATABASE_URL && process.env.NODE_ENV === 'production') throw new Error('DATABASE_URL must be configured');
  const schema = await readFile(resolve(process.cwd(), 'sql/001_init.sql'), 'utf8');
  await pool.query(schema);
}
async function serveStatic(pathname: string, res: import('node:http').ServerResponse) {
  const requested = pathname === '/' ? '/index.html' : pathname;
  const file = resolve(dist, '.' + decodeURIComponent(requested));
  if (file !== dist && !file.startsWith(dist + sep)) { res.writeHead(403); res.end(); return; }
  try {
    if (!(await stat(file)).isFile()) throw new Error('Not a file');
    const data = await readFile(file);
    res.writeHead(200, { 'content-type': mime[extname(file)] ?? 'application/octet-stream', 'x-content-type-options': 'nosniff' });
    res.end(data);
  } catch {
    if (pathname.startsWith('/assets/') || pathname.includes('.')) { res.writeHead(404); res.end('Not found'); return; }
    const page = await readFile(resolve(dist, 'index.html'));
    res.writeHead(200, { 'content-type':'text/html; charset=utf-8' }); res.end(page);
  }
}
await initialize();
createServer((req, res) => {
  const pathname = new URL(req.url ?? '/', 'http://localhost').pathname;
  if (pathname === '/healthz') {
    void pool.query('SELECT 1').then(() => { res.writeHead(200, {'content-type':'application/json'}); res.end('{"status":"ok","database":"connected"}'); }).catch(() => {res.writeHead(503); res.end('{"status":"unavailable"}');});
    return;
  }
  if (pathname.startsWith('/trpc/')) {
    void nodeHTTPRequestHandler({ req, res, router: appRouter, path: pathname.slice('/trpc/'.length), createContext: () => ({}) }); return;
  }
  void serveStatic(pathname,res).catch(() => {res.writeHead(500);res.end('Internal error');});
}).listen(port, '0.0.0.0', () => console.log(`Web app and API listening on port ${port}`));
