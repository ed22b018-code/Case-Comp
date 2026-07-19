"""
Index engine — orchestrates normalization → aggregation → both score sets.

Returns two score tables (arithmetic + geometric) per run.
The caller chooses which to write to scores.json based on config['scoring_function'].
Both are always computed for the aggregation_comparison report.
"""

from __future__ import annotations
import logging

import pandas as pd

from engine.normalizer import normalize
from engine.aggregator import aggregate

log = logging.getLogger(__name__)


def validate_weights(config: dict) -> None:
    """Assert each therapy's pillar weights sum to 1.0 ± 0.001."""
    for therapy, pw in config["weights"].items():
        total = sum(pw.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights for therapy '{therapy}' sum to {total:.4f}, expected 1.0"
            )


def compute_all_scores(
    config: dict,
    imputed_master: pd.DataFrame,
    xwalk: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Main entry point for the index engine.

    Returns
    -------
    scores_arith : pd.DataFrame — one row per district, columns defined below
    scores_geom  : pd.DataFrame — same structure, using geometric mean

    Column structure per therapy T (e.g. T=overall):
        {T}_current_demand, {T}_current_monetization, {T}_current_access, {T}_current_growth
        {T}_current_score
    """
    validate_weights(config)

    log.info("Normalizing indicators...")
    normed = normalize(imputed_master, config)

    log.info("Aggregating (arithmetic)...")
    arith = aggregate(normed, config, scoring_function="arithmetic")

    log.info("Aggregating (geometric)...")
    geom = aggregate(normed, config, scoring_function="geometric")

    def _build_table(agg_results: dict) -> pd.DataFrame:
        frames: list[pd.Series] = []
        for therapy in config["therapies"]:
            res = agg_results[therapy]
            for pillar in config["pillars"]:
                s = res["pillar_scores"][pillar].rename(f"{therapy}_pillar_{pillar}")
                frames.append(s)
            frames.append(res["headline"].rename(f"{therapy}_score"))
        table = pd.concat(frames, axis=1)
        # Attach name/state from crosswalk
        meta = (
            xwalk[["canonical_district_id", "canonical_name", "state"]]
            .drop_duplicates("canonical_district_id")
            .set_index("canonical_district_id")
        )
        return meta.join(table).dropna(subset=[f"{config['therapies'][0]}_score"])

    scores_arith = _build_table(arith)
    scores_geom  = _build_table(geom)

    log.info("Engine done: %d districts scored", len(scores_arith))
    return scores_arith, scores_geom
