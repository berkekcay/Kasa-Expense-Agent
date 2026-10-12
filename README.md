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
  `my_expenses` and `my_expense_items`. Those names are injected as CTEs filtered to the
  current user, and a row limit is applied.
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
| `GEMINI_MODEL` | backend | `gemini-2.5-flash` | Any Gemini model id your key can use |
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

## SQL Server (production database)

The schema and the row-level security policy come from the Alembic migrations. Run them with
an admin login, then let the app connect as a low-privilege user (not `db_owner`):

```bash
pip install -r requirements-mssql.txt   # pyodbc; also needs Microsoft ODBC Driver 18
MIGRATION_DATABASE_URL="mssql+pyodbc://admin:<pw>@<server>:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server" \
  alembic upgrade head
```

To review the DDL first, add `--sql` (it prints the script and needs no server). Each
transaction runs `sp_set_session_context 'user_id'`, and the RLS policy filters on that value.

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
With SQL Server, deploy with `AUTO_MIGRATE=false` and run `alembic upgrade head` as a Cloud Run
job using an admin `MIGRATION_DATABASE_URL`. Set `FIREBASE_PROJECT_ID` on the backend and the
`NEXT_PUBLIC_FIREBASE_*` build args on the frontend so only signed-in users get in.

## Sprint 1 checklist

- [x] A receipt photo goes to the receipt agent as an inline image, and its `save_expense` tool saves the expense
- [x] Expense list plus a manual add form
- [x] One house with members, equal split (the remainder is spread so shares always sum to the total)
- [x] House balances and greedy settle-up transfers
- [x] A question goes to the report agent, which runs guarded SQL and returns a chart spec that recharts draws
- [x] Dockerfiles for Cloud Run (backend and frontend)
- [x] pytest: money math, SQL guard, API happy paths, and ADK wiring with a scripted fake LLM
- [ ] Try live Gemini calls with a real key (receipt accuracy, routing quality)
- [ ] Provision SQL Server, run the migrations and test RLS end to end
- [ ] First Cloud Run deploy

## Sprint 2 foundation

- [x] Alembic migrations for SQLite and SQL Server (RLS included); a test checks they match the models
- [x] Data model for sprints 2 to 4 (splits, settlements, budgets, FX, inbox, Google, subscriptions, reminders)
- [x] Recorded payments between flatmates reduce balances
- [x] Fixed category list with Turkish synonyms
- [x] Firebase Auth (optional) with the dev header as fallback
- [x] Ollama provider for dev; the three Sprint 1 flows pass live on the team server
- [x] Skeleton modules, routes and pages for the HOUSE, MONEY, INGEST and REPORT tracks
- [x] CI: ruff, pytest, eslint and next build on every push
