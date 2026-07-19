"""
Aggregation module.

Two-stage aggregation:
  Stage 1 — Within pillar:
    weighted_mean(indicator_scores, weights=therapy_relevance / Σtherapy_relevance)
    → 0-100 pillar score per therapy.  (Amendment 2: therapy_relevance multipliers)

  Stage 2 — Across pillars:
    arithmetic: score = Σ(pillar_score × pillar_weight)
    geometric:  score = Π(max(pillar_score,1) ^ pillar_weight)  [HDI-2010]
    Controlled by config['scoring_function'].

Pillar scores stored as STANDALONE 0-100 values (Amendment 1 — not weighted summands).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

_META = {"canonical_name", "state"}


def _pillar_indicators(config: dict, pillar: str) -> list[dict]:
    return [ind for ind in config["indicators"] if ind["pillar"] == pillar]


def compute_pillar_score(
    normed: pd.DataFrame,
    pillar: str,
    therapy: str,
    config: dict,
) -> pd.Series:
    """
    Compute 0-100 pillar score for a given therapy using therapy_relevance weights.
    Returns Series indexed by canonical_district_id.
    """
    indicators = _pillar_indicators(config, pillar)
    available = [ind for ind in indicators if ind["id"] in normed.columns]

    if not available:
        return pd.Series(50.0, index=normed.index, name=pillar)

    scores: list[pd.Series] = []
    relevances: list[float] = []

    for ind in available:
        rel = float(ind.get("therapy_relevance", {}).get(therapy, 1.0))
        if rel <= 0:
            continue
        scores.append(normed[ind["id"]])
        relevances.append(rel)

    if not scores:
        return pd.Series(50.0, index=normed.index, name=pillar)

    total_rel = sum(relevances)
    weights = [r / total_rel for r in relevances]
    pillar_score = sum(s * w for s, w in zip(scores, weights))
    return pillar_score.clip(0, 100).rename(pillar)


def compute_headline_score(
    pillar_scores: pd.DataFrame,
    therapy: str,
    config: dict,
    scoring_function: str | None = None,
) -> pd.Series:
    """
    Compute headline score from pillar scores using the configured aggregation.
    pillar_scores: DataFrame with columns = pillar names, values in [0, 100].
    """
    func = scoring_function or config.get("scoring_function", "arithmetic")
    pw = config["weights"][therapy]  # {pillar: weight}
    pillars = [p for p in pw if p in pillar_scores.columns]

    if func == "geometric":
        # Weighted geometric mean (HDI-2010 style)
        # Clamp to minimum 1 to avoid log(0)
        log_scores = sum(
            pw[p] * np.log(pillar_scores[p].clip(lower=1.0))
            for p in pillars
        )
        return np.exp(log_scores).clip(0, 100).rename("score")
    else:
        # Weighted arithmetic mean
        return sum(pillar_scores[p] * pw[p] for p in pillars).clip(0, 100).rename("score")


def aggregate(
    normed: pd.DataFrame,
    config: dict,
    scoring_function: str | None = None,
) -> dict[str, dict]:
    """
    Full aggregation for all therapies.

    Returns
    -------
    {
      therapy: {
        'pillar_scores': DataFrame[district_id → {demand,monetization,access,growth}],
        'headline':      Series[district_id → score 0-100],
      }
    }
    """
    results: dict[str, dict] = {}
    pillars: list[str] = config["pillars"]

    for therapy in config["therapies"]:
        pillar_dfs = [
            compute_pillar_score(normed, p, therapy, config)
            for p in pillars
        ]
        pillar_df = pd.concat(pillar_dfs, axis=1)
        pillar_df.columns = pillars

        headline = compute_headline_score(pillar_df, therapy, config, scoring_function)
        results[therapy] = {"pillar_scores": pillar_df, "headline": headline}

    return results
