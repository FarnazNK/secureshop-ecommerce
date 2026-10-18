# Document Workflow Lab

An original full-stack document review workspace demonstrating a React / TypeScript client, tRPC endpoints, Effect services, and PostgreSQL persistence. Independent portfolio sample, not affiliated with any company.

## Features
- Create and track work items with open / review / complete status
- Attach and review text-based documents
- Atomic audit events for writes using PostgreSQL transactions
- Zod-validated tRPC endpoints and Effect-typed service failures

## Run locally

Requires Node.js 22+, Docker with Compose.

```bash
cd document-workflow-lab
cp .env.example .env
npm install
docker compose up -d
npm run dev
```

Open http://localhost:5173 (API on http://localhost:3001).

## Verify

```bash
npm run build
npm test
```

Architecture: React → tRPC + Zod → Effect service → pg repository → PostgreSQL.

This is a demonstration and is **not production-ready**. There is no authentication or tenant isolation, no file uploads, and no live LLM integration. Use only synthetic data. Add security controls and integration tests before any production use. Dependencies and build have not been verified in this environment.
