# syntax=docker/dockerfile:1.7

# ---------- Stage 1: Build (TypeScript compile + Prisma generate) ----------
# Separate builder so the runtime image doesn't carry dev dependencies,
# tsc, or the npm cache. Keeps the final image small and the attack
# surface narrow.
FROM node:20-alpine AS builder

WORKDIR /app

# Install all deps (including dev) for the build.
# Copying package-lock.json separately means dep installs cache when only
# source code changes.
COPY package.json package-lock.json ./
RUN npm ci

# Prisma needs the schema before `prisma generate` can run.
COPY prisma ./prisma
RUN npx prisma generate

# Now copy source and compile TypeScript.
COPY tsconfig.json ./
COPY src ./src
RUN npm run build


# ---------- Stage 2: Runtime ----------
# Smaller image with only production deps and the compiled output.
FROM node:20-alpine AS runtime

# Tini handles signals properly so docker stop doesn't take 10 seconds.
RUN apk add --no-cache tini

# Don't run as root in production. Create a dedicated user with no shell.
RUN addgroup -S app && adduser -S -G app -s /sbin/nologin app

WORKDIR /app

# Production deps only — no tsx, vitest, eslint, etc.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

# Pull the compiled JS and the generated Prisma client from the builder.
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma
COPY --from=builder /app/prisma ./prisma

# Runtime ownership: app user, not root.
RUN chown -R app:app /app
USER app

ENV NODE_ENV=production \
    PORT=3001

EXPOSE 3001

# Healthcheck — node fetch is built-in on Node 18+. Don't depend on curl
# or wget being in the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://localhost:3001/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

# Tini as PID 1 means SIGTERM propagates correctly to node.
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/server.js"]
