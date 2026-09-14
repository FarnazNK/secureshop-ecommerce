# AWS deployment

SecureShop's FastAPI backend can be deployed to AWS Lambda through AWS SAM. The existing static storefront can continue to run on Render while the API runs on AWS.

## Architecture

GitHub Actions (OIDC) -> AWS SAM / CloudFormation -> Lambda Function URL -> Neon PostgreSQL

The deployment uses CloudWatch for Lambda logs. The template uses 768 MB memory, a 30-second timeout, reserved concurrency of 2, and 7-day log retention.

## One-time GitHub configuration

Create a GitHub Environment named `aws` and configure:

Repository/environment variables:
- `AWS_ROLE_ARN` — IAM role trusted by GitHub OIDC
- `AWS_REGION` — for example `us-east-1`

Environment secrets:
- `AWS_DATABASE_URL` — Neon PostgreSQL connection string
- `AWS_JWT_ACCESS_SECRET` — random secret of at least 32 characters
- `AWS_JWT_REFRESH_SECRET` — a different random secret of at least 32 characters
- `AWS_ENCRYPTION_KEY` — random secret of at least 32 characters

No long-lived AWS access key is required by the workflow.

## Deploy

Run **Deploy backend to AWS Lambda** from GitHub Actions, or push a relevant backend/AWS infrastructure change after `AWS_ROLE_ARN` is configured.

After the first deployment, update the storefront's `VITE_API_URL` to the Lambda Function URL plus `/api/v1` if you want AWS to become the primary backend.

## Cost controls

The deployment is intentionally concurrency-capped for portfolio use. Lambda/CloudWatch can stay within their free allowances at low traffic, but AWS usage above those allowances is billable.
