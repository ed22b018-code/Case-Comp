"""Tests for crosswalk module."""

import pandas as pd
import pytest

from crosswalk.build_crosswalk import fuzzy_match_names, coverage_report


@pytest.fixture
def small_xwalk():
    return pd.DataFrame({
        "canonical_district_id": ["101", "102", "103"],
        "canonical_name": ["Mumbai", "Pune", "Nashik"],
        "state": ["Maharashtra", "Maharashtra", "Maharashtra"],
    })


def test_exact_match(small_xwalk):
    result = fuzzy_match_names(["Mumbai"], small_xwalk, score_cutoff=80.0)
    assert len(result) == 1
    assert result.iloc[0]["canonical_name"] == "Mumbai"
    assert result.iloc[0]["match_type"] in ("exact", "fuzzy")


def test_fuzzy_match(small_xwalk):
    # Slight spelling variation
    result = fuzzy_match_names(["Mumbay"], small_xwalk, score_cutoff=70.0)
    assert len(result) == 1
    assert result.iloc[0]["canonical_name"] == "Mumbai"
    assert result.iloc[0]["match_type"] == "fuzzy"


def test_no_match_below_cutoff(small_xwalk):
    result = fuzzy_match_names(["XYZ999"], small_xwalk, score_cutoff=90.0)
    assert result.iloc[0]["match_type"] == "no_match"


def test_coverage_report_calculation(small_xwalk):
    source = ["Mumbai", "Pune", "XYZ999"]
    matched = fuzzy_match_names(source, small_xwalk, score_cutoff=80.0)
    report = coverage_report(source, matched)
    assert report["total_source_names"] == 3
    assert report["no_matches"] == 1
    assert report["match_rate_pct"] == pytest.approx(66.7, abs=1.0)


def test_multiple_sources(small_xwalk):
    sources = ["Mumbai", "Pune", "Nashik", "Aurangabad"]
    result = fuzzy_match_names(sources, small_xwalk, score_cutoff=80.0)
    assert len(result) == 4
    matched = result[result["match_type"] != "no_match"]
    assert len(matched) == 3
