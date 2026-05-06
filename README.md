# SecureShop — Secure E-Commerce Platform (FastAPI Edition)

[![ci](https://github.com/FarnazNK/secureshop-ecommerce/actions/workflows/ci.yml/badge.svg)](https://github.com/FarnazNK/secureshop-ecommerce/actions)
[![python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Security](https://img.shields.io/badge/Security-OWASP%20Top%2010-green)](https://owasp.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](#run-with-docker)

A production-style e-commerce platform with a Python/FastAPI backend, a
React/TypeScript frontend, and a security model aligned with the OWASP
Top 10. Built as a portfolio piece demonstrating end-to-end secure
full-stack patterns with a strong AI/Python backend stack.

> **Note:** This is a portfolio project. Schema, products, and demo data
> are synthetic.

---

## Stack

**Backend (Python)**
- FastAPI 0.115+ with async route handlers
- SQLAlchemy 2.0 async ORM over PostgreSQL (asyncpg driver)
- Alembic for schema migrations
- Redis for sessions and rate-limit counters
- Pydantic v2 for request/response validation
- python-jose + bcrypt for JWT and password hashing
- slowapi for rate limiting
- structlog for JSON-structured logging in production

**Frontend (TypeScript)**
- React 18 + Vite + TypeScript
- Tailwind CSS, React Router, React Query
- nginx in production (reverse-proxies `/api/*` to the backend)

**Infrastructure**
- PostgreSQL 16, Redis 7
- Multi-stage Dockerfiles for both services (non-root, healthchecks)
- docker-compose stack with persistent volumes
- GitHub Actions CI: lint, format check, tests against live Postgres/Redis,
  Docker build matrix

---

## Security features

Built around the OWASP Top 10 and standard defense-in-depth patterns:

**Authentication & authorization**
- JWT access + refresh tokens with **distinct signing secrets** per type
- Refresh tokens stored in **HTTP-only, SameSite cookies**
- **Refresh-token rotation with reuse detection** — presenting a revoked
  token invalidates every active session for that user
- bcrypt password hashing (cost 12, configurable)
- **Constant-time login response** — bcrypt is run even on missing users
  to prevent timing-based email enumeration
- Account lockout after configurable failed-attempt threshold
- Strict password policy (min length + char-class requirements)
- Role-based access control with declarative `require_role(...)` dependency

**API hardening**
- Custom security-headers middleware: CSP, HSTS in prod, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- CORS with explicit allowed origins (no `*` with credentials)
- Per-IP rate limiting via slowapi, tighter on auth endpoints
- TrustedHostMiddleware in production
- Pydantic v2 validation on every request body, query, and path param
- Centralized exception handler that never leaks stack traces to clients
- Per-request structured logging with request-ID propagation

**Data layer**
- Parameterized queries everywhere via SQLAlchemy
- Money modeled as `Numeric(10, 2)` — never `Float`
- Order items are price/name **snapshots** at order time so receipts stay
  accurate even if the catalog changes
- No card data ever touches the database — Stripe Elements handles PCI scope

---

## Quickstart

### Run with Docker

```bash
# 1. Copy env template and fill in real secrets
cp .env.example .env
# Generate each secret with: openssl rand -base64 48

# 2. Build and start the stack (postgres + redis + backend + frontend)
docker compose up --build

# 3. In another terminal, apply DB migrations once
docker compose run --rm migrate

# Access:
#   http://localhost:8080         — frontend (React SPA)
#   http://localhost:3001/api/docs — Swagger UI (dev only)
#   http://localhost:3001/api/v1/health — health check
```

Tear everything down (including DB volume):

```bash
docker compose down -v
```

### Run backend locally (without Docker)

```bash
cd backend
make dev          # install with dev extras
cp .env.example .env
# fill in DATABASE_URL, REDIS_URL, secrets

make migrate      # apply schema
make serve        # uvicorn --reload on :3001
make test         # 23 unit tests
make lint         # ruff check + format check
```

---

## API surface

OpenAPI / Swagger UI is auto-generated at `/api/docs` (dev only — disabled
in production builds).

| Method | Path | Auth | Description |
|---|---|---|---|
| GET    | `/api/v1/health`              | —     | Liveness + DB reachability |
| POST   | `/api/v1/auth/register`       | —     | Create account, set refresh cookie, return access token |
| POST   | `/api/v1/auth/login`          | —     | Exchange credentials for tokens |
| POST   | `/api/v1/auth/refresh`        | cookie | Rotate refresh token, mint new access token |
| POST   | `/api/v1/auth/logout`         | cookie | Revoke current refresh token |
| GET    | `/api/v1/auth/me`             | bearer | Current authenticated user |
| GET    | `/api/v1/products`            | —     | List products (filters, pagination) |
| GET    | `/api/v1/products/{id}`       | —     | Product detail |
| POST   | `/api/v1/products`            | admin | Create product |
| PATCH  | `/api/v1/products/{id}`       | admin | Update product |
| DELETE | `/api/v1/products/{id}`       | admin | Delete product |
| GET    | `/api/v1/cart`                | bearer | Current user's cart |
| POST   | `/api/v1/cart/items`          | bearer | Add to cart |
| PATCH  | `/api/v1/cart/items/{id}`     | bearer | Update item quantity |
| DELETE | `/api/v1/cart/items/{id}`     | bearer | Remove item |
| DELETE | `/api/v1/cart`                | bearer | Clear cart |
| POST   | `/api/v1/orders`              | bearer | Create order from cart, returns Stripe client secret |
| GET    | `/api/v1/orders`              | bearer | List user's orders |
| GET    | `/api/v1/orders/{id}`         | bearer | Order detail |

---

## Project structure

```
secureshop-fastapi/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # FastAPI dependencies (current_user, require_role)
│   │   │   └── v1/                  # Route handlers (thin)
│   │   │       ├── auth.py
│   │   │       ├── cart.py
│   │   │       ├── health.py
│   │   │       ├── orders.py
│   │   │       └── products.py
│   │   ├── core/
│   │   │   ├── config.py            # pydantic-settings, required-secret validation
│   │   │   ├── logging.py           # structlog setup (JSON in prod)
│   │   │   └── security.py          # bcrypt + JWT primitives
│   │   ├── db/
│   │   │   ├── base.py              # declarative Base, mixins
│   │   │   └── session.py           # async session, get_db dependency
│   │   ├── middleware/
│   │   │   ├── request_logging.py   # request-ID + structured access log
│   │   │   └── security_headers.py  # CSP, HSTS, X-Frame-Options, etc.
│   │   ├── models/                  # SQLAlchemy models (User, Product, Cart, Order, ...)
│   │   ├── schemas/                 # Pydantic request/response models
│   │   ├── services/
│   │   │   └── auth_service.py      # business logic — login, register, refresh rotation
│   │   └── main.py                  # FastAPI app factory
│   ├── alembic/                     # migrations
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py
│   ├── tests/                       # 23 unit tests (security, schemas, config)
│   ├── Dockerfile                   # multi-stage, non-root, tini, healthcheck
│   ├── Makefile                     # one-line entry points
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/                        # React 18 + Vite + TypeScript SPA
│   ├── src/
│   ├── Dockerfile                   # multi-stage Vite build → nginx
│   └── nginx.conf                   # SPA fallback + /api reverse-proxy
├── docker-compose.yml               # postgres + redis + backend + frontend + migrate
├── .github/workflows/ci.yml         # lint, tests against live PG/Redis, docker build
├── .env.example
└── README.md
```

---

## Design decisions worth pointing at

**Schemas separate from models.** Pydantic schemas (`app/schemas/`) define
the wire format; SQLAlchemy models (`app/models/`) define the database. The
two evolve independently — a column rename doesn't have to break API clients.

**Refresh-token reuse detection.** Every refresh token is persisted with a
JTI. When a token is rotated, the old row's `revoked_at` is set. If a
revoked token is ever presented again (a sign of theft), `_revoke_all_for_user`
fires and invalidates every active session for that user.

**Constant-time login.** `verify_password` is run against a fixed dummy
hash even when the user lookup misses. Without this, response timing
distinguishes "no such user" from "wrong password" and enables email
enumeration.

**Order item snapshots.** `OrderItem` copies `product_name`, `product_slug`,
and `unit_price` at order time. If a product is later renamed, repriced, or
deleted, historical receipts stay correct.

**Service layer.** Business logic lives in `app/services/`, not in route
handlers. The handlers translate HTTP into service calls; this keeps the
logic testable without spinning up an HTTP server.

**Required-secret validation at boot.** The `Settings` class declares JWT
and encryption secrets with `min_length=32` and no defaults. The app crashes
at startup if any are missing — better than booting and silently using
weak crypto.

---

## Testing

```bash
cd backend
make test
```

23 unit tests covering:
- Password hashing (round-trip, salt uniqueness, malformed-hash safety)
- JWT (round-trip, type isolation, JTI uniqueness, tampering rejection)
- Auth schema validation (password policy, email format, name trimming)
- Settings parsing (CORS list, env-driven mode toggles)

Tests run with no external dependencies — DB and Redis are not required
for the unit suite. The `backend` CI job runs the full suite against a
live Postgres + Redis pair via GitHub Actions services.

---

## Production considerations not handled

- **HTTPS termination** — production should sit behind a load balancer
  (ALB / nginx / Caddy) doing TLS termination and forwarding `X-Forwarded-*`.
  `proxy-headers` is already enabled in the uvicorn command.
- **Email delivery** — SMTP is wired in but not configured by default.
  Verification and password reset emails will no-op until SMTP env vars are set.
- **Stripe webhook handler** — payment intents are created server-side; the
  webhook that flips orders to `PAID` status would land in a follow-up PR.
- **Horizontal scaling** — current setup is single-process. For real prod,
  run multiple uvicorn workers and ensure Redis is highly available.
- **Secret management** — secrets come from env vars. Production should
  pull from a secret manager (Vault, AWS Secrets Manager, GCP Secret Manager).

---

*Built by Farnaz Nasehi.*
