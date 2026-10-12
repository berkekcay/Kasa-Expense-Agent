# Kasa setup guide

This guide takes the account owner from nothing to a working Kasa deployment. Follow the
steps in order. Plan for one to two hours, most of it clicking through consoles.

At the end you have:

- `kasa-api` (FastAPI backend) and `kasa-web` (Next.js frontend) on Google Cloud Run in
  `europe-west1`
- an Azure SQL Database on the free offer, with the row-level security policy from the
  Alembic migrations
- Google sign-in through Firebase Auth, Gmail and Calendar access through Google OAuth,
  and Gemini through an AI Studio key
- Gmail push notifications through Pub/Sub, and three Cloud Scheduler jobs

The scripts in `deploy/` do the Google Cloud command-line work. The rest happens in web
consoles. Everything here has been checked offline only (script dry runs with a stubbed
`gcloud`, the SQL Server DDL rendered without a server). The first real run is yours, so
read the output of each script.

## 1. Prerequisites

- A Google account for the project owner.
- Google Cloud Shell (https://shell.cloud.google.com). It already has `gcloud`, `git`,
  `python3` and `docker`, so you install nothing. You can also use your own machine with the
  gcloud CLI, but the scripts are written and described for Cloud Shell (bash).
- An Azure account through Azure for Students (step 4). The Azure CLI (`az`) is optional;
  this guide uses the Azure portal.
- Read access to the GitHub repository.

## 2. Google Cloud project and billing

1. Open https://console.cloud.google.com, click the project picker, then **New project**.
   Name it, for example, `kasa-berke`. Write down the **project ID** (it may differ from
   the name).
2. Link a billing account (**Billing** in the menu). Cloud Run asks for one even when you
   stay inside the free tier. New billing accounts usually come with free trial credits.
3. Set a budget alert so nothing surprises you: **Billing > Budgets & alerts > Create
   budget**, for example 5 USD with alerts at 50, 90 and 100 percent.
4. Open Cloud Shell and get the code:

   ```bash
   gcloud config set project <PROJECT_ID>
   git clone https://github.com/berkekcay/Kasa-Expense-Agent.git kasa
   cd kasa
   source deploy/config.sh && echo "API: $API_URL" && echo "Web: $WEB_URL"
   ```

   Cloud Run URLs follow the pattern `https://<service>-<project number>.<region>.run.app`,
   so the two URLs are known before anything is deployed. You need them in steps 5 and 6.
   All settings for the scripts are in `deploy/config.sh`.

## 3. Gemini API key

1. Go to https://aistudio.google.com/apikey and sign in with the owner account.
2. Click **Create API key** and choose the Kasa project (or another project, see below).
3. Keep the key for step 7. Never put it in a file in the repository.

A key in a project with billing turned on uses the paid tier. To stay on the free tier,
create the key in a separate project without billing; AI Studio shows the tier next to each
key. On the free tier Google may use prompts to improve its products, so use test receipts
and test emails while you are on it.

## 4. Azure SQL Database (free offer)

### 4.1 Azure for Students

Sign up at https://azure.microsoft.com/free/students with your school email. It gives a
yearly credit and needs no credit card. The SQL Database free offer below does not use the
credit as long as you keep the auto-pause setting from step 4.2.

### 4.2 Server and database

In https://portal.azure.com search for **SQL databases** and click **Create**.

1. **Basics**
   - Resource group: **Create new**, `kasa-rg`.
   - Database name: `kasa`.
   - Server: **Create new**. Server name: something unique such as `kasa-sql-berke`.
     Location: a region near Belgium, for example **West Europe**. If the student
     subscription refuses the region (a policy error), try another European region.
     Authentication method: **Use SQL authentication**. Pick the server admin login (for
     example `kasaadmin`) and a strong password (20 or more characters; use letters, digits
     and `-_.!` only, which keeps the connection string simple). This admin login is only
     for migrations.
   - A banner offers the free offer ("Want to try Azure SQL Database for free?"). Click
     **Apply offer**. The compute tier becomes General Purpose serverless.
   - **Behavior when free limit reached**: choose **Auto-pause the database until next
     month**. With this choice the database can never cost money; it stops for the rest of
     the month instead.
2. **Networking**
   - Connectivity method: **Public endpoint**.
   - Allow Azure services and resources to access this server: **No** (Cloud Run is not an
     Azure service, and this switch would open the server to every Azure customer).
   - Add current client IP address: **Yes**, so the portal query editor works.
   - Minimum TLS version: **1.2**.
3. Leave the rest as it is and click **Review + create**, then **Create**.

### 4.3 Firewall for Cloud Run

Cloud Run has no fixed outgoing IP address, so the server cannot allow "just Cloud Run".
There are two options:

- **Allow all addresses** (what this guide uses). Open the server (not the database), go to
  **Security > Networking**, and under **Firewall rules** add a rule named
  `AllowCloudRun` from `0.0.0.0` to `255.255.255.255`. Save. The server is then reachable
  from the internet, protected by the SQL login, a strong password and TLS (the connection
  string demands `Encrypt=yes` and a valid certificate).
- **Static outgoing IP** (stricter, paid). Route the backend through a VPC with Cloud NAT
  and a reserved static IP (Cloud Run Direct VPC egress with `--vpc-egress=all-traffic`),
  then allow only that IP. The NAT gateway and the IP cost a few dollars a month, which is
  why it is not the default here.

### 4.4 Database user for the app

The app connects as a contained database user with data access only. It cannot change the
schema or the security policy, so row-level security always applies to it. The admin login
from step 4.2 is used only by the migration job.

Open the `kasa` database, click **Query editor (preview)**, sign in with the admin login, and
run this (choose a different strong password):

```sql
CREATE USER kasa_app WITH PASSWORD = '<app password>';
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO kasa_app;
```

The grant covers tables the migrations create later. After the first deploy (step 8) you can
also stop the app user from touching the migration bookkeeping:

```sql
DENY INSERT, UPDATE, DELETE ON dbo.alembic_version TO kasa_app;
```

The predicate functions live in the `security` schema, which `kasa_app` has no rights on.
Because the policy is schema-bound, users do not need any permission on those functions.

### 4.5 Connection URLs

The backend needs two SQLAlchemy URLs. `gcp_bootstrap.sh` (step 7) asks for the parts and
builds both for you, so this is for reference:

```
mssql+pyodbc://<user>:<password, URL-encoded>@<server>.database.windows.net:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

| Secret Manager name | Env var | User | Read by |
| --- | --- | --- | --- |
| `database-url` | `DATABASE_URL` | `kasa_app` | backend service |
| `migration-database-url` | `MIGRATION_DATABASE_URL` | admin login | migration job only |

Characters such as `@`, `:`, `/` and `%` in a password break the URL unless they are
percent-encoded. To encode one by hand:

```bash
python3 -c 'import getpass, urllib.parse; print(urllib.parse.quote(getpass.getpass(), safe=""))'
```

The backend image already contains Microsoft ODBC Driver 18.

### 4.6 Auto-pause and the first request

The free database pauses after a period without connections (the auto-pause delay on the
database's **Compute + storage** page; set it to the lowest value offered). While it is
paused, the first login fails with error 40613 and the database takes about a minute to
resume.

The backend handles this: `app/db/session.py` retries a login that fails with 40613 (and
Azure's other transient login errors) for about 75 seconds, so the first request after a
pause is slow but succeeds. The migration job uses the same retry. `pool_pre_ping` replaces
pooled connections that died while an instance sat idle. Pooled connections also keep the
database awake until the Cloud Run instance shuts down, which happens some minutes after the
last request.

Read "Free limits and costs" at the end before you pick the Gmail sync schedule.

## 5. Google OAuth for Gmail and Calendar

Kasa reads receipts from Gmail and adds settle-up reminders to Google Calendar through a
standard OAuth web flow on the backend.

### 5.1 Consent screen

1. Open https://console.cloud.google.com/auth/overview (Google Auth Platform) in the Kasa
   project and click **Get started**.
2. App name `Kasa`, your email as support email, audience **External**, your email as
   contact. Accept the policy and create.
3. **Audience**: leave the publishing status on **Testing**. Under **Test users** add the
   Google account of everyone who will use Kasa (up to 100).
4. **Data access > Add or remove scopes**: add these four (paste them under "Manually add
   scopes" if they are not in the list) and save:

   ```
   openid
   https://www.googleapis.com/auth/userinfo.email
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/calendar.events
   ```

What Testing mode means for Kasa:

- `gmail.readonly` is a restricted scope. Publishing the app for everyone would need Google's
  verification plus a yearly third-party security assessment, so the app stays in Testing.
- Only test users can sign in. This also covers Firebase's Google sign-in, which uses the
  same project.
- Google refresh tokens for apps in Testing expire after 7 days. Kasa notices the dead token,
  shows Google as disconnected, and the user connects again in **Settings**.
- During consent Google shows an "unverified app" warning. Click **Advanced** and continue.

### 5.2 OAuth client

1. **Clients > Create client**, type **Web application**, name `kasa-api`.
2. Under **Authorized redirect URIs** add both:

   ```
   http://localhost:8000/integrations/google/callback
   <API_URL>/integrations/google/callback
   ```

   `<API_URL>` is the backend URL printed in step 2, for example
   `https://kasa-api-123456789012.europe-west1.run.app`.
3. Click **Create** and copy the client ID and client secret right away (download the JSON
   too; the console may not show the secret again). You enter both in step 7.

The Gmail and Calendar APIs are enabled by `gcp_bootstrap.sh`.

## 6. Firebase Auth

1. Open https://console.firebase.google.com, click **Create a project** (or **Add
   project**) and choose the existing Google Cloud project from step 2, so both share one
   project. Google Analytics is not needed.
