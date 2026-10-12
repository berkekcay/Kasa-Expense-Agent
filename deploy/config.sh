# Shared settings for the Kasa deploy scripts. Sourced by gcp_bootstrap.sh, deploy_backend.sh
# and deploy_frontend.sh. Every value can be overridden by exporting it first, or by putting
# it in deploy/config.local.sh (gitignored), which is read before the defaults below.
#
#   source deploy/config.sh && echo "$API_URL"     # print the URLs without deploying
#
# Nothing in here is secret. Secrets live in Secret Manager (see gcp_bootstrap.sh).

_KASA_DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$_KASA_DEPLOY_DIR/config.local.sh" ]]; then
  # shellcheck source=/dev/null
  source "$_KASA_DEPLOY_DIR/config.local.sh"
fi
KASA_ROOT="$(cd "$_KASA_DEPLOY_DIR/.." && pwd)"

# --- Project ---------------------------------------------------------------------------------
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-europe-west1}"
if [[ -z "$PROJECT_ID" ]]; then
  echo "PROJECT_ID is not set. Run: gcloud config set project <your-project-id>" >&2
  return 1 2>/dev/null || exit 1
fi
# The deploy service account in GitHub Actions cannot read project metadata, so the workflow
# passes PROJECT_NUMBER in; locally it is looked up.
PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')}"

# --- Names -----------------------------------------------------------------------------------
REPO="${REPO:-kasa}"                       # Artifact Registry Docker repository
API_SERVICE="${API_SERVICE:-kasa-api}"     # Cloud Run service, backend
WEB_SERVICE="${WEB_SERVICE:-kasa-web}"     # Cloud Run service, frontend
MIGRATE_JOB="${MIGRATE_JOB:-kasa-migrate}" # Cloud Run job, `alembic upgrade head`
BUILD_BUCKET="${BUILD_BUCKET:-${PROJECT_ID}-kasa-build}"  # Cloud Build source uploads
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# Cloud Run URLs are predictable (https://<service>-<project number>.<region>.run.app), so the
# OAuth redirect URI, CORS origin and Pub/Sub endpoint can be set before the first deploy.
# Override these if you put the services behind a custom domain.
API_URL="${API_URL:-https://${API_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app}"
WEB_URL="${WEB_URL:-https://${WEB_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app}"

# --- Service accounts (created by gcp_bootstrap.sh) ------------------------------------------
SA_DOMAIN="${PROJECT_ID}.iam.gserviceaccount.com"
API_SA="kasa-api@${SA_DOMAIN}"           # backend runtime: reads its secrets, nothing else
MIGRATE_SA="kasa-migrate@${SA_DOMAIN}"   # migration job: reads the admin DB URL only
WEB_SA="kasa-web@${SA_DOMAIN}"           # frontend runtime: no permissions
BUILD_SA="kasa-build@${SA_DOMAIN}"       # Cloud Build: pushes images, writes build logs
PUSH_SA="kasa-pubsub-push@${SA_DOMAIN}"  # identity in the Pub/Sub push OIDC token
DEPLOYER_SA="kasa-deployer@${SA_DOMAIN}" # GitHub Actions (Workload Identity Federation)

# --- Secrets: Secret Manager name -> backend env var -----------------------------------------
SECRET_DATABASE_URL="database-url"                  # DATABASE_URL, low-privilege app user
SECRET_MIGRATION_URL="migration-database-url"       # MIGRATION_DATABASE_URL, admin, job only
SECRET_GEMINI="gemini-api-key"                      # GOOGLE_API_KEY
SECRET_TOKEN_KEY="token-encryption-key"             # TOKEN_ENCRYPTION_KEY
SECRET_OAUTH_ID="google-oauth-client-id"            # GOOGLE_OAUTH_CLIENT_ID
SECRET_OAUTH_SECRET="google-oauth-client-secret"    # GOOGLE_OAUTH_CLIENT_SECRET
SECRET_TASK_TOKEN="internal-task-token"             # INTERNAL_TASK_TOKEN
# "ENV_VAR=secret-name" pairs mounted on the backend service (when the secret has a value).
API_SECRETS=(
  "DATABASE_URL=${SECRET_DATABASE_URL}"
  "GOOGLE_API_KEY=${SECRET_GEMINI}"
  "TOKEN_ENCRYPTION_KEY=${SECRET_TOKEN_KEY}"
  "GOOGLE_OAUTH_CLIENT_ID=${SECRET_OAUTH_ID}"
  "GOOGLE_OAUTH_CLIENT_SECRET=${SECRET_OAUTH_SECRET}"
  "INTERNAL_TASK_TOKEN=${SECRET_TASK_TOKEN}"
)

