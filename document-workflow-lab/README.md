# Atlas Review

**Full-stack document operations prototype** — an independent portfolio application, with no company affiliation.

React + TypeScript frontend, tRPC contracts, Effect service layer and PostgreSQL transactional persistence. A single Node.js process serves both the compiled frontend and the live API.

## Implemented

- Create and list review work items.
- Move items through open, review and complete states.
- Save and review text-only documents (no file uploads).
- Persist changes to PostgreSQL with transactional audit events.
- Validate API inputs using Zod and propagate typed Effect service errors.
- Expose `/healthz` for database readiness.

## Architecture

Browser → React/tRPC client → Node HTTP server → tRPC/Zod → Effect services → PostgreSQL transaction layer.

## Run locally

Requires Node.js 22+, npm, and Docker Compose.

```sh
cp .env.example .env
npm install
docker compose up -d
npm run dev
```

Open http://localhost:5173.

## Run as a unified deployment

```sh
npm run build
npm start
```

Open http://localhost:3001. In production, set `DATABASE_URL` and `PORT`. The service initializes the idempotent demo schema at startup.

For Render, use root directory `document-workflow-lab`, build command `npm install && npm run build`, start command `npm start`, and a managed PostgreSQL `DATABASE_URL` environment variable. The root deployment manifest is provided as reference.

## Limitations

**Prototype, not a production-ready system.** The demo has no authentication, user isolation, OCR, real AI integration, upload pipeline, or production security hardening. It must be used only with synthetic, nonsensitive documents. Do not present unimplemented features as existing. Build/tests and live public endpoint require verification.
