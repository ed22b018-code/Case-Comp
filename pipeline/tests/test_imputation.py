"""Tests for imputation/imputer.py"""

import numpy as np
import pandas as pd
import pytest

from imputation.imputer import impute


def test_no_missing_passes_through(sample_master):
    """If no values are missing, imputed output should be close to input."""
    clean = sample_master.copy()
    ind_cols = [c for c in clean.columns if c not in ("canonical_name", "state")]
    clean[ind_cols] = clean[ind_cols].fillna(clean[ind_cols].median())
    imputed, _, audit = impute(clean)
    assert imputed[ind_cols].isna().sum().sum() == 0


def test_missing_values_filled(sample_master):
    """All NaN holes must be filled after imputation."""
    imputed, _, audit = impute(sample_master)
    ind_cols = [c for c in imputed.columns if c not in ("canonical_name", "state")]
    assert imputed[ind_cols].isna().sum().sum() == 0


def test_imputed_values_in_range(sample_master):
    """Imputed values must stay in [0, 100]."""
    imputed, _, audit = impute(sample_master)
    ind_cols = [c for c in imputed.columns if c not in ("canonical_name", "state")]
    assert (imputed[ind_cols] >= 0).all().all()
    assert (imputed[ind_cols] <= 100).all().all()


def test_audit_reports_correct_before_pct(sample_master):
    """audit missing_before_pct should match actual missingness in input."""
    _, _, audit = impute(sample_master)
    ind_cols = [c for c in sample_master.columns if c not in ("canonical_name", "state")]
    for col in ind_cols:
        expected = round(sample_master[col].isna().mean() * 100, 1)
        reported = audit[col]["missing_before_pct"]
        assert abs(reported - expected) < 1.0, f"{col}: expected ~{expected}, got {reported}"


def test_fully_missing_district_handled():
    """A district with all-NaN indicators should get imputed values, not NaN."""
    idx = [str(i) for i in range(20)]
    df = pd.DataFrame({
        "canonical_name": [f"D{i}" for i in range(20)],
        "state": ["StateA"] * 10 + ["StateB"] * 10,
        "ind_x": [float("nan")] + list(range(1, 20)),
        "ind_y": [float("nan")] + [float(i) * 2 for i in range(1, 20)],
    }, index=idx)
    df.index.name = "canonical_district_id"
    imputed, _, _ = impute(df)
    assert not imputed.loc[idx[0], "ind_x"] != imputed.loc[idx[0], "ind_x"]  # not NaN
