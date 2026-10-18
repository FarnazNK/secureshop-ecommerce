# Deployment

## Vercel frontend and API

Use the `document-workflow-lab` root directory in a Vercel project connected to the repository. Framework: Vite. Deploys use `vercel.json` and `api/` serverless routes.

Provision a PostgreSQL database and run `sql/001_init.sql` before deployment. Add `DATABASE_URL` to Vercel's environment variables (never commit credentials). Confirm `/api/healthz` returns 200, then exercise create/list/status/document operations in the browser. The `/healthz` alias is also configured.

A Vercel deployment is **not** automatically created by committing these files; a project must be linked to the GitHub repository, with its root directory set.

## Docker runtime

```bash
cd document-workflow-lab
cp .env.example .env
docker compose up -d
docker build -t atlas-review .
docker run --rm -p 3001:3001 --env-file .env atlas-review
```

Open http://localhost:3001. This sample uses a localhost database URL, which must be adjusted for container-to-container networking.

## CI

`Atlas Review CI` runs the TypeScript/Vite build, tests, and Docker image build whenever this folder changes.

## Smoke test

1. Check `/healthz` or `/api/healthz`.
2. Create a work item.
3. Change its state.
4. Add a short synthetic text document.
5. Refresh and confirm persistence.
6. Verify database audit events were written.

Do not store sensitive documents: authentication and tenant isolation are not implemented.
