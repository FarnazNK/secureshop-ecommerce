# Zero-cost portfolio mode

**No AWS account, paid cloud resource, or credit card is required.** This repository's AWS integration is a demonstration, not a deployed service. Production AWS code paths are opt-in and disabled by default. Do not set the live feature flags or `AGENTCORE_RUNTIME_ARN` when running locally.

## Demonstrate offline

Run the security regression tests without AWS credentials:

```bash
python -m pytest aws_agentcore/test_agentcore_readonly.py -q
```

These tests use a fake AgentCore client. They verify denial without authorization, isolation of the prompt/context payload, and failure when no runtime is configured. They **do not make AWS API calls** and do not validate a live deployment.

## Portfolio talking points

- Authentication is enforced in the FastAPI application before invoking an agent.
- The AWS runtime target is configured server-side, not supplied by a browser or prompt.
- The agent has read-only access and must never perform financial trades, orders, refunds, or payments.
- Prompt and context sizes are bounded, exceptions do not reveal AWS internals, and tests use dependency injection.
- Actual deployment would require IAM least privilege, AWS Bedrock Guardrails, cloud audit logs, budgets, and an end-to-end staging assessment.

**Honest limitation:** Passing mocked tests demonstrates local integration design and trust-boundary checks, not production security certification.

## One-command offline demo

From the repository root:

```bash
python aws_agentcore/demo_offline.py
```

The demo uses fake model/runtime objects and mock response streams. This command needs only Python and does **not** contact AWS. CI executes the same command to prevent demo regressions.
