"""Dependency-free, mocked security tests for optional AgentCore client."""

import importlib.util
import json
from io import BytesIO
from pathlib import Path

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
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test"
    )
    client = FakeClient()
    with pytest.raises(PermissionError):
        m.invoke_readonly_agent(
            prompt="x", context="y", authorized=False, tenant_id="a", client=client
        )
    assert not client.calls


def test_scoped_readonly_call(monkeypatch):
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test"
    )
    client = FakeClient()
    assert (
        m.invoke_readonly_agent(
            prompt="x",
            context="synthetic",
            authorized=True,
            tenant_id="a",
            client=client,
        )
        == "ok"
    )
    sent = json.loads(client.calls[0]["payload"])
    assert sent == {"prompt": "x", "context": "synthetic"}
    assert "tenant_id" not in sent


def test_missing_runtime_fails_closed(monkeypatch):
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)
    with pytest.raises(m.AgentCoreUnavailable):
        m.invoke_readonly_agent(
            prompt="x", context="y", authorized=True, tenant_id="a", client=FakeClient()
        )


@pytest.mark.parametrize(
    "prompt, context",
    [("", "data"), ("x" * 4001, "data"), ("ok", "x" * 12001)],
)
def test_invalid_request_rejected_before_client_call(monkeypatch, prompt, context):
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test",
    )
    client = FakeClient()
    with pytest.raises(ValueError):
        m.invoke_readonly_agent(
            prompt=prompt,
            context=context,
            authorized=True,
            tenant_id="test",
            client=client,
        )
    assert not client.calls


@pytest.mark.parametrize(
    "response",
    [
        {"statusCode": 403, "response": BytesIO(b"AccessDenied")},
        {"statusCode": 200, "response": BytesIO(b"invalid json")},
        {"statusCode": 200, "response": BytesIO(b'{"answer": 1}')},
        {"statusCode": 200, "response": BytesIO(b"x" * 16001)},
    ],
)
def test_provider_failures_are_sanitized(monkeypatch, response):
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test",
    )

    class BadClient:
        def invoke_agent_runtime(self, **kwargs):
            return response

    with pytest.raises(m.AgentCoreUnavailable, match="Agent invocation failed"):
        m.invoke_readonly_agent(
            prompt="question",
            context="safe text",
            authorized=True,
            tenant_id="test",
            client=BadClient(),
        )


def test_missing_user_scope_rejected_before_client_call(monkeypatch):
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test",
    )
    client = FakeClient()
    with pytest.raises(PermissionError):
        m.invoke_readonly_agent(
            prompt="question",
            context="safe text",
            authorized=True,
            tenant_id="",
            client=client,
        )
    assert not client.calls


ARN = "arn:aws:bedrock-agentcore:us-east-1:123:runtime/test"


class RaisingClient:
    def __init__(self, error):
        self.error = error

    def invoke_agent_runtime(self, **kwargs):
        raise self.error


@pytest.mark.parametrize(
    "client",
    [
        RaisingClient(OSError("connection reset")),
        RaisingClient(TimeoutError("read timed out")),
        type("NoBody", (), {"invoke_agent_runtime": lambda self, **kw: {}})(),
        type("NotADict", (), {"invoke_agent_runtime": lambda self, **kw: None})(),
    ],
    ids=["network", "timeout", "missing-body", "not-a-dict"],
)
def test_transport_and_shape_errors_are_sanitized(monkeypatch, client):
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", ARN)
    with pytest.raises(m.AgentCoreUnavailable, match="Agent invocation failed"):
        m.invoke_readonly_agent(
            prompt="question",
            context="safe",
            authorized=True,
            tenant_id="t",
            client=client,
        )


def test_aws_sdk_errors_are_sanitized(monkeypatch):
    exceptions = pytest.importorskip("botocore.exceptions")
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", ARN)
    error = exceptions.ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "arn and account details",
            }
        },
        "InvokeAgentRuntime",
    )
    with pytest.raises(
        m.AgentCoreUnavailable, match="Agent invocation failed"
    ) as raised:
        m.invoke_readonly_agent(
            prompt="question",
            context="safe",
            authorized=True,
            tenant_id="t",
            client=RaisingClient(error),
        )
    assert "account details" not in str(raised.value)


def test_unexpected_bugs_are_not_disguised_as_outages(monkeypatch):
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", ARN)
    with pytest.raises(RuntimeError, match="bug in caller"):
        m.invoke_readonly_agent(
            prompt="question",
            context="safe",
            authorized=True,
            tenant_id="t",
            client=RaisingClient(RuntimeError("bug in caller")),
        )
