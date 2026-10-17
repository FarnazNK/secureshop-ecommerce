"""Zero-cost offline demonstration of the AgentCore client security contract.

Run: python aws_agentcore/demo_offline.py
This demo intentionally uses fake response objects and never imports boto3.
"""
from __future__ import annotations

import io
import json
import os

from agentcore_readonly import invoke_readonly_agent


class OfflineAgentCore:
    def __init__(self) -> None:
        self.calls = 0

    def invoke_agent_runtime(self, **kwargs):
        self.calls += 1
        request = json.loads(kwargs["payload"])
        assert set(request) == {"prompt", "context"}
        assert kwargs["agentRuntimeArn"] == os.environ["AGENTCORE_RUNTIME_ARN"]
        return {
            "statusCode": 200,
            "response": io.BytesIO(
                json.dumps({"answer": "Offline demo: authorized context received."}).encode()
            ),
        }


def main() -> None:
    # Test-only ARN, intentionally not deployable; no AWS credentials are needed.
    os.environ["AGENTCORE_RUNTIME_ARN"] = (
        "arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/offline-demo"
    )
    client = OfflineAgentCore()
    try:
        invoke_readonly_agent(
            prompt="Explain the context",
            context="synthetic public sample",
            authorized=False,
            tenant_id="demo",
            client=client,
        )
    except PermissionError:
        print("PASS: unauthorized requests blocked before any model call")
    else:
        raise AssertionError("Unauthorized request was permitted")
    assert client.calls == 0
    answer = invoke_readonly_agent(
        prompt="Explain the context",
        context="synthetic public sample",
        authorized=True,
        tenant_id="demo",
        client=client,
    )
    assert client.calls == 1
    print("PASS:", answer)
    print("No AWS calls made. No account or payment required.")


if __name__ == "__main__":
    main()
