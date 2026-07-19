"""
Build district_crosswalk.csv from the canonical GeoJSON geography.
Also provides fuzzy-match helpers for reconciling real data source names.

Run standalone to (re)build:
    python pipeline/crosswalk/build_crosswalk.py
"""

from __future__ import annotations
import json, csv, sys
from pathlib import Path
from typing import Optional

import pandas as pd
from rapidfuzz import process, fuzz

PIPELINE_DIR = Path(__file__).parent.parent
PROJECT_ROOT = PIPELINE_DIR.parent
GEO_PATH     = PROJECT_ROOT / "data" / "geo" / "india_districts.geojson"
XWALK_PATH   = Path(__file__).parent / "district_crosswalk.csv"
OVERRIDES_PATH = PIPELINE_DIR / "config" / "manual_overrides.csv"

XWALK_COLS = [
    "canonical_district_id", "canonical_name", "state",
    "source_name", "source_vintage", "match_type", "confidence", "notes",
]


def build_from_geojson(geo_path: Path = GEO_PATH) -> pd.DataFrame:
    """Extract canonical districts from the 2011 Census GeoJSON."""
    with open(geo_path, encoding="utf-8") as f:
        geo = json.load(f)

    rows = []
    skipped = 0
    for feat in geo["features"]:
        p = feat["properties"]
        district = p.get("district", "").strip()
        state    = p.get("st_nm", "").strip()
        dt_code  = p.get("dt_code", "").strip()

        if not district or not state or not dt_code:
            skipped += 1
            continue

        rows.append({
            "canonical_district_id": dt_code,
            "canonical_name":        district,
            "state":                 state,
            "source_name":           district,       # canonical is its own source
            "source_vintage":        "census_2011",
            "match_type":            "exact",
            "confidence":            1.0,
            "notes":                 "",
        })

    df = pd.DataFrame(rows, columns=XWALK_COLS)
    print(f"[crosswalk] Built {len(df)} canonical districts  (skipped {skipped} GeoJSON features without dt_code/name)")
    return df


def load_crosswalk(path: Path = XWALK_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, comment="#")


def load_or_build_crosswalk(pipeline_dir: Path | None = None) -> pd.DataFrame:
    path = (pipeline_dir or PIPELINE_DIR) / "crosswalk" / "district_crosswalk.csv"
    if path.exists():
        return load_crosswalk(path)
    df = build_from_geojson()
    df.to_csv(path, index=False)
    return df


# ── Fuzzy matching helpers ────────────────────────────────────────────────────

def fuzzy_match_names(
    source_names: list[str],
    crosswalk_df: pd.DataFrame,
    source_vintage: str = "unknown",
    score_cutoff: float = 80.0,
    top_n: int = 1,
) -> pd.DataFrame:
    """
    Given a list of district names from a data source, propose canonical matches.

    Returns a DataFrame with columns:
        source_name, canonical_district_id, canonical_name, state, score, match_type
    Rows below score_cutoff have match_type='no_match'.

    Usage after running pipeline:
        from crosswalk.build_crosswalk import fuzzy_match_names, load_crosswalk
        xwalk = load_crosswalk()
        proposals = fuzzy_match_names(raw_names, xwalk, source_vintage="nfhs_5")
        proposals.to_csv("pipeline/config/fuzzy_proposals.csv", index=False)
        # Review proposals, add corrections to manual_overrides.csv, re-run pipeline.
    """
    canonical_names = crosswalk_df["canonical_name"].tolist()
    results = []
    for name in source_names:
        matches = process.extract(name, canonical_names, scorer=fuzz.token_sort_ratio, limit=top_n)
        if matches and matches[0][1] >= score_cutoff:
            matched_name, score, idx = matches[0]
            row = crosswalk_df.iloc[idx]
            results.append({
                "source_name":            name,
                "source_vintage":         source_vintage,
                "canonical_district_id":  row["canonical_district_id"],
                "canonical_name":         row["canonical_name"],
                "state":                  row["state"],
                "score":                  round(score, 1),
                "match_type":             "fuzzy" if score < 100 else "exact",
            })
        else:
            results.append({
                "source_name":            name,
                "source_vintage":         source_vintage,
                "canonical_district_id":  "",
                "canonical_name":         "",
                "state":                  "",
                "score":                  matches[0][1] if matches else 0.0,
                "match_type":             "no_match",
            })
    return pd.DataFrame(results)


def coverage_report(source_names: list[str], matched_df: pd.DataFrame) -> dict:
    """Summarise match quality."""
    n_total    = len(source_names)
    n_exact    = (matched_df["match_type"] == "exact").sum()
    n_fuzzy    = (matched_df["match_type"] == "fuzzy").sum()
    n_no_match = (matched_df["match_type"] == "no_match").sum()
    return {
        "total_source_names": n_total,
        "exact_matches":      int(n_exact),
        "fuzzy_matches":      int(n_fuzzy),
        "no_matches":         int(n_no_match),
        "match_rate_pct":     round((n_exact + n_fuzzy) / n_total * 100, 1) if n_total else 0,
    }


if __name__ == "__main__":
    df = build_from_geojson()
    df.to_csv(XWALK_PATH, index=False)
    print(f"[crosswalk] Written to {XWALK_PATH}")
    print(df.head(5).to_string(index=False))
