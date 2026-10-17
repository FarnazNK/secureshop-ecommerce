"""Check optional monitoring Kubernetes addon without starting a cluster."""
from pathlib import Path

import yaml

def main():
    docs = list(yaml.safe_load_all(Path(__file__).with_name("monitoring.yaml").read_text()))
    deployments = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Deployment"}
    services = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Service"}
    configs = {d["metadata"]["name"]: d for d in docs if d["kind"] == "ConfigMap"}
    assert set(deployments) == {"prometheus", "grafana"}
    assert set(services) == {"prometheus", "grafana"}
    assert set(configs) == {"prometheus-config", "grafana-datasource"}
    for name, deployment in deployments.items():
        pod = deployment["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert services[name]["spec"]["type"] == "ClusterIP"
        container = pod["containers"][0]
        assert container["resources"]["limits"]["memory"]
        assert container["readinessProbe"]
        assert container["image"].startswith(("prom/", "grafana/"))
    graph = deployments["grafana"]["spec"]["template"]["spec"]["containers"][0]
    password = next(item for item in graph["env"] if item["name"] == "GF_SECURITY_ADMIN_PASSWORD")
    assert password["valueFrom"]["secretKeyRef"]["name"] == "monitoring-secrets"
    assert "http://prometheus:9090" in configs["grafana-datasource"]["data"]["datasource.yaml"]
    scrape = configs["prometheus-config"]["data"]["prometheus.yml"]
    assert "metrics_path: /metrics" in scrape
    print("PASS: monitoring add-on is private, bounded and configured without plaintext credentials")

if __name__ == "__main__":
    main()
