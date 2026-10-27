#!/usr/bin/env bash
# One-time (and safe to re-run) Google Cloud setup for Kasa. Run it in Cloud Shell from the
# repo root as a project Owner:
#
#   bash deploy/gcp_bootstrap.sh
#
# It enables the APIs, creates the Artifact Registry repo, the service accounts and their
# least-privilege grants, the secrets (asks for values it does not have yet), the Gmail
# Pub/Sub topic and push subscription, the Cloud Scheduler jobs and, with GITHUB_REPO set,
# Workload Identity Federation for the GitHub deploy workflow. Settings: deploy/config.sh.
set -euo pipefail
# shellcheck source=deploy/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

APIS=(
  run.googleapis.com
  cloudbuild.googleapis.com
  artifactregistry.googleapis.com
  secretmanager.googleapis.com
  pubsub.googleapis.com
  cloudscheduler.googleapis.com
  gmail.googleapis.com
  calendar-json.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  sts.googleapis.com
  cloudresourcemanager.googleapis.com
  identitytoolkit.googleapis.com
  storage.googleapis.com
)

step "Project ${PROJECT_ID} (number ${PROJECT_NUMBER}), region ${REGION}"
gcloud config set project "$PROJECT_ID" >/dev/null

step "Enabling APIs (takes a minute the first time)"
gcloud services enable "${APIS[@]}"

# --- Artifact Registry ------------------------------------------------------------------------
step "Artifact Registry repository ${REPO}"
if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION" \
    --description "Kasa container images"
