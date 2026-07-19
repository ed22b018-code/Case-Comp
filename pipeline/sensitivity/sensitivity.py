"""
Sensitivity analysis — weight perturbation study.

For each therapy × each pillar:
  1. Perturb that pillar's weight ±20% (relative), re-normalise remaining weights.
  2. Recompute headline scores.
  3. Compute Spearman rank correlation vs baseline and mean absolute rank shift.

Outputs:
  - summary DataFrame: therapy, pillar, direction, spearman_vs_baseline, mean_rank_shift
  - detailed per-district rank shift table
"""

from __future__ import annotations
import logging
from copy import deepcopy

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from engine.aggregator import aggregate

log = logging.getLogger(__name__)

PERTURB_PCT = 0.20  # ±20% relative perturbation


def _perturb_config(config: dict, therapy: str, pillar: str, direction: float) -> dict:
    """
    Return a config copy with pillar's weight perturbed by ±PERTURB_PCT.
    Remaining pillar weights are scaled proportionally so they still sum to 1.
    """
    cfg = deepcopy(config)
    pw = cfg["weights"][therapy]
    other_pillars = [p for p in pw if p != pillar]

    base_w = pw[pillar]
    delta   = base_w * PERTURB_PCT * direction
    new_w   = max(0.0, base_w + delta)

    remaining_sum = sum(pw[p] for p in other_pillars)
    shortfall = 1.0 - new_w

    pw[pillar] = new_w
    if remaining_sum > 1e-9:
        scale = shortfall / remaining_sum
        for p in other_pillars:
            pw[p] = pw[p] * scale

    return cfg


def spearman_rank_corr(a: pd.Series, b: pd.Series) -> float:
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 3:
        return float("nan")
    corr, _ = spearmanr(a.loc[common], b.loc[common])
    return float(corr)


def run_sensitivity(
    config: dict,
    normed: pd.DataFrame,
    xwalk: pd.DataFrame,
    baseline_scores: pd.DataFrame,
) -> dict:
    """
    Run full sensitivity study.

    Parameters
    ----------
    normed : normalised (but not yet aggregated) indicator DataFrame
    baseline_scores : output of index_engine.compute_all_scores (arithmetic)

    Returns
    -------
    {
      'summary': pd.DataFrame,
      'rank_shifts': pd.DataFrame   (per district, per perturbation scenario),
    }
    """
    from engine.normalizer import normalize  # normed is pre-computed but we re-agg

    summary_rows: list[dict] = []
    shift_frames: list[pd.DataFrame] = []

    n_districts = len(baseline_scores)

    for therapy in config["therapies"]:
        baseline_col = f"{therapy}_score"
        if baseline_col not in baseline_scores.columns:
            continue
        baseline_series = baseline_scores[baseline_col].dropna()
        baseline_ranks  = baseline_series.rank(ascending=False)

        for pillar in config["pillars"]:
            for direction, label in [(+1, "up"), (-1, "down")]:
                cfg_perturbed = _perturb_config(config, therapy, pillar, direction)
                agg = aggregate(normed, cfg_perturbed, scoring_function="arithmetic")
                perturbed_series = agg[therapy]["headline"].reindex(baseline_series.index)

                rho = spearman_rank_corr(baseline_series, perturbed_series)
                perturbed_ranks  = perturbed_series.rank(ascending=False)
                rank_shift = (perturbed_ranks - baseline_ranks).abs()

                summary_rows.append({
                    "therapy":              therapy,
                    "pillar":               pillar,
                    "perturbation":         f"{'+' if direction > 0 else '-'}{int(PERTURB_PCT*100)}%",
                    "spearman_vs_baseline": round(rho, 4),
                    "mean_rank_shift":      round(rank_shift.mean(), 2),
                    "max_rank_shift":       int(rank_shift.max()),
                    "pct_ranks_stable_10":  round((rank_shift <= 10).mean() * 100, 1),
                })
                shift_col = f"{therapy}_{pillar}_{label}"
                shift_frames.append(rank_shift.rename(shift_col))

    summary = pd.DataFrame(summary_rows)
    rank_shifts = pd.concat(shift_frames, axis=1) if shift_frames else pd.DataFrame()

    log.info("Sensitivity done. Mean Spearman across perturbations: %.3f",
             summary["spearman_vs_baseline"].mean() if not summary.empty else float("nan"))
    return {"summary": summary, "rank_shifts": rank_shifts}
