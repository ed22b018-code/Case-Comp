#!/usr/bin/env python3
"""
MAI Pipeline — End-to-end orchestrator.

Usage:
    python pipeline/run_pipeline.py

Steps:
  1. Load config + crosswalk
  2. Ingest indicator CSVs -> district_master (current + panel)
  3. Impute missing values
  4. Index engine: arithmetic + geometric scores for all therapies
  5. Forecast to 2030
  6. Sensitivity analysis
  7. Clustering
  8. Validation harness (gated)
  9. Reports
  10. Write data/scores.json  ← M1 app reads this file

Output:
  data/scores.json           — M1-compatible district scores
  pipeline/reports/output/   — QA + methodology markdown reports
"""

from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr

# ── path setup ────────────────────────────────────────────────────────────────
PIPELINE_DIR  = Path(__file__).parent
PROJECT_ROOT  = PIPELINE_DIR.parent
DATA_DIR      = PROJECT_ROOT / "data"
REPORTS_DIR   = PIPELINE_DIR / "reports" / "output"

sys.path.insert(0, str(PIPELINE_DIR))

from crosswalk.build_crosswalk import load_or_build_crosswalk
from ingestion.loader import build_district_master, load_panel
from imputation.imputer import impute
from engine.normalizer import normalize
from engine.index_engine import compute_all_scores
from forecasting.forecaster import compute_future_scores
from sensitivity.sensitivity import run_sensitivity
from clustering.clustering import run_clustering
from validation.validation_harness import run_validation
from reports.reporter import generate_reports

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def load_config() -> dict:
    with open(PIPELINE_DIR / "config" / "index_config.yaml") as f:
        return yaml.safe_load(f)


# ── Preflight validation ───────────────────────────────────────────────────────

VALID_PILLARS    = {"demand", "monetization", "access", "growth"}
VALID_DIRECTIONS = {"higher_better", "inverse"}
VALID_SCORING    = {"arithmetic", "geometric"}

def preflight(config: dict) -> None:
    """Validate config on startup and fail fast with a clear message if anything is wrong."""
    errors: list[str] = []

    # 1. scoring_function
    sf = config.get("scoring_function", "arithmetic")
    if sf not in VALID_SCORING:
        errors.append(f"  scoring_function '{sf}' is invalid. Must be one of: {sorted(VALID_SCORING)}")

    # 2. weights: each therapy vector must sum to 1.0 +/- 0.001
    weights = config.get("weights", {})
    for therapy, pvec in weights.items():
        total = sum(pvec.values())
        if abs(total - 1.0) > 0.001:
            errors.append(
                f"  weights[{therapy}] sums to {total:.4f} (should be 1.0). "
                f"Values: {dict(pvec)}"
            )

    # 3. indicators: valid pillar, valid direction, READY files must exist
    indicators = config.get("indicators", [])
    if not indicators:
        errors.append("  No indicators defined in config.")

    raw_dir = PIPELINE_DIR / "raw" / "indicators"
    for ind in indicators:
        ind_id    = ind.get("id", "<missing id>")
        pillar    = ind.get("pillar", "")
        direction = ind.get("direction", "")
        status    = ind.get("status", "TODO")

        if pillar not in VALID_PILLARS:
            errors.append(
                f"  indicators[{ind_id}].pillar '{pillar}' invalid. "
                f"Must be one of: {sorted(VALID_PILLARS)}"
            )
        if direction not in VALID_DIRECTIONS:
            errors.append(
                f"  indicators[{ind_id}].direction '{direction}' invalid. "
                f"Must be one of: {sorted(VALID_DIRECTIONS)}"
            )
        if status == "READY":
            # Check the file exists (loader uses <indicator_id>.csv)
            csv_path = raw_dir / f"{ind_id}.csv"
            if not csv_path.exists():
                errors.append(
                    f"  indicators[{ind_id}] is READY but file not found: {csv_path}"
                )

    if errors:
        print()
        print("PREFLIGHT FAILED — fix the following before running the pipeline:")
        for e in errors:
            print(e)
        print()
        sys.exit(1)

    log.info("Preflight OK: %d indicators | weights valid | scoring=%s", len(indicators), sf)


# ── Output builder ─────────────────────────────────────────────────────────────

def _round(x, n=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), n)


