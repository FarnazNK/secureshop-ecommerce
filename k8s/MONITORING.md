# Prometheus + Grafana: free local observability

This **optional** Kubernetes add-on monitors the same local Docker-built workloads as `k8s/local.yaml`. It requires no AWS account, paid service or remote telemetry. All monitoring Services are **ClusterIP**, not public LoadBalancers. No passwords are committed.

## Start

Follow [the local Kubernetes guide](README.md) and start the app first. Then, from the repository root:

```bash
GRAFANA_PASSWORD="$(openssl rand -hex 24)"
kubectl -n secureshop-demo create secret generic monitoring-secrets \
  --from-literal=GRAFANA_ADMIN_PASSWORD="$GRAFANA_PASSWORD"
# Save the password in a secure local password manager before unsetting.
unset GRAFANA_PASSWORD
kubectl -n secureshop-demo apply -f k8s/monitoring.yaml
kubectl -n secureshop-demo rollout status deployment/prometheus --timeout=180s
kubectl -n secureshop-demo rollout status deployment/grafana --timeout=180s
```

In **separate terminals**:

```bash
kubectl -n secureshop-demo port-forward service/prometheus 9090:9090
kubectl -n secureshop-demo port-forward service/grafana 3000:3000
```

Open http://localhost:9090/targets and http://localhost:3000 (user: `admin`, password: the generated Secret). Grafana's Prometheus data source is automatically configured. Create an initial dashboard with `up`, `rate(secureshop_http_requests_total[5m])` or request latency histograms where exposed. Endpoint /metrics is designed for local diagnostics and must be access-restricted before any real public deployment.

## Alerts

`k8s/monitoring.yaml` loads alert rules into Prometheus (see http://localhost:9090/alerts). They cover the things that lose money or orders:

| Alert | Fires when |
| --- | --- |
| StripeCircuitOpen | the Stripe circuit breaker has been open for 1 minute (checkout returns 503; carts are kept) |
| StripeErrorRateHigh | over 20% of Stripe calls fail for 5 minutes |
| WebhookProcessingFailing | any Stripe webhook failed to process in the last 15 minutes (the hourly job retries it) |
| WebhookLagHigh | p95 time from Stripe event to our webhook is over 5 minutes |
| ApiErrorRateHigh | over 5% of API responses are 5xx for 5 minutes |
| ApiLatencyHigh | API p95 latency over 1 second for 10 minutes |
| RateLimiterBackendErrors | the shared rate limiter can't reach the database (it fails open) |
| BackendDown | a backend pod stops answering `/metrics` |

Prometheus scrapes **every** backend pod through the headless `backend-pods` Service, so counts stay correct when the autoscaler adds pods. Alerts show on the Prometheus alerts page and in Grafana; nothing is sent outside your computer.

The hosted demo (Vercel) has no Prometheus. There, the free signals are the GitHub Actions maintenance job (a failed run emails you through GitHub's normal notifications) and Vercel's runtime logs.

## Autoscaling

```bash
# metrics-server (free) gives the autoscaler CPU numbers
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'  # kind only
kubectl -n secureshop-demo apply -f k8s/scaling.yaml
kubectl -n secureshop-demo get hpa backend --watch
```

The backend runs 2 to 4 pods at 70% CPU, with a PodDisruptionBudget that keeps one pod up during drains. Every pod shares the rate limit through Postgres (`RATE_LIMIT_BACKEND=database` in `k8s/local.yaml`), and 4 pods x 10 connections stays under Postgres's default limit of 100.

**Limitations:** This portfolio add-on uses `emptyDir` for monitoring data, so metrics and dashboard edits are ephemeral; a deleted pod loses them. It is not an HA or production security deployment. The application exposes Prometheus metrics without credentials: do not publicly publish its service or use the local HTTP port-forward as a production design.

Remove: `kubectl -n secureshop-demo delete -f k8s/monitoring.yaml` (the monitoring Secret can be deleted separately).