2. **Build > Authentication > Get started > Sign-in method**: enable **Google**, pick the
   support email, save.
3. **Authentication > Settings > Authorized domains**: add the frontend host, which is
   `<WEB_URL>` without `https://`, for example `kasa-web-123456789012.europe-west1.run.app`.
   `localhost` is already there.
4. **Project settings > General > Your apps**: add a **Web** app (`</>`), nickname
   `kasa-web`, no Hosting. Copy `apiKey`, `authDomain`, `projectId` and `appId`.
5. Save them in Cloud Shell. This file is gitignored and Cloud Shell keeps your home folder:

   ```bash
   cat > deploy/config.local.sh <<'EOF'
   NEXT_PUBLIC_FIREBASE_API_KEY="<apiKey>"
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="<authDomain>"
   NEXT_PUBLIC_FIREBASE_PROJECT_ID="<projectId>"
   NEXT_PUBLIC_FIREBASE_APP_ID="<appId>"
   # Optional overrides of deploy/config.sh, for example:
   # SYNC_SCHEDULE="0 * * * *"     # hourly instead of every 6 hours
   # ENABLE_GMAIL_PUSH=true        # new mail within seconds (uses more free database time)
   EOF
   ```

These four values are public web config (they end up in the browser bundle), not secrets.
The backend checks Firebase ID tokens against `FIREBASE_PROJECT_ID`, which the deploy script
sets to the project ID. Both sides must name the same project.

