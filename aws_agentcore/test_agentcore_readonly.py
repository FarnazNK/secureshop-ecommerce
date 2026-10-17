"""Dependency-free, mocked security tests for optional AgentCore client."""
import importlib.util
from pathlib import Path
from io import BytesIO
import json
import pytest

P = Path(__file__).resolve().parent / "agentcore_readonly.py"
S = importlib.util.spec_from_file_location("agentcore_readonly", P)
assert S and S.loader
m = importlib.util.module_from_spec(S)
S.loader.exec_module(m)


class FakeClient:
    def __init__(self):
        self.calls = []
    def invoke_agent_runtime(self, **kwargs):
        self.calls.append(kwargs)
        return {"response": BytesIO(json.dumps({"answer": "ok"}).encode())}


def test_refuses_unauthorized_call(monkeypatch):
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test")
    client = FakeClient()
    with pytest.raises(PermissionError):
        m.invoke_readonly_agent(prompt="x", context="y", authorized=False, tenant_id="a", client=client)
    assert not client.calls


def test_scoped_readonly_call(monkeypatch):
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test")
    client = FakeClient()
    assert m.invoke_readonly_agent(prompt="x", context="synthetic", authorized=True, tenant_id="a", client=client) == "ok"
    sent = json.loads(client.calls[0]["payload"])
    assert sent == {"prompt": "x", "context": "synthetic"}
    assert "tenant_id" not in sent


def test_missing_runtime_fails_closed(monkeypatch):
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)
    with pytest.raises(m.AgentCoreUnavailable):
        m.invoke_readonly_agent(prompt="x", context="y", authorized=True, tenant_id="a", client=FakeClient())
