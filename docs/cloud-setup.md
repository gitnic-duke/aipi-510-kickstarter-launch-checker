# Cloud setup (task T2)

One-time setup of the cloud accounts and resources the project uses. Run once
by the project owner; partners only need the "For partners" section.

## What we create

| Resource | Name | Purpose |
| --- | --- | --- |
| GCP project | `kickstarter-checker-nw` | Holds everything below |
| Region | `us-east1` | Closest region to Durham; used for all resources |
| GCS bucket | `gs://kickstarter-checker-nw-data` | `raw/` and versioned `processed/vN/` data. Private, object versioning on |
| Artifact Registry repo | `kickstarter` | Docker images for the API |
| Service account | `kickstarter-api` | Identity the Cloud Run API runs as. Can only write logs |
| Budget alert | $10/month | Email at 50%, 90%, 100% |
| W&B project | `kickstarter-launch-checker` | Experiment tracking and model artifacts |

## 1. Google Cloud account and billing (console, ~10 min)

1. Sign in at https://console.cloud.google.com with a Google account.
2. Go to **Billing** (https://console.cloud.google.com/billing). If a billing account
   is listed (a free trial, education credits or a card), you're set. If not,
   create one. New accounts usually get free-trial credits, and our usage
   should stay within the free tiers of Cloud Run and Cloud Storage.
3. Create the project: **Select a project → New project**, ID `kickstarter-checker-nw`
   (if taken, add a suffix and update `PROJECT_ID` in `scripts/setup_gcp.sh`).
4. Link it to billing: **Billing → Account management → My projects → Change billing**.
5. Budget alert: **Billing → Budgets & alerts → Create budget**, scope = this
   project, amount = $10, alerts at 50%, 90%, 100%.

## 2. Install and authenticate the gcloud CLI (macOS)

Install via the official guide (https://cloud.google.com/sdk/docs/install) or
Homebrew (`brew search gcloud` shows the current cask name). Then:

```bash
gcloud --version
gcloud auth login                        # your user account, for CLI commands
gcloud auth application-default login    # credentials for Python (GCS client)
gcloud config set project kickstarter-checker-nw
```

We use Application Default Credentials locally instead of downloading
service-account key files. Keys are long-lived secrets that are easy to leak,
so this project creates none. Python's `google-cloud-storage` picks up ADC
automatically; `GOOGLE_APPLICATION_CREDENTIALS` is not needed.

## 3. Create the resources

1. Open `scripts/setup_gcp.sh` and check the variables at the top. Add your
   partner's Google account email to `PARTNER_EMAILS`.
2. Run it from the repo root:

```bash
./scripts/setup_gcp.sh
```

It enables the needed APIs, creates the private versioned bucket, the Artifact
Registry repo and the runtime service account, and grants partners access.
It is safe to re-run.

## 4. Verify

```bash
gcloud storage buckets describe gs://kickstarter-checker-nw-data \
  --format="value(versioning_enabled, public_access_prevention, location)"
# expect: True  enforced  US-EAST1

gcloud artifacts repositories list --location=us-east1     # shows "kickstarter"
gcloud iam service-accounts list | grep kickstarter-api
echo "hello" | gcloud storage cp - gs://kickstarter-checker-nw-data/tmp/hello.txt
gcloud storage cat gs://kickstarter-checker-nw-data/tmp/hello.txt
```

## 5. Weights & Biases

Owned by Partner A (who runs training).

1. Sign in at https://wandb.ai (GitHub login works).
2. Create the project `kickstarter-launch-checker` under a team both partners
   belong to, or under Partner A's personal account with visibility set so
   Partner B can view runs and download the model artifact (needed for T15).
3. Locally: `wandb login` and paste the key from https://wandb.ai/authorize.
   Put `WANDB_ENTITY` (team or username) in your `.env`.

## For partners

Your Google account email must be added by the owner (step 3). Then:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project kickstarter-checker-nw
gcloud storage ls gs://kickstarter-checker-nw-data    # should succeed
```

## Security and cost notes

- Bucket is private (public access prevention enforced) and uses uniform
  bucket-level access; object versioning protects against overwrites.
- No service-account keys exist; local access uses each person's own login.
- The Cloud Run API runs as `kickstarter-api`, not the default compute
  service account (which has broad Editor rights).
- Partners get project Viewer plus read/write on the data bucket only.
- Cloud Run scales to zero when idle, so cost stays near $0; the budget alert
  catches surprises.

## Teardown (after grading)

```bash
gcloud projects delete kickstarter-checker-nw
```
