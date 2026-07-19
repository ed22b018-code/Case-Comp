"""Tests for clustering/clustering.py"""

import numpy as np
import pandas as pd
import pytest

from clustering.clustering import run_clustering


def _make_scores(n=80):
    """Synthetic scores DataFrame with clear cluster structure."""
    rng = np.random.default_rng(7)
    idx = [str(i) for i in range(1, n + 1)]
    # Three clear groups
    g1 = rng.uniform(70, 90, size=(n // 3, 4))
    g2 = rng.uniform(30, 50, size=(n // 3, 4))
    g3 = rng.uniform(10, 30, size=(n - 2 * (n // 3), 4))
    vals = np.vstack([g1, g2, g3])
    pillars = ["demand", "monetization", "access", "growth"]
    df = pd.DataFrame(vals, columns=[f"overall_pillar_{p}" for p in pillars], index=idx)
    df["canonical_name"] = [f"D{i}" for i in range(1, n + 1)]
    df["state"] = "S1"
    df.index.name = "canonical_district_id"
    return df


def test_clustering_returns_labels(_make_scores=_make_scores):
    scores = _make_scores()
    result = run_clustering(scores)
    assert "labels" in result
    assert len(result["labels"]) == len(scores)


def test_clustering_k_in_range():
    scores = _make_scores()
    result = run_clustering(scores, config={"clustering": {"method": "kmeans", "k_range": [2, 5], "random_state": 42}})
    assert 2 <= result["k"] <= 5


def test_clustering_labels_are_integers():
    scores = _make_scores()
    result = run_clustering(scores)
    assert result["labels"].dtype in (int, "int64", "int32")


def test_cluster_profiles_have_n_districts():
    scores = _make_scores()
    result = run_clustering(scores)
    assert result["profiles"]["n_districts"].sum() == len(scores)


def test_clustering_finds_structure():
    """With three well-separated groups, optimal k should be >= 2."""
    scores = _make_scores(n=90)
    result = run_clustering(scores, config={"clustering": {"method": "kmeans", "k_range": [2, 6], "random_state": 42}})
    assert result["k"] >= 2
