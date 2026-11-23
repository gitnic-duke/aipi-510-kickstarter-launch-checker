"""Tests for the cleaning and validation logic (task T5).

Pure functions on a small in-memory DataFrame: no GCS or Kaggle access,
so these run in CI without credentials.
"""

import pandas as pd
import pytest

from src.data.transform import (
    OUTPUT_COLUMNS,
    DataQualityError,
    category_values,
    clean,
    validate,
)


def raw_rows() -> pd.DataFrame:
    """Rows shaped like ks-projects-201801.csv, including the messy cases."""
    base = {
        "ID": 1,
        "name": "Board Game",
        "category": "Tabletop Games",
        "main_category": "Games",
        "currency": "USD",
        "deadline": "2015-10-10",
        "goal": 5000.0,
        "launched": "2015-09-10 12:00:00",  # a Thursday
        "pledged": 6000.0,
        "state": "successful",
        "backers": 120,
        "country": "US",
        "usd pledged": 6000.0,
        "usd_pledged_real": 6000.0,
        "usd_goal_real": 5000.0,
    }
    rows = [
        base,
        {
            **base,
            "ID": 2,
            "name": "Indie Album",
            "category": "Indie Rock",
            "main_category": "Music",
            "state": "failed",
            "backers": 3,
            "country": "GB",
            "usd_pledged_real": 50.0,
        },
        {**base, "ID": 3, "state": "canceled"},  # not a final outcome
        {**base, "ID": 4, "state": "live"},  # not a final outcome
        {**base, "ID": 5, "launched": "1970-01-01 01:00:00"},  # placeholder date
        {**base, "ID": 6, "country": 'N,0"'},  # invalid country code
        {**base, "ID": 7, "name": None},  # missing title
        {**base, "ID": 8, "usd_goal_real": 0.0},  # zero goal
    ]
    return pd.DataFrame(rows)


def test_clean_keeps_only_valid_finished_campaigns():
    df = clean(raw_rows())
    assert len(df) == 2
    assert list(df.columns) == OUTPUT_COLUMNS
    assert df["success"].tolist() == [1, 0]


def test_clean_builds_launch_day_features():
    row = clean(raw_rows()).iloc[0]
    assert row["goal_usd"] == 5000.0
    assert row["duration_days"] == 30
    assert row["launch_month"] == 9
    assert row["launch_weekday"] == 3  # Thursday
    assert row["name"] == "Board Game"


def test_clean_keeps_leaky_columns_for_the_leakage_demo():
    df = clean(raw_rows())
    assert {"backers", "pledged_usd"} <= set(df.columns)
    assert "usd pledged" not in df.columns and "pledged" not in df.columns


def test_clean_rejects_missing_raw_columns():
    with pytest.raises(DataQualityError, match="missing columns"):
        clean(raw_rows().drop(columns=["usd_goal_real"]))


def test_validate_passes_clean_data():
    validate(clean(raw_rows()), min_rows=2)


def test_validate_reports_every_problem():
    df = clean(raw_rows())
    df.loc[0, "launch_month"] = 13
    df.loc[1, "goal_usd"] = None
    with pytest.raises(DataQualityError) as err:
        validate(df, min_rows=10)
    message = str(err.value)
    assert "launch_month" in message
    assert "Null values" in message
    assert "at least 10" in message


def test_validate_rejects_single_class_target():
    df = clean(raw_rows())
    df["success"] = 1
    with pytest.raises(DataQualityError, match="one class"):
        validate(df)


def test_category_values_for_dropdowns():
    values = category_values(clean(raw_rows()))
    assert values["main_category"] == ["Games", "Music"]
    assert values["country"] == ["GB", "US"]
    assert values["categories_by_main"]["Music"] == ["Indie Rock"]
