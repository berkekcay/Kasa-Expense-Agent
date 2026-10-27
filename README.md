# Kasa

Kasa is an AI agent (Google ADK + Gemini) that looks after a student's personal spending and
shared-flat expenses. It reads receipts, saves expenses, splits bills, settles debts and answers
money questions with charts.

The module map, the data model, who owns which files and how a request flows through the
system are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The one rule: the LLM decides *what* to do, and plain Python does all the money math.
Amounts are stored as integer minor units (kuruş/cents), never floats.

## Architecture

```
 Browser
   |
   v
 Next.js web UI (frontend/)        chat, receipt upload, expenses, house, charts
   |  HTTPS + Firebase ID token (or X-User-Id in dev mode)
   v
 FastAPI backend (backend/app)
   |-- api/        REST routers
   |-- agents/     Google ADK agents
   |     coordinator --> receipt_agent   (save_expense, list_recent_expenses)
   |                 --> house_agent     (splits, balances, settle-up, paybacks)
   |                 --> report_agent    (guarded read-only SQL -> chart spec)
   |                 --> budget_agent    (budgets, subscriptions, exchange rates)
   |                 --> inbox_agent     (expenses found in Gmail and bank statements)
   |-- services/   plain-Python data layer + money math (unit tested)
   |-- db/         SQLAlchemy models + sessions (sets SESSION_CONTEXT on MSSQL)
   |-- alembic/    migrations, including row-level security on SQL Server
   |        |                                  |
   v        v                                  v
 Gemini API (Ollama     SQLite (local dev)  /  SQL Server with row-level security (prod)
 in dev and tests)      Gmail, Calendar and TCMB exchange rates via app/integrations/
```

Guardrails:
- Report SQL is parsed with sqlglot. Only one plain `SELECT` is allowed, and only over
  `my_expenses`, `my_expense_items`, `my_house_shares`, `my_budgets` and `my_subscriptions`.
  Those names are injected as CTEs filtered to the current user, and a row limit is applied.
  A second agent, the checker, reads each query next to the user's question and can send it
  back for a fix before it runs.
- Emails and bank statements only ever create inbox items. Nothing becomes an expense until
  the user approves it, and text inside an email cannot approve anything.
- Users only see their own data, enforced three times: service queries, scoped report CTEs
  and SQL Server RLS (created by the Alembic migrations in `backend/alembic/versions/`).
- Receipt and email content is treated as data, never as instructions. This is written into
  every agent prompt, and the acting user always comes from the request, never from the model.
- No keys in code. Settings come from env vars, which are backed by Secret Manager on Cloud Run.

## Who owns what

Sprint 2 to 4 work is split into four tracks (HOUSE, MONEY, INGEST, REPORT), each with its
own files. The table is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#tracks-and-owners).

## Run locally

You need Python 3.12+ and Node 20+ (tested with Python 3.14 and Node 24). Start the backend
on :8000 and the frontend on :3000.

### Backend: Windows (PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env        # then paste your GOOGLE_API_KEY into .env
pytest
uvicorn app.main:app --reload --port 8000
```

### Backend: macOS / Linux

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # then paste your GOOGLE_API_KEY into .env
pytest
uvicorn app.main:app --reload --port 8000
```

The database schema is created and upgraded by Alembic when the app starts (`AUTO_MIGRATE=true`).
To run it by hand: `alembic upgrade head`.

API docs are at http://localhost:8000/docs. Without an LLM provider, everything works except
`POST /receipts` and `POST /chat`, which return 503. Endpoints of features that are not built
yet return 501.

### Running the agents on Ollama instead of Gemini

For development without a Gemini key, point the agents at an Ollama server in `backend/.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434     # or the team server
OLLAMA_MODEL=gpt-oss:20b                    # chat and tool calling
OLLAMA_VISION_MODEL=qwen3-vl:8b             # receipt photos
```

This needs `requirements-dev.txt` (it adds litellm). Live end-to-end tests:
`KASA_LIVE_TESTS=1 pytest -m live -s`.

### Frontend (any OS)

```bash
cd frontend
npm install
cp .env.example .env.local         # PowerShell: Copy-Item .env.example .env.local
npm run dev                        # http://localhost:3000
```

Use the "Dev user" box in the nav bar to act as different users. For example, create a house
as `ali`, add `ayse`, then switch to `ayse`.

## Environment variables

Every backend setting is listed with a comment in `backend/.env.example`; the frontend ones are
in `frontend/.env.example`. The ones you need most:

| Variable | Where | Default | Notes |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend | `sqlite:///./kasa.db` | Prod: `mssql+pyodbc://user:pass@host:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server` |
| `AUTO_MIGRATE` | backend | `true` | Prod: `false`, and migrate as a deploy step |
| `LLM_PROVIDER` | backend | `gemini` | `ollama` for dev and tests |
| `GOOGLE_API_KEY` | backend | empty | Gemini key. Empty disables the agent endpoints (503). |
| `GEMINI_MODEL` | backend | `gemini-3.5-flash-lite` | Any Gemini model id your key can use. New keys cannot use the 2.5 models. |
| `FIREBASE_PROJECT_ID` | backend | empty | Set in prod. Empty means dev mode (X-User-Id) |
| `TOKEN_ENCRYPTION_KEY` | backend | empty | Fernet key for Google refresh tokens: `python -m app.services.crypto` |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | backend | empty | Gmail and Calendar connection |
| `INTERNAL_TASK_TOKEN` | backend | empty | Cloud Scheduler secret for `/internal/*` |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | Comma-separated list |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Baked in at build time |
| `NEXT_PUBLIC_FIREBASE_*` | frontend | empty | Google sign-in; empty shows the dev user box |

