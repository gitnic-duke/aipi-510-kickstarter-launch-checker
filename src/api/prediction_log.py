"""Prediction logging (task T17).

Every /predict call writes one JSON line per instance to stdout. Cloud Run sends
stdout to Cloud Logging and parses JSON lines as structured logs, so each
prediction becomes a queryable record (inputs, probability, model version,
request id, timestamp) with no extra infrastructure, credentials or cost.
This is the raw material for monitoring data drift and model behavior.

Privacy: the campaign title is not logged, only its length (the model's
title feature), so free text typed by users never ends up in the logs.

Read the logs (needs Logs Viewer on the project, e.g. the Viewer role):
    gcloud logging read 'jsonPayload.event="prediction"' --limit 20 --format json
"""

import json
import logging
import sys
import uuid
from datetime import UTC, datetime

from src.schema import LaunchInput

logger = logging.getLogger("kickstarter_api")

_stream = sys.stdout


def prediction_records(
    instances: list[LaunchInput], probabilities: list[float], model_version: str
) -> list[dict]:
    """One structured record per prediction (pure function, easy to test)."""
    request_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat(timespec="milliseconds")
    records = []
    for index, (item, probability) in enumerate(zip(instances, probabilities, strict=True)):
        inputs = item.model_dump(exclude={"name"})
        inputs["name_length"] = len(item.name)
        records.append(
            {
                # severity + message are the fields Cloud Logging shows in its list view
                "severity": "INFO",
                "message": f"prediction {probability:.3f} ({model_version})",
                "event": "prediction",
                "request_id": request_id,
                "batch_index": index,
                "batch_size": len(instances),
                "timestamp": timestamp,
                "model_version": model_version,
                "probability": round(float(probability), 6),
                "inputs": inputs,
            }
        )
    return records


def log_predictions(
    instances: list[LaunchInput], probabilities: list[float], model_version: str
) -> None:
    """Write the records as JSON lines. Never raises: logging must not break /predict."""
    try:
        for record in prediction_records(instances, probabilities, model_version):
            _stream.write(json.dumps(record) + "\n")
        _stream.flush()
    except Exception:  # noqa: BLE001 - a logging failure must never fail a prediction
        logger.exception("Failed to log predictions")
