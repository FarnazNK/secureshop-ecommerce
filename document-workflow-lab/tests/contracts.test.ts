import { describe, it, expect } from 'vitest';
import { appRouter } from '../src/server/router.js';
describe('public API shape', () => {
  it('exposes expected typed procedures', () => {
    for (const name of ['listCases','createCase','getCase','listDocuments','addDocument','setStatus']) {
      expect(appRouter._def.procedures).toHaveProperty(name);
    }
  });
});
