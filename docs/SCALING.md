# Scaling and failure handling

Everything here runs at **$0**. The hosted demo uses only free tiers (Vercel Hobby, Neon free, Stripe test mode, GitHub Actions on a public repository). Autoscaling, Prometheus, alerts and load tests run on your own computer. No other service is needed.

## What can go wrong, and what the code does

| Problem | What happens now | Where |
| --- | --- | --- |
| Two shoppers buy the last unit at the same moment | Stock is taken with one atomic `UPDATE product SET stock = stock - n WHERE id = … AND stock >= n`. Only one succeeds; the other gets `409`. Products are locked in id order so two carts can't deadlock. | `api/v1/orders.py` |
| The browser retries "Place order" after a timeout, or the shopper double-clicks | The request carries an `Idempotency-Key`. A unique `(user_id, idempotency_key)` constraint makes the retry return the first order, even when both requests arrive together. | `api/v1/orders.py`, `CheckoutPage.tsx` |
| Stripe is slow or down | Each Stripe call times out after 10 s (the SDK default is 80 s). After 5 failures in 60 s a circuit breaker opens, and checkout answers `503 Retry-After` immediately for 30 s, keeping the cart. One trial call then tests whether Stripe is back. Stripe *rejecting* a request (a bad card, say) doesn't count as an outage. | `core/circuit_breaker.py`, `services/payments.py` |
| A webhook fails halfway (database blip, deploy) | Every event is saved to `stripe_event` first, then processed. A failure is recorded on the row and the hourly job retries it, up to 10 times. A duplicate delivery is recognised by Stripe's event id. | `api/v1/payments.py`, `jobs/payments.py` |
| A webhook never arrives | The hourly job asks Stripe about every order still Pending after 36 minutes (Checkout sessions expire after 31) and applies the answer: paid, or cancelled with stock returned. | `jobs/payments.py` |
| Our records and Stripe's disagree | The daily job lists the last 48 hours of completed Stripe payments and fixes or reports: payments with no order, and orders marked paid that Stripe doesn't have. The run fails, so GitHub emails you. | `jobs/payments.py` |
| Refunds and chargebacks | `charge.refunded` records the refunded amount (partial or full). `charge.dispute.*` records the dispute status. Admins can refund through `POST /orders/{id}/refund`, with an idempotency key so a retry can't refund twice. | `services/payments.py`, `api/v1/orders.py` |
| More traffic than one process can serve | Run more processes or pods. The rate limit can be shared through the existing Postgres (`RATE_LIMIT_BACKEND=database`), and the local autoscaler runs 2 to 4 backend pods on CPU. | `core/rate_limit.py`, `k8s/scaling.yaml` |
| The database runs out of connections | Each process has a bounded pool (5 + 5 overflow by default). A request that can't get a connection within 5 s gets `503 Retry-After: 2` instead of hanging or failing with `500`. Queries are cut off after 15 s. | `db/session.py`, `main.py` |
| Many people browsing | Catalogue reads send `Cache-Control: s-maxage=30`, so Vercel's edge cache (part of the free plan) answers repeats without running the API or waking the database. Ordering always re-checks stock, so cached pages can't cause an oversell. | `api/v1/products.py` |

## Measured

The k6 test in [`load/`](../load/README.md) hits browsing, checkout with retries, and a 200-buyers-for-50-units flash sale at once. On a shared 2-vCPU machine running the load generator, the API and PostgreSQL together:

- **Correct every time:** exactly 50 of 200 flash-sale buyers succeeded and stock ended at 0 in all five runs; about 3,600 same-key retries all returned the original order.
- **Capacity:** about 115 requests/s with one process and 180 with two, with no errors with two processes. At 182 requests/s sustained, p95 was 407 ms for browsing and 488 ms for placing an order.
- **Cost of the shared rate limiter:** about 14% of throughput on one process.

## The free-tier ceiling

The code scales by adding instances: nothing in a request depends on memory in one process once `RATE_LIMIT_BACKEND=database` is set. What limits the hosted demo is the free plans' quotas (function invocations, database compute hours and connections, Actions minutes on a private repo). The design keeps inside them:

- Maintenance jobs run **hourly**, not every few minutes, so the database can sleep between runs.
- The database limiter is **opt-in**; memory is the default.
- Catalogue reads are edge-cached, so most browsing never reaches the database.
- Serverless uses no connection pool (`DB_POOL_DISABLED=true`); Neon's own pooler handles connections.

For bigger numbers, the same containers run on any Kubernetes cluster you already have: `k8s/local.yaml`, `k8s/scaling.yaml` and `k8s/monitoring.yaml` are the starting point.

## Watching it

Prometheus metrics at `/metrics`, scraped from every pod in the local Kubernetes add-on, with alert rules for the Stripe circuit, Stripe error rate, webhook failures and lag, API error rate and latency, rate-limiter errors and pods that are down. See [`k8s/MONITORING.md`](../k8s/MONITORING.md).

On the hosted demo, the signals are Vercel's runtime logs (structured JSON with a request id on every line) and the scheduled payment job, which fails visibly when something needs a person.

## Not included

- **Sales tax.** Orders carry tax as zero. Calculating it needs a tax service, which isn't free, so it's left out.
- **Distributed tracing.** Every log line and response carries an `X-Request-ID` to follow one request; there's no tracing backend.
- **A shared circuit breaker.** Each process keeps its own breaker state. With a few processes that's fine: each one opens after its own 5 failures.
