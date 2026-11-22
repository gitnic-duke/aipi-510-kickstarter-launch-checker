"""API tests (task T7): run with `pytest` from the repo root."""

import copy

import pytest
from fastapi.testclient import TestClient

from scripts.make_dummy_model import build_and_save
from src.api.main import app

VALID_INSTANCE = {
    "main_category": "Games",
    "category": "Tabletop Games",
    "goal_usd": 5000,
    "duration_days": 30,
    "country": "US",
    "launch_month": 3,
    "launch_weekday": 1,
    "name": "Dungeon Crawl: The Board Game",
}


def instance(**overrides) -> dict:
    item = copy.deepcopy(VALID_INSTANCE)
    item.update(overrides)
    return item


@pytest.fixture(scope="module")
def model_path(tmp_path_factory):
    return build_and_save(tmp_path_factory.mktemp("model") / "model.joblib", n=200)


@pytest.fixture
def client(model_path, monkeypatch):
    monkeypatch.setenv("MODEL_PATH", str(model_path))
    monkeypatch.setenv("MODEL_VERSION", "test-v0")
    with TestClient(app) as test_client:  # `with` runs the startup (model load)
        yield test_client


@pytest.fixture
def client_without_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.joblib"))
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_model_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "test-v0"}


def test_predict_returns_probability_between_0_and_1(client):
    response = client.post("/predict", json={"instances": [instance()]})
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "test-v0"
    assert len(body["probabilities"]) == 1
    assert 0.0 <= body["probabilities"][0] <= 1.0


def test_predict_batch_keeps_length_and_order(client):
    goals = [500, 5_000, 50_000, 500_000]
    batch = [instance(goal_usd=g) for g in goals]
    probabilities = client.post("/predict", json={"instances": batch}).json()["probabilities"]
    assert len(probabilities) == len(goals)
    # Each batch item must match the same item sent alone (no mixing up order).
    for item, p in zip(batch, probabilities, strict=True):
        single = client.post("/predict", json={"instances": [item]}).json()["probabilities"][0]
        assert single == pytest.approx(p)


def test_predict_handles_unseen_category(client):
    item = instance(main_category="Brand New Category", category="Never Seen", country="ZZ")
    response = client.post("/predict", json={"instances": [item]})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "bad_item",
    [
        instance(goal_usd=-5),
        instance(goal_usd=0),
        instance(duration_days=0),
        instance(launch_month=13),
        instance(launch_weekday=7),
        instance(country="USA"),
        instance(name=""),
        {k: v for k, v in VALID_INSTANCE.items() if k != "goal_usd"},  # missing field
    ],
)
def test_predict_rejects_invalid_input(client, bad_item):
    response = client.post("/predict", json={"instances": [bad_item]})
    assert response.status_code == 422


@pytest.mark.parametrize("size", [0, 101])
def test_predict_rejects_empty_or_oversized_batch(client, size):
    response = client.post("/predict", json={"instances": [instance()] * size})
    assert response.status_code == 422


def test_returns_503_when_model_missing(client_without_model):
    assert client_without_model.get("/health").status_code == 503
    response = client_without_model.post("/predict", json={"instances": [instance()]})
    assert response.status_code == 503
