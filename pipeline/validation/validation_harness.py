"""
Validation harness (GATED) — regression of external market proxy on MAI scores.

ACTIVATION: this module runs ONLY if pipeline/raw/validation/validation_proxy.csv exists.
If the file is absent the pipeline continues normally with a logged TODO notice.

Expected proxy CSV format: district_id, proxy_value
  e.g. IPM district pharma sales (₹ Cr), IQVIA volume index, etc.

When activated, runs:
  1. OLS regression: proxy ~ overall_score
  2. Spearman rank correlation: proxy vs each therapy score
  3. Reports R², coefficients, and rank correlations

TODO: source an external market proxy before final submission.
"""

from __future__ import annotations
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def run_validation(pipeline_dir: Path, scores: pd.DataFrame) -> dict | None:
    proxy_path = pipeline_dir / "raw" / "validation" / "validation_proxy.csv"

    if not proxy_path.exists():
        log.info(
            "[validation] GATED — proxy file not found at %s. "
            "TODO: source IPM/IQVIA district-level pharma sales data and place here.",
            proxy_path,
        )
        return None

    log.info("[validation] Proxy found — running validation harness...")
    proxy = pd.read_csv(proxy_path, dtype={"district_id": str}).set_index("district_id")

    common = scores.index.intersection(proxy.index)
    if len(common) < 10:
        log.warning("[validation] Only %d districts in common — results unreliable", len(common))

    results: dict = {"n_districts": len(common), "therapy_correlations": {}}
    proxy_vals = proxy.loc[common, "proxy_value"]

    try:
        from scipy.stats import spearmanr
        import numpy as np

        for therapy in ["overall", "chronic", "acute"]:
            col = f"{therapy}_score"
            if col not in scores.columns:
                continue
            score_vals = scores.loc[common, col]
            rho, p = spearmanr(score_vals, proxy_vals)
            results["therapy_correlations"][therapy] = {
                "spearman_rho": round(float(rho), 3),
                "p_value": round(float(p), 4),
            }

        # Simple OLS: proxy ~ overall_score
        X = scores.loc[common, "overall_score"].values.reshape(-1, 1)
        y = proxy_vals.values
        X_c = np.column_stack([np.ones(len(X)), X])
        coeffs = np.linalg.lstsq(X_c, y, rcond=None)[0]
        y_hat = X_c @ coeffs
        ss_res = ((y - y_hat) ** 2).sum()
        ss_tot = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        results["ols"] = {"intercept": round(float(coeffs[0]), 3),
                          "slope": round(float(coeffs[1]), 3),
                          "r2": round(float(r2), 3)}
        log.info("[validation] OLS R²=%.3f  Spearman(overall)=%.3f",
                 r2, results["therapy_correlations"].get("overall", {}).get("spearman_rho", float("nan")))
    except Exception as exc:
        log.error("[validation] Error: %s", exc)

    return results
