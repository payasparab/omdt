# GitHub Environments Setup Guide

This document describes how to configure the `staging` and `prod` GitHub Environments used by the deploy workflow.

## 1. Create Environments

In your GitHub repository, go to **Settings → Environments** and create two environments:

| Environment | Purpose |
|-------------|---------|
| `staging`   | Pre-production validation |
| `prod`      | Production deployment     |

## 2. Environment Protection Rules

### staging
- No required reviewers (auto-deploys on push to `main`).
- Optionally restrict to the `main` branch.

### prod
- **Required reviewers**: add at least one approver.
- **Wait timer**: consider a 5-minute delay for rollback window.
- **Deployment branches**: restrict to `main` only.

## 3. Required Secrets

Add the following secrets to **each** environment (values differ per environment):

| Secret | Description |
|--------|-------------|
| `RENDER_DEPLOY_HOOK_STAGING` | Render deploy-hook URL for staging (staging env only) |
| `RENDER_DEPLOY_HOOK_PROD` | Render deploy-hook URL for production (prod env only) |
| `STAGING_URL` | Base URL for the staging service (staging env only) |
| `PROD_URL` | Base URL for the production service (prod env only) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `OPENAI_API_KEY` | OpenAI API key for LLM agents |
| `LINEAR_API_KEY` | Linear API key for issue sync |
| `OUTLOOK_CLIENT_ID` | Microsoft Graph client ID |
| `OUTLOOK_CLIENT_SECRET` | Microsoft Graph client secret |
| `OUTLOOK_TENANT_ID` | Microsoft 365 tenant ID |
| `NOTION_TOKEN` | Notion integration token |
| `SHAREPOINT_SITE_ID` | SharePoint site ID for document sync |
| `SENTRY_DSN` | Sentry DSN for error tracking |

## 4. Repository Secrets (shared across all environments)

These are set at **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `CODECOV_TOKEN` | (Optional) Codecov upload token |

## 5. Verification

After setup, trigger a manual deploy via **Actions → Deploy → Run workflow** with `environment: staging` to confirm the pipeline works end-to-end.
