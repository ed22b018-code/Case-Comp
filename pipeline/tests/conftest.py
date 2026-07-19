"""Shared fixtures for all pipeline tests."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Allow importing pipeline modules from tests
PIPELINE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PIPELINE_DIR))


PILLARS   = ["demand", "monetization", "access", "growth"]
THERAPIES = ["overall", "chronic", "acute"]

N = 50  # number of synthetic districts in test fixtures


@pytest.fixture
def rng():
    return np.random.default_rng(42)


@pytest.fixture
def sample_xwalk():
    """Minimal crosswalk with N districts."""
    return pd.DataFrame({
        "canonical_district_id": [str(i) for i in range(1, N + 1)],
        "canonical_name":        [f"District_{i}" for i in range(1, N + 1)],
        "state":                 ["StateA"] * (N // 2) + ["StateB"] * (N - N // 2),
        "source_name":           [f"District_{i}" for i in range(1, N + 1)],
        "source_vintage":        ["census_2011"] * N,
        "match_type":            ["exact"] * N,
        "confidence":            [1.0] * N,
        "notes":                 [""] * N,
    })


@pytest.fixture
def sample_master(rng, sample_xwalk):
    """Wide district_master with N districts, 6 indicators (2 per demand pillar), ~5% NaN holes."""
    idx = sample_xwalk["canonical_district_id"].tolist()
    data = rng.uniform(10, 90, size=(N, 6))
    mask = rng.random(size=data.shape) < 0.05
    data[mask] = np.nan
    cols = ["ind_a", "ind_a2", "ind_b", "ind_c", "ind_c2", "ind_d"]
    df = pd.DataFrame(data, index=idx, columns=cols)
    df.index.name = "canonical_district_id"
    df.insert(0, "state", sample_xwalk.set_index("canonical_district_id")["state"])
    df.insert(0, "canonical_name", sample_xwalk.set_index("canonical_district_id")["canonical_name"])
    return df


@pytest.fixture
def sample_config():
    """Minimal config with 2 indicators per demand/access pillar — enables therapy_relevance testing."""
    return {
        "therapies": THERAPIES,
        "pillars":   PILLARS,
        "scoring_function": "arithmetic",
        "indicators": [
            # demand: 2 indicators so therapy_relevance actually matters
            {"id": "ind_a",  "pillar": "demand",       "direction": "higher_better",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 2.0, "acute": 0.3}},
            {"id": "ind_a2", "pillar": "demand",       "direction": "higher_better",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 0.3, "acute": 2.0}},
            {"id": "ind_b",  "pillar": "monetization", "direction": "higher_better",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 1.8, "acute": 0.5}},
            # access: 2 indicators
            {"id": "ind_c",  "pillar": "access",       "direction": "inverse",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 0.4, "acute": 2.0}},
            {"id": "ind_c2", "pillar": "access",       "direction": "higher_better",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 2.0, "acute": 0.4}},
            {"id": "ind_d",  "pillar": "growth",       "direction": "higher_better",
             "transform": "winsorize_minmax", "status": "TODO",
             "therapy_relevance": {"overall": 1.0, "chronic": 1.3, "acute": 0.9}},
        ],
        "weights": {
            "overall": {"demand": 0.25, "monetization": 0.25, "access": 0.25, "growth": 0.25},
            "chronic": {"demand": 0.20, "monetization": 0.35, "access": 0.20, "growth": 0.25},
            "acute":   {"demand": 0.35, "monetization": 0.15, "access": 0.35, "growth": 0.15},
        },
        "forecasting": {"base_year": 2011, "target_year": 2030, "method": "cagr"},
        "clustering":  {"method": "kmeans", "k_range": [2, 4], "random_state": 42},
    }
