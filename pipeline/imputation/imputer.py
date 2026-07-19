"""
Imputation module.

Strategy (applied in order):
1. Hierarchical fallback for fully-missing districts (all indicators NaN):
   fill each indicator with the state median, then national median if state is also empty.
2. KNN imputation (k=5) on the partial-missing matrix.
3. One round of IterativeImputer (MICE-style) to sharpen the KNN estimates.

Returns imputed DataFrame + audit table with % imputed per indicator.
"""

from __future__ import annotations
import logging

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import KNNImputer, IterativeImputer

log = logging.getLogger(__name__)

INDICATOR_COLS_EXCLUDE = {"canonical_name", "state"}


def _indicator_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in INDICATOR_COLS_EXCLUDE]


def _hierarchical_fallback(df: pd.DataFrame) -> pd.DataFrame:
    """
    For districts where ALL indicators are NaN, fill with state medians.
    Remaining NaN (state also all-missing) → national median.
    """
    df = df.copy()
    ind_cols = _indicator_cols(df)
    meta_cols = [c for c in df.columns if c in INDICATOR_COLS_EXCLUDE]

    fully_missing_mask = df[ind_cols].isna().all(axis=1)
    n_fully_missing = fully_missing_mask.sum()
    if n_fully_missing > 0:
        log.warning("  %d districts fully missing — applying state/national fallback", n_fully_missing)

    if "state" in df.columns:
        state_medians = df.groupby("state")[ind_cols].median()
        for idx in df[fully_missing_mask].index:
            state = df.loc[idx, "state"]
            if state in state_medians.index:
                df.loc[idx, ind_cols] = state_medians.loc[state].values

    # National median for anything still NaN
    national_medians = df[ind_cols].median()
    df[ind_cols] = df[ind_cols].fillna(national_medians)
    return df


def impute(
    master_current: pd.DataFrame,
    panel: dict[int, pd.DataFrame] | None = None,
    xwalk: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[int, pd.DataFrame] | None, dict]:
    """
    Impute missing values in master_current (and optionally the panel).

    Returns
    -------
    imputed_current : pd.DataFrame  (same shape as master_current)
    imputed_panel   : dict[int, pd.DataFrame] | None
    audit           : dict — {indicator_id: {missing_before_pct, missing_after_pct}}
    """
    ind_cols = _indicator_cols(master_current)
    meta = master_current[[c for c in master_current.columns if c in INDICATOR_COLS_EXCLUDE]].copy()

    missing_before = master_current[ind_cols].isna().mean() * 100

    # Step 1: hierarchical fallback
    df = _hierarchical_fallback(master_current)

    # Step 2: KNN imputation
    knn = KNNImputer(n_neighbors=5, weights="distance")
    arr_knn = knn.fit_transform(df[ind_cols].values)
    df_knn = pd.DataFrame(arr_knn, index=df.index, columns=ind_cols)

    # Step 3: one IterativeImputer pass (MICE-style)
    mice = IterativeImputer(max_iter=2, random_state=42, tol=0.01)
    arr_mice = mice.fit_transform(df_knn.values)
    df_imputed = pd.DataFrame(
        np.clip(arr_mice, 0, 100), index=df.index, columns=ind_cols
    )

    missing_after = df_imputed.isna().mean() * 100

    audit: dict[str, dict] = {
        col: {
            "missing_before_pct": round(float(missing_before.get(col, 0)), 1),
            "missing_after_pct":  round(float(missing_after.get(col, 0)), 1),
        }
        for col in ind_cols
    }

    # Re-attach metadata
    result = meta.join(df_imputed)

    # Optionally impute panel years (reuse fitted KNN for consistency)
    imputed_panel: dict[int, pd.DataFrame] | None = None
    if panel is not None:
        imputed_panel = {}
        for yr, panel_df in panel.items():
            panel_ind = _indicator_cols(panel_df)
            panel_meta = panel_df[[c for c in panel_df.columns if c in INDICATOR_COLS_EXCLUDE]].copy()
            p2 = _hierarchical_fallback(panel_df)
            arr_p = knn.transform(p2[panel_ind].values)
            df_p = pd.DataFrame(np.clip(arr_p, 0, 100), index=p2.index, columns=panel_ind)
            imputed_panel[yr] = panel_meta.join(df_p)

    log.info("Imputation complete. Max missing after: %.1f%%",
             max(v["missing_after_pct"] for v in audit.values()))
    return result, imputed_panel, audit
