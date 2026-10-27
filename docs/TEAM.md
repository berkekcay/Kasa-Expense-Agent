# Team and working agreement

This file says who owns what, how we work on the repository, and how each person presents
their part. The role split below is a **proposal**. Swap people between rows if that fits the
team better, then update this file in a PR.

## Roles and owners

The five roles come from the project page. Agent developer #3 (QA and cloud) has no person
yet, so Mustafa and Yusuf share it until someone else joins.

| Person | GitHub | Role | Owns |
| --- | --- | --- | --- |
| Berke | @berkekcay | Product owner, architecture | user stories, architecture, priorities, issue triage, demo kit, final review of docs |
| Mustafa | @MustafaPar | Database and backend | data model, migrations and RLS, auth, REST API, Google OAuth and Gmail plumbing, statement CSV parsing |
| Yusuf | @Yusufrmak497 | Agent developer #1 | coordinator, receipt agent, budget agent and the MONEY track, email and statement parser agents |
| Ömer | @omertarikcandir | Agent developer #2 | house agent, splits, balances, settle-up, payments, Calendar reminders (HOUSE track) |
| Zehra | @zehraoz36 | Frontend | every page and component in `frontend/` |
| Mustafa and Yusuf | | Agent developer #3, QA and cloud (shared) | Yusuf: report agent, checker agent, evals. Mustafa: CI, Cloud Run deploy, Azure SQL |

### Who owns which files

