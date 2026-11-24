"""Tests for prediction logging (task T17). No cloud access needed."""

import io
import json

import pytest
from fastapi.testclient import TestClient

from scripts.make_dummy_model import build_and_save
from src.api import prediction_log
from src.api.main import app
from src.schema import LaunchInput

ITEM = {
    "main_category": "Games",
    "category": "Tabletop Games",
    "goal_usd": 5000,
    "duration_days": 30,
    "country": "US",
    "launch_month": 3,
    "launch_weekday": 1,
    "name": "Dungeon Crawl",
}


@pytest.fixture
def captured(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(prediction_log, "_stream", buffer)
    return buffer


def lines(buffer: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def test_records_have_inputs_probability_and_version():
    items = [LaunchInput(**ITEM), LaunchInput(**{**ITEM, "goal_usd": 50000})]
    records = prediction_log.prediction_records(items, [0.6, 0.3], "v1")
    assert len(records) == 2
    assert records[0]["request_id"] == records[1]["request_id"]
    assert [r["batch_index"] for r in records] == [0, 1]
    assert records[1]["inputs"]["goal_usd"] == 50000
    assert records[0]["probability"] == 0.6
    assert records[0]["model_version"] == "v1"
    assert records[0]["event"] == "prediction"


def test_title_is_not_logged_only_its_length():
    record = prediction_log.prediction_records([LaunchInput(**ITEM)], [0.5], "v1")[0]
    assert "name" not in record["inputs"]
    assert record["inputs"]["name_length"] == len(ITEM["name"])
    assert ITEM["name"] not in json.dumps(record)


def test_predict_endpoint_writes_one_json_line_per_instance(captured, monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PATH", str(build_and_save(tmp_path / "m.joblib", n=200)))
    monkeypatch.setenv("MODEL_VERSION", "test-v0")
    with TestClient(app) as client:
        body = {"instances": [ITEM, {**ITEM, "goal_usd": 99999}]}
        response = client.post("/predict", json=body)
    assert response.status_code == 200
    logged = lines(captured)
    assert len(logged) == 2
    assert [r["probability"] for r in logged] == [
        round(p, 6) for p in response.json()["probabilities"]
    ]
    assert {r["model_version"] for r in logged} == {"test-v0"}


def test_logging_failure_never_breaks_predictions(monkeypatch):
    class Broken:
        def write(self, _):
            raise OSError("disk full")

        def flush(self):
            pass

    monkeypatch.setattr(prediction_log, "_stream", Broken())
    prediction_log.log_predictions([LaunchInput(**ITEM)], [0.5], "v1")  # must not raise
