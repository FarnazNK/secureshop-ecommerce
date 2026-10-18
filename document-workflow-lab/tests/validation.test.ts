import { describe, expect, it } from 'vitest';
import { z } from 'zod';
const documentInput = z.object({ filename: z.string().trim().min(1).max(120), body: z.string().trim().min(1).max(20000) });
describe('document input contract', () => {
  it('accepts a small text document', () => expect(documentInput.safeParse({ filename: 'notes.txt', body: 'Review this draft.' }).success).toBe(true));
  it('rejects empty content', () => expect(documentInput.safeParse({ filename: 'notes.txt', body: ' ' }).success).toBe(false));
  it('rejects oversized content', () => expect(documentInput.safeParse({ filename: 'notes.txt', body: 'a'.repeat(20001) }).success).toBe(false));
});
