#  SecureShop - Enterprise E-Commerce Platform

[![Security](https://img.shields.io/badge/Security-OWASP%20Top%2010-green)](https://owasp.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)](https://www.typescriptlang.org/)

A production-ready, security-first e-commerce platform built with modern technologies. Designed as a portfolio project demonstrating senior full-stack development expertise.

## Security Features

This project implements comprehensive security measures following OWASP guidelines:

### Authentication & Authorization
- **JWT with HTTP-only cookies** - Prevents XSS token theft
- **Refresh token rotation** - Mitigates token replay attacks
- **bcrypt password hashing** - Industry-standard password security (cost factor 12)
- **Role-based access control (RBAC)** - Granular permission management
- **Account lockout** - Brute force protection after failed attempts

### Input Validation & Sanitization
- **Server-side validation** - Using Joi/Zod schemas
- **Input sanitization** - XSS prevention with DOMPurify
- **Parameterized queries** - SQL injection prevention
- **File upload validation** - Type, size, and content verification

### API Security
- **Rate limiting** - Prevents abuse and DDoS
- **CORS configuration** - Strict origin policies
- **Helmet.js** - Security headers (CSP, HSTS, etc.)
- **Request size limits** - Prevents payload attacks

### Data Protection
- **Encryption at rest** - Sensitive data encryption
- **PCI DSS considerations** - No card storage, Stripe integration
- **GDPR compliance patterns** - Data export/deletion capabilities
- **Audit logging** - Security event tracking

### Additional Protections
- **CSRF tokens** - Cross-site request forgery prevention
- **Secure session management** - Redis-backed sessions
- **Environment variable management** - No secrets in code
- **Dependency scanning** - npm audit integration

##  Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   React     │  │   Redux     │  │   React Query           │  │
│  │   18.x      │  │   Toolkit   │  │   (Server State)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (TLS 1.3)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Rate      │  │   Auth      │  │   Request               │  │
│  │   Limiter   │  │   Guard     │  │   Validator             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Express   │  │   Business  │  │   Service               │  │
│  │   Server    │  │   Logic     │  │   Layer                 │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ PostgreSQL  │  │   Redis     │  │   S3/CloudStorage       │  │
│  │ (Primary)   │  │   (Cache)   │  │   (Assets)              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

##  Quick Start

### Prerequisites
- Node.js 20.x LTS
- PostgreSQL 15+
- Redis 7+
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/secureshop.git
cd secureshop

# Install dependencies
npm run install:all

# Setup environment variables
cp .env.example .env
# Edit .env with your configuration

# Run database migrations
npm run db:migrate

# Seed demo data (development only)
npm run db:seed

# Start development servers
npm run dev
```

### Environment Variables

```bash
# Server
NODE_ENV=development
PORT=3001
API_VERSION=v1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/secureshop
DATABASE_SSL=false

# Redis
REDIS_URL=redis://localhost:6379

# JWT Secrets (generate with: openssl rand -base64 64)
JWT_ACCESS_SECRET=your-access-secret-min-32-chars
JWT_REFRESH_SECRET=your-refresh-secret-min-32-chars
JWT_ACCESS_EXPIRY=15m
JWT_REFRESH_EXPIRY=7d

# Encryption
ENCRYPTION_KEY=your-32-byte-encryption-key

# Stripe (Test Keys)
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# CORS
ALLOWED_ORIGINS=http://localhost:3000

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

##  Project Structure

```
secureshop/
├── frontend/                 # React application
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Page components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── context/         # React context providers
│   │   ├── utils/           # Utility functions
│   │   ├── types/           # TypeScript definitions
│   │   └── styles/          # Global styles
│   └── public/
├── backend/                  # Express API server
│   ├── src/
│   │   ├── config/          # Configuration files
│   │   ├── controllers/     # Route handlers
│   │   ├── middleware/      # Express middleware
│   │   ├── models/          # Database models
│   │   ├── routes/          # API routes
│   │   ├── utils/           # Helper functions
│   │   └── validators/      # Input validation schemas
│   └── tests/
├── docs/                     # Documentation
└── scripts/                  # Build/deploy scripts
```

##  API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | User registration |
| POST | `/api/v1/auth/login` | User login |
| POST | `/api/v1/auth/logout` | User logout |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/forgot-password` | Request password reset |
| POST | `/api/v1/auth/reset-password` | Reset password |

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/products` | List products (paginated) |
| GET | `/api/v1/products/:id` | Get product details |
| POST | `/api/v1/products` | Create product (admin) |
| PUT | `/api/v1/products/:id` | Update product (admin) |
| DELETE | `/api/v1/products/:id` | Delete product (admin) |

### Cart & Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cart` | Get user's cart |
| POST | `/api/v1/cart/items` | Add item to cart |
| PUT | `/api/v1/cart/items/:id` | Update cart item |
| DELETE | `/api/v1/cart/items/:id` | Remove cart item |
| POST | `/api/v1/orders` | Create order |
| GET | `/api/v1/orders` | List user orders |
| GET | `/api/v1/orders/:id` | Get order details |

##  Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run security tests
npm run test:security

# Run E2E tests
npm run test:e2e
```

##  Security Checklist

Before deploying to production, ensure:

- [ ] All secrets are in environment variables
- [ ] HTTPS is enforced
- [ ] Database connections use SSL
- [ ] Rate limiting is configured
- [ ] CORS is properly restricted
- [ ] CSP headers are set
- [ ] Dependencies are audited (`npm audit`)
- [ ] Error messages don't leak sensitive info
- [ ] Logging doesn't include sensitive data
- [ ] File uploads are validated and scanned

##  Performance Optimizations

- Redis caching for frequently accessed data
- Database query optimization with indexes
- Image optimization and CDN delivery
- Code splitting and lazy loading
- Service worker for offline support





##  Author

**Farnaz Nasehi**

Demonstrating expertise in:
- Secure application architecture
- Modern React patterns and TypeScript
- RESTful API design
- Database design and optimization
- DevOps and deployment strategies
