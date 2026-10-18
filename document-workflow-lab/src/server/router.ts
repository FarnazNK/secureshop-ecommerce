import { initTRPC, TRPCError } from '@trpc/server';
import { Effect } from 'effect';
import { z } from 'zod';
import { service } from './service.js';
const t = initTRPC.create();
const execute = async <T>(program: Effect.Effect<T, { _tag: string }>): Promise<T> => {
  const result = await Effect.runPromise(Effect.either(program));
  if (result._tag === 'Right') return result.right;
  if (result.left._tag === 'MissingCase') throw new TRPCError({ code: 'NOT_FOUND', message: 'Case not found' });
  throw new TRPCError({ code: 'INTERNAL_SERVER_ERROR', message: 'Storage operation failed' });
};
const id = z.uuid();
export const appRouter = t.router({
  listCases: t.procedure.query(() => execute(service.listCases())),
  createCase: t.procedure.input(z.object({ title: z.string().trim().min(1).max(120) })).mutation(({ input }) => execute(service.createCase(input.title))),
  getCase: t.procedure.input(z.object({ id })).query(({ input }) => execute(service.getCase(input.id))),
  listDocuments: t.procedure.input(z.object({ caseId: id })).query(({ input }) => execute(service.listDocuments(input.caseId))),
  addDocument: t.procedure.input(z.object({ caseId: id, filename: z.string().trim().min(1).max(120), body: z.string().trim().min(1).max(20000) })).mutation(({ input }) => execute(service.addDocument(input.caseId, input.filename, input.body))),
  setStatus: t.procedure.input(z.object({ caseId: id, status: z.enum(['open','review','complete']) })).mutation(({ input }) => execute(service.setStatus(input.caseId, input.status)))
});
export type AppRouter = typeof appRouter;
