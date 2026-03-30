# OMDT Setup, Credentials, Hosting & Operations Guide

## 1. Local Development Setup (5 minutes)

### Prerequisites
- Python 3.12+
- pip

### Install & Run

```bash
cd omdt
pip install -e ".[dev]"
pip install aiosqlite python-dotenv

# Create your .env (already exists if you followed setup)
# Edit .env to add your credentials (see Section 2)

# Run database migrations
python -m alembic upgrade head

# Start the API
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

# API docs available at http://localhost:8000/docs
# Health check at http://localhost:8000/api/v1/health
```

### CLI

```bash
# Validate all config files
python -m app.cli._entry config validate

# Bootstrap Snowflake connection
python -m app.cli._entry bootstrap snowflake

# Create a work item
python -m app.cli._entry work-items create
```

---

## 2. Credentials & Secrets

All secrets go in the `.env` file locally. **Never commit `.env` to git.**

### Required `.env` File

Create/edit `.env` in the project root:

```env
# ============================================================
# DATABASE
# ============================================================
# Local dev (SQLite — zero setup):
DATABASE_URL=sqlite+aiosqlite:///./omdt.db

# Production (Postgres on Render — set in Render dashboard):
# DATABASE_URL=postgresql+asyncpg://user:password@host:5432/omdt

# ============================================================
# ENVIRONMENT
# ============================================================
OMDT_ENVIRONMENT=development
OMDT_DEBUG=true

# ============================================================
# LINEAR (https://linear.app/settings/api)
# ============================================================
LINEAR_API_KEY=lin_api_xxxxxxxxxxxx

# ============================================================
# NOTION (https://www.notion.so/my-integrations)
# ============================================================
NOTION_TOKEN=secret_xxxxxxxxxxxx
NOTION_PRD_DATABASE_ID=your-database-id-here

# ============================================================
# OUTLOOK / MICROSOFT GRAPH
# (https://portal.azure.com > App registrations)
# ============================================================
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret
MICROSOFT_TENANT_ID=your-tenant-id
OUTLOOK_SHARED_MAILBOX=data-team@yourcompany.com

# ============================================================
# GITHUB (https://github.com/settings/tokens)
# ============================================================
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=omdt

# ============================================================
# SNOWFLAKE
# ============================================================
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com
SNOWFLAKE_USER=your-username
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=ANALYTICS
SNOWFLAKE_ROLE=SYSADMIN

# ============================================================
# RENDER (https://render.com/docs/api)
# ============================================================
RENDER_API_KEY=rnd_xxxxxxxxxxxx
RENDER_SERVICE_ID=srv-xxxxxxxxxxxx

# ============================================================
# GAMMA (get from Gamma settings)
# ============================================================
GAMMA_API_KEY=your-gamma-key

# ============================================================
# LOVABLE (get from Lovable project settings)
# ============================================================
LOVABLE_API_KEY=your-lovable-key
LOVABLE_PROJECT_URL=https://your-project.lovable.app

# ============================================================
# REDIS (optional — not needed for local dev)
# ============================================================
# REDIS_URL=redis://localhost:6379/0
```

### Where to Get Each Credential

| Service | Where to create the key | What to create |
|---------|------------------------|----------------|
| **Linear** | linear.app > Settings > API | Personal API key |
| **Notion** | notion.so/my-integrations | Internal integration, share your PRD database with it |
| **Microsoft/Outlook** | portal.azure.com > App registrations | App registration with Mail.Read, Mail.Send permissions |
| **GitHub** | github.com/settings/tokens | Fine-grained token with repo, workflow, issues permissions |
| **Snowflake** | Your Snowflake admin console | Service account or your user credentials |
| **Render** | render.com > Account Settings > API Keys | API key |
| **Gamma** | Gamma app settings | API key (if available) |
| **Lovable** | Lovable project settings | Project API key |

### Start Small

You don't need ALL credentials on day one. The API boots and works without any of them. Add credentials as you enable each integration:

1. **Day 1 (no credentials needed):** API + CLI + SQLite works out of the box
2. **Day 2:** Add `LINEAR_API_KEY` to start syncing work items to Linear
3. **Day 3:** Add `NOTION_TOKEN` to sync PRDs
4. **Day 4:** Add Microsoft credentials for Outlook intake
5. **Later:** Snowflake, Render, Gamma, Lovable as needed

---

## 3. Hosting on Render

### Architecture on Render

```
Render Web Service (API)  ──>  Render PostgreSQL
                          ──>  Render Redis (optional)
```

### Step-by-Step Render Deployment

#### 3.1 Create a PostgreSQL Database on Render

1. Go to render.com > New > PostgreSQL
2. Name: `omdt-db`
3. Plan: Free (90 days) or Starter ($7/mo)
4. Copy the **Internal Database URL** (starts with `postgresql://`)

#### 3.2 Create a Web Service

1. Go to render.com > New > Web Service
2. Connect your GitHub repo
3. Settings:
   - **Name:** `omdt-api`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -e ".[dev]" && pip install asyncpg && python -m alembic upgrade head`
   - **Start Command:** `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free or Starter

#### 3.3 Set Environment Variables on Render

In the Render dashboard > your service > Environment:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` (from step 3.1, change `postgresql://` to `postgresql+asyncpg://`) |
| `OMDT_ENVIRONMENT` | `production` |
| `OMDT_DEBUG` | `false` |
| `LINEAR_API_KEY` | Your Linear key |
| `NOTION_TOKEN` | Your Notion token |
| ... | (add other credentials as needed) |

