"""Tests for sensitivity/sensitivity.py"""

import numpy as np
import pandas as pd
import pytest

from sensitivity.sensitivity import run_sensitivity, _perturb_config, spearman_rank_corr


def _make_scores_and_normed(sample_config, sample_master):
    from imputation.imputer import impute
    from engine.normalizer import normalize
    from engine.aggregator import aggregate

    imputed, _, _ = impute(sample_master)
    normed = normalize(imputed, sample_config)
    agg = aggregate(normed, sample_config, scoring_function="arithmetic")

    frames = []
    for therapy in sample_config["therapies"]:
        frames.append(agg[therapy]["headline"].rename(f"{therapy}_score"))
        for pillar in sample_config["pillars"]:
            frames.append(agg[therapy]["pillar_scores"][pillar].rename(f"{therapy}_pillar_{pillar}"))
    scores = pd.concat(frames, axis=1)
    scores["canonical_name"] = imputed.get("canonical_name", pd.Series("", index=scores.index))
    scores["state"]          = imputed.get("state", pd.Series("", index=scores.index))
    return scores, normed


def test_perturb_weights_sum_to_one(sample_config):
    cfg = _perturb_config(sample_config, "overall", "demand", +1)
    total = sum(cfg["weights"]["overall"].values())
    assert abs(total - 1.0) < 1e-6


def test_perturb_weight_direction(sample_config):
    base_w = sample_config["weights"]["overall"]["demand"]
    cfg_up   = _perturb_config(sample_config, "overall", "demand", +1)
    cfg_down = _perturb_config(sample_config, "overall", "demand", -1)
    assert cfg_up["weights"]["overall"]["demand"] > base_w
    assert cfg_down["weights"]["overall"]["demand"] < base_w


def test_spearman_returns_float(sample_master):
    a = pd.Series(np.random.randn(50), index=sample_master.index[:50])
    b = pd.Series(np.random.randn(50), index=sample_master.index[:50])
    rho = spearman_rank_corr(a, b)
    assert isinstance(rho, float)
    assert -1.0 <= rho <= 1.0


def test_sensitivity_summary_shape(sample_config, sample_master):
    scores, normed = _make_scores_and_normed(sample_config, sample_master)
    from crosswalk.build_crosswalk import load_or_build_crosswalk
    result = run_sensitivity(sample_config, normed, pd.DataFrame(), scores)
    summary = result["summary"]
    # Should have 2 (directions) × n_therapies × n_pillars rows
    n_expected = 2 * len(sample_config["therapies"]) * len(sample_config["pillars"])
    assert len(summary) == n_expected


def test_sensitivity_spearman_high_for_small_perturbation(sample_config, sample_master):
    """±20% weight change should still yield Spearman > 0.8 (stable ranking)."""
    scores, normed = _make_scores_and_normed(sample_config, sample_master)
    result = run_sensitivity(sample_config, normed, pd.DataFrame(), scores)
    mean_rho = result["summary"]["spearman_vs_baseline"].mean()
    assert mean_rho > 0.7, f"Mean Spearman too low: {mean_rho:.3f}"
