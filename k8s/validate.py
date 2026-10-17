"""Validate cost-free Kubernetes demo manifests without a cluster."""
from pathlib import Path

import yaml


def main():
    documents = list(yaml.safe_load_all(Path(__file__).with_name("local.yaml").read_text()))
    assert all(isinstance(d, dict) for d in documents)
    expected = {"postgres", "redis", "backend", "frontend"}
    deploys = {d["metadata"]["name"]: d for d in documents if d["kind"] == "Deployment"}
    services = {d["metadata"]["name"]: d for d in documents if d["kind"] == "Service"}
    assert set(deploys) == expected
    assert set(services) == expected
    assert any(d["kind"] == "PersistentVolumeClaim" for d in documents)
    for name in expected:
        deployment = deploys[name]
        service = services[name]
        spec = deployment["spec"]["template"]["spec"]
        assert spec.get("automountServiceAccountToken") is False
        assert deployment["spec"]["selector"]["matchLabels"] == service["spec"]["selector"]
        assert spec["containers"]
        for container in spec["containers"]:
            assert container["image"].endswith((":local", ":16-alpine", ":7-alpine", ":pg16"))
            assert container["resources"]["requests"]["memory"]
            assert container["resources"]["limits"]["memory"]
            assert container["imagePullPolicy"] == "IfNotPresent"
            for env in container.get("env", []):
                assert "secret" not in env["name"].lower() or "valueFrom" in env
                if any(s in env["name"] for s in ("PASSWORD", "JWT", "ENCRYPTION", "DATABASE_URL")):
                    assert "valueFrom" in env
                    assert env["valueFrom"]["secretKeyRef"]["name"] == "app-secrets"
        assert service["spec"].get("type", "ClusterIP") == "ClusterIP"
    print("PASS: Kubernetes manifests have the expected services and security defaults")


if __name__ == "__main__":
    main()
