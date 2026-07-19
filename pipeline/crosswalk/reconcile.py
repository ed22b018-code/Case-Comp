#!/usr/bin/env python3
"""
Crosswalk Reconciler — match arbitrary district-name spellings to the 2011 Census canonical list.

Usage:
    python pipeline/crosswalk/reconcile.py <input_csv> [options]

Options:
    --name-col      Column name containing district names  [default: district_name]
    --cutoff        Minimum fuzzy-match confidence to accept  [default: 80]
    --output        Write markdown reconciliation report here  [default: stdout]
    --proposals     Write accepted matches (exact + fuzzy) here  [default: proposals.csv]
    --unmatched     Write unmatched rows needing manual override  [default: unmatched.csv]

Example:
    python pipeline/crosswalk/reconcile.py data/nfhs5_raw.csv \\
        --name-col district_name \\
        --output pipeline/config/nfhs5_reconciliation.md

After running, review the fuzzy-match section carefully:
  - Verify each fuzzy match is correct.
  - Add incorrect matches to pipeline/config/manual_overrides.csv.
  - Re-run reconcile.py with the overrides applied.
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PIPELINE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PIPELINE_DIR))

from crosswalk.build_crosswalk import load_or_build_crosswalk, fuzzy_match_names

OVERRIDES_PATH = PIPELINE_DIR / "config" / "manual_overrides.csv"


def load_overrides() -> dict[str, str]:
    """Load manual_overrides.csv if it exists.  Returns {source_name: canonical_district_id}."""
    if not OVERRIDES_PATH.exists():
        return {}
    df = pd.read_csv(OVERRIDES_PATH, dtype=str, comment="#")
    if "source_name" not in df.columns or "canonical_district_id" not in df.columns:
        return {}
    return dict(zip(df["source_name"].str.strip(), df["canonical_district_id"].str.strip()))


def reconcile(
    source_names: list[str],
    xwalk: pd.DataFrame,
    cutoff: float = 80.0,
    overrides: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Reconcile a list of district names against the canonical crosswalk.

    Returns
    -------
    exact_df    : exact + override matches
    fuzzy_df    : accepted fuzzy matches
    no_match_df : unmatched names (need manual_overrides.csv entry)
    """
    overrides = overrides or {}
    canonical_map = xwalk.drop_duplicates("canonical_district_id").set_index("canonical_district_id")

    # Apply overrides first
    override_rows, remaining = [], []
    for name in source_names:
        if name in overrides:
            cid = overrides[name]
            if cid in canonical_map.index:
                crow = canonical_map.loc[cid]
                override_rows.append({
                    "source_name":           name,
                    "canonical_district_id": cid,
                    "canonical_name":        crow["canonical_name"],
                    "state":                 crow["state"],
                    "score":                 100.0,
                    "match_type":            "manual_override",
                })
            else:
                remaining.append(name)  # bad override — fall through
        else:
            remaining.append(name)

    # Run fuzzy matching on remaining
    matched = fuzzy_match_names(remaining, xwalk, score_cutoff=cutoff)

    exact_df    = pd.concat([
        pd.DataFrame(override_rows),
        matched[matched["match_type"] == "exact"],
    ], ignore_index=True) if override_rows else matched[matched["match_type"] == "exact"].copy()

    fuzzy_df    = matched[matched["match_type"] == "fuzzy"].copy()
    no_match_df = matched[matched["match_type"] == "no_match"].copy()

    return exact_df, fuzzy_df, no_match_df