This is the track table from [ARCHITECTURE.md](ARCHITECTURE.md#tracks-and-owners) with a
person on each row. Backend paths are under `backend/app/` and frontend paths under
`frontend/src/`, unless they start with `backend/`, `frontend/`, `deploy/`, `docs/` or `.github/`.

| Area | Owner | Backend files | Frontend files |
| --- | --- | --- | --- |
| Shared core | Mustafa | `main.py`, `config.py`, `auth.py`, `db/*`, `backend/alembic/*`, `api/expenses.py`, `api/users.py`, `api/internal.py`, `services/expenses.py`, `services/users.py`, `services/categories.py`, `services/crypto.py`, `services/clock.py`, `schemas/common.py`, `schemas/expenses.py`, `schemas/users.py` | `lib/api/client.ts`, `lib/auth.ts` (with Zehra) |
| Agent runtime | Yusuf | `agents/common.py`, `agents/runtime.py`, `agents/coordinator.py`, `agents/language.py`, `api/agents.py`, `schemas/agents.py`, `agents/receipt_agent.py`, `agents/tools/receipt_tools.py` | |
| HOUSE | Ömer | `services/splits.py`, `services/settlement.py`, `services/houses.py`, `services/reminders.py`, `integrations/google_calendar.py`, `api/houses.py`, `schemas/houses.py`, `agents/house_agent.py`, `agents/tools/house_tools.py` | `features/houses` (with Zehra) |
| MONEY | Yusuf | `services/fx.py`, `integrations/tcmb.py`, `services/budgets.py`, `services/subscriptions.py`, `services/dashboard.py`, `api/budgets.py`, `api/subscriptions.py`, `api/dashboard.py`, `api/fx.py`, `schemas/budgets.py`, `schemas/subscriptions.py`, `schemas/dashboard.py`, `schemas/fx.py`, `agents/budget_agent.py`, `agents/tools/budget_tools.py` | `features/dashboard`, `features/budgets`, `features/subscriptions` (with Zehra) |
| INGEST plumbing | Mustafa | `integrations/google_oauth.py`, `integrations/gmail.py`, `services/gmail_sync.py`, `services/inbox.py`, `services/statements.py`, `api/integrations.py`, `api/inbox.py`, `api/imports.py`, `schemas/inbox.py`, `schemas/imports.py`, `schemas/integrations.py` | `features/inbox`, `features/imports`, `features/settings` (with Zehra) |
| INGEST agents | Yusuf | `agents/email_agent.py`, `agents/statement_agent.py`, `agents/tools/inbox_tools.py` | |
| REPORT | Yusuf (QA share) | `services/reports.py`, `agents/report_agent.py`, `agents/tools/report_tools.py`, `agents/checker_agent.py`, `backend/evals/` | `features/chat` (with Zehra) |
| Cloud and CI | Mustafa (QA share) | `backend/Dockerfile`, `deploy/*`, `.github/workflows/*`, `docs/SETUP.md` | `frontend/Dockerfile` |
| Frontend | Zehra | | `frontend/src/**` |
| Product docs and demo | Berke | `docs/USER_STORIES.md`, `docs/ARCHITECTURE.md`, `docs/TEAM.md`, `docs/DEMO.md`, `README.md`, `backend/scripts/seed_demo.py` | |

"With Zehra" means the track owner decides what the page needs and Zehra builds or reviews
it. Everyone writes tests for their own files.

### First issues for each person

Each Partial or Not started story in [USER_STORIES.md](USER_STORIES.md) becomes an issue.
The open ones, with a ready prompt for a coding agent in each:

- **Everyone:** [#3](https://github.com/berkekcay/Kasa-Expense-Agent/issues/3) set up,
  rehearse and record the Friday demo.
- **Mustafa:** [#7](https://github.com/berkekcay/Kasa-Expense-Agent/issues/7) finish the CSV
  export PR, [#8](https://github.com/berkekcay/Kasa-Expense-Agent/issues/8) Next.js 16.4.3,
  [#9](https://github.com/berkekcay/Kasa-Expense-Agent/issues/9) per-user chat limit
  (US-GUARD-07). Later: Azure SQL and RLS smoke test (US-GUARD-04), first Cloud Run deploy
  with Yusuf (US-ACCOUNT-04).
- **Yusuf:** [#4](https://github.com/berkekcay/Kasa-Expense-Agent/issues/4) verify Gemini
  with `gemini-3.5-flash-lite` (US-ASK-06, US-CAPTURE-02), then
  [#5](https://github.com/berkekcay/Kasa-Expense-Agent/issues/5) reply language (US-ASK-04).
- **Ömer:** [#6](https://github.com/berkekcay/Kasa-Expense-Agent/issues/6) house invite codes,
  backend and house agent (US-HOUSE-02). Later: Calendar reminders against a real Google
  account once the OAuth client exists (US-HOUSE-07).
- **Zehra:** [#10](https://github.com/berkekcay/Kasa-Expense-Agent/issues/10) frontend tests in
  CI, [#11](https://github.com/berkekcay/Kasa-Expense-Agent/issues/11) invite code pages
  (US-HOUSE-02). Later: "delete my data" in Settings (US-GUARD-08).
- **Berke:** keep USER_STORIES and the board current, review every PR for scope, present the
  architecture in labs.

## Working agreement

- **No direct pushes to `main`.** `main` is protected. Every change goes through a pull
  request with one approval and green CI.
- **One issue per PR.** Create the issue first, then a branch named `feature/<short-name>`
  (for example `feature/house-invites`). Use `fix/<short-name>` for bug fixes and
  `docs/<short-name>` for documentation only.
- **Use the PR template** (`.github/pull_request_template.md`): Problem, Approach, Testing,
  Screenshots, Linked issue. Write `Closes #<issue>` so the issue closes on merge.
- **One review.** Ask the owner of the files you touched. If you touched only your own files,
  ask the person whose code calls yours. The author does not merge without the approval.
- **CI must be green**: ruff, ruff format and pytest on Python 3.12 and 3.14, eslint and
  `next build` for the frontend.
- **Resolve every review thread**, including CodeRabbit's, before merging. If you disagree
  with a comment, reply with the reason and resolve it; do not leave it open.
- **Small PRs.** Under about 400 changed lines when possible. Split big features.
- **No secrets.** Keys go in `backend/.env`, which is gitignored. Never paste a key into an
  issue, a PR, a screenshot or a chat.
- **Tests stay offline.** No test may call Gemini, Google or TCMB unless it is marked live.

## Running the app and the tests

The full steps for Windows and macOS are in [DEMO.md](DEMO.md#the-day-before-setup) and the
README. In short:

```bash
cd backend
python -m venv .venv            # Windows: py -m venv .venv
# activate it: .\.venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
ruff check . && ruff format --check . && pytest -q
python -m scripts.seed_demo --user demo
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                     # http://localhost:3000, type "demo" in the Dev user box
```

Live tests against a model: `KASA_LIVE_TESTS=1 pytest -m live -s`. Evals:
`python -m evals.run_evals` (see the docstring in `backend/evals/run_evals.py`).

## Using a coding agent on this repository

Claude Code, Codex, Copilot and similar agents read [AGENTS.md](../AGENTS.md) at the
repository root (`CLAUDE.md` imports it). It lists the layout, the commands and the rules
that must never break: integer minor units, tools take the user from `tool_context`,
untrusted text is data, no secrets. Some tips:

- Give the agent one issue at a time and the story id, and ask it to write the test first.
- Ask it to run the CI commands before it says it is done.
- Read every line of the diff before you push. You are the author, not the agent.
- Never paste a real API key into an agent chat.

## Lab presentations

Everyone presents the part they own, so the instructor hears from all five of us. A short
lab slot can look like this:

| Part | Who | Time |
| --- | --- | --- |
| Problem, users and architecture | Berke (or the next presenter if Berke is away) | 2 min |
| Data model, API, security layers | Mustafa | 2 min |
| Coordinator, receipts, budgets and money math | Yusuf | 2 min |
| Houses, splits and settle-up | Ömer | 2 min |
| The app itself, page by page | Zehra | 2 min |

Each person shows one thing they built or fixed since the last lab, one test that proves it,
and what they do next. For the demo on Friday 2026-10-30, follow [DEMO.md](DEMO.md).
