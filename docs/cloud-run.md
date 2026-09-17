# SecureShop API on Google Cloud Run

The React storefront can remain on its current static host while the FastAPI
backend moves from Render to Cloud Run. The existing PostgreSQL database and
Redis-compatible service can remain external.

## Cloud Run compatibility changes

The backend now:

- listens on Cloud Run's injected `PORT`;
- allows `*.run.app` through TrustedHostMiddleware;
- makes production Swagger/OpenAPI opt-in through `ENABLE_DOCS=true`;
- keeps production docs disabled by default for non-portfolio deployments.

## One-time Google Cloud setup

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Deploy the backend from the repository root:

```bash
gcloud run deploy secureshop-api \
  --source ./backend \
  --region northamerica-northeast2 \
  --allow-unauthenticated
```

## Required runtime configuration

SecureShop intentionally fails fast when required secrets are missing. Configure:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_ACCESS_SECRET`
- `JWT_REFRESH_SECRET`
- `ENCRYPTION_KEY`
- `NODE_ENV=production`
- `ENABLE_DOCS=true` for the public portfolio API
- `ALLOWED_ORIGINS` with the public storefront origin
- `ALLOWED_HOSTS=*.run.app` or a stricter list including the generated Cloud Run host
- `FRONTEND_URL` with the public storefront URL

Optional Stripe and SMTP settings can stay unset for the portfolio demo.

Prefer Google Secret Manager for database credentials and signing/encryption
secrets.

Example non-secret settings:

```bash
gcloud run services update secureshop-api \
  --region northamerica-northeast2 \
  --update-env-vars NODE_ENV=production,ENABLE_DOCS=true,ALLOWED_HOSTS=*.run.app
```

## Database migrations

Run Alembic against the same production PostgreSQL database before switching the
frontend:

```bash
cd backend
export DATABASE_URL='YOUR_DATABASE_URL'
alembic upgrade head
```

## GitHub Actions deployment

The repository includes `.github/workflows/deploy-cloud-run.yml` and expects:

- `GCP_PROJECT_ID`
- `GCP_REGION` (optional; defaults to `northamerica-northeast2`)
- `GCP_WIF_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

After the Cloud Run service has its runtime variables/secrets, run **Deploy
SecureShop API to Cloud Run** from GitHub Actions.

## Resume links

With `ENABLE_DOCS=true`, the useful public links are:

- `/api/docs`
- `/api/v1/health`
- `/api/v1/products`

Update the README and resume only after the Cloud Run URL is live and verified.
