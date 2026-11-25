# Load test (k6, free, local only)

[k6](https://k6.io) is free and open source. The test runs on your own computer against a local API and a local PostgreSQL. **Never point it at the hosted demo**: it would burn through the free Vercel and Neon allowances, and `seed.py` refuses any non-local database.

## What it checks

`k6/shop.js` runs three scenarios at once for 2.5 minutes:

| Scenario | Load | What must hold |
| --- | --- | --- |
| browse | 150 iterations/s, each a product list + a product page | p95 under 500 ms |
| checkout | ramps to 40 shoppers adding to cart and placing orders; 1 in 5 retries with the same `Idempotency-Key` | p95 under 1.5 s; every retry returns the **same** order |
| flash_sale | starts at 60 s: 200 shoppers race for a product with **50** units | exactly 50 orders succeed, the rest get 409 "sold out", stock ends at **0** |

Plus fewer than 1% unexpected errors overall (409 "sold out" is an expected answer). Stripe is off in the test, so no Stripe calls are made; the payment path is covered by the unit tests.

## Run it

You need Python, PostgreSQL 16 and [k6](https://grafana.com/docs/k6/latest/set-up/install-k6/).

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/shop   # local only
alembic upgrade head
python ../load/seed.py > ../load/results/seed.json

# High limits so 300 test users from one IP aren't rate limited; cheaper
# bcrypt so the 300 sign-ups in setup take seconds instead of a minute.
export RATE_LIMIT_BACKEND=database RATE_LIMIT_MAX_REQUESTS=1000000 \
       AUTH_RATE_LIMIT_MAX_REQUESTS=1000000 BCRYPT_COST=10 LOG_LEVEL=WARNING
uvicorn app.main:app --host 127.0.0.1 --port 3001 --workers 2 --no-access-log &

cd ../load/k6
k6 run shop.js                                  # full load
BROWSE_RPS=60 CHECKOUT_VUS=20 k6 run shop.js    # the "sustained" profile below
```

Re-run `seed.py` before each run: it resets the limited product to 50 units.

## Results (24 Nov 2026)

Machine: one 2-vCPU Intel Xeon 2.1 GHz VM with 7 GB RAM, running k6, the API **and** PostgreSQL together, so all three compete for the same 2 CPUs. A real deployment gives the API its own CPUs; treat these numbers as a floor.

| Run | Setup | Throughput | Unexpected errors | Browse p95 | Order p95 | Flash sale (50 units) | Idempotent retries |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 1 process, shared DB rate limiter, before the fixes below | 111 req/s | 0.19% | 1.69 s | 2.11 s | 50 sold, stock 0 | 546, all matched |
| B | 1 process, shared DB rate limiter | 114 req/s | 0.04% | 1.65 s | 1.95 s | 50 sold, stock 0 | 548, all matched |
| C | 1 process, in-memory rate limiter | 132 req/s | 0.13% | 1.76 s | 2.03 s | 50 sold, stock 0 | 630, all matched |
| D | 2 processes, shared DB rate limiter | 182 req/s | **0%** | 1.02 s | 1.27 s | 50 sold, stock 0 | 815, all matched |
| E | 2 processes, sustained profile (60/s browse, 20 shoppers) | 182 req/s | **0%** | **407 ms** | **488 ms** | 50 sold, stock 0 | 1,046, all matched |

Raw k6 output for B to E is in `results/` (`run-*.txt` is the console summary, `run-*.json` the full metrics). Run E passes every threshold.

### What the numbers say

- **Correctness held at every load level.** In all five runs, 200 buyers competing for 50 units produced exactly 50 orders and stock of exactly 0, and every one of about 3,600 same-key retries returned the original order. Overload made things slow, never wrong.
- **Runs A to D ask for more than this machine can do.** k6 dropped 12,000 to 16,000 planned browse iterations because responses were slow; that's the latency thresholds failing as they should. Capacity here is about 180 requests/s with two processes.
- **Adding a process added ~60% throughput** (114 → 182 req/s) with the rate limit still shared correctly. This is what the Kubernetes autoscaler (`k8s/scaling.yaml`) does by adding pods.
- **The shared rate limiter costs ~14%** (132 vs 114 req/s on one process), because every request does one extra small database write. Use `memory` when there's only one server; use `database` when there are several (serverless or several pods), where a per-process limit would be wrong.

### Fixes made because of run A

1. **Pool exhaustion returned 500.** In run A, 147 requests waited more than 5 s for a free database connection and failed with a 500 error. They now get **503 with `Retry-After: 2`** (load shedding), and a `secureshop_db_pool_exhausted_total` metric counts them.
2. **The rate limiter waits on the same connection pool as the request.** When it can't get a connection within 1 s it stops waiting, counted in `secureshop_rate_limit_backend_errors_total`: 1,214 times in run B, 406 in run D and 170 (0.6% of requests) in run E. Ordinary requests are then let through (fail-open) so an overload doesn't lock shoppers out. **Login, sign-up and token refresh now fail closed** (429, retry in 5 s), so an overload can't switch off brute-force protection; those requests need the database anyway. With two processes (runs D and E) no request hit the 503 pool limit.
3. **Catalogue reads are now CDN-cacheable.** Product list and product pages send `Cache-Control: public, s-maxage=30, stale-while-revalidate=60`. On Vercel the edge cache (included in the free plan) can then answer repeated browsing without running the API or waking the database at all. The local test has no CDN, so the numbers above don't include that benefit. A cached page may show stock up to a minute old, but ordering always re-checks stock atomically, so it can't oversell.
4. **Index for the storefront listing:** `ix_product_active_created (is_active, created_at)` serves `WHERE is_active ORDER BY created_at DESC LIMIT 20` directly.

A few connections were reset by the server when 200 flash-sale shoppers connected in the same instant to an already-saturated single process (9 in run A, 1 in run B). With two processes there were none.
