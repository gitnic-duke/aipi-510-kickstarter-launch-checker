# Deploying the API to Cloud Run (task T10)

The API runs on Google Cloud Run as the service `kickstarter-api` in
`us-east1`. One script builds the Docker image and deploys it.

## How it works

1. **Build:** Cloud Build builds the image from the `Dockerfile` on Google's
   servers. That gives us a `linux/amd64` image (what Cloud Run runs) even
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
./scripts/deploy_api.sh                       # placeholder model
MODEL_VERSION=v3 ./scripts/deploy_api.sh      # after T15: label for the real model
```

The first build takes ~5 minutes; the script ends with a `/health` check and
prints the API URL.

## Verify

```bash
URL=$(gcloud run services describe kickstarter-api --region us-east1 --format 'value(status.url)')
curl -s "$URL/health"
curl -s -X POST "$URL/predict" -H "Content-Type: application/json" -d @scripts/sample_request.json
```

Interactive docs are at `$URL/docs`.

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

- **Build fails with a permission error on Artifact Registry or logs:** the
  Cloud Build service account is missing roles. Fallback: build locally with
  `docker buildx build --platform linux/amd64 -t IMAGE --push .` after
  `gcloud auth configure-docker us-east1-docker.pkg.dev`, then run only the
  `gcloud run deploy` command from the script.
- **Deploy says the container failed to start:** read the logs (above). The
  usual cause is the app not listening on `$PORT`; the entrypoint handles this.
