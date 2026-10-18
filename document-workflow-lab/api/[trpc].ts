import type { IncomingMessage, ServerResponse } from 'node:http';
import { nodeHTTPRequestHandler } from '@trpc/server/adapters/node-http';
import { appRouter } from '../src/server/router.js';

export default async function handler(req: IncomingMessage, res: ServerResponse) {
  if (!process.env.DATABASE_URL) {
    res.writeHead(503, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: 'Database not configured' }));
    return;
  }
  const path = new URL(req.url ?? '/', 'http://localhost').pathname;
  const procedure = path.split('/').filter(Boolean).pop();
  if (!procedure) { res.writeHead(404); res.end(); return; }
  await nodeHTTPRequestHandler({ req, res, router: appRouter, path: procedure, createContext: () => ({}) });
}
