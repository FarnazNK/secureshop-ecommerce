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

**Limitations:** This portfolio add-on uses `emptyDir` for monitoring data, so metrics and dashboard edits are ephemeral; a deleted pod loses them. It is not an HA or production security deployment. The application exposes Prometheus metrics without credentials: do not publicly publish its service or use the local HTTP port-forward as a production design.

Remove: `kubectl -n secureshop-demo delete -f k8s/monitoring.yaml` (the monitoring Secret can be deleted separately).
