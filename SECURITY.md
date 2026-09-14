# Security Policy

## Reporting a vulnerability

Please do not publish exploit details, credentials, personal data, or proof-of-concept attacks in a public issue.

If GitHub shows a **Report a vulnerability** option for this repository, use it to submit the report privately. Otherwise, contact the maintainer through the GitHub profile with a minimal notice that a private security report is needed; do not include sensitive exploit details in public discussion.

Please include:
- affected component and version/commit;
- impact and realistic attack scenario;
- minimal reproduction steps;
- any suggested remediation.

## Scope

Security reports are welcome for the application code, authentication and authorization, deployment configuration, dependency/supply-chain risks, and accidental secret exposure.

The hosted deployments are portfolio/demo services. Do not perform destructive testing, denial-of-service testing, credential stuffing, automated exploitation, or access data that is not yours.

## Secrets

No production credentials should be committed to this repository. Runtime secrets belong in the hosting provider's secret/environment configuration. If a real secret is ever committed, it should be rotated immediately; deleting it from the latest commit is not sufficient because Git history may retain it.
