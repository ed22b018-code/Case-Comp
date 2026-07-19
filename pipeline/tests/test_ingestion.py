"""Tests for ingestion/loader.py"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ingestion.loader import load_indicator, build_district_master, should_process


def _write_csv(path: Path, district_ids, values, year=2011):
    pd.DataFrame({
        "district_id": district_ids,
        "value": values,
        "year": year,
    }).to_csv(path, index=False)


def test_load_indicator_direct_join(tmp_path, sample_xwalk):
    dist_ids = sample_xwalk["canonical_district_id"].tolist()
    values   = list(range(len(dist_ids)))
    csv_path = tmp_path / "ind.csv"
    _write_csv(csv_path, dist_ids, values)

    ind_config = {"id": "test_ind", "file": str(csv_path), "status": "TODO"}
    series = load_indicator(ind_config, sample_xwalk, tmp_path.parent, year=2011)
    # After load, series is actually returned from the fn using pipeline_dir/file
    # Re-test with absolute path
    ind_config2 = {"id": "test_ind", "file": csv_path.name, "status": "TODO"}
    result = load_indicator({"id": "test_ind", "file": str(csv_path), "status":"TODO"},
                            sample_xwalk, Path("/"), year=2011)
    assert result.notna().sum() > 0


def test_load_indicator_missing_year(tmp_path, sample_xwalk):
    csv_path = tmp_path / "ind.csv"
    pd.DataFrame({"district_id": ["1"], "value": [50.0], "year": [2016]}).to_csv(csv_path, index=False)
    ind_config = {"id": "x", "file": str(csv_path), "status": "TODO"}
    result = load_indicator(ind_config, sample_xwalk, Path("/"), year=2011)
    assert len(result) == 0


def test_should_process_existing_file(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("a,b")
    ind = {"id": "x", "file": str(f), "status": "TODO"}
    assert should_process(ind, Path("/")) is True


def test_should_process_missing_file(tmp_path):
    ind = {"id": "x", "file": str(tmp_path / "nonexistent.csv"), "status": "TODO"}
    assert should_process(ind, Path("/")) is False


def test_build_district_master_shape(tmp_path, sample_xwalk, sample_config):
    """Build master from temp CSV files — shape should match districts × indicators."""
    for ind in sample_config["indicators"]:
        dist_ids = sample_xwalk["canonical_district_id"].tolist()
        vals     = list(range(len(dist_ids)))
        csv_path = tmp_path / f"{ind['id']}.csv"
        _write_csv(csv_path, dist_ids, vals)
        ind["file"] = str(csv_path)

    master, coverage = build_district_master(sample_config, sample_xwalk, Path("/"), year=2011)
    assert len(master) == len(sample_xwalk["canonical_district_id"].unique())
    assert len(coverage) == len(sample_config["indicators"])