def write_report(
    exact_df: pd.DataFrame,
    fuzzy_df: pd.DataFrame,
    no_match_df: pd.DataFrame,
    output_path: Path | None,
    source_file: str,
    cutoff: float,
) -> str:
    n_total = len(exact_df) + len(fuzzy_df) + len(no_match_df)
    n_ok    = len(exact_df) + len(fuzzy_df)

    lines = [
        f"# Crosswalk Reconciliation Report",
        f"_Source: `{source_file}` - Cutoff: {cutoff} - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
        f"## Summary\n",
        f"| Category | Count | % of total |",
        f"|----------|-------|------------|",
        f"| Exact / override matches | {len(exact_df)} | {100*len(exact_df)/n_total:.1f}% |",
        f"| Fuzzy matches (accepted >={cutoff}) | {len(fuzzy_df)} | {100*len(fuzzy_df)/n_total:.1f}% |",
        f"| Unmatched (<{cutoff}) | {len(no_match_df)} | {100*len(no_match_df)/n_total:.1f}% |",
        f"| **Total** | **{n_total}** | |",
        f"| **Overall match rate** | | **{100*n_ok/n_total:.1f}%** |\n",
    ]

    if not exact_df.empty:
        lines += [
            f"## Exact Matches ({len(exact_df)})\n",
            "| Source name | Canonical name | State | dt_code |",
            "|-------------|----------------|-------|---------|",
        ]
        for _, r in exact_df.iterrows():
            mt = f" _(override)_" if r.get("match_type") == "manual_override" else ""
            lines.append(f"| {r['source_name']} | {r['canonical_name']}{mt} | {r['state']} | {r['canonical_district_id']} |")
        lines.append("")

    if not fuzzy_df.empty:
        lines += [
            f"## Fuzzy Matches — **REVIEW THESE** ({len(fuzzy_df)})\n",
            "_These were accepted automatically at >={} confidence. Verify each row._\n".format(int(cutoff)),
            "| Source name | Canonical name | State | dt_code | Confidence |",
            "|-------------|----------------|-------|---------|------------|",
        ]
        for _, r in fuzzy_df.sort_values("score", ascending=False).iterrows():
            flag = " (!)" if r["score"] < 90 else ""
            lines.append(
                f"| {r['source_name']} | {r['canonical_name']}{flag} | {r['state']} | {r['canonical_district_id']} | {r['score']:.0f} |"
            )
        lines.append("")

    if not no_match_df.empty:
        lines += [
            f"## Unmatched — Needs Manual Override ({len(no_match_df)})\n",
            "Add these to `pipeline/config/manual_overrides.csv` with the correct `canonical_district_id`.",
            "Format: `source_name,canonical_district_id`\n",
            "| Source name | Best candidate | State | Best score |",
            "|-------------|---------------|-------|------------|",
        ]
        for _, r in no_match_df.iterrows():
            lines.append(
                f"| **{r['source_name']}** | {r['canonical_name'] or '-'} | {r['state'] or '-'} | {r['score']:.0f} |"
            )
        lines += [
            "",
            "### manual_overrides.csv snippet to fill in:\n",
            "```csv",
            "source_name,canonical_district_id",
        ]
        for _, r in no_match_df.iterrows():
            lines.append(f"{r['source_name']},<FILL_dt_code>")
        lines.append("```")

    report = "\n".join(lines)
    if output_path:
        output_path.write_text(report, encoding="utf-8")
        print(f"[reconcile] Report written to {output_path}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile district names against 2011 Census crosswalk")
    parser.add_argument("input_csv", help="CSV with a column of district names to reconcile")
    parser.add_argument("--name-col",   default="district_name", help="Column containing district names")
    parser.add_argument("--cutoff",     type=float, default=80.0, help="Min fuzzy-match confidence [0-100]")
    parser.add_argument("--output",     default=None,             help="Path for markdown report (default: stdout)")
    parser.add_argument("--proposals",  default="proposals.csv",  help="CSV of accepted matches")
    parser.add_argument("--unmatched",  default="unmatched.csv",  help="CSV of names needing manual override")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    source_df = pd.read_csv(input_path, dtype=str)
    if args.name_col not in source_df.columns:
        cols = source_df.columns.tolist()
        print(f"ERROR: Column '{args.name_col}' not found. Available: {cols}", file=sys.stderr)
        sys.exit(1)

    source_names = source_df[args.name_col].dropna().str.strip().tolist()
    print(f"[reconcile] {len(source_names)} names to reconcile from {input_path.name}")

    xwalk     = load_or_build_crosswalk(PIPELINE_DIR)
    overrides = load_overrides()
    print(f"[reconcile] Crosswalk: {len(xwalk)} rows | Manual overrides: {len(overrides)} entries")

    exact_df, fuzzy_df, no_match_df = reconcile(source_names, xwalk, args.cutoff, overrides)

    # ── Print summary ─────────────────────────────────────────────────────────
    n_total = len(exact_df) + len(fuzzy_df) + len(no_match_df)
    print(f"\n  Exact / override : {len(exact_df):>4}  ({100*len(exact_df)/n_total:.1f}%)")
    print(f"  Fuzzy (>={args.cutoff:.0f})      : {len(fuzzy_df):>4}  ({100*len(fuzzy_df)/n_total:.1f}%)")
    print(f"  Unmatched       : {len(no_match_df):>4}  ({100*len(no_match_df)/n_total:.1f}%)")
    print(f"  Match rate      : {100*(len(exact_df)+len(fuzzy_df))/n_total:.1f}%")

    # ── Write report ──────────────────────────────────────────────────────────
    output_path = Path(args.output) if args.output else None
    report = write_report(exact_df, fuzzy_df, no_match_df, output_path, input_path.name, args.cutoff)
    if not output_path:
        print("\n" + report)

    # ── Write proposals CSV ───────────────────────────────────────────────────
    proposals = pd.concat([exact_df, fuzzy_df], ignore_index=True)
    if not proposals.empty:
        proposals.to_csv(args.proposals, index=False)
        print(f"[reconcile] Proposals written to {args.proposals}")

    # ── Write unmatched CSV ───────────────────────────────────────────────────
    if not no_match_df.empty:
        no_match_df.to_csv(args.unmatched, index=False)
        print(f"[reconcile] Unmatched written to {args.unmatched}  (add to manual_overrides.csv)")
        sys.exit(2)  # exit code 2 = partial match, manual intervention needed


if __name__ == "__main__":
    main()