def build_scores_json(
    config: dict,
    scores_arith: pd.DataFrame,
    future_scores: pd.DataFrame,
    xwalk: pd.DataFrame,
    cluster_results: dict | None = None,
) -> dict:
    """
    Build the scores.json payload matching the M1 contract.

    Pillar values are STANDALONE 0-100 scores (Amendment 1).
    Headline scores are from the configured scoring_function (geometric default in M3).
    Includes clusterLabel + archetype per district (from M2 clustering).
    """
    therapies = config["therapies"]
    pillars   = config["pillars"]

    # Build cluster lookup maps
    labels   = cluster_results.get("labels", pd.Series()) if cluster_results else pd.Series()
    profiles = cluster_results.get("profiles", pd.DataFrame()) if cluster_results else pd.DataFrame()
    cluster_to_archetype: dict[int, str] = {}
    if not profiles.empty and "archetype" in profiles.columns:
        cluster_to_archetype = {int(idx): str(row["archetype"]) for idx, row in profiles.iterrows()}

    districts: list[dict] = []
    for dist_id in scores_arith.index:
        row  = scores_arith.loc[dist_id]
        frow = future_scores.loc[dist_id] if dist_id in future_scores.index else None

        scores_block = {}
        pillars_block = {}

        for therapy in therapies:
            current_score  = _round(row.get(f"{therapy}_score"))
            future_score   = _round(frow.get(f"{therapy}_future_score")) if frow is not None else None
            if future_score is None:
                future_score = current_score  # fallback: flat forecast

            scores_block[therapy] = {"current": current_score, "future": future_score}

            pillars_block[therapy] = {
                p: _round(row.get(f"{therapy}_pillar_{p}")) for p in pillars
            }

        cluster_int = int(labels.loc[dist_id]) if dist_id in labels.index else None
        archetype   = cluster_to_archetype.get(cluster_int) if cluster_int is not None else None

        districts.append({
            "districtId":   str(dist_id),
            "districtName": str(row.get("canonical_name", dist_id)),
            "state":        str(row.get("state", "")),
            "clusterLabel": cluster_int,
            "archetype":    archetype,
            "scores":       scores_block,
            "pillars":      pillars_block,
        })

    return {
        "generatedAt":     pd.Timestamp.now().isoformat(),
        "scoringFunction": config.get("scoring_function", "geometric"),
        "weights":         config["weights"],
        "districts":       districts,
    }


def build_clusters_json(config: dict, cluster_results: dict) -> dict:
    """Build clusters.json payload for the front-end archetype map."""
    profiles = cluster_results.get("profiles", pd.DataFrame())
    profiles_list = []
    for idx, row in profiles.iterrows():
        profiles_list.append({
            "clusterId":    int(idx),
            "archetype":    str(row.get("archetype", f"Cluster {idx}")),
            "n_districts":  int(row.get("n_districts", 0)),
            "demand":       _round(row.get("demand", 0)),
            "monetization": _round(row.get("monetization", 0)),
            "access":       _round(row.get("access", 0)),
            "growth":       _round(row.get("growth", 0)),
        })
    return {
        "k":       cluster_results.get("k", 0),
        "method":  config.get("clustering", {}).get("method", "kmeans"),
        "profiles": profiles_list,
    }


# ── Spearman helpers ───────────────────────────────────────────────────────────