fi
# Keep the 5 newest images and delete the rest after 30 days (0.5 GB is free).
policy_file="$(mktemp)"
cat >"$policy_file" <<'JSON'
[
  {"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 5}},
  {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"tagState": "any", "olderThan": "2592000s"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies "$REPO" --location "$REGION" \
  --policy "$policy_file" --no-dry-run --quiet >/dev/null
rm -f "$policy_file"

# --- Cloud Build source bucket ----------------------------------------------------------------
step "Build source bucket gs://${BUILD_BUCKET}"
if ! gcloud storage buckets describe "gs://${BUILD_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUILD_BUCKET}" --location "$REGION" --uniform-bucket-level-access
fi
lifecycle_file="$(mktemp)"
echo '{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 7}}]}' >"$lifecycle_file"
gcloud storage buckets update "gs://${BUILD_BUCKET}" --lifecycle-file "$lifecycle_file" >/dev/null
rm -f "$lifecycle_file"

# --- Service accounts -------------------------------------------------------------------------
ensure_sa() {  # <email> <display name>
  if ! gcloud iam service-accounts describe "$1" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${1%%@*}" --display-name "$2"
  fi
}
project_role() {  # <member> <role>
  retry gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "$1" --role "$2" \
    --condition=None --quiet >/dev/null
}

step "Service accounts"
ensure_sa "$API_SA" "Kasa backend (Cloud Run)"
ensure_sa "$MIGRATE_SA" "Kasa migrations (Cloud Run job)"
ensure_sa "$WEB_SA" "Kasa frontend (Cloud Run)"
ensure_sa "$BUILD_SA" "Kasa image builds (Cloud Build)"
ensure_sa "$PUSH_SA" "Kasa Gmail push (Pub/Sub OIDC)"

step "Grants for the build account"
project_role "serviceAccount:${BUILD_SA}" roles/logging.logWriter
retry gcloud artifacts repositories add-iam-policy-binding "$REPO" --location "$REGION" \
  --member "serviceAccount:${BUILD_SA}" --role roles/artifactregistry.writer --quiet >/dev/null
retry gcloud storage buckets add-iam-policy-binding "gs://${BUILD_BUCKET}" \
  --member "serviceAccount:${BUILD_SA}" --role roles/storage.objectViewer >/dev/null
# kasa-api, kasa-migrate and kasa-web get no project roles: each reads only its own secrets.

# --- Secrets ----------------------------------------------------------------------------------
ensure_secret() {
  if ! gcloud secrets describe "$1" >/dev/null 2>&1; then
    gcloud secrets create "$1" --replication-policy automatic >/dev/null
    info "created secret $1"
  fi
}
set_secret() {  # <name> <value>
  printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=- >/dev/null
  info "$1: saved"
}
grant_secret() {  # <secret> <service account>
  retry gcloud secrets add-iam-policy-binding "$1" --member "serviceAccount:$2" \
    --role roles/secretmanager.secretAccessor --quiet >/dev/null
}
ask() {  # <prompt> [default]; reads from the terminal, prints the answer
  local answer=""
  if [[ -t 0 ]]; then read -r -p "    $1${2:+ [$2]}: " answer; fi
  printf '%s' "${answer:-${2:-}}"
}
ask_hidden() {
  local answer=""
  if [[ -t 0 ]]; then read -r -s -p "    $1: " answer; echo >&2; fi
  printf '%s' "$answer"
}
already_set() {
  info "$1: already has a value (replace: printf '%s' NEW | gcloud secrets versions add $1 --data-file=-)"
}
# mssql+pyodbc URL for Azure SQL with the user name and password percent-encoded.
mssql_url() {  # <user> <password> <host> <database>
  KASA_U="$1" KASA_P="$2" KASA_H="$3" KASA_D="$4" python3 -c '
import os
from urllib.parse import quote
e = os.environ
print("mssql+pyodbc://%s:%s@%s:1433/%s?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
      % (quote(e["KASA_U"], safe=""), quote(e["KASA_P"], safe=""), e["KASA_H"], quote(e["KASA_D"], safe="")))'
}

step "Secrets (Secret Manager)"
for name in "$SECRET_DATABASE_URL" "$SECRET_MIGRATION_URL" "$SECRET_GEMINI" "$SECRET_TOKEN_KEY" \
  "$SECRET_OAUTH_ID" "$SECRET_OAUTH_SECRET" "$SECRET_TASK_TOKEN"; do
  ensure_secret "$name"
done

if secret_has_value "$SECRET_DATABASE_URL" && secret_has_value "$SECRET_MIGRATION_URL"; then
  already_set "$SECRET_DATABASE_URL"
  already_set "$SECRET_MIGRATION_URL"
else
  info "Azure SQL connection (docs/SETUP.md, step 4). Leave the server empty to skip for now."
  db_server="$(ask "Azure SQL server name, e.g. kasa-sql-berke")"
  if [[ -n "$db_server" ]]; then
    [[ "$db_server" == *.* ]] || db_server="${db_server}.database.windows.net"
    db_name="$(ask "Database name" kasa)"
    if ! secret_has_value "$SECRET_MIGRATION_URL"; then
      admin_user="$(ask "Server admin login (used only by the migration job)")"
      admin_pw="$(ask_hidden "Server admin password")"
      if [[ -n "$admin_user" && -n "$admin_pw" ]]; then
        set_secret "$SECRET_MIGRATION_URL" "$(mssql_url "$admin_user" "$admin_pw" "$db_server" "$db_name")"
      fi
    fi
    if ! secret_has_value "$SECRET_DATABASE_URL"; then
      app_user="$(ask "App database user" kasa_app)"
      app_pw="$(ask_hidden "App database user password")"
      if [[ -n "$app_user" && -n "$app_pw" ]]; then
        set_secret "$SECRET_DATABASE_URL" "$(mssql_url "$app_user" "$app_pw" "$db_server" "$db_name")"
      fi
    fi
    unset admin_pw app_pw
  fi
fi

for pair in "${SECRET_GEMINI}|Gemini API key from https://aistudio.google.com/apikey" \
  "${SECRET_OAUTH_ID}|Google OAuth web client ID (docs/SETUP.md, step 5)" \
  "${SECRET_OAUTH_SECRET}|Google OAuth web client secret"; do
  name="${pair%%|*}"
  if secret_has_value "$name"; then
    already_set "$name"
  else
    value="$(ask_hidden "${pair#*|} (empty = skip)")"
    if [[ -n "$value" ]]; then set_secret "$name" "$value"; else info "$name: skipped"; fi
  fi
done
unset value

# Generated here. Never rotate TOKEN_ENCRYPTION_KEY casually: stored Google refresh tokens
# can only be decrypted with the key that encrypted them (users would have to reconnect).
if secret_has_value "$SECRET_TOKEN_KEY"; then
  already_set "$SECRET_TOKEN_KEY"
else
  set_secret "$SECRET_TOKEN_KEY" \
    "$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
fi
if secret_has_value "$SECRET_AUTH"; then
  already_set "$SECRET_AUTH"
else
  set_secret "$SECRET_AUTH" "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi
if secret_has_value "$SECRET_TASK_TOKEN"; then
  already_set "$SECRET_TASK_TOKEN"
else
  set_secret "$SECRET_TASK_TOKEN" "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi

step "Secret access"
for pair in "${API_SECRETS[@]}"; do
  grant_secret "${pair#*=}" "$API_SA"
done
grant_secret "$SECRET_MIGRATION_URL" "$MIGRATE_SA"
info "kasa-api reads the app secrets; kasa-migrate reads only ${SECRET_MIGRATION_URL}"

# --- Gmail push: Pub/Sub ----------------------------------------------------------------------
if [[ "$ENABLE_GMAIL_PUSH" == "true" ]]; then
  step "Pub/Sub topic ${PUBSUB_TOPIC_NAME} and push subscription ${PUBSUB_SUBSCRIPTION}"
  if ! gcloud pubsub topics describe "$PUBSUB_TOPIC_NAME" >/dev/null 2>&1; then
    gcloud pubsub topics create "$PUBSUB_TOPIC_NAME"
  fi
  # Gmail publishes mailbox changes as this Google-owned account.
  gcloud pubsub topics add-iam-policy-binding "$PUBSUB_TOPIC_NAME" \
    --member serviceAccount:gmail-api-push@system.gserviceaccount.com \
    --role roles/pubsub.publisher >/dev/null
  # Lets Pub/Sub sign push tokens as kasa-pubsub-push (needed on projects made before 2021,
  # harmless on newer ones).
  retry gcloud iam service-accounts add-iam-policy-binding "$PUSH_SA" \
    --member "serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" \
    --role roles/iam.serviceAccountTokenCreator --quiet >/dev/null
  push_args=(
    --push-endpoint "$PUSH_ENDPOINT"
    --push-auth-service-account "$PUSH_SA"
    --push-auth-token-audience "$PUSH_AUDIENCE"
    --ack-deadline 30
  )
  if gcloud pubsub subscriptions describe "$PUBSUB_SUBSCRIPTION" >/dev/null 2>&1; then
    gcloud pubsub subscriptions update "$PUBSUB_SUBSCRIPTION" "${push_args[@]}" >/dev/null
  else
    retry gcloud pubsub subscriptions create "$PUBSUB_SUBSCRIPTION" --topic "$PUBSUB_TOPIC_NAME" \
      "${push_args[@]}" >/dev/null
  fi
  info "push to ${PUSH_ENDPOINT} as ${PUSH_SA}"
else
  step "Gmail push is off (ENABLE_GMAIL_PUSH=false): no Pub/Sub topic"
fi

# --- Cloud Scheduler --------------------------------------------------------------------------
step "Cloud Scheduler jobs (${SCHEDULER_TZ})"
task_token="$(gcloud secrets versions access latest --secret "$SECRET_TASK_TOKEN")"
scheduler_job() {  # <name> <schedule> <path> <attempt deadline>
  local args=(
    --location "$REGION" --schedule "$2" --time-zone "$SCHEDULER_TZ"
    --uri "${API_URL}$3" --http-method POST --attempt-deadline "$4"
  )
  if gcloud scheduler jobs describe "$1" --location "$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$1" "${args[@]}" \
      --update-headers "X-Kasa-Task-Token=${task_token}" --quiet >/dev/null
  else
    gcloud scheduler jobs create http "$1" "${args[@]}" \
      --headers "X-Kasa-Task-Token=${task_token}" --quiet >/dev/null
  fi
  info "$1: '$2' -> POST $3"
}
scheduler_job kasa-gmail-sync-all "$SYNC_SCHEDULE" /internal/gmail/sync-all "$SYNC_DEADLINE"
scheduler_job kasa-gmail-renew-watches "$RENEW_SCHEDULE" /internal/gmail/renew-watches 180s
scheduler_job kasa-fx-refresh "$FX_SCHEDULE" /internal/fx/refresh 180s
unset task_token

# --- GitHub Actions: Workload Identity Federation ---------------------------------------------
if [[ -n "$GITHUB_REPO" ]]; then
  step "Workload Identity Federation for ${GITHUB_REPO} (main branch only)"
  ensure_sa "$DEPLOYER_SA" "Kasa deploys from GitHub Actions"
  if ! gcloud iam workload-identity-pools describe "$WIF_POOL" --location global >/dev/null 2>&1; then
    gcloud iam workload-identity-pools create "$WIF_POOL" --location global \
      --display-name "GitHub Actions"
  fi
  if ! gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" --location global \
    --workload-identity-pool "$WIF_POOL" >/dev/null 2>&1; then
    gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" --location global \
      --workload-identity-pool "$WIF_POOL" \
      --display-name "Kasa repository" \
      --issuer-uri "https://token.actions.githubusercontent.com" \
      --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
      --attribute-condition "assertion.repository == '${GITHUB_REPO}' && assertion.ref == 'refs/heads/main'"
  fi
  pool_path="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}"
  retry gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
    --member "principalSet://iam.googleapis.com/${pool_path}/attribute.repository/${GITHUB_REPO}" \
    --role roles/iam.workloadIdentityUser --quiet >/dev/null
  # Deploys services and runs the migration job; lists (never reads) secret versions.
  project_role "serviceAccount:${DEPLOYER_SA}" roles/run.admin
  project_role "serviceAccount:${DEPLOYER_SA}" roles/secretmanager.viewer
  # The workflow builds with docker on the runner and pushes here.
  retry gcloud artifacts repositories add-iam-policy-binding "$REPO" --location "$REGION" \
    --member "serviceAccount:${DEPLOYER_SA}" --role roles/artifactregistry.writer --quiet >/dev/null
  # May attach the runtime accounts to the services and the job, nothing else.
  for sa in "$API_SA" "$MIGRATE_SA" "$WEB_SA"; do
    retry gcloud iam service-accounts add-iam-policy-binding "$sa" \
      --member "serviceAccount:${DEPLOYER_SA}" --role roles/iam.serviceAccountUser --quiet >/dev/null
  done
  info "Set these as GitHub repository variables (Settings > Secrets and variables > Actions > Variables):"
  info "  GCP_PROJECT_ID=${PROJECT_ID}"
  info "  GCP_PROJECT_NUMBER=${PROJECT_NUMBER}"
  info "  GCP_REGION=${REGION}"
  info "  GCP_WIF_PROVIDER=${pool_path}/providers/${WIF_PROVIDER}"
  info "  GCP_DEPLOYER_SA=${DEPLOYER_SA}"
fi

step "Done"
info "Backend URL:  ${API_URL}"
info "Frontend URL: ${WEB_URL}"
info "OAuth redirect URI: ${API_URL}/integrations/google/callback"
info "Firebase authorized domain: ${WEB_URL#https://}"
for name in "$SECRET_DATABASE_URL" "$SECRET_MIGRATION_URL" "$SECRET_GEMINI" "$SECRET_OAUTH_ID" "$SECRET_OAUTH_SECRET"; do
  secret_has_value "$name" || info "Still empty: ${name} (re-run this script to fill it in)"
done
info "Next: bash deploy/deploy_backend.sh && bash deploy/deploy_frontend.sh"
