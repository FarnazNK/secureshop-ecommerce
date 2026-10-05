# Free portfolio API deployment on Vercel

Use Vercel Hobby for this personal, synthetic portfolio demo only. Hobby is free
within quotas and is restricted to non-commercial personal use.

## Project setup
1. Import this repository; choose Root Directory `backend`, Framework Preset
   FastAPI, and no frontend build command.
2. Keep `NODE_ENV=production`.
3. Set `ALLOWED_HOSTS` to the exact Vercel production hostname (no scheme/path).
   Add exact custom hostnames if needed. Do not use `*`.
4. Reuse Neon **Free** PostgreSQL via its pooled URL, set `DATABASE_SSL=true`,
   and `DB_POOL_DISABLED=true`. The latter uses NullPool so async connections
   are not held across serverless event-loop lifetimes.
5. Copy your existing distinct `JWT_ACCESS_SECRET`, `JWT_REFRESH_SECRET`,
   and `ENCRYPTION_KEY` securely into Vercel environment variables.
6. `REDIS_URL` remains a required setting. The current rate limiter is
   process-local and does not connect to Redis; a syntactically valid local URL
   (`redis://localhost:6379`) is sufficient for this existing portfolio code.
   Do not provision a paid Redis service.
7. Set `ALLOWED_ORIGINS` to the exact storefront origin,
   `FRONTEND_URL` to its URL, and keep Stripe and SMTP keys unset.
8. Apply Alembic migrations from a trusted local environment before verification;
   do not run migrations on every request or against production in PR builds.

## Backend link that renders correctly
Use the actual deployed origin plus **`/api/reference`** in the resume.
This new page renders a readable route table rather than raw product JSON.
It uses no JavaScript, makes no authenticated requests, and displays no database
records. Production Swagger and OpenAPI endpoints remain disabled.

## Frontend and validation
Deploy the storefront separately as a free static Vercel Hobby project with
Root Directory `frontend`, build command `npm run build`, and output `dist`.
Set `VITE_API_URL` to the verified API origin plus `/api/v1` before building.
For a SPA, configure its navigation fallback to index.html.
Test login/refresh cookies across the selected frontend/API origins before cutover;
do not weaken cookie or CORS settings blindly.

Check `/api/reference`, `/api/v1/health`, products, authentication, carts, and
orders using synthetic data. Per-process rate limits are not globally shared on
serverless hosts; this deployment is suitable for a bounded portfolio demo.
Only retire Render after the replacement passes these checks.
