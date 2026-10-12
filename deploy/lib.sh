# Helpers shared by the deploy scripts. Sourced after `set -euo pipefail`.

# shellcheck source=deploy/config.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/config.sh"

# cloudbuild (default; Cloud Shell) or docker (GitHub Actions runner: plain docker build/push,
# so the deploy identity needs no Cloud Build or Storage roles).
BUILDER="${BUILDER:-cloudbuild}"

step() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# retry <command...>: IAM changes on a service account that was just created can fail for a
# few seconds until the account has propagated.
retry() {
  local n
  for n in 1 2 3 4 5 6; do
    if "$@"; then return 0; fi
    [[ $n == 6 ]] && return 1
    info "retrying in 5s ($n/5)"
    sleep 5
  done
}

secret_has_value() {
  [[ -n "$(gcloud secrets versions list "$1" --project "$PROJECT_ID" --filter='state=ENABLED' \
    --limit=1 --format='value(name)' 2>/dev/null)" ]]
}

# build_image <context dir> <image> <cloud build config> [KEY=VALUE build args...]
build_image() {
  local context=$1 image=$2 config=$3
  shift 3
  if [[ "$BUILDER" == "docker" ]]; then
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    local docker_args=() kv
    for kv in "$@"; do docker_args+=(--build-arg "$kv"); done
    docker build "${docker_args[@]}" -t "$image" "$context"
    docker push "$image"
    return
  fi
  # Cloud Build runs as kasa-build (not the broad default build account). A custom build
  # account must log to Cloud Logging only, which the config files set.
  local subs="_IMAGE=${image}" kv
  for kv in "$@"; do subs+="~_${kv}"; done
  gcloud builds submit "$context" \
    --project "$PROJECT_ID" \
    --config "$config" \
    --substitutions "^~^${subs}" \
    --service-account "projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA}" \
    --gcs-source-staging-dir "gs://${BUILD_BUCKET}/source"
}
