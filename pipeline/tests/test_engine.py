"""Tests for engine: normalizer, aggregator, index_engine."""

import numpy as np
import pandas as pd
import pytest

from engine.normalizer import winsorize_minmax, normalize
from engine.aggregator import compute_pillar_score, compute_headline_score, aggregate
from engine.index_engine import validate_weights


def test_winsorize_minmax_range():
    s = pd.Series([0, 10, 20, 30, 100, 200, 300])
    result = winsorize_minmax(s)
    assert result.min() >= 0
    assert result.max() <= 100


def test_winsorize_minmax_constant_series():
    s = pd.Series([42.0] * 10)
    result = winsorize_minmax(s)
    assert (result == 50.0).all()


def test_normalize_invert(sample_master, sample_config):
    """Inverse indicators should have values flipped (high raw → low normalised)."""
    sample_master_clean = sample_master.copy()
    ind_cols = [c for c in sample_master_clean.columns if c not in ("canonical_name","state")]
    sample_master_clean[ind_cols] = sample_master_clean[ind_cols].fillna(50.0)

    normed = normalize(sample_master_clean, sample_config)
    # ind_c is 'inverse' — its highest raw values should map to lowest normalised
    # We check that the correlation between raw and normed is negative for ind_c
    raw_c  = sample_master_clean["ind_c"]
    norm_c = normed["ind_c"]
    corr = raw_c.corr(norm_c)
    assert corr < 0, f"Expected negative correlation for inverse indicator, got {corr:.3f}"


def test_normalize_values_in_range(sample_master, sample_config):
    clean = sample_master.fillna(50.0)
    normed = normalize(clean, sample_config)
    ind_cols = [c for c in normed.columns if c not in ("canonical_name", "state")]
    assert (normed[ind_cols].values >= -0.01).all()
    assert (normed[ind_cols].values <= 100.01).all()


def test_pillar_score_range(sample_master, sample_config):
    clean = sample_master.fillna(50.0)
    normed = normalize(clean, sample_config)
    score = compute_pillar_score(normed, "demand", "overall", sample_config)
    assert score.between(0, 100).all()


def test_therapy_relevance_changes_pillar_score(sample_master, sample_config):
    """chronic and acute should produce different pillar scores for demand."""
    clean = sample_master.fillna(50.0)
    normed = normalize(clean, sample_config)
    s_chronic = compute_pillar_score(normed, "demand", "chronic", sample_config)
    s_acute   = compute_pillar_score(normed, "demand", "acute",   sample_config)
    # They should NOT be identical (different therapy_relevance multipliers)
    assert not s_chronic.equals(s_acute), "Chronic and acute pillar scores must differ"


def test_arithmetic_pillars_sum_to_headline(sample_master, sample_config):
    """For arithmetic aggregation: Σ(pillar × weight) == headline score."""
    clean = sample_master.fillna(50.0)
    normed = normalize(clean, sample_config)
    agg = aggregate(normed, sample_config, scoring_function="arithmetic")
    for therapy in sample_config["therapies"]:
        pw = sample_config["weights"][therapy]
        pillar_df = agg[therapy]["pillar_scores"]
        headline  = agg[therapy]["headline"]
        recomputed = sum(pillar_df[p] * pw[p] for p in pw)
        diff = (headline - recomputed).abs().max()
        assert diff < 0.01, f"Arithmetic score mismatch for {therapy}: max diff={diff:.4f}"


def test_geometric_score_penalises_imbalance():
    """
    District with imbalanced pillars [90, 90, 90, 10] should score
    lower under geometric mean than arithmetic mean.
    """
    config = {
        "therapies": ["overall"],
        "pillars": ["demand", "monetization", "access", "growth"],
        "weights": {"overall": {"demand": 0.25, "monetization": 0.25, "access": 0.25, "growth": 0.25}},
    }
    pillar_df = pd.DataFrame({
        "demand": [90.0], "monetization": [90.0], "access": [90.0], "growth": [10.0]
    }, index=["D1"])
    arith  = compute_headline_score(pillar_df, "overall", config, "arithmetic").iloc[0]
    geom   = compute_headline_score(pillar_df, "overall", config, "geometric").iloc[0]
    assert geom < arith, f"Geometric ({geom:.2f}) should be < arithmetic ({arith:.2f}) for imbalanced pillars"


def test_validate_weights_passes_valid_config(sample_config):
    validate_weights(sample_config)  # should not raise


def test_validate_weights_raises_on_bad_sum():
    bad = {
        "therapies": ["overall"],
        "pillars": ["demand", "monetization", "access", "growth"],
        "weights": {"overall": {"demand": 0.3, "monetization": 0.3, "access": 0.3, "growth": 0.3}},
    }
    with pytest.raises(ValueError, match="sum to"):
        validate_weights(bad)
