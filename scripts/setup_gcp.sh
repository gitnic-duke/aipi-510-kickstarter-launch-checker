#!/usr/bin/env bash
# One-time GCP setup for the Kickstarter Launch Checker (task T2).
# Prereqs (see docs/cloud-setup.md): gcloud installed, `gcloud auth login` done,
# project created and linked to a billing account.
# Safe to re-run: steps that already exist are skipped.
set -euo pipefail

# ---- Edit these ----
PROJECT_ID="kickstarter-checker-nw"
REGION="us-east1"
BUCKET="kickstarter-checker-nw-data"
AR_REPO="kickstarter"                 # Artifact Registry repo for Docker images
RUNTIME_SA="kickstarter-api"          # service account the Cloud Run API runs as
PARTNER_EMAILS=("mihirkosuri9@gmail.com")                   # Google account(s), e.g. ("partner@gmail.com")
# --------------------

echo "==> Using project $PROJECT_ID in $REGION"
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com

echo "==> Creating bucket gs://$BUCKET (private, versioned)"
if ! gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi
gcloud storage buckets update "gs://$BUCKET" --versioning

echo "==> Creating Artifact Registry repo $AR_REPO"
if ! gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker --location="$REGION" \
    --description="Kickstarter Launch Checker images"
fi

echo "==> Creating least-privilege runtime service account $RUNTIME_SA"
SA_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUNTIME_SA" \
    --display-name="Kickstarter API (Cloud Run runtime)"
fi
# The API only needs to write logs. The model is baked into the image, so no
# bucket access. Add roles here only when a task actually needs them.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" --role="roles/logging.logWriter" \
  --condition=None >/dev/null

for EMAIL in "${PARTNER_EMAILS[@]}"; do
  [ -z "$EMAIL" ] && continue
  echo "==> Granting $EMAIL access (project viewer + read/write on the data bucket)"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="user:$EMAIL" --role="roles/viewer" --condition=None >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --member="user:$EMAIL" --role="roles/storage.objectAdmin" >/dev/null
done

echo "==> Done. Verify with the checks in docs/cloud-setup.md"
