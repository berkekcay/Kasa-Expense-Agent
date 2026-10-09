# Kasa

Kasa is an AI agent (Google ADK + Gemini) that looks after a student's personal spending and
shared-flat expenses. It reads receipts, saves expenses, splits bills, settles debts and answers
money questions with charts.

**Core rule:** the LLM decides *what* to do; plain Python does all the money math.
Amounts are stored as integer minor units (kuruş/cents), never floats.

## Architecture

```
 Browser
   |
   v
 Next.js web UI (frontend/)        chat, receipt upload, expenses, house, charts
   |  HTTPS + X-User-Id (dev)  ->  Firebase ID token (later)
   v
 FastAPI backend (backend/app)
   |-- api/        REST routers
   |-- agents/     Google ADK agents
   |     coordinator --> receipt_agent   (save_expense, list_recent_expenses)
   |                 --> house_agent     (equal split, balances, settle-up)
   |                 --> report_agent    (guarded read-only SQL -> chart spec)
   |                 --> budget_agent    (stub, sprint 3)
   |-- services/   plain-Python data layer + money math (unit tested)
   |-- db/         SQLAlchemy models + sessions (sets SESSION_CONTEXT on MSSQL)
   |        |                                  |
   v        v                                  v
 Gemini API            SQLite (local dev)  /  SQL Server with row-level security (prod)
 (later: Gmail, Calendar, TCMB exchange rates)
```

Guardrails:
- Report SQL is parsed with sqlglot. Only one plain `SELECT` is allowed, and only over
  `my_expenses` and `my_expense_items`. Those names are injected as CTEs filtered to the
  current user, and a row limit is applied.
- Users only see their own data, enforced three times: service queries, scoped report CTEs
  and SQL Server RLS (`backend/sql/mssql/002_row_level_security.sql`).
- Receipt and email content is treated as data, never as instructions. This is written into
  every agent prompt, and the acting user always comes from the request, never from the model.
- No keys in code. Settings come from env vars, which are backed by Secret Manager on Cloud Run.

## Who owns what

| Path | Owner |
| --- | --- |
| `backend/app/db/`, `backend/app/services/expenses.py`, `backend/app/api/`, `backend/app/auth.py`, `backend/sql/` | Database & Backend |
| `backend/app/agents/coordinator.py`, `receipt_agent.py`, `budget_agent.py`, `tools/receipt_tools.py` | Agent dev #1 |
| `backend/app/agents/house_agent.py`, `tools/house_tools.py`, `backend/app/services/settlement.py`, `services/houses.py` | Agent dev #2 |
| `backend/app/agents/report_agent.py`, `tools/report_tools.py`, `backend/app/services/reports.py`, `tests/`, Dockerfiles / Cloud Run | Agent dev #3 |
| `frontend/` (`src/features/{expenses,receipts,houses,chat}`, `src/lib/api.ts`) | Frontend |

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

API docs are at http://localhost:8000/docs. Without `GOOGLE_API_KEY`, everything works except
`POST /receipts` and `POST /chat`, which return 503.

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

| Variable | Where | Default | Notes |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend | `sqlite:///./kasa.db` | Prod: `mssql+pyodbc://user:pass@host:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server` |
| `GOOGLE_API_KEY` | backend | empty | Gemini key. Empty disables the agent endpoints (503). |
| `GEMINI_MODEL` | backend | `gemini-2.5-flash` | Any Gemini model id your key can use |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | Comma-separated list |
| `DEV_DEFAULT_USER_ID` | backend | `dev-user` | Used when there is no `X-User-Id` header (dev only) |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Baked in at build time |

### Getting a Gemini API key

1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key** and pick or create a Google Cloud project.
3. Put the key in `backend/.env` as `GOOGLE_API_KEY=...`. Never commit it. `.env` is gitignored.

## SQL Server (production database)

```bash
pip install -r requirements-mssql.txt   # pyodbc; also needs Microsoft ODBC Driver 18
sqlcmd -S <server> -d kasa -i backend/sql/mssql/001_schema.sql
sqlcmd -S <server> -d kasa -i backend/sql/mssql/002_row_level_security.sql
```

The app should connect as a low-privilege user, not `db_owner`. Each transaction runs
`sp_set_session_context 'user_id'`, and the RLS policy filters on that value.

## Deploy to Google Cloud Run (outline)

```bash
gcloud config set project <PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# Secrets
printf '%s' "<gemini-key>"   | gcloud secrets create gemini-api-key --data-file=-
printf '%s' "<mssql-url>"    | gcloud secrets create database-url  --data-file=-

# Backend (builds backend/Dockerfile with Cloud Build)
gcloud run deploy kasa-api --source backend --region europe-west1 --allow-unauthenticated \
  --set-secrets GOOGLE_API_KEY=gemini-api-key:latest,DATABASE_URL=database-url:latest \
  --set-env-vars CORS_ORIGINS=https://<kasa-web-url>

# Frontend: NEXT_PUBLIC_API_URL is baked in at build time, so build the image with a build arg
# (Cloud Shell has Docker; we can't run Docker on the team laptops)
gcloud artifacts repositories create kasa --repository-format=docker --location=europe-west1
gcloud auth configure-docker europe-west1-docker.pkg.dev
IMAGE=europe-west1-docker.pkg.dev/<PROJECT_ID>/kasa/web
docker build frontend --build-arg NEXT_PUBLIC_API_URL=https://<kasa-api-url> -t $IMAGE
docker push $IMAGE
gcloud run deploy kasa-web --image $IMAGE --region europe-west1 --allow-unauthenticated
```

The Cloud Run service account needs `roles/secretmanager.secretAccessor`. Without
`DATABASE_URL`, the backend image falls back to a throwaway SQLite file in `/tmp` (demo only).
Firebase Auth replaces the `X-User-Id` dev header in a later sprint (`backend/app/auth.py`).

## Sprint 1 checklist

- [x] Receipt photo → receipt agent reads it (image sent as an inline Part) → `save_expense` tool → expense saved
- [x] Expense list plus a manual add form
- [x] One house with members, equal split (the remainder is spread so shares always sum to the total)
- [x] House balances and greedy settle-up transfers
- [x] One question → report agent → guarded SQL → chart spec rendered with recharts
- [x] Dockerfiles for Cloud Run (backend and frontend)
- [x] pytest: money math, SQL guard, API happy paths, and ADK wiring with a scripted fake LLM
- [ ] Try live Gemini calls with a real key (receipt accuracy, routing quality)
- [ ] Provision SQL Server, run the `sql/mssql` scripts and test RLS end to end
- [ ] First Cloud Run deploy