# --- Backend settings (plain env vars) -------------------------------------------------------
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-$PROJECT_ID}"  # same project unless you split them
CORS_ORIGINS="${CORS_ORIGINS:-$WEB_URL}"  # comma-separated browser origins allowed to call the API
API_MEMORY="${API_MEMORY:-1Gi}"
API_CPU="${API_CPU:-1}"
# A chat turn can wait on Gemini several times (agent, checker, retries); keep this modest so
# one instance's threads are not all stuck behind slow LLM calls.
API_CONCURRENCY="${API_CONCURRENCY:-20}"
# Must cover the longest request, POST /internal/gmail/sync-all (an LLM call per email).
API_TIMEOUT="${API_TIMEOUT:-900}"
# ADK chat sessions live in the instance's memory, so a conversation only continues while it
# keeps hitting the same instance. One instance keeps chats intact and caps the cost.
API_MAX_INSTANCES="${API_MAX_INSTANCES:-1}"
WEB_MAX_INSTANCES="${WEB_MAX_INSTANCES:-2}"

# --- Gmail push (Pub/Sub) and Cloud Scheduler ------------------------------------------------
# false (default) = no Gmail watch and no push; new mail is found by the scheduled sync only.
# Every push wakes the database and uses Azure SQL free compute, so turn it on only when you
# need new mail to show up within seconds, e.g. for a demo (see docs/SETUP.md).
ENABLE_GMAIL_PUSH="${ENABLE_GMAIL_PUSH:-false}"
PUBSUB_TOPIC_NAME="${PUBSUB_TOPIC_NAME:-kasa-gmail}"
PUBSUB_SUBSCRIPTION="${PUBSUB_SUBSCRIPTION:-kasa-gmail-push}"
PUBSUB_TOPIC="projects/${PROJECT_ID}/topics/${PUBSUB_TOPIC_NAME}"
PUSH_ENDPOINT="${API_URL}/internal/gmail/push"
PUSH_AUDIENCE="${PUSH_AUDIENCE:-$PUSH_ENDPOINT}"
SCHEDULER_TZ="${SCHEDULER_TZ:-Europe/Istanbul}"
# Every 6 hours fits the Azure SQL free allowance; an hourly sync ("0 * * * *") keeps a
# serverless database awake around the clock (see "Free limits" in docs/SETUP.md).
SYNC_SCHEDULE="${SYNC_SCHEDULE:-0 */6 * * *}"
RENEW_SCHEDULE="${RENEW_SCHEDULE:-10 8 * * *}"  # Gmail watches expire after 7 days
FX_SCHEDULE="${FX_SCHEDULE:-0 16 * * *}"        # TCMB publishes the day's rates around 15:30
SYNC_DEADLINE="${SYNC_DEADLINE:-900s}"           # Scheduler waits this long for sync-all

# --- Frontend build (public values, baked into the bundle) -----------------------------------
# From Firebase console > Project settings > Your apps > Web app. Not secrets.
NEXT_PUBLIC_FIREBASE_API_KEY="${NEXT_PUBLIC_FIREBASE_API_KEY:-}"
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN:-${PROJECT_ID}.firebaseapp.com}"
NEXT_PUBLIC_FIREBASE_PROJECT_ID="${NEXT_PUBLIC_FIREBASE_PROJECT_ID:-$FIREBASE_PROJECT_ID}"
NEXT_PUBLIC_FIREBASE_APP_ID="${NEXT_PUBLIC_FIREBASE_APP_ID:-}"

# --- GitHub Actions (optional) ---------------------------------------------------------------
# "owner/repo" allowed to deploy through Workload Identity Federation. Empty = skip that part.
GITHUB_REPO="${GITHUB_REPO:-}"
WIF_POOL="${WIF_POOL:-github}"
WIF_PROVIDER="${WIF_PROVIDER:-kasa-repo}"

# Image tag: the git commit when available, else a timestamp.
TAG="${TAG:-$(git -C "$KASA_ROOT" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
