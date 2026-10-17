# Free local Kubernetes demo (kind)

Kubernetes orchestrates Docker-built backend/frontend containers, PostgreSQL and Redis. Runs on your own computer; **no AWS, cloud deployment or subscription**. Requires Docker, `kind`, `kubectl` and `openssl`. Use synthetic/demo accounts, and do not deploy this localhost HTTP configuration to the public internet.

```bash
kind create cluster --name secureshop-portfolio
docker build -t secureshop-backend:local ./backend
docker build -t secureshop-frontend:local ./frontend
kind load docker-image --name secureshop-portfolio secureshop-backend:local secureshop-frontend:local
kubectl create namespace secureshop-demo
DB_PASSWORD="$(openssl rand -hex 24)"
ACCESS_SECRET="$(openssl rand -hex 32)"
REFRESH_SECRET="$(openssl rand -hex 32)"
ENCRYPTION_KEY="$(openssl rand -hex 32)"
kubectl -n secureshop-demo create secret generic app-secrets \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql+asyncpg://secureshop:$DB_PASSWORD@postgres:5432/secureshop" \
  --from-literal=REDIS_URL="redis://redis:6379" \
  --from-literal=JWT_ACCESS_SECRET="$ACCESS_SECRET" \
  --from-literal=JWT_REFRESH_SECRET="$REFRESH_SECRET" \
  --from-literal=ENCRYPTION_KEY="$ENCRYPTION_KEY"
unset DB_PASSWORD ACCESS_SECRET REFRESH_SECRET ENCRYPTION_KEY
kubectl -n secureshop-demo apply -f k8s/local.yaml
kubectl -n secureshop-demo rollout status deployment/postgres --timeout=180s
kubectl -n secureshop-demo exec deployment/backend -- alembic upgrade head
kubectl -n secureshop-demo rollout status deployment/backend --timeout=180s
kubectl -n secureshop-demo port-forward service/frontend 8080:8080
```

Visit `http://localhost:8080`. The nginx image proxies `/api/` to Kubernetes Service `backend:3001`. AgentCore remains off. PostgreSQL has one replica and a local persistent volume. This is **not** a production-hardened HA cluster.

Cleanup: `kind delete cluster --name secureshop-portfolio`.
