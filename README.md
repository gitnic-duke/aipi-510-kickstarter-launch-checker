# Kickstarter Launch Checker

Predicts whether a Kickstarter campaign will reach its funding goal using only
information available on launch day, and shows how the goal amount, campaign
length and category change the odds.

> **Status:** in progress — Module Project 3 (Data/ML Engineering), AIPI 510.

**Live app:** _TBD_ · **API:** _TBD_

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
Requires Python 3.11. On macOS, XGBoost also needs OpenMP: `brew install libomp`.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # then fill in values
```

## Usage
- Train the model: _TBD_
- Run the API locally: _TBD_
- Deploy to the cloud: _TBD_

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