## 7. Google Cloud bootstrap

Run this once in Cloud Shell from the repository folder. It is safe to run again; it skips
what exists and only asks for secrets that are still empty.

```bash
bash deploy/gcp_bootstrap.sh
```

It asks for the Azure SQL server name, the admin login and password, the `kasa_app`
password, the Gemini key and the OAuth client ID and secret. Leave an answer empty to skip
it and run the script again later. It creates:

- **APIs**: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Pub/Sub, Cloud
  Scheduler, Gmail, Calendar, IAM, Identity Toolkit (Firebase Auth) and a few helpers.
- **Artifact Registry** repository `kasa`, with a cleanup policy that keeps the 5 newest
  images.
- **Bucket** `<project>-kasa-build` for Cloud Build uploads (files deleted after 7 days).
- **Service accounts**, each with only what it needs:

  | Account | Used by | Permissions |
  | --- | --- | --- |
  | `kasa-api` | backend service | read its six secrets |
  | `kasa-migrate` | migration job | read `migration-database-url` |
  | `kasa-web` | frontend service | none |
  | `kasa-build` | Cloud Build | push to the `kasa` repo, read the build bucket, write logs |
  | `kasa-pubsub-push` | Pub/Sub push token | none (only its identity is used) |

- **Secrets** in Secret Manager: `database-url`, `migration-database-url`,
  `gemini-api-key`, `google-oauth-client-id`, `google-oauth-client-secret`, and two it
  generates itself: `token-encryption-key` (`TOKEN_ENCRYPTION_KEY`, the Fernet key for
  stored Google refresh tokens) and `internal-task-token` (`INTERNAL_TASK_TOKEN`). Do not
  change the encryption key later: tokens encrypted with the old key cannot be read and
  every user would have to reconnect Google.
