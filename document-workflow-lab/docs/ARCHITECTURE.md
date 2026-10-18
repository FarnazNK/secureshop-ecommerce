# Architecture

## Request path

React + TypeScript → typed tRPC client → tRPC router (Zod input schemas) → Effect program → `pg` repository → PostgreSQL.

### Consistency
Case creation, status updates, and document insertion write an audit record in the **same transaction** as the domain change. A failure rolls back both the record change and its audit event.

### Reliability
A readiness endpoint checks the database, not merely the HTTP server. Effect distinguishes missing records from storage failures. APIs use parameterized SQL and bounded payload validation.

### Runtime choices
- Docker: one Node runtime serves the built React UI and tRPC endpoints.
- Vercel: Vite outputs static assets; separate serverless handlers serve `/trpc` and `/healthz`.
- Postgres is required for persistence. Initialize `sql/001_init.sql` before first use on Vercel. The Docker/Node runtime initializes the schema on startup.

### Security scope
No authentication or authorization is implemented. This is a synthetic-data prototype; do not expose confidential documents. Required before production: identity, tenant scoping, request limits, access logs with redaction, migration versioning and integration coverage.

### API surface
- `listCases` query
- `createCase` mutation
- `getCase` query
- `listDocuments` query
- `addDocument` mutation
- `setStatus` mutation

### Verification
`npm run build`, `npm test`, `docker compose up --build`, then exercise `/healthz` and all six procedures.