### Getting a Gemini API key

1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key** and pick or create a Google Cloud project.
3. Put the key in `backend/.env` as `GOOGLE_API_KEY=...`. Never commit it. `.env` is gitignored.

## Deploying

Production runs on Google Cloud Run (`kasa-api` and `kasa-web` in `europe-west1`) with an
Azure SQL Database on the free offer. [docs/SETUP.md](docs/SETUP.md) is the full guide, from
an empty account to a smoke-tested deployment: Gemini key, Azure SQL server, database and
low-privilege app user, Google OAuth consent screen and client, Firebase Auth, secrets,
Pub/Sub, Cloud Scheduler and the GitHub deploy workflow.

The short version, in Cloud Shell after the console steps in the guide:

```bash
bash deploy/gcp_bootstrap.sh     # APIs, service accounts, secrets, Pub/Sub, Scheduler (re-runnable)
bash deploy/deploy_backend.sh    # Cloud Build, `alembic upgrade head` as a Cloud Run job, deploy
bash deploy/deploy_frontend.sh   # Cloud Build with the NEXT_PUBLIC_* build args, deploy
```

The schema and the row-level security policy come only from the Alembic migrations. They run
as a Cloud Run job with an admin login (`MIGRATION_DATABASE_URL`), while the service runs with
`AUTO_MIGRATE=false` as a contained database user that can read and write data but not change
the schema. Each transaction sets `SESSION_CONTEXT('user_id')`, and the RLS policy filters on
it. To review the SQL Server DDL without a server:

```bash
cd backend
alembic -x url="mssql+pyodbc://u:p@host/kasa?driver=ODBC+Driver+18+for+SQL+Server" upgrade head --sql
```

`.github/workflows/deploy.yml` runs the same deploy scripts from GitHub (manual trigger, `main`
only) with Workload Identity Federation instead of a key file.

## Sprint 1 checklist

- [x] A receipt photo goes to the receipt agent as an inline image, and its `save_expense` tool saves the expense
- [x] Expense list plus a manual add form
- [x] One house with members, equal split (the remainder is spread so shares always sum to the total)
- [x] House balances and greedy settle-up transfers
- [x] A question goes to the report agent, which runs guarded SQL and returns a chart spec that recharts draws
- [x] Dockerfiles for Cloud Run (backend and frontend)
- [x] pytest: money math, SQL guard, API happy paths, and ADK wiring with a scripted fake LLM
- [ ] Try live Gemini calls with a real key (receipt accuracy, routing quality)
- [ ] Provision SQL Server, run the migrations and test RLS end to end (Azure SQL steps are in docs/SETUP.md)
- [ ] First Cloud Run deploy (the scripts in `deploy/` are ready but have not run against a real project)

## Sprint 2 foundation

- [x] Alembic migrations for SQLite and SQL Server (RLS included); a test checks they match the models
- [x] Data model for sprints 2 to 4 (splits, settlements, budgets, FX, inbox, Google, subscriptions, reminders)
- [x] Recorded payments between flatmates reduce balances
- [x] Fixed category list with Turkish synonyms
- [x] Firebase Auth (optional) with the dev header as fallback
- [x] Ollama provider for dev; the three Sprint 1 flows pass live on the team server
- [x] Skeleton modules, routes and pages for the HOUSE, MONEY, INGEST and REPORT tracks
- [x] CI: ruff, pytest, eslint and next build on every push

## Sprints 2 to 4 tracks

All four tracks have landed and the backend has no stubs left. Tested offline with fakes for
Google and the LLM; the REPORT evals also ran live on Ollama (`backend/evals/latest.md`).

- [x] HOUSE: equal, percent, exact and per-item splits, recorded payments, settle-up reminders (Google Calendar)
- [x] MONEY: TCMB exchange rates, budgets with alerts, subscription detection, dashboard
- [x] INGEST: Google OAuth connection, Gmail sync and push handler, CSV and PDF statement import, inbox approval
- [x] REPORT: user-scoped relations, checker agent that reviews each query, eval runner
- [ ] Real Google OAuth consent, Gmail push and Calendar events against Google
- [ ] The same flows on Gemini instead of Ollama

## Deployment kit

- [x] Setup guide from an empty account to a smoke test: [docs/SETUP.md](docs/SETUP.md)
- [x] `deploy/` scripts for Cloud Shell: bootstrap, backend (migration job, then service), frontend; checked with `bash -n` and dry runs against a stubbed `gcloud`
- [x] Manual GitHub Actions deploy with Workload Identity Federation (`.github/workflows/deploy.yml`)
- [x] Backend waits for a paused Azure SQL serverless database to resume (connect retry, unit tested)
- [x] SQL Server DDL reviewed for Azure SQL Database; a test keeps out `USE`, cross-database names and server-level statements
- [ ] Run the scripts against a real Google Cloud project and Azure SQL database
- [ ] RLS checked on Azure SQL with real users (smoke test in docs/SETUP.md)
