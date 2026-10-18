import pg from 'pg';
import { randomUUID } from 'node:crypto';
const { Pool } = pg;
export const pool = new Pool({ connectionString: process.env.DATABASE_URL ?? 'postgres://app:app@localhost:5432/workflow' });
export type CaseRecord = { id: string; title: string; status: 'open' | 'review' | 'complete'; created_at: Date };
export type DocumentRecord = { id: string; case_id: string; filename: string; body: string; created_at: Date };
export const repository = {
  listCases: async (): Promise<CaseRecord[]> => (await pool.query<CaseRecord>('SELECT * FROM cases ORDER BY created_at DESC')).rows,
  createCase: async (title: string): Promise<CaseRecord> => {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const row = (await client.query<CaseRecord>('INSERT INTO cases (id, title) VALUES ($1, $2) RETURNING *', [randomUUID(), title])).rows[0];
      await client.query('INSERT INTO audit_events (case_id, action) VALUES ($1, $2)', [row.id, 'case.created']);
      await client.query('COMMIT'); return row;
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  },
  getCase: async (id: string): Promise<CaseRecord | undefined> => (await pool.query<CaseRecord>('SELECT * FROM cases WHERE id=$1', [id])).rows[0],
  listDocuments: async (caseId: string): Promise<DocumentRecord[]> => (await pool.query<DocumentRecord>('SELECT * FROM documents WHERE case_id=$1 ORDER BY created_at DESC', [caseId])).rows,
  addDocument: async (caseId: string, filename: string, body: string): Promise<DocumentRecord> => {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const doc = (await client.query<DocumentRecord>('INSERT INTO documents (id, case_id, filename, body) VALUES ($1,$2,$3,$4) RETURNING *', [randomUUID(), caseId, filename, body])).rows[0];
      await client.query('UPDATE cases SET status=$1 WHERE id=$2', ['review', caseId]);
      await client.query('INSERT INTO audit_events (case_id, action) VALUES ($1,$2)', [caseId, 'document.added']);
      await client.query('COMMIT'); return doc;
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  },
  setStatus: async (caseId: string, status: CaseRecord['status']): Promise<CaseRecord | undefined> => {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const row = (await client.query<CaseRecord>('UPDATE cases SET status=$1 WHERE id=$2 RETURNING *', [status, caseId])).rows[0];
      if (row) await client.query('INSERT INTO audit_events (case_id, action) VALUES ($1,$2)', [caseId, `case.status.${status}`]);
      await client.query('COMMIT'); return row;
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  }
};
