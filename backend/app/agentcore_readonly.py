"""Read-only AgentCore client; call only from an authenticated, authorized backend.

Do not expose runtime ARN to browsers, accept an ARN from clients, or send
credentials, payments, or unverified tenant data to model providers.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any


class AgentCoreUnavailable(RuntimeError):
    """Generic, safe-to-return error with no provider details."""


def invoke_readonly_agent(
    *,
    prompt: str,
    context: str,
    authorized: bool,
    tenant_id: str,
    client: Any = None,
) -> str:
    """Invoke the fixed, private runtime. Authorization MUST precede retrieval."""
    if not authorized or not isinstance(tenant_id, str) or not tenant_id.strip():
        raise PermissionError("Unauthorized agent invocation")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise ValueError("Invalid prompt")
    if not isinstance(context, str) or len(context) > 12000:
        raise ValueError("Invalid context")
    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
    if not runtime_arn.startswith("arn:aws:bedrock-agentcore:"):
        raise AgentCoreUnavailable("Agent runtime is not configured")
    if client is None:
        import boto3

        client = boto3.client("bedrock-agentcore")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=str(uuid.uuid4()),
            payload=json.dumps({"prompt": prompt, "context": context}).encode(),
            qualifier="DEFAULT",
        )
        # Runtime returns a bounded JSON body; never expose raw SDK exceptions.
        if response.get("statusCode", 200) != 200:
            raise AgentCoreUnavailable("Agent invocation failed")
        body = response["response"]
        raw = body.read(16001) if hasattr(body, "read") else body
        if len(raw) > 16000:
            raise AgentCoreUnavailable("Agent response exceeded limit")
        result = json.loads(raw)
        if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
            raise AgentCoreUnavailable("Invalid agent response")
        return result["answer"][:12000]
    except Exception:
        raise AgentCoreUnavailable("Agent invocation failed") from None
