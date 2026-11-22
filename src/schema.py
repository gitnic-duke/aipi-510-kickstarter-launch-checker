"""Shared input/output schema for the Kickstarter Launch Checker.

Shared contract (task T3): the API, training pipeline and front-end all import
this module so feature names can't drift apart. Only fields a creator knows on
launch day belong in LaunchInput — never post-launch fields like pledged or backers.
"""

from pydantic import BaseModel, Field

# Column names in processed/vN/kickstarter.parquet
TARGET = "success"  # 1 = successful, 0 = failed
CATEGORICAL = ["main_category", "category", "country"]
NUMERIC = ["goal_usd", "duration_days", "launch_month", "launch_weekday"]
TEXT = ["name"]
FEATURES = CATEGORICAL + NUMERIC + TEXT

# Post-launch columns. Kept in the processed data ONLY for the leakage demo run
# (config: features.include_leaky). Never part of LaunchInput or the served model.
LEAKY = ["backers", "pledged_usd"]

# T5 writes the valid values of each categorical column here (and to GCS next to
# the parquet), so the front-end dropdowns match what the model was trained on.
CATEGORY_VALUES_FILE = "category_values.json"


class LaunchInput(BaseModel):
    main_category: str = Field(examples=["Games"])
    category: str = Field(examples=["Tabletop Games"])
    goal_usd: float = Field(gt=0, examples=[5000.0])
    duration_days: int = Field(ge=1, le=92, examples=[30])
    country: str = Field(min_length=2, max_length=2, examples=["US"])  # 2-letter code
    launch_month: int = Field(ge=1, le=12, examples=[3])
    launch_weekday: int = Field(ge=0, le=6, examples=[1])  # 0 = Monday
    name: str = Field(min_length=1, examples=["Dungeon Crawl: The Board Game"])


class PredictRequest(BaseModel):
    instances: list[LaunchInput] = Field(min_length=1, max_length=100)


class PredictResponse(BaseModel):
    probabilities: list[float]  # P(success), one per instance, same order
    model_version: str
