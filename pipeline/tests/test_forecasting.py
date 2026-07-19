"""Tests for forecasting/forecaster.py"""

import numpy as np
import pandas as pd
import pytest

from forecasting.forecaster import CAGRForecast, compute_future_scores


def _make_panel(n_districts=20, years=(2011, 2016, 2021), growth_rate=0.02):
    """Synthetic panel with deterministic growth."""
    idx = [str(i) for i in range(1, n_districts + 1)]
    panel = {}
    rng = np.random.default_rng(0)
    base = rng.uniform(20, 80, size=n_districts)
    for yr in years:
        vals = base * ((1 + growth_rate) ** (yr - years[0]))
        vals = np.clip(vals, 0, 100)
        df = pd.DataFrame({
            "canonical_name": [f"D{i}" for i in range(1, n_districts + 1)],
            "state": ["S1"] * n_districts,
            "ind_a": vals,
            "ind_b": vals * 0.8,
        }, index=idx)
        df.index.name = "canonical_district_id"
        panel[yr] = df
    return panel


def test_cagr_forecast_positive_growth():
    """Districts growing 2%/yr should have higher 2030 values than 2021."""
    panel = _make_panel(growth_rate=0.02)
    strategy = CAGRForecast().fit(panel, ["ind_a", "ind_b"])
    proj = strategy.predict(2030)
    assert (proj["ind_a"] >= panel[2021]["ind_a"].clip(0, 100) * 0.95).all(), \
        "Projected values should generally exceed 2021 for growing districts"


def test_cagr_forecast_single_period():
    """With only one year, CAGR cannot be computed — should return flat forecast."""
    panel = {2011: _make_panel(years=(2011,))[2011]}
    strategy = CAGRForecast().fit(panel, ["ind_a", "ind_b"])
    proj = strategy.predict(2030)
    assert not proj.empty


def test_cagr_values_clamped():
    """Projected values must not exceed 100 or go below 0."""
    panel = _make_panel(growth_rate=0.15, n_districts=30)  # aggressive growth
    strategy = CAGRForecast().fit(panel, ["ind_a", "ind_b"])
    proj = strategy.predict(2030)
    assert (proj >= 0).all().all()
    assert (proj <= 100).all().all()


def test_future_scores_shape(sample_config, sample_xwalk):
    """compute_future_scores should return one row per district, one col per therapy."""
    panel = _make_panel(n_districts=len(sample_xwalk), growth_rate=0.01)
    # Re-index panel to match sample_xwalk district_ids
    idx_map = {str(i+1): sample_xwalk.iloc[i]["canonical_district_id"] for i in range(len(sample_xwalk))}
    for yr in panel:
        panel[yr].index = [idx_map.get(i, i) for i in panel[yr].index]

    # Replace ind_a/ind_b with config indicator ids
    for yr in panel:
        for ind in sample_config["indicators"]:
            panel[yr][ind["id"]] = panel[yr].get("ind_a", panel[yr].iloc[:, 2])
        panel[yr] = panel[yr].drop(columns=["ind_a", "ind_b"], errors="ignore")

    future = compute_future_scores(sample_config, panel, sample_xwalk)
    expected_cols = [f"{t}_future_score" for t in sample_config["therapies"]]
    for col in expected_cols:
        assert col in future.columns, f"Missing column: {col}"
