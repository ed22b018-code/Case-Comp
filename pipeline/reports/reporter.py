"""
Report generator — emits all QA and methodology markdown files.

Outputs (written to reports/output/):
  join_coverage.md         — districts matched / dropped
  missingness.md           — % missing before/after imputation per indicator
  outlier_flags.md         — districts > 3 SD on any indicator
  directionality_check.md  — correlation sanity check (inverse indicators should have
                              negative correlation with score)
  aggregation_comparison.md — Spearman arith vs geom + top movers (Amendment 1)
  sensitivity_summary.md    — rank stability table from weight perturbations
  cluster_profiles.md       — archetype descriptions + size table
  data_dictionary.md        — auto-generated from config (appendix-ready)
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from scipy.stats import spearmanr


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _spearman(a: pd.Series, b: pd.Series) -> float:
    common = a.dropna().index.intersection(b.dropna().index)
    if len(common) < 3:
        return float("nan")
    rho, _ = spearmanr(a.loc[common], b.loc[common])
    return float(rho)


# ─────────────────────────────────────────────────────────────────────────────

def write_join_coverage(xwalk: pd.DataFrame, coverage: dict, out_dir: Path) -> None:
    n_canonical = xwalk["canonical_district_id"].nunique()
    n_matched   = sum(1 for v in coverage.values() if v["values_present"] > 0)
    n_todo      = sum(1 for v in coverage.values() if v["status"] == "TODO")

    lines = [
        f"# Join Coverage Report\n_Generated {_ts()}_\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Canonical districts (2011 Census) | {n_canonical} |",
        f"| Indicators processed | {len(coverage)} |",
        f"| Indicators with status TODO (synthetic) | {n_todo} |",
        f"| Indicators with status READY (real data) | {len(coverage) - n_todo} |",
        f"",
        f"## Per-Indicator District Coverage\n",
        f"| Indicator | Total | Present | Missing | Missing% | Status |",
        f"|-----------|-------|---------|---------|----------|--------|",
    ]
    for ind_id, v in sorted(coverage.items()):
        lines.append(
            f"| {ind_id} | {v['total_districts']} | {v['values_present']} "
            f"| {v['missing']} | {v['missing_pct']}% | {v['status']} |"
        )

    (out_dir / "join_coverage.md").write_text("\n".join(lines), encoding="utf-8")


def write_missingness(audit: dict, out_dir: Path) -> None:
    lines = [
        f"# Missingness Report\n_Generated {_ts()}_\n",
        f"| Indicator | Missing Before Imputation (%) | Missing After (%) |",
        f"|-----------|-------------------------------|-------------------|",
    ]
    for ind_id, v in sorted(audit.items()):
        lines.append(f"| {ind_id} | {v['missing_before_pct']} | {v['missing_after_pct']} |")
    (out_dir / "missingness.md").write_text("\n".join(lines), encoding="utf-8")


def write_outlier_flags(normed: pd.DataFrame, config: dict, out_dir: Path) -> None:
    ind_cols = [ind["id"] for ind in config["indicators"] if ind["id"] in normed.columns]
    flags: list[dict] = []
    for col in ind_cols:
        s = normed[col].dropna()
        mean, std = s.mean(), s.std()
        if std < 1e-6:
            continue
        outliers = normed[(normed[col] - mean).abs() > 3 * std][["canonical_name", "state", col]]
        for idx, row in outliers.iterrows():
            flags.append({
                "indicator": col,
                "district_id": idx,
                "district": row.get("canonical_name", idx),
                "state": row.get("state", ""),
                "value": round(row[col], 1),
                "z_score": round((row[col] - mean) / std, 2),
            })

    lines = [
        f"# Outlier Flags  (> 3 SD on any normalised indicator)\n_Generated {_ts()}_\n",
        f"| Indicator | District | State | Normed Value | Z-score |",
        f"|-----------|----------|-------|-------------|---------|",
    ]
    for r in sorted(flags, key=lambda x: abs(x["z_score"]), reverse=True)[:50]:
        lines.append(f"| {r['indicator']} | {r['district']} | {r['state']} | {r['value']} | {r['z_score']} |")
    if not flags:
        lines.append("_No outliers found._")
    (out_dir / "outlier_flags.md").write_text("\n".join(lines), encoding="utf-8")


def write_directionality_check(normed: pd.DataFrame, scores: pd.DataFrame, config: dict, out_dir: Path) -> None:
    ind_cols = [ind for ind in config["indicators"] if ind["id"] in normed.columns]
    lines = [
        f"# Directionality Sanity Check\n_Generated {_ts()}_\n",
        "Verifies that 'inverse' indicators correlate negatively with the overall score.",
        f"\n| Indicator | Direction | Spearman vs Overall Score | Expected Sign | Pass |",
        f"|-----------|-----------|--------------------------|---------------|------|",
    ]
    overall_col = "overall_score"
    if overall_col not in scores.columns:
        lines.append("_overall_score not found in scores table._")
    else:
        for ind in ind_cols:
            if ind["id"] not in normed.columns:
                continue
            rho = _spearman(normed[ind["id"]], scores.reindex(normed.index).get(overall_col, pd.Series()))
            expected = "−" if ind["direction"] == "inverse" else "+"
            actual_sign = "−" if rho < 0 else "+"
            passed = "PASS" if actual_sign == expected else "FAIL"
            lines.append(f"| {ind['id']} | {ind['direction']} | {rho:.3f} | {expected} | {passed} |")
    (out_dir / "directionality_check.md").write_text("\n".join(lines), encoding="utf-8")


def write_aggregation_comparison(
    scores_arith: pd.DataFrame,
    scores_geom: pd.DataFrame,
    config: dict,
    out_dir: Path,
) -> None:
    """Amendment 1 — compare arithmetic vs geometric aggregation."""
    lines = [
        f"# Aggregation Comparison: Arithmetic vs Geometric Mean\n_Generated {_ts()}_\n",
        "## Spearman Rank Correlation (Arithmetic vs Geometric)\n",
        "| Therapy | Spearman rho |",
        "|---------|--------------|",
    ]
    for therapy in config["therapies"]:
        col = f"{therapy}_score"
        rho = _spearman(scores_arith.get(col, pd.Series()), scores_geom.get(col, pd.Series()))
        lines.append(f"| {therapy} | {rho:.4f} |")

    lines += [
        "",
        "## Top 20 Districts by Rank Movement (Overall Therapy)\n",
        "| District | State | Arith Rank | Geom Rank | Δ Rank |",
        "|----------|-------|-----------|-----------|--------|",
    ]
    col = "overall_score"
    if col in scores_arith.columns and col in scores_geom.columns:
        common_idx = scores_arith[col].dropna().index.intersection(scores_geom[col].dropna().index)
        arith_ranks = scores_arith.loc[common_idx, col].rank(ascending=False).astype(int)
        geom_ranks  = scores_geom.loc[common_idx, col].rank(ascending=False).astype(int)
        delta = (geom_ranks - arith_ranks).abs()
        top_movers = delta.nlargest(20).index
        for idx in top_movers:
            name  = scores_arith.loc[idx, "canonical_name"] if "canonical_name" in scores_arith.columns else idx
            state = scores_arith.loc[idx, "state"] if "state" in scores_arith.columns else ""
            lines.append(f"| {name} | {state} | {arith_ranks[idx]} | {geom_ranks[idx]} | {delta[idx]} |")

    lines += [
        "",
        "## Methodology Note\n",
        "**Default**: arithmetic weighted mean (M1 waterfall compatible).",
        "**Intended final method**: geometric weighted mean (HDI-2010 non-compensatory precedent,",
        "OECD/JRC Handbook §3.2). Districts with an uneven pillar profile are",
        "penalised under geometric mean — this is a feature, not a bug.",
        "",
        "Switch `scoring_function: geometric` in `pipeline/config/index_config.yaml`",
        "and redesign the M1 waterfall chart (M3) to activate the primary method.",
    ]
    (out_dir / "aggregation_comparison.md").write_text("\n".join(lines), encoding="utf-8")


def write_sensitivity_summary(sensitivity: dict, out_dir: Path) -> None:
    summary = sensitivity.get("summary", pd.DataFrame())
    if summary.empty:
        (out_dir / "sensitivity_summary.md").write_text("# Sensitivity Summary\n_No data._", encoding="utf-8")
        return
    lines = [
        f"# Sensitivity Analysis — Weight Perturbation ±{int(20)}%\n_Generated {_ts()}_\n",
        f"| Therapy | Pillar | Direction | Spearman vs Baseline | Mean Rank Shift | % Stable (≤10 ranks) |",
        f"|---------|--------|-----------|---------------------|----------------|----------------------|",
    ]
    for _, row in summary.sort_values(["therapy","pillar","perturbation"]).iterrows():
        lines.append(
            f"| {row['therapy']} | {row['pillar']} | {row['perturbation']} "
            f"| {row['spearman_vs_baseline']:.4f} | {row['mean_rank_shift']:.1f} | {row['pct_ranks_stable_10']}% |"
        )
    mean_rho = summary["spearman_vs_baseline"].mean()
    lines.append(f"\n**Mean Spearman across all perturbations: {mean_rho:.4f}**")
    (out_dir / "sensitivity_summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_cluster_profiles(cluster_results: dict, out_dir: Path) -> None:
    profiles = cluster_results.get("profiles", pd.DataFrame())
    k = cluster_results.get("k", 0)
    lines = [
        f"# Market Archetype Clusters (k={k})\n_Generated {_ts()}_\n",
        f"| Cluster | Archetype | N Districts | Demand | Monetization | Access | Growth |",
        f"|---------|-----------|-------------|--------|-------------|--------|--------|",
    ]
    for idx, row in profiles.iterrows():
        lines.append(
            f"| {idx} | {row.get('archetype',idx)} | {int(row.get('n_districts',0))} "
            f"| {row.get('demand','—')} | {row.get('monetization','—')} "
            f"| {row.get('access','—')} | {row.get('growth','—')} |"
        )
    (out_dir / "cluster_profiles.md").write_text("\n".join(lines), encoding="utf-8")


def write_data_dictionary(config: dict, out_dir: Path) -> None:
    lines = [
        f"# Data Dictionary — MAI Index Variables\n_Auto-generated from config · {_ts()}_\n",
        "_This document doubles as the Variable Selection & Business Rationale appendix._\n",
        f"| Pillar | ID | Label | Source | Direction | Transform | Therapy Relevance | Status |",
        f"|--------|-----|-------|--------|-----------|-----------|-------------------|--------|",
    ]
    for ind in config["indicators"]:
        rel = ind.get("therapy_relevance", {})
        rel_str = f"ov={rel.get('overall',1.0)} chr={rel.get('chronic',1.0)} ac={rel.get('acute',1.0)}"
        lines.append(
            f"| {ind['pillar']} | `{ind['id']}` | {ind['label']} | {ind['source']} "
            f"| {ind['direction']} | {ind['transform']} | {rel_str} | {ind['status']} |"
        )
    lines += [
        "\n## Weight Vectors (Placeholder)\n",
        "| Pillar | Overall | Chronic | Acute |",
        "|--------|---------|---------|-------|",
    ]
    for pillar in config["pillars"]:
        w = config["weights"]
        lines.append(f"| {pillar} | {w['overall'][pillar]} | {w['chronic'][pillar]} | {w['acute'][pillar]} |")
    lines.append("\n_Weights are equal-weight placeholders. See CLAUDE.md §Final Weights for finalisation process._")
    (out_dir / "data_dictionary.md").write_text("\n".join(lines), encoding="utf-8")


def generate_reports(
    config: dict,
    xwalk: pd.DataFrame,
    coverage: dict,
    imputation_audit: dict,
    scores_arith: pd.DataFrame,
    scores_geom: pd.DataFrame,
    sensitivity: dict,
    cluster_results: dict,
    out_dir: Path,
    normed: pd.DataFrame | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_join_coverage(xwalk, coverage, out_dir)
    write_missingness(imputation_audit, out_dir)
    if normed is not None:
        write_outlier_flags(normed, config, out_dir)
        write_directionality_check(normed, scores_arith, config, out_dir)
    write_aggregation_comparison(scores_arith, scores_geom, config, out_dir)
    write_sensitivity_summary(sensitivity, out_dir)
    write_cluster_profiles(cluster_results, out_dir)
    write_data_dictionary(config, out_dir)
    print(f"[reports] 8 reports written to {out_dir}")