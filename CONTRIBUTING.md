# Contributing

## Workflow
1. Never push to `main`. Every change goes through a pull request with one
   approving review from your partner (and a green CI check once CI exists).
2. One task per branch: `<type>/<short-description>`, where type is
   `feat`, `fix`, `docs`, `ci`, `chore`, `refactor` or `exp`.
   Example: `feat/data-clean`. Delete the branch after merging.
3. Keep PRs small (one task, ideally < ~400 changed lines). Rebase on `main`
   before requesting review: `git fetch origin && git rebase origin/main`.
4. Merge with a merge commit (don't squash) so individual commits stay visible.

## Commit messages
[Conventional Commits](https://www.conventionalcommits.org/), present tense,
one logical change per commit:

    feat: add batch predict endpoint
    fix: drop rows with 1970 launch dates
    test: add data quality checks
    docs: document Cloud Run deploy steps

## Never commit
Data (`*.csv`, `*.parquet`), models (`*.joblib`), `wandb/`, keys,
service-account files, `kaggle.json` or `.env`. Data lives in GCS, models in
W&B, secrets in `.env` locally and in Secret Manager / Streamlit secrets in the cloud.

## Dependencies
- Use **Python 3.11** (any 3.11.x). Other versions may fail to install the pinned packages.
- `requirements.in` lists our direct dependencies without versions. Edit this file.
- `requirements.txt` pins only those direct dependencies to exact versions; their
  sub-dependencies float so installs work on both macOS and Linux (Docker).
  Regenerate it with the commands at the top of `requirements.in`.
- If an install fails, unblock yourself with `pip install -r requirements.in`,
  then fix the conflicting pin in a `fix:` PR.

## Using AI coding tools
- Give the AI `src/schema.py` and `config.yaml` as context.
- Generate one task at a time; commit in small logical pieces.
- Read and run everything before committing.
- Never paste keys or `.env` contents into an AI tool.
