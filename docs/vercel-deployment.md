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
7. Set `ALLOWED_ORIGINS` to the exact storefront origin and `FRONTEND_URL` to
   its URL (Stripe sends customers back there). Keep SMTP keys unset. For Stripe,
   see "Payments (Stripe test mode)" below.
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

## Payments (Stripe test mode)

Without `STRIPE_SECRET_KEY` the storefront shows the demo checkout. To take
test payments:

1. Apply migrations first (`0003_stripe_checkout` and
   `0004_production_hardening` add the columns and tables the new code reads). Use the manual **database migrations** workflow in GitHub
   Actions with the `PROD_DATABASE_URL` repository secret, or run
   `alembic upgrade head` from a trusted machine.
2. In the Stripe dashboard (test mode), copy the **secret key** (`sk_test_...`).
3. Add a webhook endpoint: `https://<api-host>/api/v1/payments/webhook`, events
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `checkout.session.async_payment_failed`, `checkout.session.expired`,
   `charge.refunded`, `charge.dispute.created`, `charge.dispute.updated`,
   `charge.dispute.closed`. Copy its **signing secret** (`whsec_...`).
4. Set on the API project: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
   (both as sensitive), and optionally `STRIPE_CURRENCY` (default `usd`).
   Redeploy the API.
5. Verify: buy something with card `4242 4242 4242 4242`; the order page should
   show **Paid**, and the webhook's delivery log in Stripe should show `200`.

Never use live keys for this portfolio demo.

## Payment safety net (free)

`.github/workflows/payments-maintenance.yml` runs on GitHub Actions (free for a
public repository):

- **Hourly:** retries webhook events that failed to process, and resolves orders
  stuck in Pending because a webhook never arrived (asks Stripe directly).
- **Daily:** reconciles the last 48 hours of Stripe payments against the
  database. The run fails (and GitHub emails you) if anything needs a person:
  money taken with no order, or an order marked paid that Stripe doesn't know.

It needs two repository secrets: `PROD_DATABASE_URL` (already used by the
migrations workflow) and `STRIPE_SECRET_KEY` (the same `sk_test_...` key). Until
both exist, runs skip without failing. The job refuses anything except a
`sk_test_` key. It runs hourly rather than more often so Neon's free compute
can stay asleep between runs.

## Scaling settings (all optional)

| Variable | Default | When to change |
| --- | --- | --- |
| `RATE_LIMIT_BACKEND` | `memory` | Set `database` on Vercel: serverless instances don't share memory, so only a database counter limits requests correctly. Costs one small write per request on the existing Neon database. |
| `DB_POOL_DISABLED` | `false` | Keep `true` on Vercel (see above). |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 5 / 5 | Long-running servers only. Keep replicas × (size + overflow) under the database's connection limit. |
| `DB_POOL_TIMEOUT_SECONDS` | 5 | How long a request waits for a free connection before getting a 503 "server busy". |
| `DB_COMMAND_TIMEOUT_SECONDS` | 15 | Longest a single query may run. |
| `STRIPE_TIMEOUT_SECONDS` | 10 | Longest a single Stripe call may take before it counts as a failure. |

Product list and product pages send `Cache-Control: s-maxage=30`, so Vercel's
edge cache answers repeat browsing without running the function or waking the
database. That keeps usage inside the free plan for longer.
