import { Effect, Data } from 'effect';
import { repository } from './db.js';
export class StorageError extends Data.TaggedError('StorageError')<{ cause: unknown }> {}
export class MissingCase extends Data.TaggedError('MissingCase')<{ id: string }> {}
const storage = <T>(operation: () => Promise<T>) => Effect.tryPromise({ try: operation, catch: cause => new StorageError({ cause }) });
export const service = {
  listCases: () => storage(() => repository.listCases()),
  createCase: (title: string) => storage(() => repository.createCase(title)),
  getCase: (id: string) => Effect.gen(function* () {
    const item = yield* storage(() => repository.getCase(id));
    if (!item) return yield* Effect.fail(new MissingCase({ id }));
    return item;
  }),
  listDocuments: (caseId: string) => Effect.gen(function* () {
    yield* service.getCase(caseId);
    return yield* storage(() => repository.listDocuments(caseId));
  }),
  addDocument: (caseId: string, filename: string, body: string) => Effect.gen(function* () {
    yield* service.getCase(caseId);
    return yield* storage(() => repository.addDocument(caseId, filename, body));
  }),
  setStatus: (caseId: string, status: 'open' | 'review' | 'complete') => Effect.gen(function* () {
    const updated = yield* storage(() => repository.setStatus(caseId, status));
    if (!updated) return yield* Effect.fail(new MissingCase({ id: caseId }));
    return updated;
  })
};
