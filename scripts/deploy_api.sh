#!/usr/bin/env bash
# Build the API image with Cloud Build and deploy it to Cloud Run (task T10).
# Run from the repo root, logged in as a project owner (see docs/deploy.md).
#   ./scripts/deploy_api.sh                      # placeholder model
#   MODEL_VERSION=v3 ./scripts/deploy_api.sh     # label for a real model (T15)
set -euo pipefail

# ---- Settings (match scripts/setup_gcp.sh) ----
PROJECT_ID="kickstarter-checker-nw"
REGION="us-east1"
AR_REPO="kickstarter"
SERVICE="kickstarter-api"
RUNTIME_SA="kickstarter-api@${PROJECT_ID}.iam.gserviceaccount.com"
MODEL_VERSION="${MODEL_VERSION:-placeholder-v0}"
# -----------------------------------------------

# Tag every image with the git commit it was built from, so any running
# revision can be traced back to exact code. Uncommitted changes are flagged.
TAG="$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  TAG="${TAG}-dirty"
  echo "WARNING: uncommitted changes; image will be tagged ${TAG}"
fi
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/api:${TAG}"

echo "==> Building ${IMAGE} (model: ${MODEL_VERSION}) with Cloud Build"
gcloud builds submit . \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE},_MODEL_VERSION=${MODEL_VERSION}"

echo "==> Deploying ${SERVICE} to Cloud Run"
# Public (the front-end calls it without auth); runs as the least-privilege
# service account; scales to zero when idle; capped at 2 instances so a
# traffic spike or abuse can't run up costs.
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$IMAGE" \
  --service-account="$RUNTIME_SA" \
  --allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory=1Gi \
  --concurrency=40 \
  --min-instances=0 \
  --max-instances=2 \
  --labels="git-sha=${TAG//[^a-z0-9-]/-}"

URL="$(gcloud run services describe "$SERVICE" --project="$PROJECT_ID" \
  --region="$REGION" --format='value(status.url)')"

echo "==> Smoke test: ${URL}/health"
curl -sf "${URL}/health" && echo
echo "Deployed ${IMAGE}"
echo "API URL: ${URL}   (docs: ${URL}/docs)"
