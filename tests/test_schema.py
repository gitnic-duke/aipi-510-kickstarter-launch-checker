"""Tests for the shared data contract in src/schema.py (task T9).

These guard the contract that the API, pipeline and front-end all depend on.
"""

import pytest
from pydantic import ValidationError

from src.schema import (
    CATEGORICAL,
    FEATURES,
    LEAKY,
    NUMERIC,
    TEXT,
    LaunchInput,
    PredictRequest,
)

VALID = {
    "main_category": "Games",
    "category": "Tabletop Games",
    "goal_usd": 5000,
    "duration_days": 30,
    "country": "US",
    "launch_month": 3,
    "launch_weekday": 1,
    "name": "Dungeon Crawl: The Board Game",
}


def test_valid_input_is_accepted():
    assert LaunchInput(**VALID).goal_usd == 5000


def test_feature_lists_match_launch_input_fields():
    assert set(FEATURES) == set(LaunchInput.model_fields)
    assert FEATURES == CATEGORICAL + NUMERIC + TEXT


def test_leaky_columns_are_never_model_inputs():
    """Post-launch columns must never be part of what the API accepts."""
    assert not set(LEAKY) & set(FEATURES)
    assert not set(LEAKY) & set(LaunchInput.model_fields)


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("goal_usd", 0),
        ("goal_usd", -100),
        ("duration_days", 0),
        ("duration_days", 93),
        ("launch_month", 0),
        ("launch_month", 13),
        ("launch_weekday", -1),
        ("launch_weekday", 7),
        ("country", "USA"),
        ("name", ""),
    ],
)
def test_out_of_range_values_are_rejected(field, bad_value):
    with pytest.raises(ValidationError):
        LaunchInput(**{**VALID, field: bad_value})


def test_batch_size_limits():
    with pytest.raises(ValidationError):
        PredictRequest(instances=[])
    with pytest.raises(ValidationError):
        PredictRequest(instances=[VALID] * 101)
    assert len(PredictRequest(instances=[VALID] * 100).instances) == 100
