#!/usr/bin/env bash
# Build the frontend image with the public NEXT_PUBLIC_* values baked in, then deploy the
# kasa-web service. Run from Cloud Shell (or GitHub Actions):
#
#   bash deploy/deploy_frontend.sh
#
# Settings: deploy/config.sh. Put the Firebase web config in deploy/config.local.sh.
set -euo pipefail
# shellcheck source=deploy/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

IMAGE="${IMAGE_BASE}/web:${TAG}"

# Without the Firebase config the UI falls back to the dev user box, which the production
# API (FIREBASE_PROJECT_ID set) rejects.
[[ -n "$NEXT_PUBLIC_FIREBASE_API_KEY" && -n "$NEXT_PUBLIC_FIREBASE_APP_ID" ]] ||
  die "set NEXT_PUBLIC_FIREBASE_API_KEY and NEXT_PUBLIC_FIREBASE_APP_ID (docs/SETUP.md, step 6)"

step "Building ${IMAGE} (${BUILDER}) for API ${API_URL}"
build_image "$KASA_ROOT/frontend" "$IMAGE" "$KASA_ROOT/deploy/cloudbuild-frontend.yaml" \
  "NEXT_PUBLIC_API_URL=${API_URL}" \
  "NEXT_PUBLIC_FIREBASE_API_KEY=${NEXT_PUBLIC_FIREBASE_API_KEY}" \
  "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN}" \
  "NEXT_PUBLIC_FIREBASE_PROJECT_ID=${NEXT_PUBLIC_FIREBASE_PROJECT_ID}" \
  "NEXT_PUBLIC_FIREBASE_APP_ID=${NEXT_PUBLIC_FIREBASE_APP_ID}"

step "Deploying service ${WEB_SERVICE}"
gcloud run deploy "$WEB_SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --service-account "$WEB_SA" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --concurrency 80 \
  --timeout 60 \
  --min-instances 0 \
  --max-instances "$WEB_MAX_INSTANCES" \
  --quiet

info "Frontend: ${WEB_URL}"
