#!/usr/bin/env bash
# Build the backend image, migrate the database with a Cloud Run job, then deploy the
# kasa-api service. Run from Cloud Shell (or GitHub Actions) after gcp_bootstrap.sh:
#
#   bash deploy/deploy_backend.sh
#
# Settings: deploy/config.sh. Secrets come from Secret Manager and are mounted as env vars.
set -euo pipefail
# shellcheck source=deploy/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

IMAGE="${IMAGE_BASE}/api:${TAG}"

step "Checking secrets"
for required in "$SECRET_DATABASE_URL" "$SECRET_MIGRATION_URL"; do
  secret_has_value "$required" || die "secret ${required} is empty; run deploy/gcp_bootstrap.sh first"
done
api_secrets=()
for pair in "${API_SECRETS[@]}"; do
  if secret_has_value "${pair#*=}"; then
    api_secrets+=("${pair}:latest")
  else
    info "not set: ${pair%%=*} (secret ${pair#*=} is empty)"
  fi
done
secret_has_value "$SECRET_GEMINI" || info "without ${SECRET_GEMINI}, /chat and /receipts answer 503"
# AUTH_MODE=accounts below: every request needs a sign-in session. Accounts need both keys.
secret_has_value "$SECRET_TOKEN_KEY" || die "${SECRET_TOKEN_KEY} is empty; run deploy/gcp_bootstrap.sh"
secret_has_value "$SECRET_AUTH" || die "${SECRET_AUTH} is empty; run deploy/gcp_bootstrap.sh"

step "Building ${IMAGE} (${BUILDER})"
build_image "$KASA_ROOT/backend" "$IMAGE" "$KASA_ROOT/deploy/cloudbuild-backend.yaml"

# The app's database user cannot run DDL, so the schema is migrated here with the admin URL,
# before the new code starts serving. The job runs the same image with another command.
step "Migrating the database (Cloud Run job ${MIGRATE_JOB})"
gcloud run jobs deploy "$MIGRATE_JOB" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$MIGRATE_SA" \
  --set-secrets "MIGRATION_DATABASE_URL=${SECRET_MIGRATION_URL}:latest" \
  --command alembic \
  --args upgrade,head \
  --tasks 1 \
  --max-retries 1 \
  --task-timeout 600s \
  --cpu 1 \
  --memory 1Gi \
  --quiet
gcloud run jobs execute "$MIGRATE_JOB" --region "$REGION" --wait

env_vars=(
  "AUTO_MIGRATE=false"
  "LLM_PROVIDER=gemini"
  "GEMINI_MODEL=${GEMINI_MODEL}"
  "AUTH_MODE=accounts"
  "CORS_ORIGINS=${CORS_ORIGINS}"
  "FRONTEND_URL=${WEB_URL}"
  "GOOGLE_OAUTH_REDIRECT_URI=${API_URL}/integrations/google/callback"
  "GOOGLE_LOGIN_REDIRECT_URI=${API_URL}/auth/google/callback"
)
[[ -z "$FIREBASE_PROJECT_ID" ]] || env_vars+=("FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID}")
if [[ "$ENABLE_GMAIL_PUSH" == "true" ]]; then
  env_vars+=(
    "PUBSUB_TOPIC=${PUBSUB_TOPIC}"
    "PUBSUB_PUSH_AUDIENCE=${PUSH_AUDIENCE}"
    "PUBSUB_PUSH_SERVICE_ACCOUNT=${PUSH_SA}"
  )
fi
# "^@^" makes @ the separator, so values may contain commas (several CORS origins).
env_flag="^@^$(IFS=@; echo "${env_vars[*]}")"
secrets_flag="$(IFS=,; echo "${api_secrets[*]}")"

# Why these flags:
# --no-cpu-throttling  POST /internal/gmail/push answers 204 at once and parses the mail in a
#                      background task, and the OAuth callback starts the first Gmail sync the
#                      same way. With request-based billing Cloud Run starves the CPU as soon as
#                      the response is sent, so that work would stall. Instance-based billing
#                      keeps the CPU on; instances still scale to zero when idle.
# --timeout 900        sync-all makes one Gemini call per new email.
# --concurrency 20     requests mostly wait on Gemini and the database.
# --max-instances 1    ADK chat sessions are kept in instance memory (see config.sh).
# --allow-unauthenticated  the browser, Pub/Sub and Cloud Scheduler call the API directly;
#                      the app checks a Kasa session, the push OIDC token or the task token.
step "Deploying service ${API_SERVICE}"
gcloud run deploy "$API_SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$API_SA" \
  --allow-unauthenticated \
  --cpu "$API_CPU" \
  --memory "$API_MEMORY" \
  --concurrency "$API_CONCURRENCY" \
  --timeout "$API_TIMEOUT" \
  --min-instances 0 \
  --max-instances "$API_MAX_INSTANCES" \
  --no-cpu-throttling \
  --cpu-boost \
  --set-env-vars "$env_flag" \
  --set-secrets "$secrets_flag" \
  --quiet

step "Health check"
if curl -fsS --max-time 60 "${API_URL}/health"; then
  echo
else
  info "no answer from ${API_URL}/health yet; compare with: gcloud run services describe ${API_SERVICE} --region ${REGION} --format='value(status.url)'"
fi
info "Backend: ${API_URL}"
