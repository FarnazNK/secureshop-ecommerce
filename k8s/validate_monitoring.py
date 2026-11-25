"""Check optional monitoring Kubernetes addon without starting a cluster."""

from pathlib import Path

import yaml


def main():
    docs = list(
        yaml.safe_load_all(Path(__file__).with_name("monitoring.yaml").read_text())
    )
    deployments = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Deployment"}
    services = {d["metadata"]["name"]: d for d in docs if d["kind"] == "Service"}
    configs = {d["metadata"]["name"]: d for d in docs if d["kind"] == "ConfigMap"}
    assert set(deployments) == {"prometheus", "grafana"}
    assert set(services) == {"prometheus", "grafana", "backend-pods"}
    assert services["backend-pods"]["spec"]["clusterIP"] == "None"
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
    password = next(
        item for item in graph["env"] if item["name"] == "GF_SECURITY_ADMIN_PASSWORD"
    )
    assert password["valueFrom"]["secretKeyRef"]["name"] == "monitoring-secrets"
    assert (
        "http://prometheus:9090"
        in configs["grafana-datasource"]["data"]["datasource.yaml"]
    )
    scrape = configs["prometheus-config"]["data"]["prometheus.yml"]
    assert "metrics_path: /metrics" in scrape
    assert "/etc/prometheus/alerts.yml" in scrape
    rules = yaml.safe_load(configs["prometheus-config"]["data"]["alerts.yml"])
    names = {r["alert"] for g in rules["groups"] for r in g["rules"]}
    assert {"StripeCircuitOpen", "WebhookProcessingFailing", "ApiErrorRateHigh"} <= names
    for group in rules["groups"]:
        for rule in group["rules"]:
            assert rule["expr"] and rule["annotations"]["summary"]
    scaling = list(yaml.safe_load_all(Path(__file__).with_name("scaling.yaml").read_text()))
    kinds = {d["kind"]: d for d in scaling}
    assert set(kinds) == {"HorizontalPodAutoscaler", "PodDisruptionBudget"}
    hpa = kinds["HorizontalPodAutoscaler"]["spec"]
    assert hpa["scaleTargetRef"]["name"] == "backend"
    assert 2 <= hpa["minReplicas"] <= hpa["maxReplicas"] <= 4
    assert kinds["PodDisruptionBudget"]["spec"]["minAvailable"] == 1
    print(
        "PASS: monitoring add-on is private, bounded, has alert rules and configured without"
        " plaintext credentials; autoscaling add-on is bounded"
    )


if __name__ == "__main__":
    main()
