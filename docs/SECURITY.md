# Security Documentation

## Overview

This document outlines the security measures implemented in SecureShop to protect user data and prevent common web vulnerabilities. The implementation follows OWASP Top 10 guidelines and industry best practices.

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Input Validation & Sanitization](#input-validation--sanitization)
3. [Session Management](#session-management)
4. [API Security](#api-security)
5. [Data Protection](#data-protection)
6. [Error Handling](#error-handling)
7. [Security Headers](#security-headers)
8. [Logging & Monitoring](#logging--monitoring)
9. [Deployment Security](#deployment-security)

---

## Authentication & Authorization

### Password Security

```typescript
// Password requirements (config/security.config.ts)
const passwordConfig = {
  minLength: 12,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSpecialChars: true,
  bcryptRounds: 12,          // High cost factor for bcrypt
  maxLoginAttempts: 5,
  lockoutDuration: 30 * 60 * 1000, // 30 minutes
};
```

**Key Features:**
- Passwords hashed using bcrypt with cost factor 12
- Strong password policy enforcement
- Account lockout after failed attempts
- No password hints or security questions

### JWT Implementation

**Token Strategy:**
- Access tokens: Short-lived (15 minutes)
- Refresh tokens: Longer-lived (7 days)
- Stored in HTTP-only cookies (prevents XSS token theft)
- Refresh token rotation on use

```typescript
// Token structure
const tokenPayload = {
  userId: string,
  email: string,
  role: string,
  sessionId: string,  // Unique session identifier
  iat: number,        // Issued at
  exp: number,        // Expiration
};
```

**Cookie Configuration:**
```typescript
const cookieConfig = {
  httpOnly: true,      // Prevents JavaScript access
  secure: true,        // HTTPS only in production
  sameSite: 'strict',  // CSRF protection
  path: '/',
};
```

### Role-Based Access Control (RBAC)

```typescript
// Available roles
enum Role {
  CUSTOMER,  // Standard user
  MANAGER,   // Can manage products
  ADMIN,     // Full access
}

// Usage in routes
router.delete('/products/:id',
  authenticate,
  authorize('ADMIN'),  // Only admins
  deleteProduct
);
```

---

## Input Validation & Sanitization

### Zod Schema Validation

All inputs are validated using Zod schemas before processing:

```typescript
const registerSchema = z.object({
  email: z.string().email().max(255),
  password: passwordSchema,  // Complex validation
  firstName: sanitizedString(1, 50),  // XSS prevention
  lastName: sanitizedString(1, 50),
});
```

### XSS Prevention

```typescript
// sanitize-html for user content
const sanitizedHtml = (content: string) =>
  sanitizeHtml(content, {
    allowedTags: ['b', 'i', 'em', 'strong', 'p'],
    allowedAttributes: {},
  });
```

### SQL Injection Prevention

- Using Prisma ORM with parameterized queries
- No raw SQL queries
- Input validation before database operations

---

## Session Management

### Redis-Based Sessions

```typescript
// Session storage
await redis.setex(
  `session:${sessionId}`,
  24 * 60 * 60,  // 24 hours
  JSON.stringify({
    userId,
    createdAt: new Date().toISOString(),
    ip: clientIp,
    userAgent,
  })
);
```

### Session Security

- Unique session ID per login
- Session invalidation on logout
- Session blacklisting support
- Concurrent session limits

---

## API Security

### Rate Limiting

```typescript
const rateLimitConfig = {
  general: {
    windowMs: 15 * 60 * 1000,  // 15 minutes
    max: 100,                   // requests per window
  },
  auth: {
    windowMs: 15 * 60 * 1000,
    max: 5,                     // Stricter for auth
  },
};
```

### CORS Configuration

```typescript
const corsConfig = {
  origin: allowedOrigins,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-CSRF-Token'],
};
```

### Request Size Limits

```typescript
app.use(express.json({ limit: '10kb' }));
app.use(express.urlencoded({ limit: '10kb' }));
```

---

## Data Protection

### Encryption at Rest

```typescript
// AES-256-GCM encryption for sensitive data
const encryptionConfig = {
  algorithm: 'aes-256-gcm',
  ivLength: 16,
  tagLength: 16,
};
```

### Sensitive Data Handling

- Credit card data: NOT stored (Stripe handles)
- Passwords: Hashed with bcrypt
- Personal data: Encrypted at rest
- Audit logs: Sensitive fields redacted

---

## Error Handling

### Secure Error Messages

```typescript
// Production error response
if (process.env.NODE_ENV === 'production' && !isOperational) {
  message = 'An unexpected error occurred';
  details = undefined;  // No stack traces
}
```

### Error Types

| Status | Code | Description |
|--------|------|-------------|
| 400 | BAD_REQUEST | Invalid input |
| 401 | UNAUTHORIZED | Authentication required |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error (sanitized) |

---

## Security Headers

### Helmet.js Configuration

```typescript
const helmetConfig = {
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'", 'https://js.stripe.com'],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", 'data:', 'https:'],
      connectSrc: ["'self'", 'https://api.stripe.com'],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true,
  },
  frameguard: { action: 'deny' },
  noSniff: true,
  xssFilter: true,
  referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
};
```

---

## Logging & Monitoring

### Audit Logging

```typescript
// Events tracked
const auditEvents = [
  'auth.login',
  'auth.logout',
  'auth.failed_login',
  'auth.password_reset',
  'user.created',
  'user.updated',
  'order.created',
  'admin.action',
];
```

### Log Sanitization

```typescript
// Sensitive fields automatically redacted
const SENSITIVE_FIELDS = [
  'password',
  'token',
  'creditCard',
  'ssn',
  'authorization',
];
```

---

## Deployment Security

### Environment Variables

```bash
# Required secrets (never commit to git)
JWT_ACCESS_SECRET=<min-32-chars>
JWT_REFRESH_SECRET=<min-32-chars>
ENCRYPTION_KEY=<exactly-32-chars>
DATABASE_URL=<connection-string>
```

### Production Checklist

- [ ] HTTPS enforced
- [ ] Database SSL enabled
- [ ] Environment variables secured
- [ ] Rate limiting configured
- [ ] CORS origins restricted
- [ ] CSP headers set
- [ ] Dependencies audited
- [ ] Logs don't contain secrets
- [ ] Error messages sanitized
- [ ] File uploads validated

---

## Security Testing

### Recommended Tools

- **npm audit**: Dependency vulnerabilities
- **OWASP ZAP**: Web application scanning
- **Burp Suite**: API security testing
- **SQLMap**: SQL injection testing

### Running Security Tests

```bash
# Check dependencies
npm audit

# Run security-focused tests
npm run test:security

# Lint for security issues
npm run lint
```

---

## Incident Response

### Reporting Vulnerabilities

Please report security vulnerabilities privately to: security@example.com

**Do not:**
- Open public GitHub issues
- Share on social media
- Exploit vulnerabilities

**We will:**
- Acknowledge within 24 hours
- Provide timeline for fix
- Credit researchers (if desired)

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheets](https://cheatsheetseries.owasp.org/)
- [Node.js Security Best Practices](https://nodejs.org/en/docs/guides/security/)
- [Express.js Security Best Practices](https://expressjs.com/en/advanced/best-practice-security.html)
