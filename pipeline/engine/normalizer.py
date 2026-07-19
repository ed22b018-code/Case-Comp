"""
Normalization module.

Per indicator:
  1. Winsorize at 1st / 99th percentile (handles extreme outliers).
  2. Min-max scale to [0, 100].
  3. Invert if direction == 'inverse'  →  score = 100 - score.
"""

from __future__ import annotations
import pandas as pd
import numpy as np

_META = {"canonical_name", "state"}


def winsorize_minmax(series: pd.Series, lo_pct: float = 0.01, hi_pct: float = 0.99, ref_series: pd.Series = None) -> pd.Series:
    """Winsorize then min-max scale to [0, 100]."""
    if ref_series is None:
        ref_series = series

    lo = ref_series.quantile(lo_pct)
    hi = ref_series.quantile(hi_pct)
    clipped = series.clip(lo, hi)
    rng = hi - lo
    if rng < 1e-9:
        return pd.Series(50.0, index=series.index, name=series.name)
    return (clipped - lo) / rng * 100


def normalize(
    master: pd.DataFrame,
    config: dict,
    reference_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Apply winsorize_minmax to each indicator column, respecting direction.
    If reference_df is provided, the min/max bounds are fit on reference_df 
    rather than master.
    Returns a DataFrame of the same shape with values in [0, 100].
    Meta columns (canonical_name, state) are passed through unchanged.
    """
    result = pd.DataFrame(index=master.index)

    # pass-through meta
    for col in _META:
        if col in master.columns:
            result[col] = master[col]

    ind_lookup = {ind["id"]: ind for ind in config["indicators"]}

    for col in master.columns:
        if col in _META:
            continue
        ind = ind_lookup.get(col)
        if ind is None:
            result[col] = master[col]
            continue

        ref_series = reference_df[col].dropna() if reference_df is not None and col in reference_df else None
        normed = winsorize_minmax(master[col].dropna(), ref_series=ref_series)
        # Re-index to full master index (NaN for districts that were NaN)
        normed = normed.reindex(master.index)

        if ind.get("direction") == "inverse":
            normed = 100.0 - normed

        result[col] = normed.clip(0, 100)

    return result
