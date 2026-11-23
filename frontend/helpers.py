"""Pure helper functions for the Streamlit app (task T14).

No Streamlit import here, so these run in CI's unit tests without the UI.
"""

import math
from datetime import date

MIN_GOAL_USD = 1
MAX_DURATION_DAYS = 60  # Kickstarter's maximum campaign length today
MAX_BATCH = 100  # matches PredictRequest's limit in src/schema.py


def build_instance(
    *,
    name: str,
    main_category: str,
    category: str,
    country: str,
    goal_usd: float,
    duration_days: int,
    launch_date: date,
) -> dict:
    """One /predict instance in the API's schema, derived from the form inputs."""
    return {
        "main_category": main_category,
        "category": category,
        "goal_usd": float(goal_usd),
        "duration_days": int(duration_days),
        "country": country,
        "launch_month": launch_date.month,
        "launch_weekday": launch_date.weekday(),  # 0 = Monday, same as the schema
        "name": name.strip(),
    }


def goal_grid(goal_usd: float, points: int = 15, span: float = 10.0) -> list[float]:
    """Log-spaced goals from goal/span to goal*span, always including the user's goal.

    Used for the what-if chart: all points go to the API in one batch request.
    """
    low = max(goal_usd / span, MIN_GOAL_USD)
    high = max(goal_usd * span, low + 1)
    step = (math.log(high) - math.log(low)) / (points - 1)
    grid = {round(math.exp(math.log(low) + i * step), 2) for i in range(points)}
    grid.add(round(float(goal_usd), 2))
    return sorted(grid)


def subcategories(values: dict, main_category: str) -> list[str]:
    """Subcategories for a main category, falling back to the full list."""
    by_main = values.get("categories_by_main", {})
    return by_main.get(main_category) or values.get("category", [])


def odds_label(probability: float) -> str:
    """Plain-language reading of a success probability."""
    if probability >= 0.6:
        return "Good odds"
    if probability >= 0.4:
        return "Toss-up"
    return "Long shot"
