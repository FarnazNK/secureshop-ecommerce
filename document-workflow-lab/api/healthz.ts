import type { IncomingMessage, ServerResponse } from 'node:http';
import { pool } from '../src/server/db.js';
export default async function handler(_req: IncomingMessage, res: ServerResponse) {
  try {
    await pool.query('SELECT 1');
    res.writeHead(200, {'content-type':'application/json','cache-control':'no-store'});
    res.end(JSON.stringify({ status:'ok', database:'connected' }));
  } catch {
    res.writeHead(503, {'content-type':'application/json','cache-control':'no-store'});
    res.end(JSON.stringify({ status:'unavailable' }));
  }
}
