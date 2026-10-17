# Optional AWS Bedrock AgentCore integration — not activated by default

This directory contains a **read-only AgentCore invocation adapter**. It does not register a public route, modify checkout/trading behavior, or deploy AWS resources. The caller must be an existing authenticated backend service; never import this into a frontend.

## Required integration constraints

1. Verify the actual authenticated principal and tenant/workspace ownership against the database **before** retrieving context. Never trust a client-supplied tenant ID, portfolio, order ID, or full context document.
2. Fetch only authorized, bounded and redacted context; pass it to `invoke_readonly_agent(prompt=...,context=...,authorized=True,tenant_id=...)`. Do **not** set `authorized=True` based on user request body flags.
3. Set `AGENTCORE_RUNTIME_ARN` only in server-side secret/configuration, use runtime IAM (no long-lived static AWS credentials). Grant only `bedrock-agentcore:InvokeAgentRuntime` for the exact runtime ARN to the backend service execution role. Restrict AWS region and session policies as appropriate.
4. Use the read-only, no-tools runtime from [Grounded Agent Platform](https://github.com/FarnazNK/grounded-agent-platform/pull/26). Configure Bedrock Guardrails, IAM, network egress, AWS WAF/quotas, CloudWatch redaction, CloudTrail, cost budgets, and short retention.
5. Keep orders, refunds, payments, holdings changes, investment execution, and administrative changes outside the agent. Human-authorized application routes continue to own all transactions.
6. Tests: `python -m pytest aws_agentcore/test_agentcore_readonly.py -q`. Mock tests **do not** verify a live AWS runtime.
7. No AWS deployment or actual end-to-end API route is provided here. Production use requires provider runtime validation, service-side authorization wiring and cross-tenant adversarial tests.
