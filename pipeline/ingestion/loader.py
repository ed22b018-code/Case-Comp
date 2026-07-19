"""
Ingestion module — loads tidy indicator CSVs, joins to canonical district_id,
assembles the wide district_master table used by the rest of the pipeline.

Tidy CSV format (columns): district_id, value, year
  district_id : source identifier (for synthetic data = canonical dt_code;
                for real data: any name reconciled via crosswalk)
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import logging

import pandas as pd

log = logging.getLogger(__name__)


def _resolve_join_key(raw_df: pd.DataFrame, xwalk: pd.DataFrame) -> pd.DataFrame:
    """
    Join raw rows to canonical_district_id.
    Tries direct match on dt_code first; falls back to name-based crosswalk lookup.
    Unresolved rows are kept with canonical_district_id = NaN (flagged as gaps).
    """
    canonical_ids = set(xwalk["canonical_district_id"].astype(str))
    raw_df = raw_df.copy()
    raw_df["district_id"] = raw_df["district_id"].astype(str).str.strip()

    # Direct match
    direct_mask = raw_df["district_id"].isin(canonical_ids)
    resolved = raw_df[direct_mask].copy()
    resolved["canonical_district_id"] = resolved["district_id"]

    # Name-based match for the remainder
    unresolved = raw_df[~direct_mask].copy()
    if not unresolved.empty:
        name_map = (
            xwalk.set_index("source_name")["canonical_district_id"]
            .to_dict()
        )
        unresolved["canonical_district_id"] = unresolved["district_id"].map(name_map)
        log.debug("  Name-based match resolved %d / %d unresolved rows",
                  unresolved["canonical_district_id"].notna().sum(), len(unresolved))

    combined = pd.concat([resolved, unresolved], ignore_index=True)
    return combined


def load_indicator(
    ind_config: dict,
    xwalk: pd.DataFrame,
    pipeline_dir: Path,
    year: int = 2011,
) -> pd.DataFrame:
    """
    Load a single indicator CSV for the given year.
    Returns DataFrame: canonical_district_id, value  (unmatched rows have NaN value).
    """
    file_path = pipeline_dir / ind_config["file"]
    if not file_path.exists():
        log.warning("  [SKIP] File not found: %s", file_path)
        return pd.Series(name=ind_config["id"], dtype=float)

    raw = pd.read_csv(file_path, dtype={"district_id": str})
    
    if raw.empty:
        log.warning("  [SKIP] File is empty: %s", file_path)
        return pd.Series(name=ind_config["id"], dtype=float)

    raw["year"] = raw["year"].astype(int)
    year_df = raw[raw["year"] == year].copy()

    if year_df.empty:
        closest_year = raw.loc[(raw["year"] - year).abs().idxmin(), "year"]
        log.warning("  [FALLBACK] No rows for year=%d in %s, falling back to year=%d", year, file_path.name, closest_year)
        year_df = raw[raw["year"] == closest_year].copy()

    if year_df.empty:
        log.warning("  [SKIP] No rows for year=%d in %s", year, file_path.name)
        return pd.Series(name=ind_config["id"], dtype=float)

    joined = _resolve_join_key(year_df, xwalk)
    result = (
        joined[["canonical_district_id", "value"]]
        .dropna(subset=["canonical_district_id"])
        .drop_duplicates(subset=["canonical_district_id"])
    )
    return result.set_index("canonical_district_id")["value"].rename(ind_config["id"])


def should_process(ind_config: dict, pipeline_dir: Path) -> bool:
    """Process indicator if its file exists (READY or TODO with synthetic data)."""
    return (pipeline_dir / ind_config["file"]).exists()


def build_district_master(
    config: dict,
    xwalk: pd.DataFrame,
    pipeline_dir: Path,
    year: int = 2011,
) -> tuple[pd.DataFrame, dict]:
    """
    Build wide district_master DataFrame (rows=districts, cols=indicators).
    Returns (master_df, coverage_report).
    Coverage report: {indicator_id: {total, matched, missing_pct}}.
    """
    # All canonical districts as index
    canonical = (
        xwalk[["canonical_district_id", "canonical_name", "state"]]
        .drop_duplicates(subset=["canonical_district_id"])
        .set_index("canonical_district_id")
    )

    frames: list[pd.Series] = []
    coverage: dict[str, dict] = {}

    for ind in config["indicators"]:
        if not should_process(ind, pipeline_dir):
            log.info("  [SKIP] %s — file not found", ind["id"])
            continue

        series = load_indicator(ind, xwalk, pipeline_dir, year)
        # Re-index to full canonical district list → missing districts become NaN
        series = series.reindex(canonical.index)
        frames.append(series)

        n_missing = series.isna().sum()
        n_total   = len(series)
        coverage[ind["id"]] = {
            "total_districts":  n_total,
            "values_present":   int(n_total - n_missing),
            "missing":          int(n_missing),
            "missing_pct":      round(n_missing / n_total * 100, 1),
            "status":           ind["status"],
        }

    if not frames:
        raise RuntimeError("No indicator files found — run generate_synthetic.py first.")

    master = pd.concat(frames, axis=1)
    master.index.name = "canonical_district_id"
    # Attach metadata columns
    master = canonical.join(master)
    log.info("District master: %d districts × %d indicators (year=%d)",
             len(master), len(frames), year)
    return master, coverage


def load_panel(
    config: dict,
    xwalk: pd.DataFrame,
    pipeline_dir: Path,
    years: list[int] | None = None,
) -> dict[int, pd.DataFrame]:
    """
    Load district_master for each year separately.
    Returns {year: master_df}.
    Used by the forecaster.
    """
    if years is None:
        years = [2011, 2016, 2021]
    return {
        yr: build_district_master(config, xwalk, pipeline_dir, yr)[0]
        for yr in years
    }
