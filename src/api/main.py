"""FastAPI service (task T7): /health and /predict (batch).

Loads a scikit-learn Pipeline from MODEL_PATH at startup and validates every
request against the shared schema in src/schema.py. Until the trained model is
swapped in (T15), MODEL_PATH points at the placeholder built by
`python -m scripts.make_dummy_model`.

Environment variables:
    MODEL_PATH     path to the joblib-saved Pipeline (default: models/model.joblib)
    MODEL_VERSION  label returned with every prediction (default: "unversioned")
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from src.schema import FEATURES, LaunchInput, PredictRequest, PredictResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kickstarter_api")

DEFAULT_MODEL_PATH = "models/model.joblib"


def load_model(path: str):
    """Return the Pipeline saved at `path`, or None if the file doesn't exist."""
    model_file = Path(path)
    if not model_file.exists():
        logger.warning("No model at %s; /predict will return 503", model_file)
        return None
    logger.info("Loading model from %s", model_file)
    return joblib.load(model_file)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at startup, not per request: keeps /predict fast.
    app.state.model = load_model(os.getenv("MODEL_PATH", DEFAULT_MODEL_PATH))
    app.state.model_version = os.getenv("MODEL_VERSION", "unversioned")
    yield


app = FastAPI(
    title="Kickstarter Launch Checker API",
    description="Predicts the probability that a Kickstarter campaign reaches its goal.",
    version="0.1.0",
    lifespan=lifespan,
)


def to_frame(instances: list[LaunchInput]) -> pd.DataFrame:
    """Turn validated inputs into a DataFrame with columns in training order."""
    return pd.DataFrame([item.model_dump() for item in instances], columns=FEATURES)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    """Liveness + readiness: 200 only when a model is loaded."""
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok", "model_version": app.state.model_version}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    """Return P(success) for each campaign, in the same order as the input.

    Accepts a batch so the front-end's what-if chart needs only one request.
    """
    model = app.state.model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    features = to_frame(request.instances)
    probabilities = model.predict_proba(features)[:, 1]
    return PredictResponse(
        probabilities=[float(p) for p in probabilities],
        model_version=app.state.model_version,
    )
