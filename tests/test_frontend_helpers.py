"""Tests for the front-end's pure helpers (task T14). No Streamlit needed."""

from datetime import date

from frontend.helpers import MAX_BATCH, build_instance, goal_grid, odds_label, subcategories
from src.schema import FEATURES, PredictRequest


def make_instance(**overrides):
    fields = {
        "name": "  My Game  ",
        "main_category": "Games",
        "category": "Tabletop Games",
        "country": "US",
        "goal_usd": 5000,
        "duration_days": 30,
        "launch_date": date(2026, 3, 2),  # a Monday
    }
    fields.update(overrides)
    return build_instance(**fields)


def test_instance_matches_api_schema():
    instance = make_instance()
    assert set(instance) == set(FEATURES)
    PredictRequest(instances=[instance])  # raises if the API would reject it


def test_launch_date_becomes_month_and_weekday():
    instance = make_instance()
    assert instance["launch_month"] == 3
    assert instance["launch_weekday"] == 0
    assert instance["name"] == "My Game"


def test_goal_grid_includes_goal_and_fits_one_batch():
    grid = goal_grid(5000)
    assert 5000 in grid
    assert grid == sorted(grid)
    assert grid[0] >= 1
    assert len(grid) <= MAX_BATCH


def test_goal_grid_handles_tiny_goal():
    grid = goal_grid(1)
    assert 1 in grid
    assert all(g >= 1 for g in grid)


def test_subcategories_filter_by_main_with_fallback():
    values = {"category": ["A", "B"], "categories_by_main": {"Games": ["Tabletop Games"]}}
    assert subcategories(values, "Games") == ["Tabletop Games"]
    assert subcategories(values, "Unknown") == ["A", "B"]


def test_odds_label_bands():
    assert odds_label(0.75) == "Good odds"
    assert odds_label(0.5) == "Toss-up"
    assert odds_label(0.1) == "Long shot"
