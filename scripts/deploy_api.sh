#!/usr/bin/env bash
# Build the API image with Cloud Build and deploy it to Cloud Run (tasks T10, T15).
# Run from the repo root, logged in as a project owner (see docs/deploy.md).
#   ./scripts/deploy_api.sh                                   # production model v1
#   MODEL_VERSION=v2 MODEL_URI=gs://.../models/v2/model.joblib ./scripts/deploy_api.sh
#   MODEL_VERSION=placeholder-v0 MODEL_URI= ./scripts/deploy_api.sh   # placeholder
set -euo pipefail

# ---- Settings (match scripts/setup_gcp.sh) ----
PROJECT_ID="kickstarter-checker-nw"
REGION="us-east1"
AR_REPO="kickstarter"
SERVICE="kickstarter-api"
RUNTIME_SA="kickstarter-api@${PROJECT_ID}.iam.gserviceaccount.com"
MODEL_VERSION="${MODEL_VERSION-v1}"
MODEL_URI="${MODEL_URI-gs://${PROJECT_ID}-data/models/${MODEL_VERSION}/model.joblib}"
# -----------------------------------------------

# Tag every image with the git commit it was built from, so any running
# revision can be traced back to exact code. Uncommitted changes are flagged.
TAG="$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  TAG="${TAG}-dirty"
  echo "WARNING: uncommitted changes; image will be tagged ${TAG}"
fi
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/api:${TAG}"

echo "==> Building ${IMAGE} (model ${MODEL_VERSION} from ${MODEL_URI:-placeholder}) with Cloud Build"
gcloud builds submit . \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions="_IMAGE=${IMAGE},_MODEL_VERSION=${MODEL_VERSION},_MODEL_URI=${MODEL_URI}"

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
HEALTH="$(curl -sf "${URL}/health")"
echo "$HEALTH"
if ! grep -q "\"model_version\":\"${MODEL_VERSION}\"" <<<"$HEALTH"; then
  echo "ERROR: expected model_version ${MODEL_VERSION} in /health" >&2
  exit 1
fi
echo "Deployed ${IMAGE}"
echo "API URL: ${URL}   (docs: ${URL}/docs)"
