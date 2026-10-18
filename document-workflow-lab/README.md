# Atlas Review

A document operations application built with React, TypeScript, tRPC, Effect and PostgreSQL.

## Features

- Create and list review work items.
- Move items between open, review and complete statuses.
- Create and review text documents.
- Store records in PostgreSQL and write audit events transactionally.
- Validate API input with Zod and handle service failures with Effect.
- Serve the web interface and API through one Node.js service.
- Check database availability with `/healthz`.

## Architecture

React client → tRPC API → Effect service → PostgreSQL.

## Local development

Requires Node.js 22+, npm and Docker Compose.

```sh
cp .env.example .env
npm install
docker compose up -d
npm run dev
```

Open http://localhost:5173.

## Production deployment

```sh
npm run build
npm start
```

Configure `DATABASE_URL` and `PORT`. The Node.js server hosts both the built UI and API. The database schema initializes on startup.

For Render, set root directory to `document-workflow-lab`, build command to `npm install && npm run build`, and start command to `npm start`.

## Current scope

Supports text-only documents. Authentication, user permissions, OCR, uploads and AI processing are not yet implemented. Use synthetic data only. Build, tests and hosted deployment still need validation.
