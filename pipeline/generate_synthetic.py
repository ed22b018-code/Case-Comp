"""
Generate deterministic synthetic tidy indicator CSVs.
One file per indicator in config, columns: [district_id, value, year].
Three time periods: 2011, 2016, 2021 (enables CAGR forecasting).
~5% NaN holes introduced deterministically for imputation testing.

Run:  python pipeline/generate_synthetic.py
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PIPELINE_DIR = Path(__file__).parent
PROJECT_ROOT = PIPELINE_DIR.parent
CONFIG_PATH  = PIPELINE_DIR / "config" / "index_config.yaml"
XWALK_PATH   = PIPELINE_DIR / "crosswalk" / "district_crosswalk.csv"
OUT_DIR      = PIPELINE_DIR / "raw" / "indicators"

YEARS = [2011, 2016, 2021]
NAN_RATE = 0.05     # fraction of district-year cells set to NaN


def djb2(s: str) -> int:
    h = 5381
    for c in s:
        h = ((h << 5) + h) + ord(c)
        h &= 0xFFFFFFFF
    return h


def state_level_component(state: str, indicator_id: str) -> float:
    """Shared spatial component across all districts in a state: ±20 pts."""
    seed = djb2(f"STATE|{state}|{indicator_id}") & 0xFFFFFF
    rng = np.random.default_rng(seed)
    return rng.uniform(-20, 20)


def generate_district_values(
    district_id: str,
    state: str,
    indicator_id: str,
    direction: str,
    years: list[int],
    nan_rate: float,
) -> list[dict]:
    """Generate base + trend values for a single district across years."""
    seed = djb2(f"DIST|{district_id}|{indicator_id}") & 0xFFFFFF
    rng = np.random.default_rng(seed)

    state_comp = state_level_component(state, indicator_id)

    # Base value for 2011: uniform [10, 90] + state component, clamped [5, 95]
    base = float(np.clip(rng.uniform(10, 90) + state_comp * 0.5, 5, 95))

    # Annual trend: ±1.5 pts/year with slight positive skew
    trend_pa = float(rng.uniform(-1.0, 2.5))

    rows = []
    for i, year in enumerate(years):
        value = base + trend_pa * (year - years[0])
        value = float(np.clip(value, 0, 100))

        # NaN injection: deterministic based on district+indicator+year
        nan_seed = djb2(f"NAN|{district_id}|{indicator_id}|{year}") & 0xFFFFFF
        nan_rng = np.random.default_rng(nan_seed)
        if nan_rng.random() < nan_rate:
            value = float("nan")

        rows.append({"district_id": district_id, "value": value, "year": year})

    return rows


def main() -> None:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    xwalk = pd.read_csv(XWALK_PATH, dtype=str)
    districts = xwalk[["canonical_district_id", "state"]].drop_duplicates()
    print(f"[synthetic] Generating data for {len(districts)} canonical districts")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for ind in config["indicators"]:
        ind_id  = ind["id"]
        ind_dir = ind["direction"]
        all_rows: list[dict] = []

        for _, row in districts.iterrows():
            all_rows.extend(
                generate_district_values(
                    row["canonical_district_id"],
                    row["state"],
                    ind_id,
                    ind_dir,
                    YEARS,
                    NAN_RATE,
                )
            )

        df = pd.DataFrame(all_rows)
        out_path = PIPELINE_DIR / ind["file"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)

        n_missing = df["value"].isna().sum()
        n_total   = len(df)
        print(f"  {ind_id:30s}  {n_total} rows  {n_missing} NaN ({n_missing/n_total*100:.1f}%)")

    print(f"\n[synthetic] Done — {len(config['indicators'])} indicator CSVs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
