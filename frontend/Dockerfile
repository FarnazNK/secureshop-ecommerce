# syntax=docker/dockerfile:1.7

# ---------- Stage 1: Build (Vite + TypeScript) ----------
FROM node:20-alpine AS builder

WORKDIR /app

# VITE_* env vars must be present at build time — they get baked into the
# bundle. Pass them as Docker build args. The default points to the in-cluster
# backend service name; override for prod.
ARG VITE_API_URL=http://backend:3001
ENV VITE_API_URL=$VITE_API_URL

# Install deps with cache-friendly layering.
COPY package.json package-lock.json ./
RUN npm ci

# Compile TypeScript and bundle with Vite.
COPY tsconfig.json tsconfig.node.json vite.config.ts ./
COPY tailwind.config.ts postcss.config.js ./
COPY index.html ./
COPY src ./src
RUN npm run build


# ---------- Stage 2: Runtime (nginx serving the static bundle) ----------
# Nginx is the right choice for a SPA — it's small, battle-tested, and
# handles the HTML5 history API redirect correctly. Node serving static
# files would be wasteful here.
FROM nginx:1.27-alpine AS runtime

# Replace the default nginx config with one that:
# - serves the SPA with proper history-API fallback
# - reverse-proxies /api to the backend service
# - sets reasonable cache headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built bundle.
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx listens on 8080 (non-privileged port — needed because the official
# image runs as non-root by default in newer versions).
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:8080/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