- **Pub/Sub** for Gmail push (skipped with `ENABLE_GMAIL_PUSH=false`): topic `kasa-gmail`,
  publish rights on it for Gmail's own account, and a push subscription that sends each
  message to the backend with a Google-signed OIDC token. The backend checks that token's
  audience and service account. The core commands are:

  ```bash
  gcloud pubsub topics create kasa-gmail
  gcloud pubsub topics add-iam-policy-binding kasa-gmail \
    --member serviceAccount:gmail-api-push@system.gserviceaccount.com --role roles/pubsub.publisher
  gcloud pubsub subscriptions create kasa-gmail-push --topic kasa-gmail \
    --push-endpoint "$API_URL/internal/gmail/push" \
    --push-auth-service-account "kasa-pubsub-push@$PROJECT_ID.iam.gserviceaccount.com" \
    --push-auth-token-audience "$API_URL/internal/gmail/push" --ack-deadline 30
  ```

- **Cloud Scheduler** jobs, time zone Europe/Istanbul, each a `POST` with the header
  `X-Kasa-Task-Token: <internal-task-token>`:

  | Job | Default schedule | Endpoint | Deadline |
  | --- | --- | --- | --- |
  | `kasa-gmail-sync-all` | every 6 hours (`SYNC_SCHEDULE`) | `/internal/gmail/sync-all` | 900 s |
  | `kasa-gmail-renew-watches` | daily 08:10 | `/internal/gmail/renew-watches` | 180 s |
  | `kasa-fx-refresh` | daily 16:00 | `/internal/fx/refresh` | 180 s |

  The sync job gets a long deadline because it parses every new email with Gemini. Gmail
  watches expire after 7 days, so the daily renewal keeps push alive. TCMB publishes the
  day's exchange rates around 15:30. The token is stored in the job settings, where project
  viewers can see it; anyone else gets 401 from `/internal/*`.

When it finishes it prints the URLs and lists any secret that is still empty.

## 8. Deploy the backend

```bash
bash deploy/deploy_backend.sh
```

The first run takes about ten minutes. The script:

1. Stops if `database-url` or `migration-database-url` is empty.
2. Builds `backend/Dockerfile` with Cloud Build as `kasa-build` and pushes
   `europe-west1-docker.pkg.dev/<project>/kasa/api:<git commit>`.
3. Deploys the Cloud Run job `kasa-migrate` from the same image with the command
   `alembic upgrade head` and only `MIGRATION_DATABASE_URL` mounted, then runs it and waits.
   A failed migration stops the script before any new code serves traffic.
