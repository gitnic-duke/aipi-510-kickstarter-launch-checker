# Kickstarter Launch Checker

Predicts whether a Kickstarter campaign will reach its funding goal using only
information available on launch day, and shows how the goal amount, campaign
length and category change the odds.

> **Status:** in progress — Module Project 3 (Data/ML Engineering), AIPI 510.

**Live app:** _TBD_ · **API:** https://kickstarter-api-zcqiii5fia-ue.a.run.app ([interactive docs](https://kickstarter-api-zcqiii5fia-ue.a.run.app/docs))

## Project overview and goals
_TBD_

## Dataset
[Kickstarter Projects](https://www.kaggle.com/datasets/kemical/kickstarter-projects) (Kaggle),
about 380k campaigns, 2009–2018. _Cleaning and leakage notes TBD._

## Model and evaluation
_TBD_

## Cloud services
| Purpose | Service |
| --- | --- |
| Data storage | Google Cloud Storage |
| Experiment tracking | Weights & Biases |
| API hosting | Google Cloud Run |
| Front-end hosting | Streamlit Community Cloud |

## Setup
Requires **Python 3.11** (any 3.11.x; other versions may fail to install the pinned packages). On macOS, XGBoost also needs OpenMP: `brew install libomp`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in values
```

## Usage
- Train the model: _TBD_
- Run the API locally:

  ```bash
  python -m scripts.make_dummy_model          # placeholder model -> models/model.joblib (until T15)
  uvicorn src.api.main:app --reload --port 8000
  ```

  Then open http://localhost:8000/docs for interactive docs, or use curl:

  ```bash
  curl -s localhost:8000/health
  curl -s -X POST localhost:8000/predict \
    -H "Content-Type: application/json" -d @scripts/sample_request.json
  ```

  `/predict` takes a batch (`{"instances": [...]}`, 1 to 100 items) and returns one
  success probability per item, in order. Bad input gets a 422 explaining what's wrong.
- Run the tests: `pytest`
- Build and run with Docker (one image, two entry points: `serve` and `train`):

  ```bash
  docker build -t kickstarter-api .
  docker run --rm -p 8080:8080 kickstarter-api      # serves the API on port 8080
  curl -s localhost:8080/health
  ```

  The model is baked into the image at build time (a placeholder until T15).
  On Apple Silicon, images for Cloud Run must be built for `linux/amd64`
  (see the deploy instructions).
- Deploy to the cloud: `./scripts/deploy_api.sh` (builds with Cloud Build, deploys to Cloud Run). See [docs/deploy.md](docs/deploy.md).

## Repository structure
```
src/
  schema.py        shared input/output schema
  data/            extract.py, transform.py, ingest.py
  features.py      transformers used inside the model Pipeline
  train.py         training + W&B logging
  api/main.py      FastAPI service
frontend/app.py    Streamlit app
scripts/           helper scripts
tests/             pytest tests
docs/              setup and deploy docs
```

## Limitations and ethics
_TBD_

## Team
- Partner A (data and ML): _name_
- Partner B (serving and app): _name_

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, commit and PR workflow.
