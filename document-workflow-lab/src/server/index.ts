import 'dotenv/config';
import { createServer } from 'node:http';
import { nodeHTTPRequestHandler } from '@trpc/server/adapters/node-http';
import { appRouter } from './router.js';
const port = Number(process.env.PORT ?? 3001);
createServer((req, res) => {
  if (!req.url?.startsWith('/trpc/')) {
    res.writeHead(404, { 'content-type': 'application/json' }); res.end(JSON.stringify({ error: 'Not found' })); return;
  }
  void nodeHTTPRequestHandler({ req, res, router: appRouter, path: req.url.split('?')[0].slice('/trpc/'.length), createContext: () => ({}) });
}).listen(port, () => console.log(`API listening on http://localhost:${port}`));