4. Deploys the service `kasa-api` with `AUTO_MIGRATE=false`, `LLM_PROVIDER=gemini`,
   `FIREBASE_PROJECT_ID`, `CORS_ORIGINS` and `FRONTEND_URL` set to the frontend URL,
   `GOOGLE_OAUTH_REDIRECT_URI`, the three `PUBSUB_*` settings, and the six secrets mounted as
   env vars (`DATABASE_URL`, `GOOGLE_API_KEY`, `TOKEN_ENCRYPTION_KEY`,
   `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `INTERNAL_TASK_TOKEN`). A secret
   that is still empty is left out, and the feature behind it reports itself as not
   configured.
5. Calls `/health`.

Service settings and why:

| Setting | Value | Reason |
| --- | --- | --- |
| CPU, memory | 1 vCPU, 1 GiB | ADK, the Google clients and pyodbc do not fit well in 512 MiB |
| Concurrency | 20 | requests mostly wait on Gemini and the database |
| Timeout | 900 s | `sync-all` makes one Gemini call per new email |
| Max instances | 1 | chat sessions live in instance memory, and it caps the cost |
| `--no-cpu-throttling` | on | see below |
| `--allow-unauthenticated` | on | the app checks Firebase tokens, the push token and the task token itself |

`--no-cpu-throttling` is needed because two endpoints keep working after they answer:
`POST /internal/gmail/push` replies 204 at once and parses the email in a background task,
and the OAuth callback starts the first Gmail sync the same way. With the default
request-based billing Cloud Run throttles the CPU as soon as the response is sent, and that
work would stall. Instance-based billing keeps the CPU on while the instance lives. Instances
still scale to zero when there is no traffic.

## 9. Deploy the frontend

```bash
bash deploy/deploy_frontend.sh
```

`NEXT_PUBLIC_*` values are baked into the bundle at build time, so the script passes
`NEXT_PUBLIC_API_URL` (the backend URL) and the four Firebase values as Docker build args,
then deploys `kasa-web` (512 MiB, scales to zero). It stops if the Firebase values are
missing, since the production API rejects the dev user box.

To redeploy after a code change, `git pull` in Cloud Shell and run the script for the part
that changed. Run the backend first when both changed.

## 10. GitHub Actions deploy (optional)

`.github/workflows/deploy.yml` deploys from GitHub with a manual button and no JSON keys.
GitHub hands the job a short-lived OIDC token, Google's Workload Identity Federation trades
it for credentials of the `kasa-deployer` service account, and only workflows from `main` of
your repository are accepted.

One-time setup:

1. In Cloud Shell:

   ```bash
   GITHUB_REPO=berkekcay/Kasa-Expense-Agent bash deploy/gcp_bootstrap.sh
   ```

   Besides the usual work this creates the identity pool `github`, the provider `kasa-repo`
   (condition: this repository and `refs/heads/main`), and `kasa-deployer` with:
   Cloud Run Admin, Secret Manager Viewer (lists secret versions, cannot read values),
   Artifact Registry Writer on the `kasa` repo, and Service Account User on `kasa-api`,
   `kasa-migrate` and `kasa-web` only. The workflow builds images with Docker on the runner,
   so the deployer needs no Cloud Build or Storage roles.
2. In GitHub, **Settings > Secrets and variables > Actions > Variables**, add the variables
   the script printed (`GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_REGION`,
   `GCP_WIF_PROVIDER`, `GCP_DEPLOYER_SA`) and the four `NEXT_PUBLIC_FIREBASE_*` values. With
   the GitHub CLI: `gh variable set GCP_PROJECT_ID --body <value>` and so on.
3. Run it from **Actions > Deploy > Run workflow** on `main`, choosing backend, frontend or
   both.

## 11. Smoke test

Run these in Cloud Shell after `source deploy/config.sh`:

- [ ] `curl -s "$API_URL/health"` shows `"status":"ok"`, `"agents_enabled":true` and
  `"auth":"firebase"`.
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' "$API_URL/expenses"` prints `401`.
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$API_URL/internal/fx/refresh"`
  prints `401` (no task token).
- [ ] `gcloud run jobs executions list --job kasa-migrate --region "$REGION"` shows a
  successful run.
- [ ] `gcloud scheduler jobs run kasa-fx-refresh --location "$REGION"`, then the job shows
  a successful last run in **Cloud Scheduler** and a 200 in the `kasa-api` logs.

Then in the browser, at `$WEB_URL`, signed in as a test user:

- [ ] Google sign-in works and the nav bar shows your name, not the dev user box.
- [ ] Add an expense by hand; it appears in the list.
- [ ] Upload a receipt photo; the receipt agent saves it (first live Gemini call).
- [ ] Ask the chat "bu ay kategoriye göre ne kadar harcadım?"; a chart comes back.
- [ ] Create a house, add a second test user, add a shared expense. The second user signs in
  and sees the same balances, and a third account does not see the house.
- [ ] **Settings > Connect Google**, accept the scopes, and land back on Settings with
  Google connected and a Gmail watch expiry date.
- [ ] Send yourself an email with "Sipariş" or "Order" in the subject. An inbox item appears
  within a minute (push) or after you press the Gmail sync button in Settings.
- [ ] Row-level security, in the Azure query editor as the admin:

  ```sql
  SELECT name, is_enabled FROM sys.security_policies;   -- kasa_policy, 1
  SELECT COUNT(*) FROM dbo.expenses;                    -- 0: no user in SESSION_CONTEXT
  EXEC sp_set_session_context @key = N'user_id', @value = N'<your Firebase UID>';
  SELECT COUNT(*) FROM dbo.expenses;                    -- your expenses only
  ```

  The UID is in **Firebase console > Authentication > Users**.
- [ ] Leave the app alone until the portal shows the database as **Paused**, then reload
  Kasa. The first page takes up to a minute and then works.

## Free limits and costs

Prices and limits change; check the pages of each service.

- **Azure SQL free offer**: 100,000 vCore seconds of compute and 32 GB of storage per
  database per month. While the database is awake it is billed at least its minimum vCores
  (see **Compute + storage**). At 0.5 vCores that is about 55 hours awake per month, under
  two hours a day. An hourly `sync-all` job, or Gmail push for active mailboxes, keeps the
  database from pausing, and the free amount runs out within days; the database then stays
  paused until the next month. That is why the defaults are a sync every 6 hours and push
  off. To turn push on for a demo, set in `deploy/config.local.sh`:

  ```bash
  ENABLE_GMAIL_PUSH=true        # new mail within seconds
  ```

  then run `bash deploy/gcp_bootstrap.sh` and `bash deploy/deploy_backend.sh` again. The
  database **Overview** page shows how much of the free amount is left.
- **Cloud Run**: a monthly free allowance of vCPU and memory seconds. Instance-based billing
  (`--no-cpu-throttling`) counts the whole time an instance is up, which is still small for a
  handful of users because instances scale to zero.
- **Artifact Registry**: 0.5 GB free; the cleanup policy keeps it near that.
- **Cloud Scheduler**: 3 free jobs per billing account, which is exactly what Kasa uses.
- **Secret Manager**: a few active secret versions are free; Kasa's seven cost cents.
- **Cloud Build, Pub/Sub, Firebase Auth**: Kasa's use fits the free tiers.
- **Gemini**: free tier with rate limits, or paid per token (step 3).

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Every API call is 401 after sign-in | `NEXT_PUBLIC_FIREBASE_PROJECT_ID` and the backend's `FIREBASE_PROJECT_ID` name different projects |
| `auth/unauthorized-domain` on sign-in | add the frontend host to Firebase authorized domains (step 6) |
| CORS error in the browser console | `CORS_ORIGINS` must equal the frontend URL exactly, without a trailing slash |
| `redirect_uri_mismatch` from Google | the OAuth client needs `<API_URL>/integrations/google/callback` (step 5.2) |
| `Login failed for user 'kasa_app'` | the user was created in `master` instead of `kasa`, or the password differs from the secret |
| Error 40613 for more than two minutes | the free amount is used up and the database is paused until next month |
| Migration job failed | open the execution in **Cloud Run > Jobs > kasa-migrate** and read the logs |
| Push logs "unexpected service account" | the subscription's push account differs from `PUBSUB_PUSH_SERVICE_ACCOUNT`; rerun both scripts |
| Scheduler jobs get 401 | the task token changed; rerun `gcp_bootstrap.sh` and `deploy_backend.sh` |

To replace a secret, add a version and redeploy so new instances read it:

```bash
printf '%s' '<new value>' | gcloud secrets versions add gemini-api-key --data-file=-
bash deploy/deploy_backend.sh
```