def _spearman(a: pd.Series, b: pd.Series) -> float:
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 3:
        return float("nan")
    rho, _ = spearmanr(a.loc[common], b.loc[common])
    return float(rho)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 60)
    log.info("MAI Pipeline  —  starting")
    log.info("=" * 60)

    # 1. Config + crosswalk
    config = load_config()
    preflight(config)
    log.info("Config loaded: %d indicators | scoring=%s",
             len(config["indicators"]), config.get("scoring_function", "arithmetic"))

    xwalk = load_or_build_crosswalk(PIPELINE_DIR)
    n_canonical = xwalk["canonical_district_id"].nunique()
    log.info("Crosswalk: %d canonical districts", n_canonical)

    # 2. Ingestion
    log.info("Ingesting current-year indicators (2011)...")
    master_current, coverage = build_district_master(config, xwalk, PIPELINE_DIR, year=2011)
    log.info("Ingesting panel for forecasting...")
    panel = load_panel(config, xwalk, PIPELINE_DIR, years=[2011, 2016, 2021])

    n_matched = len(master_current)
    n_total_source_names = len(xwalk)
    match_rate = n_matched / n_total_source_names * 100 if n_total_source_names else 0

    # 3. Imputation
    log.info("Imputing missing values...")
    imputed_current, imputed_panel, imputation_audit = impute(master_current, panel, xwalk)

    # 4. Index engine (both agg methods)
    log.info("Running index engine...")
    scores_arith, scores_geom = compute_all_scores(config, imputed_current, xwalk)

    # 5. Forecasting
    log.info("Forecasting to 2030...")
    future_scores = compute_future_scores(config, imputed_panel, xwalk)

    # 6. Sensitivity
    log.info("Running sensitivity analysis...")
    normed_for_sensitivity = normalize(imputed_current, config)
    sensitivity = run_sensitivity(config, normed_for_sensitivity, xwalk, scores_arith)

    # 7. Clustering
    log.info("Running clustering...")
    cluster_results = run_clustering(scores_arith, config)

    # 8. Validation (gated)
    run_validation(PIPELINE_DIR, scores_arith)

    # 9. Reports
    log.info("Writing reports...")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    normed_full = normalize(imputed_current, config)
    generate_reports(
        config, xwalk, coverage, imputation_audit,
        scores_arith, scores_geom,
        sensitivity, cluster_results,
        REPORTS_DIR,
        normed=normed_full,
    )

    # 10. Write data/scores.json + data/clusters.json
    log.info("Building scores.json...")
    payload = build_scores_json(config, scores_arith, future_scores, xwalk, cluster_results)
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "scores.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Written: %s  (%d districts)", out_path, len(payload["districts"]))

    clusters_path = DATA_DIR / "clusters.json"
    clusters_payload = build_clusters_json(config, cluster_results)
    with open(clusters_path, "w", encoding="utf-8") as f:
        json.dump(clusters_payload, f, indent=2, ensure_ascii=False)
    log.info("Written: %s  (k=%d clusters)", clusters_path, clusters_payload["k"])

    # ── Summary report (Amendment 3) ──────────────────────────────────────────
    print()
    print("=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)

    # (a) Districts
    print(f"  (a) Districts in canonical geography : {n_canonical}")
    print(f"      Districts scored                 : {len(scores_arith)}")

    # (b) Crosswalk match rate
    n_scored = len(scores_arith)
    print(f"  (b) Crosswalk match rate             : {n_scored}/{n_canonical} "
          f"= {n_scored/n_canonical*100:.1f}%")

    # (c) Imputation % per pillar
    print("  (c) Imputation % (before -> after imputation):")
    pillar_map: dict[str, list[str]] = {p: [] for p in config["pillars"]}
    for ind in config["indicators"]:
        pillar_map[ind["pillar"]].append(ind["id"])
    for pillar, ind_ids in pillar_map.items():
        before = np.mean([imputation_audit.get(i, {}).get("missing_before_pct", 0) for i in ind_ids])
        after  = np.mean([imputation_audit.get(i, {}).get("missing_after_pct", 0) for i in ind_ids])
        print(f"      {pillar:15s}  {before:.1f}% -> {after:.1f}%")

    # (d) Sensitivity rank stability
    if not sensitivity["summary"].empty:
        mean_rho = sensitivity["summary"]["spearman_vs_baseline"].mean()
        mean_shift = sensitivity["summary"]["mean_rank_shift"].mean()
        pct_stable = sensitivity["summary"]["pct_ranks_stable_10"].mean()
        print(f"  (d) Sensitivity (+/-20% weight perturb):")
        print(f"      Mean Spearman vs baseline       : {mean_rho:.4f}")
        print(f"      Mean rank shift                 : {mean_shift:.1f} positions")
        print(f"      % districts stable (<=10 ranks)  : {pct_stable:.1f}%")

    # (e) Three-therapy Spearman rank correlations
    print("  (e) Three-therapy Spearman rank correlations (current score):")
    ov = scores_arith.get("overall_score", pd.Series())
    ch = scores_arith.get("chronic_score", pd.Series())
    ac = scores_arith.get("acute_score", pd.Series())
    print(f"      Spearman(overall, chronic) = {_spearman(ov, ch):.3f}")
    print(f"      Spearman(overall, acute)   = {_spearman(ov, ac):.3f}")
    print(f"      Spearman(chronic, acute)   = {_spearman(ch, ac):.3f}")

    # (f) Arithmetic vs geometric
    print("  (f) Arithmetic vs Geometric Spearman (all therapies):")
    for therapy in config["therapies"]:
        a_col = f"{therapy}_score"
        g_col = f"{therapy}_score"
        rho_t = _spearman(scores_arith.get(a_col, pd.Series()), scores_geom.get(g_col, pd.Series()))
        print(f"      rho(arith, geom) {therapy:8s} = {rho_t:.4f}")

    print()
    print(f"  scores.json -> {out_path}")
    print(f"  Reports     -> {REPORTS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
