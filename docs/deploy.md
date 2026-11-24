# Deploying the API to Cloud Run (task T10)

The API runs on Google Cloud Run as the service `kickstarter-api` in
`us-east1`. One script builds the Docker image and deploys it.

## How it works

1. **Build:** Cloud Build downloads the production model from
   `gs://kickstarter-checker-nw-data/models/<version>/model.joblib`, then
   builds the image from the `Dockerfile` on Google's servers, with the model
   baked in. That gives us a `linux/amd64` image (what Cloud Run runs) even
   from an Apple Silicon Mac. The image is tagged with the git commit it was
   built from and stored in Artifact Registry.
2. **Deploy:** Cloud Run runs a new revision from that image, as the
   least-privilege `kickstarter-api` service account.

| Setting | Value | Why |
| --- | --- | --- |
| Access | Public (`--allow-unauthenticated`) | The Streamlit front-end calls it directly |
| Service account | `kickstarter-api` | Can only write logs; not the default Editor account |
| CPU / memory | 1 vCPU / 1 GiB | Enough for pandas + scikit-learn |
| Instances | 0 to 2 | Scales to zero when idle (cost ~$0); capped at 2 to limit cost and abuse |
| Image tag | git short SHA (`-dirty` if uncommitted changes) | Every revision traces back to exact code |

## Prerequisites

- `docs/cloud-setup.md` completed (project, APIs, Artifact Registry, service account)
- Logged in as a project owner: `gcloud auth login`
- Run from the repo root on a clean, committed branch

## Deploy

```bash
./scripts/deploy_api.sh        # production model v1 (models/v1/model.joblib)
```

The script checks that `/health` reports the expected `model_version` and
fails otherwise.

The first build takes ~5 minutes; the script ends with a `/health` check and
prints the API URL.

## Verify

```bash
URL=$(gcloud run services describe kickstarter-api --region us-east1 --format 'value(status.url)')
curl -s "$URL/health"
curl -s -X POST "$URL/predict" -H "Content-Type: application/json" -d @scripts/sample_request.json
```

Interactive docs are at `$URL/docs`.

## Updating the model (task T15)

The production model is published by training (`python -m src.train --promote`
logs it to W&B with the `production` alias) and then copied to a versioned
path in the data bucket, which the build reads:

```bash
# 1. Publish a new version (never overwrite an existing one)
wandb artifact get <entity>/kickstarter-launch-checker/kickstarter-model:production --root /tmp/prod
gcloud storage cp /tmp/prod/model.joblib gs://kickstarter-checker-nw-data/models/v2/model.joblib

# 2. Deploy it (same URL; roll back with the revision commands above)
MODEL_VERSION=v2 ./scripts/deploy_api.sh
```

The model file must be trained with the same scikit-learn and XGBoost
versions pinned in `requirements.txt`, or the API can't load it.

Without a downloaded model (CI, plain `docker build`), the Dockerfile falls
back to the placeholder model. It refuses to build if a model file is present
without a version label, or a version label is set without a model file, so
a placeholder can never be deployed under a real version name.

To build the real model locally:

```bash
mkdir -p model-artifact
gcloud storage cp gs://kickstarter-checker-nw-data/models/v1/model.joblib model-artifact/model.joblib
docker build --build-arg MODEL_VERSION=v1 -t kickstarter-api .
```

`model-artifact/` is gitignored.

## Cold starts

With minimum instances at 0, the first request after ~15 idle minutes takes a
few seconds while a container starts and loads the model. For a live demo,
keep one instance warm, then turn it back off afterwards (a warm instance is billed):

```bash
gcloud run services update kickstarter-api --region us-east1 --min-instances 1   # before demo
gcloud run services update kickstarter-api --region us-east1 --min-instances 0   # after
```

## Roll back

Each deploy creates a new revision; old ones stay available.

```bash
gcloud run revisions list --service kickstarter-api --region us-east1
gcloud run services update-traffic kickstarter-api --region us-east1 --to-revisions REVISION_NAME=100
```

## Logs

```bash
gcloud run services logs read kickstarter-api --region us-east1 --limit 50
```

## Troubleshooting

- **Build fails copying the model (403 / permission denied on the bucket):**
  the Cloud Build service account can't read the bucket. Find its email in
  the error, then grant read access:
  `gcloud storage buckets add-iam-policy-binding gs://kickstarter-checker-nw-data --member=serviceAccount:<email> --role=roles/storage.objectViewer`

- **Build fails with a permission error on Artifact Registry or logs:** the
  Cloud Build service account is missing roles. Fallback: build locally with
  `docker buildx build --platform linux/amd64 -t IMAGE --push .` after
  `gcloud auth configure-docker us-east1-docker.pkg.dev`, then run only the
  `gcloud run deploy` command from the script.
- **Deploy says the container failed to start:** read the logs (above). The
  usual cause is the app not listening on `$PORT`; the entrypoint handles this.

## Front-end (Streamlit Community Cloud, task T16)

**Live app:** https://aipi-510-kickstarter-launch-checker.streamlit.app

Deployed from the `main` branch; every merge to `main` redeploys it automatically.

Settings used (on share.streamlit.io, **Create app → Deploy a public app from GitHub**):

| Setting | Value |
| --- | --- |
| Repository / branch | `gitnic-duke/aipi-510-kickstarter-launch-checker` / `main` |
| Main file path | `frontend/app.py` (dependencies come from `frontend/requirements.txt`) |
| Python version | 3.11 |
| Secrets | `API_URL = "https://kickstarter-api-zcqiii5fia-ue.a.run.app"` |

The app reads `API_URL` from Streamlit secrets (or the `API_URL` environment
variable locally), so pointing it at a different API needs no code change:
edit the secret under **App settings → Secrets** and the app restarts.

Streamlit apps sleep after a period with no visitors; the first visitor wakes
it with one click, which takes ~30 seconds.