#### 3.4 Deploy

Push to your `main` branch. Render auto-deploys.

Your API will be live at: `https://omdt-api.onrender.com`

#### 3.5 Verify

```bash
curl https://omdt-api.onrender.com/api/v1/health
```

### render.yaml (Infrastructure as Code)

Create this file to auto-provision on Render:

```yaml
databases:
  - name: omdt-db
    plan: free
    databaseName: omdt

services:
  - type: web
    name: omdt-api
    runtime: python
    plan: free
    buildCommand: pip install -e . && pip install asyncpg && python -m alembic upgrade head
    startCommand: uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: omdt-db
          property: connectionString
      - key: OMDT_ENVIRONMENT
        value: production
      - key: OMDT_DEBUG
        value: "false"
      - key: LINEAR_API_KEY
        sync: false
      - key: NOTION_TOKEN
        sync: false
      - key: GITHUB_TOKEN
        sync: false
```

---

## 4. Accessing Audit Events & Activity

### 4.1 Via API

**Get all audit events:**
```bash
curl http://localhost:8000/api/v1/audit/events
```

**Filter by project, actor, event type, or time:**
```bash
# By event type
curl "http://localhost:8000/api/v1/audit/events?event_name=prd.approved"

# By actor
curl "http://localhost:8000/api/v1/audit/events?actor_id=payas"

# By time range
curl "http://localhost:8000/api/v1/audit/events?after=2026-03-01&before=2026-04-01"
```

### 4.2 Via Status Dashboard Endpoints

These endpoints power the Lovable dashboard and give you a quick overview:

```bash
# All project summaries
curl http://localhost:8000/api/v1/status/projects

# Active work items
curl http://localhost:8000/api/v1/status/work-items

# Recent deployments
curl http://localhost:8000/api/v1/status/deployments

# Recent audit trail
curl http://localhost:8000/api/v1/status/audit

# Pipeline health
curl http://localhost:8000/api/v1/status/pipelines
```

### 4.3 Via Swagger UI (Interactive)

Open in your browser:
- **Local:** http://localhost:8000/docs
- **Render:** https://your-app.onrender.com/docs

This gives you a full interactive API explorer where you can try every endpoint.

### 4.4 Via SQLite Directly (Local Dev)

```bash
# Open the database
sqlite3 omdt.db

# See all audit events
SELECT event_name, actor_id, object_type, change_summary, created_at
FROM audit_events ORDER BY created_at DESC LIMIT 20;

# See all work items
SELECT title, canonical_state, priority, source_channel, created_at
FROM work_items ORDER BY created_at DESC;

# See project status
SELECT name, state, owner_person_key FROM projects;

# Verify audit hash chain integrity
SELECT sequence_number, event_hash, prev_event_hash FROM audit_events ORDER BY sequence_number;
```

### 4.5 Via CLI

```bash
# List work items
python -m app.cli._entry work-items list

# Validate config
python -m app.cli._entry config validate
```

---

## 5. Key API Workflows

### Submit a Request (Intake)

```bash
curl -X POST http://localhost:8000/api/v1/intake/messages \
  -H "Content-Type: application/json" \
  -d '{
    "message_body": "I need a dashboard showing weekly revenue by product line",
    "subject": "Revenue Dashboard Request",
    "source_channel": "cli",
    "requester_email": "payas@example.com"
  }'
```

### Transition a Work Item

```bash
curl -X POST http://localhost:8000/api/v1/work-items/{id}/transition \
  -H "Content-Type: application/json" \
  -d '{"to_state": "TRIAGE", "actor_id": "payas", "reason": "Starting triage"}'
```

### Sync to Linear

```bash
curl -X POST http://localhost:8000/api/v1/linear/sync/{work_item_id}
```

### Create a Deployment

```bash
curl -X POST http://localhost:8000/api/v1/deployments \
  -H "Content-Type: application/json" \
  -d '{
    "git_sha": "abc123",
    "branch_tag": "main",
    "environment": "staging",
    "triggered_by": "payas"
  }'
```

---

## 6. Monitoring in Production

### Health Checks

Set up an uptime monitor (UptimeRobot, Better Uptime, etc.) pointed at:
```
GET https://your-app.onrender.com/api/v1/health
```

### Logs on Render

View live logs in the Render dashboard > your service > Logs.

All OMDT logs are structured JSON with correlation IDs, making them searchable.

### Audit Trail

The audit system records every meaningful action with:
- Who initiated it (actor)
- What changed (object type + ID)
- When (timestamp)
- Why (correlation ID linking related actions)
- Hash chain for tamper detection

Query via `GET /api/v1/audit/events` or directly in the database.

---

## 7. Quick Reference: File Locations

| What | Where |
|------|-------|
| API credentials | `.env` (never commit this) |
| App config | `config/omdt.yaml` |
| People/identities | `config/people.yaml` |
| Linear mappings | `config/linear.schema.yaml` |
| Approval policies | `config/approvals.yaml` |
| Role bundles | `config/role_bundles.yaml` |
| Database (local) | `omdt.db` (SQLite file) |
| API entry point | `app/api/main.py` |
| CLI entry point | `app/cli/main.py` |
| All API routes | http://localhost:8000/docs |
